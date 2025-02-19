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
        contact = news.get("contact", "")
        requirements = news.get("requirements", "")

        news_text = f"Source: {source}\n Description: {description}\n Link: {link}\n Relevancy: {relevancy}\n Location: {location}\n Contact: {contact}\n Requirements: {requirements}\n"

        if link or len(link) > 5:
            print("link:", link)
            input("Press Enter to continue...")

            p = multiprocessing.Process(target=run_crawler, args=(link,))
            p.start()
            p.join()

            with open("page.txt", "r") as f:
                page_content = f.read()
                print("Page Content:\n", page_content)
                news_text += f"Article Content:\n{page_content}\n"

        total_text += f"Article {news_list.index(news)}:\n" + news_text + "\n"

    print(total_text)

if __name__ == '__main__':
    main()
