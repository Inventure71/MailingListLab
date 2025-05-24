import email
import os
import base64
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Dict, Tuple

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

# Define system labels consistently across all methods
SYSTEM_LABELS = {"INBOX", "UNREAD", "STARRED", "SENT", "IMPORTANT", "TRASH", "SPAM", "DRAFT"}


class GmailHelper:
    """
    Minimal Gmail utility focused on:
        1. Listing / filtering messages
        2. Parsing message contents
        3. Deleting, archiving, label / read-state changes
        4. Sending HTML e-mail (raw string or file)

    Only the seven public methods requested are exposed; everything
    else is marked _private.
    """

    def __init__(
        self,
        credentials_file: str = "credentials/credentials.json",
        token_file: str = "credentials/token.json",
    ):
        self.creds = self._load_credentials(credentials_file, token_file)
        self.service = build("gmail", "v1", credentials=self.creds)

    @staticmethod
    def _load_credentials(credentials_file: str, token_file: str) -> Credentials:
        creds = None
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)

        # refresh / run flow if necessary
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0, open_browser=False)
            with open(token_file, "w") as f:
                f.write(creds.to_json())
        return creds

    def list_emails(
        self,
        *,
        start_date: Optional[str] = None,  # "YYYY/MM/DD"
        end_date: Optional[str] = None,    # "YYYY/MM/DD"
        archived_status: int = 0,          # 0: non-archived (in INBOX), 1: archived (not INBOX), 2: both
        read_status: int = 2,              # 0: unread, 1: read, 2: both
        include_labels: Optional[List[str]] = None, # Must have ALL these labels
        exclude_labels: Optional[List[str]] = None, # Must NOT have ANY of these labels
        sender: Optional[str] = None,
        max_results: int = 100,
        limit_newest: Optional[int] = None,  # Limit to newest N emails (oldest eliminated)
    ) -> List[Dict]:
        """
        Return message stubs that satisfy the given filters.
        All parameters are optional; ones left as None are ignored.

        `start_date` and `end_date` are inclusive (we add +1 day internally
        for the Gmail `before:` keyword which is < exclusive).
        `archived_status`: 0 for in INBOX, 1 for not in INBOX (archived), 2 for no filter.
        `read_status`: 0 for unread, 1 for read, 2 for no filter.
        `limit_newest`: If provided, returns only the newest N emails (Gmail returns newest first by default).
        """
        query_parts: List[str] = []
        label_ids_to_include_server_side: Optional[List[str]] = None

        # Determine the actual limit to use for the API call
        # Gmail returns emails in reverse chronological order (newest first)
        api_max_results = max_results
        if limit_newest is not None and limit_newest < max_results and limit_newest > 0:
            api_max_results = limit_newest

        # --- date range -----------------------------------------------------
        if start_date:
            query_parts.append(f"after:{start_date}")
        if end_date:
            dt = datetime.strptime(end_date, "%Y/%m/%d") + timedelta(days=1)
            query_parts.append(f"before:{dt.strftime('%Y/%m/%d')}")

        # --- read / unread status -------------------------------------------
        if read_status == 0: # unread
            query_parts.append("is:unread")
        elif read_status == 1: # read
            query_parts.append("is:read")
        # if read_status == 2, no filter is applied (default)

        # --- archived status ------------------------------------------------
        if archived_status == 0: # Non-archived (must be in INBOX)
            query_parts.append("in:inbox")
        elif archived_status == 1: # Archived (must NOT be in INBOX, also not TRASH/SPAM for clarity)
            query_parts.append("-in:inbox -in:trash -in:spam")
        # if archived_status == 2, no filter is applied (default behavior for archived)
        
        # --- sender ---------------------------------------------------------
        if sender:
            query_parts.append(f"from:{sender}")

        # --- label filters --------------------------------------------------
        # Optimize: get all labels only once if we need them
        all_user_labels = None
        if include_labels or exclude_labels:
            all_user_labels = self._get_labels_indexed_by_name()
        
        # Handle included labels
        if include_labels:
            current_label_ids_to_include = []
            for label_name in include_labels:
                label_id = None
                if label_name.upper() in SYSTEM_LABELS:
                    label_id = label_name.upper()
                else:
                    label_id = all_user_labels.get(label_name.lower())
                
                if label_id:
                    current_label_ids_to_include.append(label_id)
                else:
                    # If a required label doesn't exist, no email can match
                    return [] 
            if current_label_ids_to_include:
                # Gmail API's labelIds parameter performs an AND operation.
                # So, we can use it for server-side filtering of included labels.
                label_ids_to_include_server_side = current_label_ids_to_include

        # Handle excluded labels (always via query string)
        if exclude_labels:
            for label_name in exclude_labels:
                label_id = None
                if label_name.upper() in SYSTEM_LABELS:
                    label_id = label_name.upper()
                else:
                    label_id = all_user_labels.get(label_name.lower())
                
                if label_id: # Only add to query if the label exists
                    query_parts.append(f"-label:{label_id}")

        query_str = " ".join(query_parts) if query_parts else None

        try:
            resp = (
                self.service.users()
                .messages()
                .list(
                    userId="me",
                    q=query_str,
                    labelIds=label_ids_to_include_server_side, 
                    maxResults=api_max_results,  # Use the computed limit
                )
                .execute()
            )
            messages = resp.get("messages", [])
            
            # Additional client-side limiting if needed
            # (Gmail should already return in newest-first order, but this ensures consistency)
            if limit_newest is not None and len(messages) > limit_newest:
                messages = messages[:limit_newest]
                
            return messages
        except HttpError as e:
            print(f"Gmail API error while listing messages: {e}")
            return []

    def parse_email(self, message_id: str) -> Dict:
        """
        Resolve a full Gmail message and return:
        sender, title, text_content, html_content, links, images, labels, date
        """
        msg = (
            self.service.users().messages().get(userId="me", id=message_id, format="full").execute()
        )

        headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
        date_rfc2822 = headers.get("date")
        date_obj = email.utils.parsedate_to_datetime(date_rfc2822) if date_rfc2822 else None

        plain, html = self._extract_bodies(msg["payload"])
        links, images = self._extract_links_and_images(html)

        return {
            "id": message_id,
            "sender": headers.get("from"),
            "title": headers.get("subject"),
            "text": plain,
            "html": html,
            "links": links,
            "images": images,
            "labels": msg.get("labelIds", []),
            "date": date_obj,
        }

    @staticmethod
    def _extract_bodies(payload) -> Tuple[str, str]:
        """Recursively walk MIME parts → (plain, html)"""
        plain, html = "", ""

        def walk(part):
            nonlocal plain, html
            if part.get("parts"):
                for sub in part["parts"]:
                    walk(sub)
            else:
                data = part.get("body", {}).get("data")
                if not data:
                    return
                decoded = base64.urlsafe_b64decode(data.encode()).decode("utf-8", "replace")
                if part["mimeType"] == "text/plain":
                    plain += decoded
                elif part["mimeType"] == "text/html":
                    html += decoded

        walk(payload)
        return plain, html

    @staticmethod
    def _extract_links_and_images(html: str) -> Tuple[List[str], List[str]]:
        if not html:
            return [], []
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract links but filter out problematic ones
        raw_links = [a["href"] for a in soup.find_all("a", href=True)]
        filtered_links = []
        
        for link in raw_links:
            # Skip mailto:, tel:, sms:, and other protocol links that trigger system actions
            if link.lower().startswith(('mailto:', 'tel:', 'sms:', 'callto:', 'skype:')):
                continue
            # Skip javascript: links
            if link.lower().startswith('javascript:'):
                continue
            # Skip empty or anchor-only links
            if not link.strip() or link.strip() == '#':
                continue
                
            filtered_links.append(link)
        
        images = [img["src"] for img in soup.find_all("img", src=True)]
        return filtered_links, images

    def delete_email(self, message_id: str) -> bool:
        try:
            self.service.users().messages().delete(userId="me", id=message_id).execute()
            return True
        except HttpError as e:
            print("Gmail API error while deleting:", e)
            return False

    def archive_email(self, message_id: str) -> bool:
        try:
            self.service.users().messages().modify(userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}).execute()
            return True
        except HttpError as e:
            print("Gmail API error while archiving:", e)
            return False

    def update_email_state(
        self,
        message_id: str,
        labels_to_add: Optional[List[str]] = None,
        labels_to_remove: Optional[List[str]] = None,
        read: Optional[bool] = None,  # True → mark READ, False → mark UNREAD
    ) -> bool:
        """
        • Accepts **label names** (not IDs) in `labels_to_add/remove`.  
        • Creates missing labels automatically.  
        • Handles the read/unread toggle via UNREAD system label.
        """
        add_ids, remove_ids = [], []

        # convert custom label names → IDs
        for name in labels_to_add or []:
            if name.upper() in SYSTEM_LABELS:  # Use consistent system labels set
                add_ids.append(name.upper())
            else:
                add_ids.append(self._ensure_label_id(name))

        for name in labels_to_remove or []:
            if name.upper() in SYSTEM_LABELS:  # Use consistent system labels set
                remove_ids.append(name.upper())
            else:
                remove_ids.append(self._ensure_label_id(name))

        # read/unread flag → adjust UNREAD label
        if read is True:
            remove_ids.append("UNREAD")
        elif read is False:
            add_ids.append("UNREAD")

        body: Dict[str, List[str]] = {}
        if add_ids:
            body["addLabelIds"] = add_ids
        if remove_ids:
            body["removeLabelIds"] = remove_ids

        try:
            self.service.users().messages().modify(
                userId="me", id=message_id, body=body
            ).execute()
            return True
        except HttpError as e:
            print("Gmail API error while updating labels/state:", e)
            return False
    
    def send_email_html(
        self,
        to: str,
        subject: str,
        html_content: str,
        sender: Optional[str] = None,
    ):
        mime = MIMEMultipart("alternative")
        mime["to"] = to
        mime["subject"] = subject
        mime["from"] = sender if sender else "me"
        mime.attach(MIMEText(html_content, "html"))

        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        try:
            return (
                self.service.users().messages().send(userId="me", body={"raw": raw}).execute()
            )
        except HttpError as e:
            print("Gmail API error while sending:", e)
            return None

    def send_email_from_html_file(
        self,
        to: str,
        subject: str,
        html_path: str,
        sender: Optional[str] = None,
    ):
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            return self.send_email_html(to, subject, html, sender)
        except FileNotFoundError:
            print(f"HTML file not found: {html_path}")
            return None

    # ---------- helpers -----------------------------------------------------
    
    # ---------- label helpers -----------------------------------------------------
    def _get_labels_indexed_by_name(self) -> Dict[str, str]:
        """
        Returns {lower-cased label name → label ID} for **all** labels
        the user currently has.
        """
        resp = self.service.users().labels().list(userId="me").execute()
        return {lbl["name"].lower(): lbl["id"] for lbl in resp.get("labels", [])}

    def _ensure_label_id(self, label_name: str) -> str:
        """
        Return the label ID for `label_name` (case-insensitive).  
        Creates the label if it doesn't exist and returns the new ID.
        """
        index = self._get_labels_indexed_by_name()
        if label_name.lower() in index:                # already exists
            return index[label_name.lower()]

        # create it
        body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        new_label = (
            self.service.users().labels().create(userId="me", body=body).execute()
        )
        return new_label["id"]
    
