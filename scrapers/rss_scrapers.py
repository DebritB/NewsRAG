import feedparser
import requests
from datetime import datetime
from typing import List
from bs4 import BeautifulSoup
from models import Article
from .html_extractor import extract_full_content_from_url, is_placeholder_text, sanitize_text_alnum_only
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRY_FULL_EXTRACTION_IN_PRODUCTION = os.getenv('TRY_FULL_EXTRACTION_IN_PRODUCTION', 'true').lower() in ('1', 'true', 'yes')
# Only attempt full HTML extraction if the RSS-provided content is short
EXTRACTION_CONTENT_THRESHOLD = 400
# Control whether to use strict alphanumeric-only sanitization in production
USE_STRICT_SANITIZER_IN_PRODUCTION = os.getenv('USE_STRICT_SANITIZER_IN_PRODUCTION', 'false').lower() in ('1', 'true', 'yes')


def _post_process_article(article: Article) -> Article:
    """Attempt to replace article.content with full HTML-extracted text, and sanitize content/summary."""
    try:
        original_len = len(article.content or '')
        extracted_len = 0
        strategy = None
        if TRY_FULL_EXTRACTION_IN_PRODUCTION and getattr(article, 'url', None):
            # Skip full extraction if the RSS content is already long enough
            if article.content and len(article.content) > EXTRACTION_CONTENT_THRESHOLD:
                logger.debug(f"Skipping full extraction for {article.url} because content len > threshold")
            else:
                try:
                    full_content, strategy = extract_full_content_from_url(article.url)
                    extracted_len = len(full_content or '')
                    if full_content and not is_placeholder_text(full_content):
                        article.content = full_content
                except Exception as e:
                    logger.debug(f"Full content extraction failed for {article.url}: {e}")
        article.extraction_strategy = strategy or 'rss'
        article._original_len = original_len
        article._extracted_len = extracted_len
        if isinstance(article.summary, str):
            if USE_STRICT_SANITIZER_IN_PRODUCTION:
                article.summary = sanitize_text_alnum_only(article.summary)
            else:
                from .html_extractor import sanitize_text
                article.summary = sanitize_text(article.summary)
        if isinstance(article.content, str):
            if USE_STRICT_SANITIZER_IN_PRODUCTION:
                article.content = sanitize_text_alnum_only(article.content)
            else:
                from .html_extractor import sanitize_text
                article.content = sanitize_text(article.content)
    except Exception as e:
        logger.error(f"Error post-processing article {getattr(article, 'url', None)}: {e}")
    return article

class ABCNewsScraper:
    """Scraper for ABC News Australia RSS feeds - ALL news"""
    
    RSS_FEEDS = [
        ('ABC News - Just In', 'https://www.abc.net.au/news/feed/51120/rss.xml'),
        ('ABC News - Top Stories', 'https://www.abc.net.au/news/feed/45910/rss.xml'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'  
        })
    
    def scrape(self, max_articles: int = 100) -> List[Article]:
        """Scrape articles from all ABC News feeds"""
        articles = []
        
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                logger.info(f"Scraping {feed_name}...")
                feed_articles = self._scrape_feed(feed_url, feed_name)
                articles.extend(feed_articles)
                logger.info(f"Found {len(feed_articles)} articles from {feed_name}")
            except Exception as e:
                logger.error(f"Error scraping {feed_name}: {e}")
        
        return articles[:max_articles]
    
    def _scrape_feed(self, feed_url: str, feed_name: str) -> List[Article]:
        """Scrape a single RSS feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    article = Article(
                        title=entry.title,
                        url=entry.link,
                        source='ABC News',
                        published_date=self._parse_date(entry.get('published', '')),
                        content=self._extract_content(entry),
                        summary=entry.get('summary', ''),
                        author=entry.get('author', 'ABC News'),
                        category=None,  # Will categorize later
                        keywords=[],
                        image_url=self._extract_image(entry)
                    )
                    article = _post_process_article(article)
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing ABC article: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error fetching ABC feed {feed_url}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date from RSS feed"""
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
    
    def _extract_content(self, entry) -> str:
        """Extract content from RSS entry"""
        if hasattr(entry, 'content'):
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        return ''
    
    def _extract_image(self, entry) -> str:
        """Extract image URL from entry"""
        if hasattr(entry, 'media_content'):
            return entry.media_content[0].get('url', '')
        elif hasattr(entry, 'links'):
            for link in entry.links:
                if link.get('type', '').startswith('image/'):
                    return link.get('href', '')
        return ''


