import os
from typing import List
from datetime import datetime
import requests
from models import Article
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GNewsAPIScraper:
    """Scraper using GNews API"""
    
    BASE_URL = "https://gnews.io/api/v4/top-headlines"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('GNEWS_API_KEY')
        if not self.api_key:
            logger.warning("GNews API key not found. Set GNEWS_API_KEY environment variable.")
    
    def scrape(self, max_articles: int = 100) -> List[Article]:
        """Scrape articles from GNews API - Australian news"""
        if not self.api_key:
            logger.warning("GNews API not configured. Skipping...")
            return []
        
        articles = []
        
        try:
            logger.info("Scraping GNews API...")
            
            params = {
                'apikey': self.api_key,
                'country': 'au',
                'max': min(100, max_articles),
                'lang': 'en'
            }
            
            response = requests.get(self.BASE_URL, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'articles' in data:
                    for article_data in data['articles']:
                        try:
                            article = Article(
                                title=article_data.get('title', ''),
                                url=article_data.get('url', ''),
                                source=article_data.get('source', {}).get('name', 'GNews'),
                                published_date=self._parse_date(article_data.get('publishedAt', '')),
                                content=article_data.get('content', ''),
                                summary=article_data.get('description', ''),
                                author=article_data.get('source', {}).get('name', ''),
                                category=None,
                                keywords=[],
                                image_url=article_data.get('image', '')
                            )
                            articles.append(article)
                        except Exception as e:
                            logger.error(f"Error parsing GNews article: {e}")
                    
                    logger.info(f"Found {len(data['articles'])} articles from GNews API")
            else:
                logger.warning(f"GNews API returned status code: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error with GNews API: {e}")
        
        return articles[:max_articles]
    
    def _parse_date(self, date_str: str) -> datetime:
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()


class NewsDataIOScraper:
    """Scraper using NewsData.io API"""
    
    BASE_URL = "https://newsdata.io/api/1/news"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('NEWSDATA_API_KEY')
        if not self.api_key:
            logger.warning("NewsData.io API key not found. Set NEWSDATA_API_KEY environment variable.")
    
    def scrape(self, max_articles: int = 100) -> List[Article]:
        """Scrape articles from NewsData.io API - Australian news"""
        if not self.api_key:
            logger.warning("NewsData.io API not configured. Skipping...")
            return []
        
        articles = []
        
        try:
            logger.info("Scraping NewsData.io API...")
            
            params = {
                'apikey': self.api_key,
                'country': 'au',
                'language': 'en'
            }
            
            response = requests.get(self.BASE_URL, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success' and 'results' in data:
                    for article_data in data['results']:
                        try:
                            article = Article(
                                title=article_data.get('title', ''),
                                url=article_data.get('link', ''),
                                source=article_data.get('source_id', 'NewsData.io'),
                                published_date=self._parse_date(article_data.get('pubDate', '')),
                                content=article_data.get('content', ''),
                                summary=article_data.get('description', ''),
                                author=article_data.get('creator', [''])[0] if article_data.get('creator') else '',
                                category=None,
                                keywords=article_data.get('keywords', []) if article_data.get('keywords') else [],
                                image_url=article_data.get('image_url', '')
                            )
                            articles.append(article)
                        except Exception as e:
                            logger.error(f"Error parsing NewsData.io article: {e}")
                    
                    logger.info(f"Found {len(data['results'])} articles from NewsData.io API")
            else:
                logger.warning(f"NewsData.io API returned status code: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error with NewsData.io API: {e}")
        
        return articles[:max_articles]
    
    def _parse_date(self, date_str: str) -> datetime:
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()


class GuardianAPIScraper:
    """Scraper using The Guardian API"""
    
    BASE_URL = "https://content.guardianapis.com/search"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('GUARDIAN_API_KEY')
        if not self.api_key:
            logger.warning("Guardian API key not found. Set GUARDIAN_API_KEY environment variable.")
    
    def scrape(self, max_articles: int = 100) -> List[Article]:
        """Scrape articles from The Guardian API - ALL news"""
        if not self.api_key:
            logger.warning("Guardian API not configured. Skipping...")
            return []
        
        articles = []
        
        try:
            logger.info("Scraping Guardian API...")
            
            # Get ALL latest articles without section filter
            params = {
                'api-key': self.api_key,
                'page-size': 50,  # Max per page
                'show-fields': 'all',
                'order-by': 'newest'
            }
            
            response = requests.get(self.BASE_URL, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                if data['response']['status'] == 'ok':
                    for result in data['response']['results']:
                        try:
                            fields = result.get('fields', {})
                            
                            article = Article(
                                title=result.get('webTitle', ''),
                                url=result.get('webUrl', ''),
                                source='The Guardian API',
                                published_date=self._parse_date(result.get('webPublicationDate', '')),
                                content=fields.get('bodyText', ''),
                                summary=fields.get('trailText', ''),
                                author=fields.get('byline', ''),
                                category=None,  # Will categorize later
                                keywords=[],
                                image_url=fields.get('thumbnail', '')
                            )
                            articles.append(article)
                        except Exception as e:
                            logger.error(f"Error parsing Guardian article: {e}")
                    
                    logger.info(f"Found {len(data['response']['results'])} articles from Guardian API")
        
        except Exception as e:
            logger.error(f"Error with Guardian API: {e}")
        
        return articles[:max_articles]
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date from API response"""
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            return datetime.now()
