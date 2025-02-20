import json
from typing import List, Dict


class NewsEmailGenerator:
    def __init__(self, title: str = "Daily News Update", footer_text: str = "Powered by Ie Robotics Lab"):
        self.title = title
        self.footer_text = footer_text

    def generate_header(self) -> str:
        return f'''
        <tr>
            <td style="background-color: #003366; color: #ffffff; text-align: center; padding: 15px; 
                       font-size: 24px; font-weight: bold; margin-top: 0;">
                {self.title}
            </td>
        </tr>'''

    def generate_article(self, article: Dict) -> str:
        return f'''
        <tr>
            <td style="padding: 8px 20px;">
                <div style="background-color: #fafafa; border: 1px solid #dddddd; border-radius: 8px; 
                           margin-bottom: 8px; padding: 12px;">
                    {'<img src="' + article["image"] + '" alt="Article Image" style="width: 100%; display: block; margin-bottom: 12px; border-radius: 8px;">' if "image" in article else ""}
                    <div style="font-size: 20px; color: #333333; font-weight: bold; margin-bottom: 8px;">
                        {article["title"]}
                    </div>
                    <div style="font-size: 14px; color: #777777; margin-bottom: 8px; line-height: 1.4;">
                        <div>Source: {article["source"]}</div>
                        <div>Location: {article["location"]}</div>
                        <div>Contact: {article["contact"]}</div>
                    </div>
                    <div style="display: block; font-size: 16px; color: #555555; line-height: 1.5; 
                              position: relative; min-height: 50px;" class="article-desc">
                        <div style="position: relative;">
                            {article["description"]}
                        </div>
                        <div style="display: none; position: absolute; background-color: rgba(249, 249, 249, 0.95); 
                                  color: #333333; border: 1px solid #cccccc; padding: 5px; 
                                  width: 100%; height: 100%; font-size: 14px; z-index: 20; 
                                  border-radius: 5px; top: 0; left: 0; box-sizing: border-box;" 
                             class="summary">
                            Article Summary: {article["summary"]}
                        </div>
                    </div>
                    <div style="margin-top: 8px;">
                        <a href="{article["link"]}" style="font-size: 16px; color: #1a73e8; 
                           text-decoration: none;">Read more</a>
                    </div>
                </div>
            </td>
        </tr>'''

    def generate_footer(self) -> str:
        return f'''
        <tr>
            <td style="text-align: center; background-color: #f4f4f4; color: #777777; 
                       padding: 12px; font-size: 12px;">
                {self.footer_text}
            </td>
        </tr>'''

    def generate_email(self, articles: List[Dict]) -> str:
        articles_html = "\n".join(self.generate_article(article) for article in articles)

        return f'''<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>{self.title}</title>
        <style type="text/css">
            .article-desc {{
                position: relative !important;
                display: block !important;
            }}
            .article-desc .summary {{
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.2s;
            }}
            .article-desc:hover .summary {{
                display: block !important;
                opacity: 1 !important;
                visibility: visible !important;
            }}
            body {{
                margin: 0;
                padding: 0;
            }}
            table {{
                margin: 0;
                padding: 0;
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f4f4f4; font-family: Arial, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; margin: 0;">
            <tr>
                <td align="center" style="padding: 0;">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; margin: 0;">
                        {self.generate_header()}
                        {articles_html}
                        {self.generate_footer()}
                    </table>
                </td>
            </tr>
        </table>
    </body>
</html>'''


# Example usage:
if __name__ == "__main__":
    # Sample news articles in JSON format
    sample_news = [
        {
            "title": "Breaking News Story",
            "source": "Global News Network",
            "location": "New York, USA",
            "contact": "news@gnn.com",
            "description": "Major breakthrough in renewable energy technology.",
            "summary": "Scientists develop new solar panel with 40% increased efficiency.",
            "link": "https://www.gnn.com/story",
            "image": "https://via.placeholder.com/560x200"
        },
        {
            "title": "Technology Update",
            "source": "Tech Daily",
            "location": "San Francisco, USA",
            "contact": "editor@techdaily.com",
            "description": "Latest developments in artificial intelligence.",
            "summary": "New AI model shows human-like reasoning capabilities.",
            "link": "https://www.techdaily.com/ai-update"
        }
    ]

    # Generate the email
    generator = NewsEmailGenerator()
    email_html = generator.generate_email(sample_news)

    # Save to file
    with open("output.html", "w", encoding="utf-8") as f:
        f.write(email_html)