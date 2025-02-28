from typing import List, Dict


class RepostEmailGenerator:
    CATEGORY_COLORS = {
        "News": "#007BFF",
        "Jobs": "#28A745",
        "Presentation": "#DC3545",
        "Opportunity": "#FFC107",
        "General": "#6c757d"  # default color if no category is provided
    }

    def __init__(self, title: str = "News Repost", shared_by: str = "Unknown",
                 footer_text: str = "Powered by Ie Robotics & AI Lab"):
        """
        Initializes the repost email generator.

        Parameters:
            title (str): The title of the repost email.
            shared_by (str): The name or email of the user who requested the repost.
            footer_text (str): Footer text for the email.
        """
        self.title = title
        self.shared_by = shared_by
        self.footer_text = footer_text

    def generate_header(self) -> str:
        """Generate the header of the email including who shared the repost."""
        return f'''
        <tr>
            <td style="background-color: #003366; color: #ffffff; text-align: center; padding: 15px; 
                       font-size: 24px; font-weight: bold;">
                {self.title}
            </td>
        </tr>
        <tr>
            <td style="background-color: #f4f4f4; color: #333333; text-align: center; padding: 8px; font-size: 16px;">
                Shared by: {self.shared_by}
            </td>
        </tr>'''

    @staticmethod
    def generate_article(article: Dict) -> str:
        """Generate the HTML for a single news article."""
        category = article.get("category", "General")
        border_color = RepostEmailGenerator.CATEGORY_COLORS.get(category,
                                                                RepostEmailGenerator.CATEGORY_COLORS["General"])
        return f'''
        <tr>
            <td style="padding: 8px 20px;">
                <div style="background-color: #fafafa; border: 2px solid {border_color}; border-radius: 8px; 
                           margin-bottom: 8px; padding: 12px;">
                    {'<img src="' + article["image"] + '" alt="Article Image" style="width: 100%; display: block; margin-bottom: 12px; border-radius: 8px;">' if "image" in article else ""}
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

    def generate_footer(self) -> str:
        """Generate the footer of the email."""
        return f'''
        <tr>
            <td style="text-align: center; background-color: #f4f4f4; color: #777777; 
                       padding: 12px; font-size: 12px;">
                {self.footer_text}
            </td>
        </tr>'''

    def generate_email(self, articles: List[Dict]) -> str:
        """
        Generate the full HTML content of the repost email.

        Parameters:
            articles (List[Dict]): A list of articles (each a dictionary with the required fields).

        Returns:
            str: The complete HTML content for the repost email.
        """
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


if __name__ == "__main__":
    # Example usage of RepostEmailGenerator with sample articles.
    sample_articles = [
        {
            "title": "Breaking News Story",
            "source": "Global News Network",
            "location": "New York, USA",
            "contact": "news@gnn.com",
            "category": "News",
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
            "category": "News",
            "description": "Latest developments in artificial intelligence.",
            "summary": "New AI model shows human-like reasoning capabilities.",
            "link": "https://www.techdaily.com/ai-update"
        }
    ]

    generator = RepostEmailGenerator(shared_by="alice@example.com")
    email_html = generator.generate_email(sample_articles)

    with open("files/repost_output.html", "w", encoding="utf-8") as f:
        f.write(email_html)
