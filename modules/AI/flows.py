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
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import json


"""MOVE THIS"""
class Scraper:
    def __init__(self):
        self.options = Options()
        self.options.add_argument("--headless=new")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--disable-web-security")
        self.options.add_argument("--allow-running-insecure-content")
        self.options.add_argument("--disable-extensions")
        self.options.add_argument("--disable-background-timer-throttling")
        self.options.add_argument("--disable-backgrounding-occluded-windows")
        self.options.add_argument("--disable-renderer-backgrounding")
        self.options.add_argument("--remote-debugging-port=9222")
        self.options.add_argument("--window-size=1920,1080")
        self.driver = None

    def init_driver(self, url="https://example.com"):
        if self.driver is None:
            try:
                # Try to use Chrome/Chromium
                self.driver = webdriver.Chrome(options=self.options)
            except Exception as chrome_error:
                logging.warning(f"Chrome WebDriver failed: {chrome_error}")
                # Fallback to Firefox if Chrome fails
                try:
                    from selenium.webdriver.firefox.options import Options as FirefoxOptions
                    firefox_options = FirefoxOptions()
                    firefox_options.add_argument("--headless")
                    firefox_options.add_argument("--no-sandbox")
                    firefox_options.add_argument("--disable-dev-shm-usage")
                    
                    # Try to specify the actual Firefox binary location for snap installation
                    firefox_options.binary_location = "/snap/firefox/current/usr/lib/firefox/firefox"
                    
                    self.driver = webdriver.Firefox(options=firefox_options)
                except Exception as firefox_error:
                    logging.error(f"Both Chrome and Firefox WebDriver failed. Chrome: {chrome_error}, Firefox: {firefox_error}")
                    raise Exception("No working WebDriver found")
        
        self.driver.get(url)
        return self.driver

    def _filter_problematic_links(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Remove problematic links that could trigger system actions"""
        filtered_count = 0
        # Find all anchor tags
        for link in soup.find_all("a", href=True):
            href = link.get("href", "").lower()
            # Remove links that start with problematic protocols
            if href.startswith(('mailto:', 'tel:', 'sms:', 'callto:', 'skype:', 'javascript:')):
                # Convert to span to preserve text but remove link functionality
                span = soup.new_tag("span")
                span.string = link.get_text()
                link.replace_with(span)
                filtered_count += 1
                logging.debug(f"Filtered problematic link: {href}")
        
        if filtered_count > 0:
            logging.info(f"Filtered {filtered_count} problematic links from scraped content")
        
        return soup

    def scrape_website(self, url: str, download_images=True, folder_extra_name: str = "") -> str:
        driver = None
        try:
            driver = self.init_driver(url)
            html = driver.page_source
            
            soup = BeautifulSoup(html, "html.parser")

            # Remove scripts/styles, then filter links
            for tag in soup(["script", "style", "noscript", "iframe"]):
                tag.extract()
            soup = self._filter_problematic_links(soup)

            # Download images if desired (this doesn't affect the text extraction)
            if download_images:
                self._download_images_from_soup(soup, base_url=url, folder_extra_name=folder_extra_name)

            # Extract *only* visible text, normalize whitespace:
            text = soup.get_text(separator="\n", strip=True)
            # Collapse multiple blank lines:
            cleaned = re.sub(r'\n\s*\n+', '\n\n', text)
            return cleaned
            
        except Exception as e:
            logging.error(f"WebDriver failed for {url}: {e}")
            # Fallback to requests if WebDriver fails
            try:
                logging.info(f"Attempting fallback requests scraping for {url}")
                return self._scrape_with_requests(url, download_images, folder_extra_name)
            except Exception as fallback_error:
                logging.error(f"Fallback requests scraping also failed for {url}: {fallback_error}")
                return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logging.warning(f"Failed to quit driver: {e}")

    def _scrape_with_requests(self, url: str, download_images=True, folder_extra_name: str = "") -> str:
        """Fallback scraping method using requests instead of Selenium"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")

        # Remove scripts/styles, then filter links
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.extract()
        soup = self._filter_problematic_links(soup)

        # Download images if desired (this doesn't affect the text extraction)
        if download_images:
            self._download_images_from_soup(soup, base_url=url, folder_extra_name=folder_extra_name)

        # Extract *only* visible text, normalize whitespace:
        text = soup.get_text(separator="\n", strip=True)
        # Collapse multiple blank lines:
        cleaned = re.sub(r'\n\s*\n+', '\n\n', text)
        return cleaned

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

    # concatenate parsed mail Title, text and links to a single string with good formatting
    mail_content = parsed_mail["title"] + "\n\n" + parsed_mail["text"] + "\n\n" + "\n\n".join(link_articles.values())

    articles_response = gemini_handler.divide_news_gemini(mail_content)
    logging.info(f"Received articles response from Gemini: {articles_response}")
    
    # Parse final response
    try:
        articles_data = json.loads(articles_response)
        final_articles = articles_data.get("news", [])
        return final_articles
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse Gemini evaluation response: {e}")
        return []

