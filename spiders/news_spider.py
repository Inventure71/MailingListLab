import scrapy
import json
import os

class NewsSpider(scrapy.Spider):
    name = "news_spider"

    def __init__(self, url=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load configuration from file if it exists
        config_path = os.path.join('files', 'news_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                self.start_urls = [config.get('news_url', url)]
                self.article_selector = config.get('article_selector', 'article')
                self.title_selector = config.get('title_selector', 'h2')
                self.link_selector = config.get('link_selector', 'a')
                self.description_selector = config.get('description_selector', 'p')
        else:
            # Default configuration
            if not url:
                raise ValueError("A URL must be provided. Use -a url=<URL> when running the spider.")
            self.start_urls = [url]
            self.article_selector = 'article'
            self.title_selector = 'h2'
            self.link_selector = 'a'
            self.description_selector = 'p'

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        news_items = []

        # Try multiple approaches to find news articles

        # Approach 1: Use the configured selectors
        articles = response.css(self.article_selector)

        if articles:
            for article in articles:
                # Extract title
                title_texts = article.css(f'{self.title_selector} ::text').getall()
                title = ' '.join([t.strip() for t in title_texts if t.strip()])

                # Extract link
                link = article.css(f'{self.link_selector}::attr(href)').get()
                if link:
                    link = response.urljoin(link)

                # Extract description
                desc_texts = article.css(f'{self.description_selector} ::text').getall()
                description = ' '.join([t.strip() for t in desc_texts if t.strip()])

                # Create news item
                if title or description:
                    news_item = {
                        'title': title if title else '',
                        'description': description if description else '',
                        'link': link if link else '',
                        'source': response.url,
                        'category': 'News',
                        'location': '',
                        'contact': '',
                        'requirements': '',
                        'imageVideosLinks': ''
                    }
                    news_items.append(news_item)

        # Approach 2: Try common patterns for news articles if no articles found
        if not news_items:
            # Try to find any heading elements that might be article titles
            headings = response.css('h1, h2, h3, h4, h5')

            for heading in headings:
                # Extract title
                title = ' '.join([t.strip() for t in heading.css('::text').getall() if t.strip()])

                # Extract link - look for a link in the heading or its parent
                link = heading.css('a::attr(href)').get() or heading.xpath('..//a/@href').get()
                if link:
                    link = response.urljoin(link)

                # Extract description - look for paragraphs after the heading
                desc_texts = heading.xpath('./following::p[1]//text()').getall()
                description = ' '.join([t.strip() for t in desc_texts if t.strip()])

                # Create news item
                if title and (link or description):
                    news_item = {
                        'title': title,
                        'description': description if description else '',
                        'link': link if link else '',
                        'source': response.url,
                        'category': 'News',
                        'location': '',
                        'contact': '',
                        'requirements': '',
                        'imageVideosLinks': ''
                    }
                    news_items.append(news_item)

        # Approach 3: As a last resort, look for any links with text
        if not news_items:
            links = response.css('a')

            for link_elem in links:
                # Extract title (link text)
                title = ' '.join([t.strip() for t in link_elem.css('::text').getall() if t.strip()])

                # Extract link
                link = link_elem.css('::attr(href)').get()
                if link:
                    link = response.urljoin(link)

                # Create news item
                if title and link and len(title) > 10:  # Only consider links with substantial text
                    news_item = {
                        'title': title,
                        'description': '',
                        'link': link,
                        'source': response.url,
                        'category': 'News',
                        'location': '',
                        'contact': '',
                        'requirements': '',
                        'imageVideosLinks': ''
                    }
                    news_items.append(news_item)

        # Save news items to file
        with open('files/latest_news.json', 'w') as f:
            json.dump(news_items, f, indent=2)

        return news_items
