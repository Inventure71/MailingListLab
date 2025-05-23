from datetime import datetime, timedelta
import json
import os
import threading
import logging

from modules.AI.flows import analyze_repost, analyze_emails_newsletter
from modules.AI.use_gemini_v2 import GeminiHandler
from modules.email.compose_repost_email import RepostEmailGenerator
from modules.email.compose_weekly_email import NewsEmailGenerator
from modules.email.gmail_handler_v2 import GmailHelper

"""LOGGING"""
logging.basicConfig(level=logging.INFO)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("server.log"),
        logging.StreamHandler()
    ]
)
"""LOGGING"""

def check_directories():
    if not os.path.exists("configs"):
        logging.warning("Configs directory not found, creating default configs directory")
        raise Exception("Configs directory not found")

    if not os.path.exists("files"):
        os.makedirs("files")
    if not os.path.exists("files/setup.json"):
        logging.warning("Setup file not found, creating default setup file")
        with open("files/setup.json", "w") as f:
            json.dump({"active": True, "days": [], "release_time_str": "", "seconds_between_checks": 10}, f)

check_directories()

"""DEFAULT VALUES"""
active = True 
days = []
release_time_str = ""
seconds_between_checks = 10
whitelisted_senders = []
newsletter_timer_thread = None
newsletter_email = ""
"""DEFAULT VALUES"""


def load_setup():
    with open("files/setup.json", "r") as f:
        setup = json.load(f)

    active = setup["active"]
    days = setup["days"]
    release_time_str = setup["release_time_str"]
    seconds_between_checks = setup["seconds_between_checks"]
    whitelisted_senders = setup["whitelisted_senders"]
    newsletter_email = setup["newsletter_email"]
    logging.info("active: %s, days: %s, release_time_str: %s, seconds_between_checks: %s, whitelisted_senders: %s, newsletter_email: %s", active, days, release_time_str, seconds_between_checks, whitelisted_senders, newsletter_email)
    return active, days, release_time_str, seconds_between_checks, whitelisted_senders, newsletter_email

active, days, release_time_str, seconds_between_checks, whitelisted_senders, newsletter_email = load_setup()

gh = GmailHelper()
gemini_handler = GeminiHandler()


"""REPOST"""
def create_repost_email(msg_id, parsed_mail, send_mail=True):
    repost_email_generator = RepostEmailGenerator()

    articles = analyze_repost(parsed_mail, intensive_mode=True, include_link_info=True, include_images=True)

    mail_htlm = repost_email_generator.generate_email(articles)

    if send_mail:
        gh.send_email_html(newsletter_email, "Repost", mail_htlm)
        logging.info("Sent repost email to %s", newsletter_email)
    else:
        logging.info("Not sending repost email to %s", newsletter_email)
    
    return mail_htlm


"""NEWSLETTER"""
def create_news_letter(send_mail=True):
    generator = NewsEmailGenerator()
    
    emails_to_analyze = [] # list of emails to analyze

    # TODO: get all unread emails from today to last sent newsletter (maximum 7 days)
    start_date = datetime.now().strftime("%Y/%m/%d")
    end_date = (datetime.now() - timedelta(days=7)).strftime("%Y/%m/%d")

    msgs = gh.list_emails(
        start_date=start_date,
        end_date=end_date,
        read=False,
        label="ANALYZED",
        label_included=False,
    )

    logging.debug("Found %s unprocessed mails", len(msgs))

    for msg in msgs:
        logging.info("Found unprocessed mail: %s", msg)
        # parse the mail
        mail = gh.parse_email(msg["id"])
        logging.info("Parsed mail: %s", mail)
        emails_to_analyze.append(mail)
        # add the label "ANALYZED" to the mail
        gh.update_email_state(msg["id"], labels_to_add=["ANALYZED"])

    # TODO: remove any duplicate articles

    articles = analyze_emails_newsletter(emails_to_analyze, intensive_mode=True, include_link_info=True, include_website_news=True, include_images=True)

    email_html = generator.generate_email(articles)


"""CHECKING + TIME RELATED"""
def check_reposts():
    logging.info("Checking reposts")

    threading.Timer(seconds_between_checks, check_reposts).start()
    