"""NEWSLETTER"""
def analyze_emails_newsletter(emails, intensive_mode=False, include_link_info=False, include_website_news=False, include_images=False, gemini_handler=None):
    folder_extra_name = "newsletter"
    
    # clear images folder
    shutil.rmtree("images/" + folder_extra_name, ignore_errors=True)
    os.makedirs("images/" + folder_extra_name)

    # FIRST PASS: scrape all links WITHOUT images and build comprehensive content
    combined_content = ""
    article_data = {}  # Maps article IDs to complete article information
    article_id_counter = 0

    for email_idx, email in enumerate(emails):
        email_header = f"\n{'='*40}\nEMAIL {email_idx+1}"
        if "id" in email:
            email_header += f" (ID: {email['id']})"
        if "subject" in email:
            email_header += f" - Subject: {email['subject']}"
        email_header += f"\n{'='*40}\n"
        combined_content += email_header
        
        # Add email content
        email_content = ""
        if "content" in email:
            email_content = f"Content:\n{email['content']}\n"
        elif "body" in email:
            email_content = f"Body:\n{email['body']}\n"
        elif "text" in email:
            email_content = f"Text:\n{email['text']}\n"
        combined_content += email_content

        # Process links without images first
        links = email.get("links", [])
        for link_idx, link in enumerate(links):
            article_id = f"ARTICLE_{article_id_counter}"
            article_id_counter += 1
            
            scraper = Scraper()
            html = scraper.scrape_website(link, download_images=False, folder_extra_name=folder_extra_name)
            link_header = f"\n--- {article_id} - Link {link_idx+1}: {link} ---\n"
            
            # Store complete article information for later use
            article_data[article_id] = {
                'email_idx': email_idx,
                'link_idx': link_idx,
                'link': link,
                'email': email,
                'email_content': email_content,
                'email_header': f"\n{'='*40}\n{article_id} - EMAIL {email_idx+1}" + 
                               (f" (ID: {email['id']})" if "id" in email else "") +
                               (f" - Subject: {email['subject']}" if "subject" in email else "") +
                               f"\n{'='*40}\n",
                'scraped_html': html,
                'link_header': f"\n--- {article_id} - Link: {link} ---\n"
            }
            
            if html is not None:
                logging.info(f"Scraped content for {link} (first 500 chars): {html[:500]}")
                combined_content += link_header + html + "\n"
            else:
                logging.info(f"Failed to scrape content for {link}")
                combined_content += link_header + "[Failed to scrape this link]\n"

    # Send to Gemini for evaluation
    logging.info(f"Sending to Gemini for evaluation (first 500 chars): {combined_content[:500]}")
    evaluation_response = gemini_handler.evaluate_articles_gemini(combined_content)
    logging.info(f"Received evaluation response from Gemini: {evaluation_response}")
    
    # Parse JSON response
    try:
        evaluation_data = json.loads(evaluation_response)
        all_articles = evaluation_data.get("news", [])
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse Gemini evaluation response: {e}")
        return []

    # Sort by relevancy and get top 5
    all_articles = sorted(all_articles, key=lambda x: x.get("relevancy", 0), reverse=True)
    top_5_articles = all_articles[:5]
    logging.info(f"Top 5 articles selected: {[{'ID': a.get('ID', ''), 'relevancy': a.get('relevancy', 0)} for a in top_5_articles]}")

    # SECOND PASS: build content for top 5 articles using stored data and re-scrape only for images
    top_5_combined_content = ""
    
    for article in top_5_articles:
        article_id = article.get("ID", "")
        logging.info(f"Looking for article_id '{article_id}' in article_data")
        logging.info(f"Available keys in article_data: {list(article_data.keys())}")
        
        if article_id in article_data:
            logging.info(f"Found match for article_id '{article_id}'")
            stored_data = article_data[article_id]
            
            # Use stored email header and content
            top_5_combined_content += stored_data['email_header']
            top_5_combined_content += stored_data['email_content']

            # Add Gemini's evaluation info
            top_5_combined_content += f"Source: {article.get('source', '')}\n"
            top_5_combined_content += f"Brief Description: {article.get('brief description', '')}\n"
            top_5_combined_content += f"Reasoning: {article.get('reasoning', '')}\n"
            top_5_combined_content += f"Relevancy: {article.get('relevancy', 0)}\n"
            
            # Use stored scraped content, but re-scrape for images if needed
            if include_images:
                logging.info(f"Re-scraping {stored_data['link']} for images only")
                scraper = Scraper()
                # Re-scrape WITH images for this specific link
                html_with_images = scraper.scrape_website(stored_data['link'], download_images=True, folder_extra_name=folder_extra_name)
                if html_with_images is not None:
                    top_5_combined_content += stored_data['link_header'] + html_with_images + "\n"
                else:
                    # Fall back to stored HTML if re-scraping fails
                    logging.warning(f"Failed to re-scrape {stored_data['link']} for images, using stored content")
                    top_5_combined_content += stored_data['link_header'] + (stored_data['scraped_html'] or "[Failed to scrape this link]") + "\n"
            else:
                # Just use the stored HTML content
                top_5_combined_content += stored_data['link_header'] + (stored_data['scraped_html'] or "[Failed to scrape this link]") + "\n"
        else:
            logging.warning(f"No match found for article_id '{article_id}' in article_data")

    # Send comprehensive info about top 5 to divide_news_gemini
    logging.info(f"Sending to Gemini for news division (first 500 chars): {top_5_combined_content[:500]}")
    articles_response = gemini_handler.divide_news_gemini(top_5_combined_content)
    logging.info(f"Received articles response from Gemini: {articles_response}")
    
    # Parse final response
    try:
        articles_data = json.loads(articles_response)
        final_articles = articles_data.get("news", [])
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse Gemini articles response: {e}")
        return []

    return final_articles

if __name__ == "__main__":
    scraper = Scraper()
    html = scraper.scrape_website("https://ras.papercept.net/conferences/support/support.php", download_images=True)
    print(html)