import time
import shutil
import os
import re
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
from lxml.html.clean import Cleaner

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


class Combiner:
    # Default values
    SOURCE_FOLDER = "accelerationrobotics.com"  # (not used if overridden)
    OUTPUT_FILE = "tutorial/output.txt"
    FILTER_PATTERNS_ENABLED = True
    REMOVE_DUPLICATES_ENABLED = True
    MERGE_LINES_ENABLED = True
    ADD_PHP = False

    @staticmethod
    def remove_consecutive_duplicates(text):
        """Remove consecutive duplicate lines."""
        lines = text.splitlines()
        deduped = []
        for line in lines:
            if not deduped or deduped[-1] != line:
                deduped.append(line)
        return "\n".join(deduped)

    @staticmethod
    def filter_repetitive_patterns(text, patterns=None):
        """Filter out lines that contain known repetitive patterns."""
        if patterns is None:
            patterns = [
                'ROBOTCORE®', 'RPU', 'ROS 2', 'RTPS', 'UDP/IP',
                'Perception', 'Transform', 'Framework', 'Cloud',
                'ROBOTPERF®', 'Services'
            ]
        lines = text.splitlines()
        filtered = [line for line in lines if not any(pat in line for pat in patterns)]
        return "\n".join(filtered)

    @staticmethod
    def merge_incomplete_lines(text):
        """Merge lines that appear to be split in the middle of a sentence."""
        lines = text.splitlines()
        merged_lines = []
        buffer = ""
        for line in lines:
            if buffer and re.search(r'[.!?]$', buffer):
                merged_lines.append(buffer)
                buffer = line
            else:
                if buffer:
                    buffer += " " + line
                else:
                    buffer = line
        if buffer:
            merged_lines.append(buffer)
        return "\n".join(merged_lines)

    @staticmethod
    def clean_text(text, filter_patterns_enabled=True, remove_duplicates_enabled=True, merge_lines_enabled=True):
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)

        if filter_patterns_enabled:
            cleaned = Combiner.filter_repetitive_patterns(cleaned)
        if remove_duplicates_enabled:
            cleaned = Combiner.remove_consecutive_duplicates(cleaned)
        if merge_lines_enabled:
            cleaned = Combiner.merge_incomplete_lines(cleaned)
        return cleaned

    @staticmethod
    def strip_php(content):
        """Remove PHP code blocks."""
        return re.sub(r'<\?php.*?\?>', '', content, flags=re.DOTALL)

    @classmethod
    def extract_text_from_html_file(cls, filepath, add_php=False, filter_patterns_enabled=True,
                                    remove_duplicates_enabled=True, merge_lines_enabled=True):
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read()
        except Exception as e:
            print(f"Could not read {filepath}: {e}")
            return ""

        if not add_php:
            content = cls.strip_php(content)

        cleaner = Cleaner(style=True, scripts=True, comments=True, javascript=True,
                          page_structure=False, safe_attrs_only=False)
        cleaned_content = cleaner.clean_html(content)

        soup = BeautifulSoup(cleaned_content, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)

        links = []
        for a in soup.find_all('a', href=True):
            href = a.get('href')
            anchor_text = a.get_text(strip=True)
            if anchor_text and anchor_text != href:
                links.append(f"{anchor_text} -> {href}")
            else:
                links.append(href)
        if links:
            links_text = "\n\nLinks:\n" + "\n".join(links)
            text += links_text

        return cls.clean_text(text, filter_patterns_enabled, remove_duplicates_enabled, merge_lines_enabled)

    @classmethod
    def extract_text_from_pdf_file(cls, filepath, filter_patterns_enabled=True,
                                   remove_duplicates_enabled=True, merge_lines_enabled=True):
        try:
            reader = PdfReader(filepath)
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            combined = "\n".join(text_parts)
            return cls.clean_text(combined, filter_patterns_enabled, remove_duplicates_enabled, merge_lines_enabled)
        except Exception as e:
            print(f"Could not extract text from {filepath}: {e}")
            return ""

    @classmethod
    def combine_text_from_folder(cls, source_folder=None, output_file=None, filter_patterns_enabled=None,
                                 remove_duplicates_enabled=None, merge_lines_enabled=None, add_php=None):

        source_folder = source_folder or cls.SOURCE_FOLDER
        output_file = output_file or cls.OUTPUT_FILE
        filter_patterns_enabled = filter_patterns_enabled if filter_patterns_enabled is not None else cls.FILTER_PATTERNS_ENABLED
        remove_duplicates_enabled = remove_duplicates_enabled if remove_duplicates_enabled is not None else cls.REMOVE_DUPLICATES_ENABLED
        merge_lines_enabled = merge_lines_enabled if merge_lines_enabled is not None else cls.MERGE_LINES_ENABLED
        add_php = add_php if add_php is not None else cls.ADD_PHP

        combined_text = []
        for root, _, files in os.walk(source_folder):
            for filename in files:
                ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
                filepath = os.path.join(root, filename)
                print(f"Processing: {filepath}")
                text = ""
                if ext in ['html', 'htm', 'php']:
                    text = cls.extract_text_from_html_file(
                        filepath,
                        add_php=add_php,
                        filter_patterns_enabled=filter_patterns_enabled,
                        remove_duplicates_enabled=remove_duplicates_enabled,
                        merge_lines_enabled=merge_lines_enabled
                    )
                elif ext == 'pdf':
                    text = cls.extract_text_from_pdf_file(
                        filepath,
                        filter_patterns_enabled=filter_patterns_enabled,
                        remove_duplicates_enabled=remove_duplicates_enabled,
                        merge_lines_enabled=merge_lines_enabled
                    )
                else:
                    print(f"Skipping unsupported file type: {filepath}")
                    continue

                if text:
                    header = f"\n--- Text from {filepath} ---\n"
                    combined_text.append(header + text + "\n")

        try:
            with open(output_file, 'w', encoding='utf-8') as out:
                out.write("\n".join(combined_text))
            print(f"\nCombined text saved to: {output_file}")
        except Exception as e:
            print(f"Failed to write output file {output_file}: {e}")