def check_mails():
    global active, days, release_time_str, seconds_between_checks, whitelisted_senders, gh
    logging.info("Checking mails for reposts or changes to config")

    # get mails from today
    msgs = gh.list_emails(
        start_date=datetime.now().strftime("%Y/%m/%d"),
        end_date=datetime.now().strftime("%Y/%m/%d"),
        read=True,
        label="NOT_WHITELISTED",
        label_included=False,
    )

    for msg in msgs:
        logging.info("Found unprocessed mail: %s", msg)
        # parse the mail
        mail = gh.parse_email(msg["id"])
        logging.info("Parsed mail: %s", mail)
        
        if mail["sender"] in whitelisted_senders:
            logging.info("Found whitelisted sender: %s", mail["sender"])
            if mail["title"].lower() == "config":
                logging.info("Found config mail, updating config")

                new_modifications = json.loads(mail["text"])
                logging.info("New modifications: %s", new_modifications)
                logging.info("OLD config: %s", {"active": active, "days": days, "release_time_str": release_time_str, "seconds_between_checks": seconds_between_checks, "whitelisted_senders": whitelisted_senders, "newsletter_email": newsletter_email})


                # parse the json and try to find modifications
                for key, value in new_modifications.items():
                    if key == "active":
                        active = value
                    elif key == "days":
                        days = value
                    elif key == "release_time_str":
                        release_time_str = value
                    elif key == "seconds_between_checks":
                        seconds_between_checks = value
                    elif key == "whitelisted_senders":
                        whitelisted_senders = value
                    elif key == "newsletter_email":
                        newsletter_email = value
                    elif key == "send_now":
                        logging.info("Sending newsletter now")
                        create_news_letter()
                
                logging.info("NEW config: %s", {"active": active, "days": days, "release_time_str": release_time_str, "seconds_between_checks": seconds_between_checks, "whitelisted_senders": whitelisted_senders, "newsletter_email": newsletter_email})

                # update the setup file
                with open("files/setup.json", "w") as f:
                    json.dump({"active": active, "days": days, "release_time_str": release_time_str, "seconds_between_checks": seconds_between_checks, "whitelisted_senders": whitelisted_senders, "newsletter_email": newsletter_email}, f)
                
                # archive the mail
                gh.archive_email(msg["id"])

                # stop the newsletter thread
                if newsletter_timer_thread:
                    newsletter_timer_thread.cancel()
                    find_and_start_newsletter_timer()
            
            else:
                logging.info("Found non-config mail, with title: %s, checking for reposts", mail["title"])
                #print("IMPLEMENT REPOST MAIL")
                create_repost_email(msg["id"], mail)
                gh.archive_email(msg["id"])
                logging.info("Archived mail")

def find_and_start_newsletter_timer():
    global newsletter_timer_thread, release_time_str, days, active

    if not active:
        logging.info("Newsletter is inactive, timer not started.")
        return

    if not release_time_str or not days:
        logging.warning("Newsletter config incomplete (missing release_time_str or days)")
        return

    try:
        now = datetime.now()
        today_name = now.strftime("%A")
        target_time = datetime.strptime(release_time_str, "%H:%M:%S").time()

        # If today is a valid day and the target time is still in the future
        if today_name in days and now.time() < target_time:
            target_datetime = datetime.combine(now.date(), target_time)
        else:
            # Find the next valid day in the list
            weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            today_idx = now.weekday()

            # Find next day index in sorted fashion (wraparound included)
            for offset in range(1, 8):
                next_idx = (today_idx + offset) % 7
                next_day = weekdays[next_idx]
                if next_day in days:
                    days_ahead = offset
                    break

            # Set target datetime to the next valid day at release_time
            next_date = now + timedelta(days=days_ahead)
            target_datetime = datetime.combine(next_date.date(), target_time)

        # Calculate delay and start timer
        delay_seconds = (target_datetime - now).total_seconds()
        logging.info("Next newsletter scheduled for %s (in %.2f seconds)", target_datetime, delay_seconds)

        newsletter_timer_thread = threading.Timer(delay_seconds, create_news_letter)
        newsletter_timer_thread.start()

    except Exception as e:
        logging.error("Failed to schedule newsletter timer: %s", str(e))


find_and_start_newsletter_timer()
check_reposts()
"""CHECKING"""