class GuardianAUScraper:
    """Scraper for The Guardian Australia RSS feeds - ALL news"""
    
    RSS_FEEDS = [
        ('The Guardian AU - All', 'https://www.theguardian.com/au/rss'),
        ('The Guardian AU - Australia News', 'https://www.theguardian.com/australia-news/rss'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, max_articles: int = 150) -> List[Article]:
        """Scrape articles from The Guardian Australia"""
        articles = []
        
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                logger.info(f"Scraping {feed_name}...")
                feed_articles = self._scrape_feed(feed_url, feed_name)
                articles.extend(feed_articles)
                logger.info(f"Found {len(feed_articles)} articles from {feed_name}")
            except Exception as e:
                logger.error(f"Error scraping {feed_name}: {e}")
        
        return articles[:max_articles]
    
    def _scrape_feed(self, feed_url: str, feed_name: str) -> List[Article]:
        """Scrape a single RSS feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    article = Article(
                        title=entry.title,
                        url=entry.link,
                        source='The Guardian Australia',
                        published_date=self._parse_date(entry.get('published', '')),
                        content=self._extract_content(entry),
                        summary=entry.get('summary', ''),
                        author=entry.get('author', 'The Guardian'),
                        category=None,  # Will categorize later
                        keywords=[],
                        image_url=self._extract_image(entry)
                    )
                    article = _post_process_article(article)
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing Guardian article: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error fetching Guardian feed {feed_url}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date from RSS feed"""
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
    
    def _extract_content(self, entry) -> str:
        """Extract content from RSS entry"""
        if hasattr(entry, 'content'):
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        return ''
    
    def _extract_image(self, entry) -> str:
        """Extract image URL from entry"""
        if hasattr(entry, 'media_content'):
            return entry.media_content[0].get('url', '')
        return ''


class NewsDotComAUScraper:
    """Scraper for News.com.au RSS feeds - ALL news"""
    
    RSS_FEEDS = [
        ('News.com.au - Breaking News', 'https://www.news.com.au/content-feeds/latest-news-national/'),
        ('News.com.au - Travel', 'https://www.news.com.au/content-feeds/latest-news-travel/'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, max_articles: int = 60) -> List[Article]:
        """Scrape articles from News.com.au"""
        articles = []
        
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                logger.info(f"Scraping {feed_name}...")
                feed_articles = self._scrape_feed(feed_url, feed_name)
                articles.extend(feed_articles)
                logger.info(f"Found {len(feed_articles)} articles from {feed_name}")
            except Exception as e:
                logger.error(f"Error scraping {feed_name}: {e}")
        
        return articles[:max_articles]
    
    def _scrape_feed(self, feed_url: str, feed_name: str) -> List[Article]:
        """Scrape a single RSS feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    article = Article(
                        title=entry.title,
                        url=entry.link,
                        source='News.com.au',
                        published_date=self._parse_date(entry.get('published', '')),
                        content=self._extract_content(entry),
                        summary=entry.get('summary', ''),
                        author=entry.get('author', 'News.com.au'),
                        category=None,  # Will categorize later
                        keywords=[],
                        image_url=self._extract_image(entry)
                    )
                    article = _post_process_article(article)
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing News.com.au article: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error fetching News.com.au feed {feed_url}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date from RSS feed"""
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
    
    def _extract_content(self, entry) -> str:
        """Extract content from RSS entry"""
        if hasattr(entry, 'content'):
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        return ''
    
    def _extract_image(self, entry) -> str:
        """Extract image URL from entry"""
        if hasattr(entry, 'media_content'):
            return entry.media_content[0].get('url', '')
        return ''


class SMHScraper:
    """Scraper for Sydney Morning Herald RSS feeds - ALL news"""
    
    RSS_FEEDS = [
        ('SMH - Latest News', 'https://www.smh.com.au/rss/feed.xml'),
        ('SMH - National', 'https://www.smh.com.au/rss/national.xml'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, max_articles: int = 40) -> List[Article]:
        """Scrape articles from SMH"""
        articles = []
        
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                logger.info(f"Scraping {feed_name}...")
                feed_articles = self._scrape_feed(feed_url, feed_name)
                articles.extend(feed_articles)
                logger.info(f"Found {len(feed_articles)} articles from {feed_name}")
            except Exception as e:
                logger.error(f"Error scraping {feed_name}: {e}")
        
        return articles[:max_articles]
    
    def _scrape_feed(self, feed_url: str, feed_name: str) -> List[Article]:
        """Scrape a single RSS feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    article = Article(
                        title=entry.title,
                        url=entry.link,
                        source='Sydney Morning Herald',
                        published_date=self._parse_date(entry.get('published', '')),
                        content=self._extract_content(entry),
                        summary=entry.get('summary', ''),
                        author=entry.get('author', 'SMH'),
                        category=None,  # Will categorize later
                        keywords=[],
                        image_url=self._extract_image(entry)
                    )
                    article = _post_process_article(article)
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing SMH article: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error fetching SMH feed {feed_url}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date from RSS feed"""
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
    
    def _extract_content(self, entry) -> str:
        """Extract content from RSS entry"""
        if hasattr(entry, 'content'):
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        return ''
    
    def _extract_image(self, entry) -> str:
        """Extract image URL from entry"""
        if hasattr(entry, 'media_content'):
            return entry.media_content[0].get('url', '')
        return ''


class TheAgeScraper:
    """Scraper for The Age RSS feeds - ALL news"""
    
    RSS_FEEDS = [
        ('The Age - Latest', 'https://www.theage.com.au/rss/feed.xml'),
        ('The Age - National', 'https://www.theage.com.au/rss/national.xml'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, max_articles: int = 40) -> List[Article]:
        """Scrape articles from The Age"""
        articles = []
        
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                logger.info(f"Scraping {feed_name}...")
                feed_articles = self._scrape_feed(feed_url, feed_name)
                articles.extend(feed_articles)
                logger.info(f"Found {len(feed_articles)} articles from {feed_name}")
            except Exception as e:
                logger.error(f"Error scraping {feed_name}: {e}")
        
        return articles[:max_articles]
    
    def _scrape_feed(self, feed_url: str, feed_name: str) -> List[Article]:
        """Scrape a single RSS feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    article = Article(
                        title=entry.title,
                        url=entry.link,
                        source='The Age',
                        published_date=self._parse_date(entry.get('published', '')),
                        content=self._extract_content(entry),
                        summary=entry.get('summary', ''),
                        author=entry.get('author', 'The Age'),
                        category=None,  # Will categorize later
                        keywords=[],
                        image_url=self._extract_image(entry)
                    )
                    article = _post_process_article(article)
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing The Age article: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error fetching The Age feed {feed_url}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date from RSS feed"""
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
    
    def _extract_content(self, entry) -> str:
        """Extract content from RSS entry"""
        if hasattr(entry, 'content'):
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        return ''
    
    def _extract_image(self, entry) -> str:
        """Extract image URL from entry"""
        if hasattr(entry, 'media_content'):
            return entry.media_content[0].get('url', '')
        return ''


# NEW SCRAPERS - Additional verified sources

class SBSNewsScraper:
    """Scraper for SBS News RSS feeds"""
    
    RSS_FEEDS = [
        ('SBS News - Latest', 'https://www.sbs.com.au/news/feed'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, max_articles: int = 30) -> List[Article]:
        """Scrape articles from SBS News"""
        articles = []
        
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                logger.info(f"Scraping {feed_name}...")
                feed_articles = self._scrape_feed(feed_url, feed_name)
                articles.extend(feed_articles)
                logger.info(f"Found {len(feed_articles)} articles from {feed_name}")
            except Exception as e:
                logger.error(f"Error scraping {feed_name}: {e}")
        
        return articles[:max_articles]
    
    def _scrape_feed(self, feed_url: str, feed_name: str) -> List[Article]:
        """Scrape a single RSS feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    article = Article(
                        title=entry.title,
                        url=entry.link,
                        source='SBS News',
                        published_date=self._parse_date(entry.get('published', '')),
                        content=self._extract_content(entry),
                        summary=entry.get('summary', ''),
                        author=entry.get('author', 'SBS News'),
                        category=None,
                        keywords=[],
                        image_url=self._extract_image(entry)
                    )
                    article = _post_process_article(article)
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing SBS article: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error fetching SBS feed {feed_url}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime:
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
    
    def _extract_content(self, entry) -> str:
        if hasattr(entry, 'content'):
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        return ''
    
    def _extract_image(self, entry) -> str:
        if hasattr(entry, 'media_content'):
            return entry.media_content[0].get('url', '')
        return ''


class NineNewsScraper:
    """Scraper for 9News RSS feeds"""
    
    RSS_FEEDS = [
        ('9News - National', 'https://www.9news.com.au/rss'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, max_articles: int = 20) -> List[Article]:
        """Scrape articles from 9News"""
        articles = []
        
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                logger.info(f"Scraping {feed_name}...")
                feed_articles = self._scrape_feed(feed_url, feed_name)
                articles.extend(feed_articles)
                logger.info(f"Found {len(feed_articles)} articles from {feed_name}")
            except Exception as e:
                logger.error(f"Error scraping {feed_name}: {e}")
        
        return articles[:max_articles]
    
    def _scrape_feed(self, feed_url: str, feed_name: str) -> List[Article]:
        """Scrape a single RSS feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    article = Article(
                        title=entry.title,
                        url=entry.link,
                        source='9News',
                        published_date=self._parse_date(entry.get('published', '')),
                        content=self._extract_content(entry),
                        summary=entry.get('summary', ''),
                        author=entry.get('author', '9News'),
                        category=None,
                        keywords=[],
                        image_url=self._extract_image(entry)
                    )
                    article = _post_process_article(article)
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing 9News article: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error fetching 9News feed {feed_url}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime:
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
    
    def _extract_content(self, entry) -> str:
        if hasattr(entry, 'content'):
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        return ''
    
    def _extract_image(self, entry) -> str:
        if hasattr(entry, 'media_content'):
            return entry.media_content[0].get('url', '')
        return ''


class SevenNewsScraper:
    """Scraper for 7News RSS feeds"""
    
    RSS_FEEDS = [
        ('7News - Latest', 'https://7news.com.au/feed'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, max_articles: int = 100) -> List[Article]:
        """Scrape articles from 7News"""
        articles = []
        
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                logger.info(f"Scraping {feed_name}...")
                feed_articles = self._scrape_feed(feed_url, feed_name)
                articles.extend(feed_articles)
                logger.info(f"Found {len(feed_articles)} articles from {feed_name}")
            except Exception as e:
                logger.error(f"Error scraping {feed_name}: {e}")
        
        return articles[:max_articles]
    
    def _scrape_feed(self, feed_url: str, feed_name: str) -> List[Article]:
        """Scrape a single RSS feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    article = Article(
                        title=entry.title,
                        url=entry.link,
                        source='7News',
                        published_date=self._parse_date(entry.get('published', '')),
                        content=self._extract_content(entry),
                        summary=entry.get('summary', ''),
                        author=entry.get('author', '7News'),
                        category=None,
                        keywords=[],
                        image_url=self._extract_image(entry)
                    )
                    article = _post_process_article(article)
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing 7News article: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error fetching 7News feed {feed_url}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime:
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
    
    def _extract_content(self, entry) -> str:
        if hasattr(entry, 'content'):
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        return ''
    
    def _extract_image(self, entry) -> str:
        if hasattr(entry, 'media_content'):
            return entry.media_content[0].get('url', '')
        return ''


class BrisbaneTimesScraper:
    """Scraper for Brisbane Times RSS feeds"""
    
    RSS_FEEDS = [
        ('Brisbane Times - Latest', 'https://www.brisbanetimes.com.au/rss/feed.xml'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, max_articles: int = 20) -> List[Article]:
        """Scrape articles from Brisbane Times"""
        articles = []
        
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                logger.info(f"Scraping {feed_name}...")
                feed_articles = self._scrape_feed(feed_url, feed_name)
                articles.extend(feed_articles)
                logger.info(f"Found {len(feed_articles)} articles from {feed_name}")
            except Exception as e:
                logger.error(f"Error scraping {feed_name}: {e}")
        
        return articles[:max_articles]
    
    def _scrape_feed(self, feed_url: str, feed_name: str) -> List[Article]:
        """Scrape a single RSS feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    article = Article(
                        title=entry.title,
                        url=entry.link,
                        source='Brisbane Times',
                        published_date=self._parse_date(entry.get('published', '')),
                        content=self._extract_content(entry),
                        summary=entry.get('summary', ''),
                        author=entry.get('author', 'Brisbane Times'),
                        category=None,
                        keywords=[],
                        image_url=self._extract_image(entry)
                    )
                    article = _post_process_article(article)
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing Brisbane Times article: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error fetching Brisbane Times feed {feed_url}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime:
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
    
    def _extract_content(self, entry) -> str:
        if hasattr(entry, 'content'):
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        return ''
    
    def _extract_image(self, entry) -> str:
        if hasattr(entry, 'media_content'):
            return entry.media_content[0].get('url', '')
        return ''


class WATodayScraper:
    """Scraper for WA Today RSS feeds"""
    
    RSS_FEEDS = [
        ('WA Today - Latest', 'https://www.watoday.com.au/rss/feed.xml'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, max_articles: int = 20) -> List[Article]:
        """Scrape articles from WA Today"""
        articles = []
        
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                logger.info(f"Scraping {feed_name}...")
                feed_articles = self._scrape_feed(feed_url, feed_name)
                articles.extend(feed_articles)
                logger.info(f"Found {len(feed_articles)} articles from {feed_name}")
            except Exception as e:
                logger.error(f"Error scraping {feed_name}: {e}")
        
        return articles[:max_articles]
    
    def _scrape_feed(self, feed_url: str, feed_name: str) -> List[Article]:
        """Scrape a single RSS feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    article = Article(
                        title=entry.title,
                        url=entry.link,
                        source='WA Today',
                        published_date=self._parse_date(entry.get('published', '')),
                        content=self._extract_content(entry),
                        summary=entry.get('summary', ''),
                        author=entry.get('author', 'WA Today'),
                        category=None,
                        keywords=[],
                        image_url=self._extract_image(entry)
                    )
                    article = _post_process_article(article)
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing WA Today article: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error fetching WA Today feed {feed_url}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime:
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
    
    def _extract_content(self, entry) -> str:
        if hasattr(entry, 'content'):
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        return ''
    
    def _extract_image(self, entry) -> str:
        if hasattr(entry, 'media_content'):
            return entry.media_content[0].get('url', '')
        return ''


class CanberraTimesScraper:
    """Scraper for Canberra Times RSS feeds"""
    
    RSS_FEEDS = [
        ('Canberra Times - Latest', 'https://www.canberratimes.com.au/rss.xml'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, max_articles: int = 20) -> List[Article]:
        """Scrape articles from Canberra Times"""
        articles = []
        
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                logger.info(f"Scraping {feed_name}...")
                feed_articles = self._scrape_feed(feed_url, feed_name)
                articles.extend(feed_articles)
                logger.info(f"Found {len(feed_articles)} articles from {feed_name}")
            except Exception as e:
                logger.error(f"Error scraping {feed_name}: {e}")
        
        return articles[:max_articles]
    
    def _scrape_feed(self, feed_url: str, feed_name: str) -> List[Article]:
        """Scrape a single RSS feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    article = Article(
                        title=entry.title,
                        url=entry.link,
                        source='Canberra Times',
                        published_date=self._parse_date(entry.get('published', '')),
                        content=self._extract_content(entry),
                        summary=entry.get('summary', ''),
                        author=entry.get('author', 'Canberra Times'),
                        category=None,
                        keywords=[],
                        image_url=self._extract_image(entry)
                    )
                    article = _post_process_article(article)
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing Canberra Times article: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error fetching Canberra Times feed {feed_url}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime:
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
    
    def _extract_content(self, entry) -> str:
        if hasattr(entry, 'content'):
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        return ''
    
    def _extract_image(self, entry) -> str:
        if hasattr(entry, 'media_content'):
            return entry.media_content[0].get('url', '')
        return ''


class AustralianSportsScraper:
    """Scraper for Australian Sports RSS feeds"""
    
    RSS_FEEDS = [
        ('AFL - Latest', 'https://www.afl.com.au/rss'),
        ('NRL - Latest', 'https://www.nrl.com.au/rss'),
        ('Cricket Australia - Latest', 'https://www.cricket.com.au/rss'),
        ('Fox Sports Australia - Latest', 'https://www.foxsports.com.au/rss'),
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape(self, max_articles: int = 100) -> List[Article]:
        """Scrape articles from Australian Sports sources"""
        articles = []
        
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                logger.info(f"Scraping {feed_name}...")
                feed_articles = self._scrape_feed(feed_url, feed_name)
                articles.extend(feed_articles)
                logger.info(f"Found {len(feed_articles)} articles from {feed_name}")
            except Exception as e:
                logger.error(f"Error scraping {feed_name}: {e}")
        
        return articles[:max_articles]
    
    def _scrape_feed(self, feed_url: str, feed_name: str) -> List[Article]:
        """Scrape a single RSS feed"""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    article = Article(
                        title=entry.title,
                        url=entry.link,
                        source=feed_name.split(' - ')[0],  # e.g., 'AFL'
                        published_date=self._parse_date(entry.get('published', '')),
                        content=self._extract_content(entry),
                        summary=entry.get('summary', ''),
                        author=entry.get('author', feed_name.split(' - ')[0]),
                        category='Sports',  # Pre-categorize as Sports
                        keywords=[],
                        image_url=self._extract_image(entry)
                    )
                    article = _post_process_article(article)
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing {feed_name} article: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error fetching {feed_name} feed {feed_url}: {e}")
        
        return articles
    
    def _parse_date(self, date_str: str) -> datetime:
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
    
    def _extract_content(self, entry) -> str:
        if hasattr(entry, 'content'):
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        return ''
    
    def _extract_image(self, entry) -> str:
        if hasattr(entry, 'media_content'):
            return entry.media_content[0].get('url', '')
        return ''
