import re
import scrapy
from pathlib import Path
from urllib.parse import urlparse
import mimetypes

class CustomFolderSpider(scrapy.Spider):
    name = "website"

    def __init__(self, start_urls=None, allowed_domains=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Accept comma-separated strings or lists
        if isinstance(start_urls, str):
            self.start_urls = [url.strip() for url in start_urls.split(',') if url.strip()]
        else:
            self.start_urls = start_urls or []
        if isinstance(allowed_domains, str):
            self.allowed_domains = [domain.strip() for domain in allowed_domains.split(',') if domain.strip()]
        else:
            self.allowed_domains = allowed_domains or []

    def parse(self, response):
        # Determine and sanitize the folder name based on the domain
        domain = self.get_domain(response.url)
        folder_name = "temporary_files/" + self.sanitize_filename(domain)
        folder_path = Path(folder_name)
        folder_path.mkdir(parents=True, exist_ok=True)

        # Determine a safe filename based on the URL path and response Content-Type
        path = urlparse(response.url).path.strip('/')
        content_type = response.headers.get('Content-Type', b'').decode('utf-8').lower()
        mime_type = content_type.split(';')[0] if content_type else ''

        # Attempt to guess the file extension if it's not HTML
        ext = None
        if mime_type and mime_type != 'text/html':
            ext = mimetypes.guess_extension(mime_type)
            if ext is None:
                # Fallback: use the subtype as the extension
                ext = '.' + mime_type.split('/')[-1]

        if not path or response.url.endswith('/'):
            # For root pages, name the file 'index' with an appropriate extension
            if mime_type == 'text/html':
                filename = "index.html"
            else:
                filename = "index" + (ext if ext else '')
        else:
            # Replace directory separators with underscores and sanitize the result
            filename = self.sanitize_filename(path.replace('/', '_'))
            if '.' not in filename:
                if mime_type == 'text/html':
                    filename += ".html"
                elif ext:
                    filename += ext

        file_path = folder_path / filename
        self.logger.info("Saving %s to %s", response.url, file_path)

        try:
            file_path.write_bytes(response.body)
        except Exception as e:
            self.logger.error("Failed to save %s: %s", response.url, e)

        # Only follow links if the content is HTML
        if 'text/html' in mime_type:
            for href in response.css('a::attr(href)').getall():
                next_page = response.urljoin(href)
                if self.is_allowed_url(next_page):
                    yield response.follow(next_page, callback=self.parse)

    def is_allowed_url(self, url):
        """
        Allow URLs only if they belong to one of the allowed domains.
        Subdomains of an allowed domain are also accepted.
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not self.allowed_domains:
            return True

        for allowed in self.allowed_domains:
            allowed = allowed.lower()
            if domain == allowed or domain.endswith('.' + allowed):
                return True
        return False

    def get_domain(self, url):
        """
        Extract the domain from the URL.
        """
        return urlparse(url).netloc

    def sanitize_filename(self, value):
        """
        Sanitize a string to be safely used as a filename.
        Removes or replaces characters that may be invalid on some filesystems.
        """
        # Remove query parameters if present
        value = value.split('?')[0]
        # Replace any character that is not alphanumeric, dot, underscore, or dash with an underscore
        return re.sub(r'[^\w\.-]', '_', value)
