import json
from collections import defaultdict
from typing import List, Dict

class NewsEmailGenerator:
    def __init__(self, title: str = "Weekly News", footer_text: str = "Powered by Ie Robotics & AI Lab", skip_images: bool = True):
        self.title = title
        self.footer_text = footer_text
        with open("configs/mail_configs.json", 'r') as file:
            config_data = json.load(file)
            self.category_colors = config_data["category_colors"]
        self.skip_images = skip_images

    def generate_header(self) -> str:
        """Generate the header of the email based on the title variable."""
        return f'''
        <tr>
            <td style="background-color: #003366; color: #ffffff; text-align: center; padding: 15px; 
                       font-size: 24px; font-weight: bold; margin-top: 0;">
                {self.title}
            </td>
        </tr>'''

    def generate_article(self, article: Dict) -> str:
        """Generate the HTML for a single news article."""
        category = article.get("category", "Other")

        border_color = self.category_colors.get(category, self.category_colors["Other"])

        return f'''
        <tr>
            <td style="padding: 8px 20px;">
                <div style="background-color: #fafafa; border: 2px solid {border_color}; border-radius: 8px; 
                           margin-bottom: 8px; padding: 12px;">
                    {'<img src="' + article["image"] + '" alt="Article Image" style="width: 100%; display: block; margin-bottom: 12px; border-radius: 8px;">' if "image" in article and not self.skip_images else ""}
                    <div style="font-size: 20px; color: #333333; font-weight: bold; margin-bottom: 8px;">
                        {article["title"]}
                    </div>
                    <div style="font-size: 14px; color: #777777; margin-bottom: 8px; line-height: 1.4;">
                        <div>Source: {article["source"]}</div>
                        <div>Location: {article["location"]}</div>
                        {'<div>Contact: ' + article["contact"] + '</div>' if "contact" in article else ""}
                        <div>Category: {category}</div>
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
                             Summary: {article["summary"]}
                        </div>
                    </div>
                    <div style="margin-top: 8px;">
                        <a href="{article["link"]}" style="font-size: 16px; color: {border_color}; 
                           text-decoration: none;">Read more</a>
                    </div>
                </div>
            </td>
        </tr>'''

    def generate_category_section(self, category: str, articles: List[Dict]) -> str:
        """Generate a section for a specific category with a colored header."""

        header_color = self.category_colors.get(category, self.category_colors["Other"])
        articles_html = "\n".join(self.generate_article(article) for article in articles)
        return f'''
        <tr>
            <td style="background-color: {header_color}; color: #ffffff; text-align: center; padding: 10px; font-size: 18px;">
                {category}
            </td>
        </tr>
        {articles_html}'''

    def generate_footer(self) -> str:
        """Generate the footer of the email based on the footer_text variable."""
        return f'''
        <tr>
            <td style="text-align: center; background-color: #f4f4f4; color: #777777; 
                       padding: 12px; font-size: 12px;">
                {self.footer_text}
                <br><br>
                <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #cccccc;">
                    <em>This email is automatically generated.</em>
                </div>
            </td>
        </tr>
        <tr>
            <td style="text-align: center; background-color: #e8f4fd; color: #333333; 
                       padding: 20px; border: 2px solid #0066cc; border-radius: 8px; margin: 10px;">
                <div style="font-size: 18px; font-weight: bold; color: #0066cc; margin-bottom: 12px;">
                    📝 Your Feedback Matters!
                </div>
                <div style="font-size: 16px; line-height: 1.4; margin-bottom: 15px;">
                    Your feedback is really important to improve the project.<br>
                    Please help us enhance your experience by sharing your thoughts!
                </div>
                <a href="https://forms.gle/UegbAWJ6zEcv7yKT8" 
                   style="display: inline-block; background-color: #0066cc; color: #ffffff; 
                          padding: 12px 24px; font-size: 16px; font-weight: bold; 
                          text-decoration: none; border-radius: 5px; 
                          box-shadow: 0 2px 4px rgba(0,102,204,0.3);">
                    Complete Feedback Form
                </a>
            </td>
        </tr>'''

    def generate_email(self, articles: List[Dict]) -> str:
        """Generate the full HTML content of the email, grouping articles by category."""
        articles_by_category = defaultdict(list)
        for article in articles:
            category = article.get("category", "Other")
            articles_by_category[category].append(article)

        sorted_categories = sorted(articles_by_category.keys())
        sections_html = "\n".join(
            self.generate_category_section(category, articles_by_category[category])
            for category in sorted_categories
        )

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
                        {sections_html}
                        {self.generate_footer()}
                    </table>
                </td>
            </tr>
        </table>
    </body>
</html>'''

if __name__ == "__main__":
    sample_news = [
        {
            "title": "Breaking News Story",
            "source": "Global News Network",
            "location": "New York, USA",
            "contact": "news@gnn.com",
            "category": "AI",
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
            "category": "AI",
            "description": "Latest developments in artificial intelligence.",
            "summary": "New AI model shows human-like reasoning capabilities.",
            "link": "https://www.techdaily.com/ai-update"
        }
    ]

    generator = NewsEmailGenerator()
    email_html = generator.generate_email(sample_news)

    with open("../files/output.html", "w", encoding="utf-8") as f:
        f.write(email_html)
