import logging
import shutil
import requests
from bs4 import BeautifulSoup

import os
import re
import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from modules.utils.sanitization import sanitize_string
from selenium import webdriver
from selenium.webdriver.firefox.options import Options


"""MOVE THIS"""
class Scraper:
    def __init__(self):
        self.options = Options()
        self.options.add_argument("--headless")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.driver = None

    def init_driver(self, url="https://example.com"):
        if self.driver is None:
            self.driver = webdriver.Firefox(options=self.options)
        self.driver.get(url)
        return self.driver

    def scrape_website(self, url: str, download_images=True, folder_extra_name: str = "") -> str:
        driver = self.init_driver(url)
        html = driver.page_source
        driver.quit()

        soup = BeautifulSoup(html, "html.parser")

        if download_images:
            self._download_images_from_soup(soup, base_url=url, folder_extra_name=folder_extra_name)

        return soup.prettify()

    def _download_images_from_soup(self, soup: BeautifulSoup, base_url: str, folder_extra_name: str = ""):
        folder_name = "images/" + folder_extra_name + "/" + sanitize_string(base_url)
        os.makedirs(folder_name, exist_ok=True)

        img_tags = soup.find_all("img")
        logging.info("Found %d images.", len(img_tags))

        for idx, img in enumerate(img_tags):
            src = img.get("src")
            if not src:
                continue

            img_url = urljoin(base_url, src)
            try:
                response = requests.get(img_url, stream=True, timeout=10)
                response.raise_for_status()

                # Choose filename from URL or fallback
                filename = os.path.basename(urlparse(img_url).path)
                if not filename or '.' not in filename:
                    filename = f"image_{idx}.jpg"

                save_path = os.path.join(folder_name, filename)
                with open(save_path, "wb") as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)

                logging.info("Downloaded: %s → %s", img_url, save_path)
            except Exception as e:
                logging.warning("Failed to download %s: %s", img_url, str(e))


"""REPOST"""
def analyze_repost(parsed_mail, intensive_mode=False, include_link_info=False, include_images=False, gemini_handler=None):
    folder_extra_name = "repost"
    
    shutil.rmtree("images/" + folder_extra_name, ignore_errors=True)
    os.makedirs("images/" + folder_extra_name)
    
    link_articles = {}
    for link in parsed_mail["links"]:
        scraper = Scraper()
        html = scraper.scrape_website(link, download_images=include_images, folder_extra_name=folder_extra_name)
        if html is not None:
            link_articles[link] = html
        else:
            logging.warning("Failed to scrape website: %s", link)

    # concatenate parsed mail Title, content and links to a single string with good formatting
    mail_content = parsed_mail["title"] + "\n\n" + parsed_mail["content"] + "\n\n" + "\n\n".join(link_articles.values())

    articles = gemini_handler.generate_repost(mail_content)

    # TODO: add a step that checks for each article what images would be good  
    return articles


"""NEWSLETTER"""
def analyze_emails_newsletter(emails, intensive_mode=False, include_link_info=False, include_website_news=False, include_images=False, gemini_handler=None):
    folder_extra_name = "newsletter"
    
    # clear images folder
    shutil.rmtree("images/" + folder_extra_name, ignore_errors=True)
    os.makedirs("images/" + folder_extra_name)

    combined_content = ""  # formatted such that each mail is clearly separated by ID or subject

    for idx, email in enumerate(emails):
        email_header = f"\n{'='*40}\nEMAIL {idx+1}"
        if "id" in email:
            email_header += f" (ID: {email['id']})"
        if "subject" in email:
            email_header += f" - Subject: {email['subject']}"
        email_header += f"\n{'='*40}\n"
        combined_content += email_header
        if "content" in email:
            combined_content += f"Content:\n{email['content']}\n"
        if "body" in email and not email.get("content"):
            combined_content += f"Body:\n{email['body']}\n"
        if "text" in email and not (email.get("content") or email.get("body")):
            combined_content += f"Text:\n{email['text']}\n"

        # Process links
        links = email.get("links", [])
        for lidx, link in enumerate(links):
            scraper = Scraper()
            html = scraper.scrape_website(link, download_images=include_images, folder_extra_name=folder_extra_name)
            link_header = f"\n--- Link {lidx+1}: {link} ---\n"
            if html is not None:
                combined_content += link_header + html + "\n"
            else:
                combined_content += link_header + "[Failed to scrape this link]\n"

    return combined_content

if __name__ == "__main__":
    scraper = Scraper()
    html = scraper.scrape_website("https://ras.papercept.net/conferences/support/support.php", download_images=True)
    print(html)