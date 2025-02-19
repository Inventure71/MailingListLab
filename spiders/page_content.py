import scrapy

class PageContentSpider(scrapy.Spider):
    name = "page_content"

    def __init__(self, url=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not url:
            raise ValueError("A URL must be provided. Use -a url=<URL> when running the spider.")
        self.start_urls = [url]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        # Instead of saving to a file, yield the page content.
        content = response.text  # or response.body if you need bytes
        #self.log(f"Fetched content from {response.url}")

        with open("page.txt", "w") as f:
            f.write(content)

        yield {
            'url': response.url,
            'content': content,
        }
