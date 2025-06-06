# MailingListLab

An automated email processing and newsletter generation system that uses AI to analyze incoming emails, extract news articles, and generate formatted newsletters and reposts.

## Overview

MailingListLab is a sophisticated email automation system that:

1. **Monitors Gmail inbox** for new emails
2. **Analyzes email content** using Google Gemini AI
3. **Extracts and categorizes news articles** from email content and web links
4. **Generates formatted newsletters** on a scheduled basis
5. **Creates instant reposts** for important emails from whitelisted senders
6. **Sends professionally formatted HTML emails** with categorized content

## Architecture

### Core Components

#### 1. **Email Processing Module** (`modules/email/`)
- **`gmail_handler_v2.py`**: Gmail API integration for reading, parsing, and sending emails
- **`compose_weekly_email.py`**: Generates HTML newsletters with categorized articles
- **`compose_repost_email.py`**: Creates repost emails for specific senders

#### 2. **AI Processing Module** (`modules/AI/`)
- **`use_gemini_v2.py`**: Google Gemini AI handler with rate limiting and retry logic
- **`flows.py`**: Email analysis workflows and web scraping functionality

#### 3. **Utility Module** (`modules/utils/`)
- **`sanitization.py`**: Text sanitization utilities
- **`extract_email_address.py`**: Email address extraction from text

#### 4. **Main Server** (`server_v2.py`)
- Central orchestrator that coordinates all components
- Handles scheduled newsletter generation
- Manages instant repost functionality
- Provides robust error handling and logging

### Data Flow

```
Incoming Emails → Gmail API → Email Parser → AI Analysis → Content Extraction → HTML Generation → Email Sending
```

## Features

### 📧 **Newsletter Generation**
- **Scheduled newsletters** on configurable days and times
- **AI-powered content analysis** to extract relevant articles
- **Automatic categorization** (News, Talks, Events, Workshops, Opportunity, Other)
- **Professional HTML formatting** with category-specific colors
- **Web scraping** for additional context from linked websites
- **Image handling** with optional image downloading and inclusion

### 🔄 **Instant Reposts**
- **Whitelisted sender monitoring** for immediate processing
- **Real-time email analysis** and repost generation
- **Professional formatting** with attribution to original sender

### 🎨 **HTML Email Generation**
- **Responsive design** optimized for various email clients
- **Category-based color coding** for easy visual organization
- **Interactive elements** with hover effects for article summaries
- **Feedback collection** with embedded Google Forms

### 🤖 **AI-Powered Analysis**
- **Content extraction** from emails and linked websites
- **Article categorization** and summarization
- **Duplicate detection** and content filtering
- **Rate-limited API calls** with exponential backoff

### 🔧 **Configuration Management**
- **JSON-based configuration** for easy customization
- **Flexible scheduling** with day-of-week and time settings
- **Sender whitelisting** for repost functionality
- **Category color customization**

## Setup Instructions

### Prerequisites

1. **Python 3.8+** installed
2. **Gmail account** with API access
3. **Google Cloud Project** with Gmail API enabled
4. **Google Gemini API key**

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd MailingListLab
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Configuration

#### 1. **Gmail API Setup**
   - Create a Google Cloud Project
   - Enable Gmail API
   - Create OAuth2 credentials
   - Download credentials as `credentials/credentials.json`

#### 2. **Gemini AI Setup**
   Create one of the following:
   - Environment variable: `export GEMINI_API_KEY="your_api_key"`
   - `.env` file: `GEMINI_API_KEY=your_api_key`
   - Credentials file: `credentials/key.json` with `{"key": "your_api_key"}`

#### 3. **Application Configuration**
   Edit `configs/setup.json`:
   ```json
   {
     "active": true,
     "days": ["Monday", "Wednesday", "Friday"],
     "release_time_str": "09:00:00",
     "seconds_between_checks": 60,
     "whitelisted_senders": ["sender@example.com"],
     "newsletter_email": "newsletter@yourdomain.com",
     "limit_newest": 30
   }
   ```

