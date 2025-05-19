import json
import multiprocessing
import os

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from modules.compose_weekly_email import NewsEmailGenerator
from modules.compose_repost_email import RepostEmailGenerator
from modules.gmail_handler import GmailManager
from spiders.page_content import PageContentSpider
from spiders.news_spider import NewsSpider
from modules.use_gemini import GeminiHandler

#TODO: Add automatic removal of emails from non allowed users (instant and before creating mail to send)

def run_crawler(link):
    process = CrawlerProcess(get_project_settings())
    process.crawl(PageContentSpider, url=link)
    process.start()

def run_news_crawler():
    process = CrawlerProcess(get_project_settings())
    process.crawl(NewsSpider)
    process.start()

    # Return the scraped news items
    news_path = os.path.join('files', 'latest_news.json')
    if os.path.exists(news_path):
        with open(news_path, 'r') as f:
            return json.load(f)
    return []

def extract_top_N(response, N=5):
    """
    Extract the top N news items from the response, sorted by relevancy.

    This function also ensures that no duplicate news from the same website is included
    by checking the 'source' field of each news item.

    Args:
        response (str): JSON string containing news items.
        N (int): Number of top news items to extract.

    Returns:
        list: Top N news items sorted by relevancy, with no duplicates from the same website.
    """
    # parse the JSON string into a Python dictionary
    response_data = json.loads(response)

    news_items = response_data.get("news", [])

    news_list = []
    # Keep track of sources we've already included to avoid duplicates
    included_sources = set()

    for news in news_items:
        relevancy = news.get("relevancy", 0)
        source = news.get("source", "")

        # Skip if we've already included news from this source
        if source and source in included_sources:
            continue

        added = False

        for x in news_list:
            if x.get("relevancy", 0) < relevancy:
                news_list.insert(news_list.index(x), news)
                added = True
                # Add the source to our set of included sources
                if source:
                    included_sources.add(source)
                break

        if len(news_list) == 0 or not added:
            news_list.append(news)
            # Add the source to our set of included sources
            if source:
                included_sources.add(source)

    return news_list[:N]

def convert_news(data):
    """
    Convert a dictionary containing a "news" key into a list of news dictionaries.

    Each news dictionary will include the following keys:
      - title
      - source
      - location
      - contact
      - description
      - summary
      - link
      - image (if present in the original item)

    Args:
        data (dict): Input dictionary containing a "news" key.

    Returns:
        list: A list of formatted news dictionaries.
    """
    news_items = data.get("news", [])
    news = []
    for item in news_items:
        news_entry = {
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "location": item.get("location", ""),
            "contact": item.get("contact", ""),
            "description": item.get("description", ""),
            "summary": item.get("summary", ""),
            "category": item.get("category", ""),
            "link": item.get("link", "")
        }
        # optionally add an image key. For instance, if an "image" key is present in the input
        if "image" in item:
            news_entry["image"] = item["image"]

        news.append(news_entry)
    return news

