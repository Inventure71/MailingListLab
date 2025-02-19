import json
import os
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from bs4 import BeautifulSoup

# Use these scopes to allow reading (modifying) and sending emails.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send"
]


class GmailManager:
    def __init__(self, credentials_file="credentials/credentials.json", token_file="token.json"):
        """
        Initializes the Gmail API service using OAuth 2.0 credentials.
        If no valid token is found, it runs the OAuth flow to obtain one.
        """
        self.token_file = token_file
        self.creds = None
        if os.path.exists(token_file):
            self.creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open(token_file, "w") as token:
                token.write(self.creds.to_json())
        self.service = build("gmail", "v1", credentials=self.creds)

    def get_email_content(self, payload):
        """
        Extracts plain text and HTML content from the email payload.
        This function recursively walks through MIME parts.
        """
        plain_text = ""
        html_text = ""

        def parse_part(part):
            nonlocal plain_text, html_text
            mime_type = part.get("mimeType")
            body = part.get("body", {})
            data = body.get("data")
            # If the part has its own parts, process them recursively.
            if part.get("parts"):
                for subpart in part.get("parts"):
                    parse_part(subpart)
            else:
                if data:
                    decoded_data = base64.urlsafe_b64decode(data.encode("UTF-8")).decode("utf-8", errors="replace")
                    if mime_type == "text/plain":
                        plain_text += decoded_data
                    elif mime_type == "text/html":
                        html_text += decoded_data

        parse_part(payload)
        return plain_text, html_text

    def extract_links_and_images(self, html_content):
        """
        Parses HTML content using BeautifulSoup to extract all hyperlinks and image sources.
        Returns a tuple of (links, images).
        """
        soup = BeautifulSoup(html_content, "html.parser")
        links = [a.get("href") for a in soup.find_all("a", href=True)]
        images = [img.get("src") for img in soup.find_all("img", src=True)]
        return links, images

    def get_emails(self, max_results=5):
        """
        Fetches unread emails from the user's inbox and marks them as read.
        Returns a list of dictionaries containing email details.
        """
        emails = []
        try:
            # Query for unread messages only using the 'is:unread' filter
            results = self.service.users().messages().list(
                userId="me",
                maxResults=max_results,
                q="is:unread"
            ).execute()

            messages = results.get("messages", [])
            if not messages:
                print("No unread messages found.")
                return emails

            for msg in messages:
                msg_id = msg["id"]
                message = self.service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="full"
                ).execute()

                # Extract email details as before
                headers = message.get("payload", {}).get("headers", [])
                subject = None
                sender = None
                for header in headers:
                    if header["name"] == "Subject":
                        subject = header["value"]
                    if header["name"] == "From":
                        sender = header["value"]

                payload = message.get("payload", {})
                plain_text, html_text = self.get_email_content(payload)
                links = []
                images = []
                if html_text:
                    links, images = self.extract_links_and_images(html_text)

                email_data = {
                    "id": msg_id,
                    "subject": subject,
                    "from": sender,
                    "plain_text": plain_text,
                    "html_text": html_text,
                    "links": links,
                    "images": images
                }
                emails.append(email_data)

                # Mark the message as read by removing the UNREAD label
                self.service.users().messages().modify(
                    userId="me",
                    id=msg_id,
                    body={"removeLabelIds": ["UNREAD"]}
                ).execute()

            return emails

        except HttpError as error:
            print(f"An error occurred: {error}")
            return emails

    def combine_unread_emails_text_in_period(self, start_date, end_date, max_results=100):
        """
        Combines the text content of all unread emails within a specified time period.

        Parameters:
            start_date (str): The start date in "YYYY/MM/DD" format (inclusive).
            end_date (str): The end date in "YYYY/MM/DD" format (exclusive).
            max_results (int): Maximum number of emails to process.

        Returns:
            str: A single string containing the concatenated text content of all unread emails
                 within the specified period.
        """
        # Construct the Gmail query. For example: "is:unread after:2025/01/01 before:2025/01/31"
        query = f"is:unread after:{start_date} before:{end_date}"
        combined_text = ""

        try:
            # List unread messages matching the date range
            results = self.service.users().messages().list(
                userId="me", q=query, maxResults=max_results
            ).execute()
            messages = results.get("messages", [])

            if not messages:
                print("No unread messages found in this period.")
                return combined_text

            for msg in messages:
                # Retrieve the full email message
                message = self.service.users().messages().get(
                    userId="me", id=msg["id"], format="full"
                ).execute()

                # Extract plain text and HTML content
                plain_text, html_text = self.get_email_content(message.get("payload", {}))

                # If plain text is missing, extract text from the HTML content.
                if not plain_text and html_text:
                    soup = BeautifulSoup(html_text, "html.parser")
                    email_text = soup.get_text()
                else:
                    email_text = plain_text

                combined_text += email_text.strip() + "\n\n"

            return combined_text.strip()

        except HttpError as error:
            print(f"An error occurred: {error}")
            return combined_text

    def send_email_from_html_file(self, to, subject, html_file_path, sender=None):
        """
        Sends an email using the content from an HTML file.
        Parameters:
            to: Recipient email address
            subject: Email subject
            html_file_path: Path to the HTML file containing the email content
            sender: Optional sender email address
        """
        try:
            # Read the HTML content from file
            with open(html_file_path, 'r', encoding='utf-8') as file:
                html_content = file.read()

            # Send the email using the existing send_email_html method
            return self.send_email_html(to, subject, html_content, sender)

        except FileNotFoundError:
            print(f"Error: HTML file not found at {html_file_path}")
            return None
        except Exception as e:
            print(f"Error reading HTML file: {str(e)}")
            return None



if __name__ == "__main__":
    gmail_manager = GmailManager()

    '''
    emails = gmail_manager.get_emails(max_results=5)
    for email_data in emails:
        print("=" * 50)
        print("Message ID:", email_data["id"])
        print("Subject:", email_data["subject"])
        print("From:", email_data["from"])
        if email_data["plain_text"]:
            print("\nPlain Text:\n", email_data["plain_text"])
        if email_data["html_text"]:
            print("\nHTML Content:\n", email_data["html_text"])
            print("\nExtracted Links:")
            for link in email_data["links"]:
                print(link)
            print("\nExtracted Images:")
            for image in email_data["images"]:
                print(image)
        print("=" * 50 + "\n")'''

    # Example: Send an email in HTML format
    # Uncomment the following lines to send a test email.

    recipient = "roboticslabie.u@gmail.com"
    email_subject = "Test Email from Gmail API"
    html_body = """
    <html>
      <body>
        <h1>Hello!</h1>
        <p>This is a test email sent using the Gmail API in <b>HTML format</b>.</p>
        <p>Visit <a href="https://www.example.com">Example</a> for more details.</p>
      </body>
    </html>"""

    # gmail_manager.send_email_from_html_file(to=recipient, subject=email_subject, html_file_path="mail.html")

    # year, month, day
    start_date = "2025/02/11"
    end_date = "2025/02/19"

    combined_text = gmail_manager.combine_unread_emails_text_in_period(start_date, end_date)
    print("Combined Email Text:\n", combined_text)
