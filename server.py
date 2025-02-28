import time
from datetime import datetime, timedelta
import json
from gmail_handler import GmailManager
from main import create_email_procedurally


def check_new_emails(gm):
    today = datetime.now().strftime("%Y/%m/%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y/%m/%d")

    emails = gm.get_emails(start_date=today, end_date=tomorrow, max_results=10, unread_only=True, set_as_read=False)

    if emails:
        print(f"Found {len(emails)} new emails.")

        whitelist = json.load(open("files/whitelist.json"))

        for email in emails:
            message = gm.object_to_email(email)

            headers = message["payload"]["headers"]

            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")
            if "<" in sender and ">" in sender:
                sender_email = sender.split("<")[1].split(">")[0]  # Extracts email inside <>
            else:
                sender_email = sender  # If no name is present, just return the whole value

            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")

            #plain_text, html_text = self.get_email_content(message.get("payload", {}))
            #print(f"Sender: {sender_email}")

            for user in whitelist["allowed_emails"]:
                #print(f"Checking user: {user}.")
                if sender_email == user:
                    print(f"Found user: {user}. (DEBUG)")
                if subject == "REPOST":
                    print(f"Found subject: {subject}. (DEBUG)")

                if sender_email == user and subject == "REPOST":
                    print(f"Sharing email from {sender} with subject {subject}.")
                    gm.set_as_read(email)


    else:
        print("No new emails found.")


gm = GmailManager()

while True:
    check_new_emails(gm)
    print("Sleeping for 10 seconds...")
    time.sleep(10)

    create_email_procedurally
