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

        # ---------- 1. Retrieve e-mails (updated) -------------------------------
    
    def list_emails(
        self,
        *,
        start_date: Optional[str] = None,  # "YYYY/MM/DD"
        end_date: Optional[str] = None,    # "YYYY/MM/DD"
        label: Optional[str] = None,       # label *name* (not ID)
        label_included: bool = True,       # True ↦ must have, False ↦ must NOT
        read: Optional[bool] = None,       # True ↦ is:read, False ↦ is:unread
        sender: Optional[str] = None,
        max_results: int = 100,
    ) -> List[Dict]:
        """
        Return message stubs that satisfy the given filters.
        All parameters are optional; ones left as None are ignored.

        `start_date` and `end_date` are inclusive (we add +1 day internally
        for the Gmail `before:` keyword which is < exclusive).
        """
        query_parts: List[str] = []
        label_ids_filter: Optional[List[str]] = None  # only used when *including*

        # --- date range -----------------------------------------------------
        if start_date:
            query_parts.append(f"after:{start_date}")
        if end_date:
            dt = datetime.strptime(end_date, "%Y/%m/%d") + timedelta(days=1)
            query_parts.append(f"before:{dt.strftime('%Y/%m/%d')}")

        # --- read / unread --------------------------------------------------
        if read is True:
            query_parts.append("is:read")
        elif read is False:
            query_parts.append("is:unread")

        # --- sender ---------------------------------------------------------
        if sender:
            query_parts.append(f"from:{sender}")

        # --- label filter ---------------------------------------------------
        if label:
            # system labels already *are* IDs
            sys_labels = {"INBOX", "UNREAD", "STARRED", "SENT", "IMPORTANT", "TRASH", "SPAM", "DRAFT"}
            if label.upper() in sys_labels:
                label_id = label.upper()
            else:
                index = self._get_labels_indexed_by_name()
                label_id = index.get(label.lower())
                if not label_id:
                    # label doesn't exist → nothing can match if it *must* be present
                    if label_included:
                        return []
                    # if it must be *absent* we can just ignore it (everything qualifies)
                    label_id = None

            if label_id:
                if label_included:
                    label_ids_filter = [label_id]          # server-side include
                else:
                    query_parts.append(f"-label:{label_id}")  # text query exclude

        query_str = " ".join(query_parts) if query_parts else None

        try:
            resp = (
                self.service.users()
                .messages()
                .list(
                    userId="me",
                    q=query_str,
                    labelIds=label_ids_filter,  # None → ignored
                    maxResults=max_results,
                )
                .execute()
            )
            return resp.get("messages", [])
        except HttpError as e:
            print("Gmail API error while listing messages:", e)
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
        links = [a["href"] for a in soup.find_all("a", href=True)]
        images = [img["src"] for img in soup.find_all("img", src=True)]
        return links, images

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
            if name.upper() in ("INBOX", "UNREAD", "STARRED"):  # system labels
                add_ids.append(name.upper())
            else:
                add_ids.append(self._ensure_label_id(name))

        for name in labels_to_remove or []:
            if name.upper() in ("INBOX", "UNREAD", "STARRED"):
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
        Creates the label if it doesn’t exist and returns the new ID.
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

    # 1️⃣  List unread messages from Alice between two dates
    msgs = gh.list_emails(
        start_date="2025/05/01",
        end_date="2025/05/22",
        read=True,
        label="TEST",
        label_included=True,
        #sender="alice@example.com",
    )

    if msgs:
        details = gh.parse_email(msgs[0]["id"])
        print(details["title"], details["sender"], details["links"], details["date"])

        gh.update_email_state(msgs[0]["id"], read=True, labels_to_add=["TEST"])
        #gh.archive_email(msgs[0]["id"])