def create_email_procedurally(gmail_handler=None, gemini_handler=None, email_creator=None, send_mail=True, force_emails=None, from_user=None, include_website_news=True):
    if not gmail_handler:
        gmail_handler = GmailManager()
    if not gemini_handler:
        gemini_handler = GeminiHandler()
    if not email_creator:
        email_creator = NewsEmailGenerator()

    # year, month, day
    start_date = "2025/02/11"
    end_date = "2025/02/19"

    combined_text = gmail_handler.combine_unread_emails_text_in_period(start_date, end_date, unread_only=False, force_emails=force_emails)
    print("Combined Email Text:\n", combined_text)

    if include_website_news:
        print("Scraping latest news from website...")
        p = multiprocessing.Process(target=run_news_crawler)
        p.start()
        p.join()
        p.close()

        # Load the scraped news
        website_news = run_news_crawler()
        if website_news:
            print(f"Found {len(website_news)} news items from website")

            # Convert website_news list to a string representation
            website_news_text = json.dumps(website_news, indent=2)
            combined_text += "\n\n### WEBSITE NEWS ###\n" + website_news_text

            print("Added website news to the combined text")
        else:
            print("No news found from website")

    response = gemini_handler.retrieve_news_gemini(combined_text)
    print("Response:\n", response)

    news_list = extract_top_N(response)
    print("Top News Items:\n", news_list)

    total_text = ""

    for news in news_list:
        source = news.get("source", "")
        # Handle both formats: from Gemini and from NewsSpider
        description = news.get("brief description", news.get("description", ""))
        link = news.get("linkToAricle", news.get("link", ""))
        #relevancy = news.get("relevancy", 0)
        location = news.get("location", "")
        images_videos_links = news.get("imageVideosLinks", "")
        contact = news.get("contact", "")
        category = news.get("category", "")
        requirements = news.get("requirements", "")
        # Add title if available (from NewsSpider)
        title = news.get("title", "")

        # Include title if available
        title_text = f"Title: {title}\n" if title else ""
        news_text = f"{title_text}Source: {source}\n Description: {description}\n Link: {link}\n Location: {location}\n Contact: {contact}\n Category: {category}\nRequirements: {requirements}\n Images and Videos Links: {images_videos_links}\n"

        if link and len(link) > 5 and link != "Unknown":
            print("link:", link)
            #input("Press Enter to continue...")

            p = multiprocessing.Process(target=run_crawler, args=(link,))
            p.start()
            print("Crawler Started.")
            p.join()
            p.close()

            print("Crawler finished.")

            with open("files/page.txt", "r") as f:
                page_content = f.read()
                print("Page Content:\n", page_content)
                news_text += f"Article Content:\n{page_content}\n"

        total_text += f"Article {news_list.index(news)}:\n" + news_text + "\n"

    print(total_text)

    #OLD PROMPT ⬇
    prompt = f"""
    You are an expert in crafting HTML email templates. Based on the following news articles, please generate a responsive, clean, and professional HTML email template. Each news article should be displayed in its own section and include the following information:

- **Article Title**
- **Source**
- **Article Description** (A more detailed description of the news)
- **Article Summary** (A quick bite-sized summary of the news, only visible when hovering over the article description)
- **Category** (1 category, e.g. Robotics, Artificial Intelligence, etc.)
- **Link** (displayed as a clickable hyperlink)
- **Location**
- **Contact**

Additional requirements:
- Utilize some images (if provided via link) to make the email visually appealing, be sure that the path is absolute.
- The email should have a header with the title "Daily News Update" and a footer with a note like "Powered by Ie Robotics Lab".
- Use inline CSS styling to ensure compatibility across major email clients.
- The layout should be clean, mobile-friendly, and easy to read.
- Do not include any additional commentary or explanations—output only the complete HTML code.
- Make it look professional and visually appealing.

Here are the news articles data:
{total_text}
    """
    #OLD PROMPT ⬆

    prompt = "Given the following information about the news do as instructed for each of them.\n" + total_text
    response = gemini_handler.divide_news_gemini(prompt)
    print("Response:\n", response)

    """
    pattern = r'^```(?:[a-zA-Z]+)?\s*\n([\s\S]*?)\n```$'
    match = re.match(pattern, response)
    if match:
        response = match.group(1)

    # Split into lines and remove the first line if it starts with an HTML tag (e.g., <!DOCTYPE or <html)
    lines = response.splitlines()
    if lines and re.match(r'^\s*(<!doctype|<html)', lines[0], re.IGNORECASE):
        lines = lines[1:]
    response = "\n".join(lines)

    with open("output.html", "w") as f:
        f.write(response)
        f.close()"""

    # parse the JSON string into a dictionary
    response_dict = json.loads(response)
    processed_news = convert_news(response_dict)


    if force_emails and from_user:
        # use different class for repost emails
        rm = RepostEmailGenerator(shared_by=from_user)
        email_html = rm.generate_email(processed_news)
    else:
        # weekly class
        email_html = email_creator.generate_email(processed_news)

    with open("files/output.html", "w", encoding="utf-8") as f:
        f.write(email_html)

    if send_mail:
        gmail_handler.send_email_from_html_file("matteo.giorgetti.05@gmail.com", "Daily News Update", "files/output.html")


if __name__ == '__main__':
    gmail_handler = GmailManager()
    email_creator = NewsEmailGenerator()
    gemini_handler = GeminiHandler()


    #gmail_handler.send_email_from_html_file("matteo.giorgetti.05@gmail.com", "Daily News Update", "output.html")


    create_email_procedurally(gmail_handler, gemini_handler, email_creator)
