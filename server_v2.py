from datetime import datetime, timedelta
import json
import os
import threading
import logging
import time

from modules.AI.flows import analyze_repost, analyze_emails_newsletter
from modules.AI.use_gemini_v2 import GeminiHandler
from modules.email.compose_repost_email import RepostEmailGenerator
from modules.email.compose_weekly_email import NewsEmailGenerator
from modules.email.gmail_handler_v2 import GmailHelper
from modules.utils.extract_email_address import extract_email_address


# pip install -r requirements.txt
# TODO: add google form at the end of emails to collect feedback

"""LOGGING"""
logging.basicConfig(
    level=logging.DEBUG,
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
    
    if not os.path.exists("images"):
        os.makedirs("images")

    if not os.path.exists("files"):
        os.makedirs("files")

    if not os.path.exists("configs/setup.json"):
        logging.warning("Setup file not found, creating default setup file")
        with open("configs/setup.json", "w") as f:
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
limit_newest = None
"""DEFAULT VALUES"""


def load_setup():
    with open("configs/setup.json", "r") as f:
        setup = json.load(f)

    active = setup.get("active", True)
    days = setup.get("days", [])
    release_time_str = setup.get("release_time_str", "")
    seconds_between_checks = setup.get("seconds_between_checks", 10)
    whitelisted_senders = setup.get("whitelisted_senders", [])
    newsletter_email = setup.get("newsletter_email", "")
    limit_newest = setup.get("limit_newest", 10)
    if not newsletter_email:
        logging.warning("newsletter_email is not configured in setup.json! Email sending will be disabled.")
    
    logging.info("active: %s, days: %s, release_time_str: %s, seconds_between_checks: %s, whitelisted_senders: %s, newsletter_email: %s, limit_newest: %s", active, days, release_time_str, seconds_between_checks, whitelisted_senders, newsletter_email, limit_newest)
    return active, days, release_time_str, seconds_between_checks, whitelisted_senders, newsletter_email, limit_newest

active, days, release_time_str, seconds_between_checks, whitelisted_senders, newsletter_email, limit_newest = load_setup()

gh = GmailHelper()
gemini_handler = GeminiHandler()


"""REPOST"""
def create_repost_email(parsed_mail, send_mail=True):
    try:
        # Create a separate Gmail instance for this thread to avoid thread safety issues
        thread_gh = GmailHelper()
        repost_email_generator = RepostEmailGenerator()

        articles = analyze_repost(parsed_mail, intensive_mode=True, include_link_info=True, include_images=True, gemini_handler=gemini_handler)

        mail_htlm = repost_email_generator.generate_email(articles)

        # Update email state with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                thread_gh.update_email_state(parsed_mail["id"], labels_to_add=["ANALYZED"])
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logging.error(f"Failed to label email {parsed_mail['id']} after {max_retries} attempts: {e}")
                else:
                    logging.warning(f"Attempt {attempt + 1} failed to label email {parsed_mail['id']}: {e}, retrying...")
                    time.sleep(2 ** attempt)  # exponential backoff

        if send_mail:
            try:
                if not newsletter_email:
                    logging.error("newsletter_email is not configured! Cannot send repost.")
                    return None
                logging.info(f"Attempting to send repost email to: {newsletter_email}")
                thread_gh.send_email_html(newsletter_email, "Repost", mail_htlm)
                logging.info("Sent repost email to %s", newsletter_email)
            except Exception as e:
                logging.error(f"Failed to send repost email: {e}")
        else:
            logging.info("Not sending repost email to %s", newsletter_email)
        
        return mail_htlm
        
    except Exception as e:
        logging.error(f"Error in create_repost_email: {e}")
        return None


"""NEWSLETTER"""
def create_news_letter(send_mail=True):
    # Create a separate Gmail instance for this thread to avoid thread safety issues
    try:
        logging.info("---STARTING--- Creating newsletter")
        thread_gh = GmailHelper()
        generator = NewsEmailGenerator()
        
        emails_to_analyze = [] # list of emails to analyze

        # Get all unread emails from 7 days ago to today, that are not archived and not labeled "ANALYZED"
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y/%m/%d")
        end_date = datetime.now().strftime("%Y/%m/%d")

        msgs = thread_gh.list_emails(
            start_date=start_date,
            end_date=end_date,
            read_status=2,  # both read and unread
            archived_status=0, # 0: only non-archived (in INBOX)
            exclude_labels=["ANALYZED"],
            limit_newest=limit_newest,  # Limit to newest 100 emails for performance
        )

        logging.debug("Found %s unprocessed mails", len(msgs))

        for msg in msgs:
            try:
                logging.info("Found unprocessed mail candidate for newsletter: %s", msg)
                # parse the mail
                mail = thread_gh.parse_email(msg["id"])
                logging.info("Parsed mail (first 5 words): %s", " ".join(mail.get("text", "").split()[:5]))
                emails_to_analyze.append(mail)
                
                # add the label "ANALYZED" to the mail with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        thread_gh.update_email_state(msg["id"], labels_to_add=["ANALYZED"])
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            logging.error(f"Failed to label email {msg['id']} after {max_retries} attempts: {e}")
                        else:
                            logging.warning(f"Attempt {attempt + 1} failed to label email {msg['id']}: {e}, retrying...")
                            time.sleep(2 ** attempt)  # exponential backoff
                            
            except Exception as e:
                logging.error(f"Error processing email {msg.get('id', 'unknown')}: {e}")
                continue
        
        # TODO: remove any duplicate articles

        articles = analyze_emails_newsletter(emails_to_analyze, intensive_mode=True, include_link_info=True, include_website_news=True, include_images=True, gemini_handler=gemini_handler)

        email_html = generator.generate_email(articles)

        if send_mail:
            try:
                if not newsletter_email:
                    logging.error("newsletter_email is not configured! Cannot send newsletter.")
                    return
                logging.info(f"Attempting to send newsletter to: {newsletter_email}")
                thread_gh.send_email_html(newsletter_email, "Newsletter", email_html)
                logging.info("Sent newsletter to %s", newsletter_email)
            except Exception as e:
                logging.error(f"Failed to send newsletter: {e}")
        else:
            logging.info("Not sending newsletter to %s", newsletter_email)
            
    except Exception as e:
        logging.error(f"Error in create_news_letter: {e}")
        return


def create_news_letter_threaded(send_mail=True):
    # Wrapper to run create_news_letter in a new thread
    thread = threading.Thread(target=create_news_letter, args=(send_mail,), daemon=True)
    thread.start()
    logging.info("Started create_news_letter in a new thread.")
    
    # IMPORTANT: Schedule the next newsletter after this one completes
    # Use a separate thread to restart the timer after newsletter completes
    def restart_timer_after_completion():
        thread.join()  # Wait for newsletter to complete
        logging.info("Newsletter completed, scheduling next newsletter")
        find_and_start_newsletter_timer()
    
    restart_thread = threading.Thread(target=restart_timer_after_completion, daemon=True)
    restart_thread.start()


"""CHECKING + TIME RELATED"""
def check_mails():
    global active, days, release_time_str, seconds_between_checks, whitelisted_senders, newsletter_email, newsletter_timer_thread, gh, limit_newest
    logging.info("Checking mails for reposts or changes to config")
    logging.debug(f"Current newsletter_email: {newsletter_email}")

    # Get unread, non-archived emails from today that are NOT labeled "NOT_WHITELISTED"
    today_str = datetime.now().strftime("%Y/%m/%d")
    msgs = gh.list_emails(
        start_date=today_str,
        end_date=today_str,
        read_status=2, # both read and unread
        archived_status=0,
        exclude_labels=["NOT_WHITELISTED", "ANALYZED"],
    )

    print("FOUND MAILS: ", len(msgs))

    for msg in msgs:
        logging.info("Found unprocessed mail to consider for config or repost: %s", msg)
        # parse the mail
        mail = gh.parse_email(msg["id"])
        logging.info("Parsed mail (first 5 words): %s", " ".join(mail.get("text", "").split()[:5]))
        
        # Extract just the email address from the full sender string
        sender_email = extract_email_address(mail["sender"])
        logging.info("Extracted sender email: %s", sender_email)
        
        if sender_email in whitelisted_senders:
            logging.info("Found whitelisted sender: %s", sender_email)
            if mail["title"].lower() == "config":
                logging.info("Found config mail, updating config")

                new_modifications = json.loads(mail["text"])
                logging.info("New modifications: %s", new_modifications)
                logging.info("OLD config: %s", {"active": active, "days": days, "release_time_str": release_time_str, "seconds_between_checks": seconds_between_checks, "whitelisted_senders": whitelisted_senders, "newsletter_email": newsletter_email, "limit_newest": limit_newest})

                should_send_now = False

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
                    elif key == "limit_newest":
                        limit_newest = value
                    elif key == "send_now":
                        should_send_now = value
                        logging.info("Sending newsletter now")
                
                logging.info("NEW config: %s", {"active": active, "days": days, "release_time_str": release_time_str, "seconds_between_checks": seconds_between_checks, "whitelisted_senders": whitelisted_senders, "newsletter_email": newsletter_email, "limit_newest": limit_newest})

                # update the setup file
                with open("configs/setup.json", "w") as f:
                    json.dump({"active": active, "days": days, "release_time_str": release_time_str, "seconds_between_checks": seconds_between_checks, "whitelisted_senders": whitelisted_senders, "newsletter_email": newsletter_email, "limit_newest": limit_newest}, f)
                
                # archive the mail
                gh.update_email_state(msg["id"], labels_to_add=["ANALYZED"])
                gh.archive_email(msg["id"])

                # send the newsletter
                if should_send_now:
                    if newsletter_timer_thread:
                        newsletter_timer_thread.cancel()
                    create_news_letter_threaded(send_mail=True)
                    # Note: find_and_start_newsletter_timer() will be called automatically after newsletter completes

                # restart the newsletter thread with new config
                elif newsletter_timer_thread:
                    newsletter_timer_thread.cancel()
                    find_and_start_newsletter_timer()
            
            else:
                logging.info("Found non-config mail, with title: %s, checking for reposts", mail["title"])
                # Launch create_repost_email in a new thread
                repost_thread = threading.Thread(target=create_repost_email, args=(mail,), daemon=True)
                repost_thread.start()
                logging.info("Started create_repost_email in a new thread.")
                
                gh.archive_email(msg["id"]) # Archive immediately
                logging.info("Archived mail")
        
        else:
            logging.info("Found non-whitelisted mail, with sender: %s (email: %s), skipping", mail["sender"], sender_email)
            # add the label "NOT_WHITELISTED" to the mail
            gh.update_email_state(msg["id"], labels_to_add=["NOT_WHITELISTED"])


def find_and_start_newsletter_timer():
    global newsletter_timer_thread, release_time_str, days, active

    if not active:
        logging.info("Newsletter is inactive, timer not started.")
        return

    if not release_time_str or not days:
        logging.warning("Newsletter config incomplete (missing release_time_str or days)")
        return

    try:
        logging.info("Finding and starting newsletter timer current time: %s, config: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str({"active": active, "days": days, "release_time_str": release_time_str}))
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

            days_ahead = None  # Initialize to avoid undefined variable
            # Find next day index in sorted fashion (wraparound included)
            for offset in range(1, 8):
                next_idx = (today_idx + offset) % 7
                next_day = weekdays[next_idx]
                if next_day in days:
                    days_ahead = offset
                    break
            
            # If no valid day found, log error and return
            if days_ahead is None:
                logging.error(f"No valid days found in configuration: {days}. Valid days are: {weekdays}")
                return

            # Set target datetime to the next valid day at release_time
            next_date = now + timedelta(days=days_ahead)
            target_datetime = datetime.combine(next_date.date(), target_time)

        # Calculate delay and start timer
        delay_seconds = (target_datetime - now).total_seconds()
        logging.info("Next newsletter scheduled for %s (in %.2f seconds)", target_datetime, delay_seconds)

        newsletter_timer_thread = threading.Timer(delay_seconds, create_news_letter_threaded)
        newsletter_timer_thread.start()

    except Exception as e:
        logging.error("Failed to schedule newsletter timer: %s", str(e))


find_and_start_newsletter_timer()

# Start the email checking loop
def check_mails_loop():
    while True:
        try:
            check_mails()
        except Exception as e:
            logging.error(f"Error in check_mails_loop: {e}")
        time.sleep(seconds_between_checks)

# Start email checking thread
threading.Thread(target=check_mails_loop, daemon=True).start()
logging.info("Started email checking thread")

# Keep the main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logging.info("Server stopped by user")

"""CHECKING"""