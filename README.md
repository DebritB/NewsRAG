# NewsRAG - AI-Powered News Aggregation & Chatbot

Australian news aggregation system with AI-powered categorization and RAG chatbot.

## Setup

1. Create virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file with API keys:
```
NEWSAPI_KEY=your_newsapi_key_here
GUARDIAN_API_KEY=your_guardian_api_key_here
```

4. Run the news scraper:
```bash
python scrape_news.py
```

## Project Structure

- `scrapers/` - News scraping modules
- `models/` - Data models
- `data/` - Scraped articles storage
- `categorizer/` - Article categorization
- `rag/` - RAG chatbot implementation
- `ui/` - Web UI
