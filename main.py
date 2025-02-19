import json
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import multiprocessing

from googleapiclient.errors import HttpError
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from gmail_handler import GmailManager
from spiders.page_content import PageContentSpider
from use_gemini import GeminiHandler

def run_crawler(link):
    process = CrawlerProcess(get_project_settings())
    process.crawl(PageContentSpider, url=link)
    process.start()

def extract_top_N(response, N=5):
    # Parse the JSON string into a Python dictionary
    response_data = json.loads(response)

    news_items = response_data.get("news", [])

    news_list = []
    for news in news_items:
        relevancy = news.get("relevancy", 0)
        added = False

        for x in news_list:
            if x.get("relevancy", 0) < relevancy:
                news_list.insert(news_list.index(x), news)
                added = True
                break

        if len(news_list) == 0 or not added:
            news_list.append(news)

    return news_list[:N]

def main():
    gmail_handler = GmailManager()
    gemini_handler = GeminiHandler()

    # year, month, day
    start_date = "2025/02/11"
    end_date = "2025/02/19"

    combined_text = gmail_handler.combine_unread_emails_text_in_period(start_date, end_date)
    print("Combined Email Text:\n", combined_text)

    response = gemini_handler.retrieve_news_gemini(combined_text)
    print("Response:\n", response)

    news_list = extract_top_N(response)
    print("Top News Items:\n", news_list)

    total_text = ""

    for news in news_list:
        source = news.get("source", "")
        description = news.get("brief description", "")
        link = news.get("linkToAricle", "")
        relevancy = news.get("relevancy", 0)
        location = news.get("location", "")
        images_videos_links = news.get("imageVideosLinks", "")
        contact = news.get("contact", "")
        requirements = news.get("requirements", "")

        news_text = f"Source: {source}\n Description: {description}\n Link: {link}\n Relevancy: {relevancy}\n Location: {location}\n Contact: {contact}\n Requirements: {requirements}\n"

        if link and len(link) > 5 and link != "Unknown":
            print("link:", link)
            #input("Press Enter to continue...")

            p = multiprocessing.Process(target=run_crawler, args=(link,))
            p.start()
            p.join()
            p.close()

            with open("page.txt", "r") as f:
                page_content = f.read()
                print("Page Content:\n", page_content)
                news_text += f"Article Content:\n{page_content}\n"

        total_text += f"Article {news_list.index(news)}:\n" + news_text + "\n"

    print(total_text)

    prompt = f"""
    You are an expert in crafting HTML email templates. Based on the following news articles, please generate a responsive, clean, and professional HTML email template. Each news article should be displayed in its own section and include the following information:

- **Article Title**
- **Source**
- **Description**
- **Link** (displayed as a clickable hyperlink)
- **Location**
- **Contact**
- **Article Summary** 

Additional requirements:
- Utilize some images (if provided via link) to make the email visually appealing.
- The email should have a header with the title "Daily News Update" and a footer with a note like "Powered by Ie Robotics Lab".
- Use inline CSS styling to ensure compatibility across major email clients.
- The layout should be clean, mobile-friendly, and easy to read.
- Do not include any additional commentary or explanations—output only the complete HTML code.

Here are the news articles data:
{total_text}
    """

    response = gemini_handler.generic_ask_gemini(prompt)[0]
    print("Response:\n", response)

    with open("output.html", "w") as f:
        f.write(response)
        f.close()



if __name__ == '__main__':
    main()
