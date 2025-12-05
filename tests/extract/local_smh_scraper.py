import feedparser
import logging
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field
import requests
from bs4 import BeautifulSoup

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Model Definition (copied from models/article.py) ---
@dataclass
class Article:
    """Unified article data model"""
    title: str
    url: str
    source: str
    published_date: datetime
    content: str
    summary: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    image_url: Optional[str] = None
    source_list: Optional[List[str]] = field(default_factory=list)
    occurrence_count: Optional[int] = 1
    embedding: Optional[List[float]] = None
    confidence: float = 0.0
    highlight: bool = False
    
    def __post_init__(self):
        if not self.source_list:
            self.source_list = [self.source]

# --- Scraper Logic (adapted from scrapers/rss_scrapers.py) ---
def parse_date(date_str: str) -> datetime:
    """Parse date from RSS feed"""
    if not date_str:
        return datetime.now()
    try:
        from dateutil import parser
        return parser.parse(date_str)
    except ImportError:
        logger.warning("dateutil.parser not found. Please install it (`pip install python-dateutil`). Falling back to basic parsing.")
        # Fallback for different common RSS date formats
        for fmt in (
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%SZ"
        ):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return datetime.now() # Fallback if all formats fail
    except Exception:
        return datetime.now()

def extract_full_content_from_url(url: str) -> tuple[str, str]:
    """Fetch and parse the full article content from the URL.

    Strategy:
    1) Try a curated list of CSS selectors (SMH specific + common patterns)
    2) If selectors fail, use heuristic: pick the element with the most <p> children or most text
    3) Clean the extracted text
    """
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove script, style, noscript, form, and ads containers to reduce noise
        for tag in soup(['script', 'style', 'noscript', 'iframe', 'form', 'nav', 'aside', 'header', 'footer']):
            tag.decompose()

        # Strategy 1: curated selectors
        selectors = [
            "div[data-testid=article-body]",
            "article",
            "div[itemprop=articleBody]",
            "div[class*='article__body']",
            "div[class*='article-body']",
            "div[class*='content-body']",
            "div[class*='main-content']",
        ]

        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                paragraphs = el.find_all('p')
                text = "\n".join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
                if len(text) > 100:
                    logger.debug(f"Extraction success using selector: {sel} for URL: {url}")
                    return clean_article_text(text), f"selector:{sel}"

        # Strategy 2: heuristic - pick element with most <p> tags and longest text
        candidates = []
        for div in soup.find_all(['div', 'article', 'main']):
            ps = div.find_all('p')
            if len(ps) >= 2:
                text = "\n".join(p.get_text().strip() for p in ps if p.get_text().strip())
                candidates.append((len(ps), len(text), text, div))

        if candidates:
            # prioritize by number of paragraphs, then by total length
            candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
            best_text = candidates[0][2]
            if len(best_text) > 100:
                logger.debug(f"Extraction success using heuristic for URL: {url}")
                return clean_article_text(best_text), "heuristic:max-paragraphs"

        # Strategy 3: final fallback - join all <p> in body
        body = soup.body
        if body:
            paragraphs = body.find_all('p')
            text = "\n".join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
            if len(text) > 100:
                logger.debug(f"Fallback extraction success for URL: {url}")
                return clean_article_text(text), "fallback:body-paragraphs"

        logger.warning(f"Could not find article body for URL: {url}")
        return "", "none"
    except requests.RequestException as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return "", "error"
    except Exception as e:
        logger.error(f"Error parsing HTML for URL {url}: {e}")
        return "", "error"


def clean_article_text(text: str) -> str:
    """Clean article text: remove excessive whitespace and trailing disclaimers/footers."""
    # Remove repeated whitespace
    import re
    txt = re.sub(r"\r\n|\r", "\n", text)
    txt = re.sub(r"\n{2,}", "\n\n", txt)
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    # Remove common 'Read more' or social tags
    txt = re.sub(r"\s*Read more.*$", "", txt, flags=re.I | re.M)
    txt = re.sub(r"\s*RELATED:.*$", "", txt, flags=re.I | re.M)
    return txt.strip()


def is_placeholder_text(text: str) -> bool:
    """Detect placeholder text commonly used for paywalled or unavailable content.
    Returns True if the text seems like a site message rather than article content.
    """
    if not text or len(text.strip()) == 0:
        return True
    # Lowercase text once for checks
    t = text.strip().lower()
    # Common placeholder phrases
    placeholders = [
        r"we['’]?re sorry",
        r"this feature is currently unavailable",
        r"please try again later",
        r"please sign in",
        r"subscribe to continue",
        r"subscription required",
        r"sign in to read",
        r"please log in",
        r"feature is temporarily unavailable",
        r"you must be a subscriber",
    ]
    import re
    for p in placeholders:
        if re.search(p, t):
            return True
    # Very short content (e.g., under 120 characters) is unlikely to be a full article
    if len(t) < 120:
        return True
    return False


def extract_image(entry) -> str:
    """Extract image URL from entry"""
    if hasattr(entry, 'media_content'):
        return entry.media_content[0].get('url', '')
    return ''

def scrape_smh_feed(feed_url: str) -> List[Article]:
    """Scrape a single SMH RSS feed"""
    articles = []
    logger.info(f"Fetching feed: {feed_url}")
    try:
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries:
            try:
                summary_from_rss = entry.get('summary', '')
                full_content, strategy = extract_full_content_from_url(entry.link)
                if strategy and strategy != 'none':
                    logger.info(f"Content extracted using {strategy} for {entry.link}")
                # If extraction returned a placeholder message or very short content, fallback to summary
                if is_placeholder_text(full_content):
                    logger.info(f"Placeholder content detected for {entry.link} (len={len(full_content)}). Falling back to RSS summary.")
                    full_content = ''
                
                article = Article(
                    title=entry.title,
                    url=entry.link,
                    source='Sydney Morning Herald',
                    published_date=parse_date(entry.get('published', '')),
                    content=full_content or summary_from_rss, # Fallback to summary if content is empty
                    summary=summary_from_rss,
                    author=entry.get('author', 'SMH'),
                    category=None,
                    keywords=[],
                    image_url=extract_image(entry)
                )
                articles.append(article)
            except Exception as e:
                logger.error(f"Error parsing SMH article: {e}")
                continue
    except Exception as e:
        logger.error(f"Error fetching SMH feed {feed_url}: {e}")
    
    logger.info(f"Found {len(articles)} articles from the feed.")
    return articles

def main():
    """Main function to run the scraper and print results."""
    smh_feeds = [
        ('SMH - Latest News', 'https://www.smh.com.au/rss/feed.xml'),
        ('SMH - National', 'https://www.smh.com.au/rss/national.xml'),
    ]
    
    all_smh_articles = []
    for feed_name, feed_url in smh_feeds:
        all_smh_articles.extend(scrape_smh_feed(feed_url))
        
    print("\n--- SCRAPED SMH ARTICLES ---")
    if not all_smh_articles:
        print("No articles were found.")
    else:
        for i, article in enumerate(all_smh_articles, 1):
            print(f"--- Article {i} ---")
            print(f"  Title: {article.title}")
            print(f"  URL: {article.url}")
            print(f"  Published Date: {article.published_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Author: {article.author}")
            print(f"  Summary: {article.summary}")
            print(f"  Content: {article.content[:500]}...") # Print first 500 chars of content
            print("-" * (len(f"--- Article {i} ---")))


if __name__ == "__main__":
    main()