class CustomFolderSpider(CrawlSpider):
    name = 'custom_folder'
    allowed_domains = ['accelerationrobotics.com']
    start_urls = ['https://accelerationrobotics.com/']
    # Deny any links containing "forum" (using a case-insensitive regex)
    rules = (
        Rule(LinkExtractor(deny=(r'(?i)forum',)), callback='parse_item', follow=True),
    )

    def parse_item(self, response):
        # Save the scraped page to the temporary_files folder.
        folder = 'temporary_files'
        if not os.path.exists(folder):
            os.makedirs(folder)
        # Create a safe filename from the URL.
        filename = re.sub(r'\W+', '_', response.url) + ".html"
        filepath = os.path.join(folder, filename)
        with open(filepath, 'wb') as f:
            f.write(response.body)
        self.logger.info("Saved file %s", filepath)
        # The CrawlSpider's rules handle further link extraction and following.


class Scraper:
    def __init__(self, start_urls=None, allowed_domains=None, force_update=False):
        self.custom_start_urls = start_urls  # e.g., ['https://accelerationrobotics.com/']
        self.custom_allowed_domains = allowed_domains  # e.g., ['accelerationrobotics.com']
        self.website_name = allowed_domains[0].replace('.com', '')
        self.force_update = force_update
        self.settings = get_project_settings()
        self.Combiner = Combiner()

    def scrape_website(self):
        """
        Scrape the website, combine the text from saved files, and return the output.
        """
        output_file = f"{self.website_name}_total.txt"
        if os.path.exists(output_file) and not self.force_update:
            print(f"Output file '{output_file}' already exists. Skipping scraping, loading old file.")
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
            return content

        # Safely remove and recreate the temporary_files directory.
        if os.path.exists('temporary_files'):
            shutil.rmtree('temporary_files')
        os.makedirs('temporary_files', exist_ok=True)

        self.run_spider()
        source_folder = self.move_folders()

        self.Combiner.combine_text_from_folder(source_folder=source_folder, output_file=output_file,
                                                 filter_patterns_enabled=None,
                                                 remove_duplicates_enabled=None,
                                                 merge_lines_enabled=None,
                                                 add_php=None)

        time.sleep(1)

        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()

        return content

    def run_spider(self):
        process = CrawlerProcess(self.settings)
        process.crawl(CustomFolderSpider,
                      start_urls=self.custom_start_urls,
                      allowed_domains=self.custom_allowed_domains)
        process.start()  # Blocks until the spider finishes

    def move_folders(self):
        """
        Move all files from the 'temporary_files' directory to a folder named after the website.
        """
        destination_folder = "scraped/" + self.website_name
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)
        source_dir = 'temporary_files'
        if not os.path.exists(source_dir):
            print(f"Source directory '{source_dir}' does not exist")
            return source_dir

        try:
            for item in os.listdir(source_dir):
                source_path = os.path.join(source_dir, item)
                destination_path = os.path.join(destination_folder, item)
                if os.path.exists(source_path):
                    shutil.move(source_path, destination_path)
                    print(f"Moved {item} to {destination_folder}")

            if os.path.exists(source_dir) and not os.listdir(source_dir):
                os.rmdir(source_dir)
                print(f"Removed empty directory: {source_dir}")

            return destination_folder

        except Exception as e:
            print(f"An error occurred while moving folders: {str(e)}")
            return None


if __name__ == "__main__":
    # Initialize the scraper with the desired start URL and allowed domain.
    scraper = Scraper(['https://accelerationrobotics.com/'], ['accelerationrobotics.com'])
    output = scraper.scrape_website()
    print(output)