#### 4. **Category Configuration**
   Customize email categories in `configs/mail_configs.json`:
   ```json
   {
     "category_colors": {
       "News": "#007BFF",
       "Talks": "#28A745",
       "Events": "#DC3545",
       "Workshops": "#17A2B8",
       "Opportunity": "#FFC107",
       "Other": "#6c757d"
     }
   }
   ```

## Usage

### Starting the Server

```bash
# Start the server
./start_server.sh

# Check logs
tail -f logs/server.log

# Stop the server
./stop_server.sh
```

### Manual Testing

Use `testing.py` for development and testing:
```bash
python testing.py
```

### Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `active` | Enable/disable the service | `true` |
| `days` | Days to send newsletters | `[]` |
| `release_time_str` | Time to send newsletters | `""` |
| `seconds_between_checks` | Email check frequency | `10` |
| `whitelisted_senders` | Senders for instant reposts | `[]` |
| `newsletter_email` | Recipient email address | `""` |
| `limit_newest` | Max emails to process | `null` |

## File Structure

```
MailingListLab/
├── configs/                 # Configuration files
│   ├── setup.json          # Main application settings
│   ├── mail_configs.json   # Email formatting settings
│   ├── news_config.json    # News scraping settings
│   └── whitelist.json      # Additional whitelist settings
├── credentials/             # API credentials (not in repo)
│   ├── credentials.json    # Gmail API credentials
│   ├── token.json         # OAuth token (auto-generated)
│   └── key.json           # Gemini API key (optional)
├── modules/
│   ├── AI/                 # AI processing components
│   ├── email/              # Email handling components
│   └── utils/              # Utility functions
├── logs/                   # Application logs
├── images/                 # Downloaded images (auto-generated)
├── files/                  # Temporary files
├── server_v2.py           # Main server application
├── testing.py             # Testing script
├── start_server.sh        # Server startup script
├── stop_server.sh         # Server shutdown script
└── requirements.txt       # Python dependencies
```

## Logging

The application uses comprehensive logging:

- **Application logs**: `logs/server.log` (rotated at 5MB, 3 backups)
- **System logs**: `logs/nohup.out` (stdout/stderr when running as daemon)
- **Log levels**: INFO for normal operations, DEBUG for detailed debugging

## Error Handling

- **Robust retry logic** with exponential backoff for API failures
- **Rate limiting** to prevent API quota exceeded errors
- **Graceful degradation** when services are unavailable
- **Comprehensive error logging** with context information

## Security Considerations

- **OAuth2 authentication** for Gmail access
- **Secure credential storage** outside version control
- **Input sanitization** for email content processing
- **Rate limiting** to prevent abuse
- **Filtered web scraping** to avoid problematic links

## Development

### Adding New Categories

1. Update `configs/mail_configs.json` with new category and color
2. Modify AI prompts in `modules/AI/use_gemini_v2.py` if needed
3. Test with sample emails

### Customizing Email Templates

- Edit `modules/email/compose_weekly_email.py` for newsletter format
- Edit `modules/email/compose_repost_email.py` for repost format
- Modify CSS styles in the template generation methods

### Extending AI Analysis

- Enhance prompts in `modules/AI/use_gemini_v2.py`
- Add new analysis flows in `modules/AI/flows.py`
- Implement custom content extractors

## Troubleshooting

### Common Issues

1. **Gmail API authentication errors**
   - Ensure `credentials/credentials.json` is valid
   - Check OAuth consent screen configuration
   - Verify Gmail API is enabled

2. **Gemini API errors**
   - Verify API key is correct and active
   - Check rate limiting settings
   - Monitor quota usage

3. **Email sending failures**
   - Confirm `newsletter_email` is configured
   - Check Gmail sending limits
   - Verify recipient email addresses

4. **Web scraping failures**
   - Ensure Chrome/Firefox is installed for Selenium
   - Check network connectivity
   - Review website blocking policies

### Logs Analysis

```bash
# Monitor real-time logs
tail -f logs/server.log

# Search for errors
grep ERROR logs/server.log

# Check system output
tail -f logs/nohup.out
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with appropriate tests
4. Update documentation
5. Submit a pull request

## License

[License information to be added]

## Support

For support and questions:
- Check the logs for error details
- Review configuration settings
- Consult the troubleshooting section
- Create an issue in the repository 