if __name__ == "__main__":
    gh = GmailHelper()

    print("--- Example 1: Unread, in Inbox, from past 7 days ---")
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y/%m/%d")
    today = datetime.now().strftime("%Y/%m/%d")
    ex1_msgs = gh.list_emails(
        start_date=seven_days_ago,
        end_date=today,
        read_status=0,       # Unread
        archived_status=0,   # In Inbox
    )
    print(f"Found {len(ex1_msgs)} emails.")
    for msg_stub in ex1_msgs[:2]: # Print details for first 2
        details = gh.parse_email(msg_stub['id'])
        print(f"  ID: {details['id']}, Subject: {details['title']}, Sender: {details['sender']}, Date: {details['date']}")

    print("\n--- Example 2: Read, Archived, with label 'ANALYZED' ---")
    ex2_msgs = gh.list_emails(
        read_status=1,       # Read
        archived_status=1,   # Archived
        include_labels=["ANALYZED"],
    )
    print(f"Found {len(ex2_msgs)} emails.")
    for msg_stub in ex2_msgs[:2]:
        details = gh.parse_email(msg_stub['id'])
        print(f"  ID: {details['id']}, Subject: {details['title']}, Labels: {details['labels']}")

    print("\n--- Example 3: Any status, from 'specific.sender@example.com', excluding 'OldProject' label ---")
    ex3_msgs = gh.list_emails(
        read_status=2,              # Any read status
        archived_status=2,          # Any archive status
        sender="matteo.giorgetti.05@gmail.com",
        exclude_labels=["OldProject"],
    )
    print(f"Found {len(ex3_msgs)} emails.")
    for msg_stub in ex3_msgs[:2]:
        details = gh.parse_email(msg_stub['id'])
        print(f"  ID: {details['id']}, Subject: {details['title']}, Sender: {details['sender']}")

    print("\n--- Example 4: Unread, in Inbox, must have 'Urgent' and 'Work' labels ---")
    ex4_msgs = gh.list_emails(
        read_status=0,
        archived_status=0,
        include_labels=["Urgent", "Work"],
    )
    print(f"Found {len(ex4_msgs)} emails.")
    for msg_stub in ex4_msgs[:2]:
        details = gh.parse_email(msg_stub['id'])
        print(f"  ID: {details['id']}, Subject: {details['title']}, Labels: {details['labels']}")

    print("\n--- Example 5: Read, in Inbox, from past 2 days, excluding 'Newsletter' and 'Promotions' ---")
    two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y/%m/%d")
    ex5_msgs = gh.list_emails(
        start_date=two_days_ago,
        end_date=today,
        read_status=1, # Read
        archived_status=0, # In Inbox
        exclude_labels=["Newsletter", "Promotions"],
    )
    print(f"Found {len(ex5_msgs)} emails.")
    for msg_stub in ex5_msgs[:2]:
        details = gh.parse_email(msg_stub['id'])
        print(f"  ID: {details['id']}, Subject: {details['title']}, Date: {details['date']}")

    # Example of testing label creation and filtering
    print("\n--- Example 6: Test label filtering with both include and exclude ---")
    # This example tests both include_labels and exclude_labels together
    ex6_msgs = gh.list_emails(
        read_status=2,              # Any read status
        archived_status=2,          # Any archive status  
        include_labels=["INBOX"],   # Must be in INBOX (system label)
        exclude_labels=["SPAM", "TRASH"],  # Exclude SPAM and TRASH (system labels)
        max_results=5,
    )
    print(f"Found {len(ex6_msgs)} emails in INBOX excluding SPAM/TRASH.")
    for msg_stub in ex6_msgs[:2]:
        details = gh.parse_email(msg_stub['id'])
        print(f"  ID: {details['id']}, Subject: {details['title']}, Labels: {details['labels']}")

    print("\n--- Example 7: Test limit_newest parameter - Get only newest 3 emails ---")
    ex7_msgs = gh.list_emails(
        read_status=2,              # Any read status
        archived_status=0,          # In Inbox only
        limit_newest=3,             # Limit to newest 3 emails
    )
    print(f"Found {len(ex7_msgs)} newest emails (should be max 3).")
    for msg_stub in ex7_msgs:
        details = gh.parse_email(msg_stub['id'])
        print(f"  ID: {details['id']}, Subject: {details['title']}, Date: {details['date']}")

    # Example of how you might set up a label for testing include_labels
    # label_id = gh._ensure_label_id("TestLabel") 
    # print(f"\nEnsured 'TestLabel' exists with ID: {label_id}")
    # If you have a message ID, you can add this label to it for testing Example 2:
    # test_message_id = "YOUR_TEST_MESSAGE_ID_HERE" 
    # if test_message_id != "YOUR_TEST_MESSAGE_ID_HERE":
    #     gh.update_email_state(test_message_id, labels_to_add=["TestLabel"], read=True)
    #     gh.archive_email(test_message_id)
    #     print(f"Updated message {test_message_id} for Example 2 testing.")
