import time
from datetime import datetime, timedelta
import json
import logging
from gmail_handler import GmailManager
from main import create_email_procedurally


#TODO: USE GOOGLE FORM FOR RESPONSES


"""VARIABLES"""
sent_newsletter = False
start_of_newsletter_str = "2025/03/01"
days = ["Monday", "Friday"] # Monday and Friday
release_time_str = "12:23:00"
"""VARIABLES"""


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("email_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("email_monitor")


def handle_newsletter():
    global sent_newsletter, start_of_newsletter_str, days, release_time_str

    date_object = datetime.now()
    release_time = datetime.strptime(release_time_str, "%H:%M:%S").time()
    release_datetime = datetime.combine(datetime.now().date(), release_time)

    diff = datetime.now() - release_datetime

    if not sent_newsletter:
        if date_object.strftime("%A") in days:
            print(f"It's {date_object.strftime('%A')}")

            if diff.total_seconds() >= 0 and diff.total_seconds() <= 600:
                print("It's time to send the newsletter")

                sent_newsletter = True

                create_email_procedurally(
                    send_mail=True,
                )

            # if datetime.now().strftime("%H:%M:%S") >= release_time:
            #    print("It's time to send the newsletter")

    else:
        if diff.total_seconds() > 6000:
            print("Resetting newsletter flag")
            sent_newsletter = False


def check_new_emails(gm):
    today = datetime.now().strftime("%Y/%m/%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y/%m/%d")

    try:
        emails = gm.get_emails(start_date=today, end_date=tomorrow, max_results=10, unread_only=True, set_as_read=False)

        if emails:
            logger.info(f"Found {len(emails)} new emails.")

            try:
                with open("files/whitelist.json", "r") as f:
                    whitelist = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Error loading whitelist: {e}")
                return

            for email in emails:
                try:
                    message = gm.object_to_email(email)

                    headers = message["payload"]["headers"]
                    sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")

                    if "<" in sender and ">" in sender:
                        sender_email = sender.split("<")[1].split(">")[0]
                    else:
                        sender_email = sender

                    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")

                    logger.debug(f"Processing email from {sender_email} with subject '{subject}'")

                    if sender_email in whitelist["allowed_emails"]:
                        if subject.upper() == "REPOST":
                            logger.info(f"Processing repost from {sender_email}")

                            gm.set_as_read(email)
                            gm.archive_email(email) # so it will not be used later

                            create_email_procedurally(
                                gmail_handler=gm,
                                send_mail=True,
                                force_emails=[email],
                                from_user=sender
                            )

                            logger.info(f"Successfully processed repost from {sender_email}")
                except Exception as e:
                    logger.error(f"Error processing email: {e}")
        else:
            logger.debug("No new emails found.")
    except Exception as e:
        logger.error(f"Error checking emails: {e}")


def main():
    logger.info("Starting email monitor service")

    try:
        gm = GmailManager()

        while True:
            check_new_emails(gm)

            handle_newsletter()

            logger.debug("Sleeping for 10 seconds...")
            time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Email monitor service stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error in email monitor: {e}")
        raise


if __name__ == "__main__":
    main()
