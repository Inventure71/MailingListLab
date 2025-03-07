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
        # extract text nodes excluding script and style elements.
        texts = response.xpath('//body//text()[not(ancestor::script) and not(ancestor::style)]').getall()
        # clean and join the text parts, filtering out empty strings.
        cleaned_text = " ".join(t.strip() for t in texts if t.strip())

        # extract links from anchor tags and image sources.
        # this XPath selects href from <a> and src from <img>.
        links = response.xpath('//a/@href | //img/@src').getall()
        # convert relative URLs to absolute URLs.
        links = [response.urljoin(link) for link in links]

        # save for debugging purposes
        with open("files/page.txt", "w", encoding="utf-8") as f:
            f.write(cleaned_text)

        yield {
            'url': response.url,
            'content': cleaned_text,
            'links': links,
        }
