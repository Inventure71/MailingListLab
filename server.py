import json
import time
from datetime import datetime, timedelta
import flask
from gmail_handler import GmailManager

def check_new_emails(gm):
    today = datetime.now().strftime("%Y/%m/%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y/%m/%d")

    emails = gm.get_emails(start_date=today, end_date=tomorrow, max_results=10, unread_only=True, set_as_read=False)

    if emails:
        whitelist = json.load(open("files/whitelist.json"))

        for email in emails:
            message = gm.read_email(email)

            headers = message["payload"]["headers"]

            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")

            #subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            #plain_text, html_text = self.get_email_content(message.get("payload", {}))

            for user in whitelist:
                if sender == user:
                    print(f"Found user: {user['name']}, sharing this email.")

    else:
        print("No new emails found.")


gm = GmailManager()

while True:
    check_new_emails(gm)
    print("Sleeping for 10 seconds...")
    time.sleep(10)