import json
import os
from datetime import datetime
from typing import List, Dict, Tuple

# Optional: Load .env file for local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available (e.g., in Lambda with Secrets Manager)

from models import Article
from scrapers import (
    ABCNewsScraper,
    NewsDotComAUScraper,
    SMHScraper,
    TheAgeScraper,
    SBSNewsScraper,
    NineNewsScraper,
    SevenNewsScraper,
    BrisbaneTimesScraper,
    WATodayScraper,
    CanberraTimesScraper,
    GuardianAPIScraper,
    GNewsAPIScraper,
    NewsDataIOScraper
)
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NewsAggregator:
    """Main orchestrator for scraping all news sources"""
    
    # Target categories - only these 5 allowed
    ALLOWED_CATEGORIES = ['sports', 'lifestyle', 'music', 'finance', 'other']
    
    def __init__(self):
        self.rss_scrapers = [
            ABCNewsScraper(),
            NewsDotComAUScraper(),
            SMHScraper(),
            TheAgeScraper(),
            SBSNewsScraper(),
            NineNewsScraper(),
            SevenNewsScraper(),
            BrisbaneTimesScraper(),
            WATodayScraper(),
            CanberraTimesScraper()
        ]
        
        self.api_scrapers = [
            GuardianAPIScraper(),
            GNewsAPIScraper(),
            NewsDataIOScraper()
        ]
        
        self.all_articles = []
    
    @staticmethod
    def remove_duplicates(articles: List[Article]) -> List[Article]:
        """
        Remove exact duplicate articles based on title and summary.
        Prioritizes API sources over RSS feeds when duplicates exist.
        Also removes syndicated content (same article from different sources).
        
        Args:
            articles: List of Article objects
            
        Returns:
            Deduplicated list of Article objects
        """
        # API source names to prioritize
        api_sources = {
            'the guardian api', 'guardian api', 'gnews api', 'newsdata.io api',
            'newsdata.io', 'gnews', 'currents api'
        }
        
        # Sort articles to process API sources first
        def is_api_source(article):
            source = (article.source or '').strip().lower()
            return any(api_name in source for api_name in api_sources)
        
        # Process API articles first, then RSS
        sorted_articles = sorted(articles, key=lambda a: (not is_api_source(a), a.title or ''))
        
        seen_content = {}  # Map content to article
        seen_with_source = set()  # Track complete duplicates including source
        duplicates_count = 0
        syndicated_count = 0
        api_preferred_count = 0
        
        for article in sorted_articles:
            # Normalize title and summary
            title = (article.title or '').strip().lower()
            summary = (article.summary or '').strip().lower()
            source = (article.source or '').strip().lower()
            
            # Create keys for comparison
            content_key = (title, summary)  # Source-agnostic key
            article_key = (title, summary, source)  # Full key including source
            
            if content_key not in seen_content:
                # Completely new content
                seen_content[content_key] = article
                seen_with_source.add(article_key)
            elif article_key not in seen_with_source:
                # Same content, different source
                seen_with_source.add(article_key)
                
                # Check if we should count this as API replacement or syndication
                existing_article = seen_content[content_key]
                existing_source = (existing_article.source or '').strip().lower()
                existing_is_api = any(api_name in existing_source for api_name in api_sources)
                current_is_api = is_api_source(article)
                
                if existing_is_api and not current_is_api:
                    # API version kept, RSS discarded
                    api_preferred_count += 1
                else:
                    # Both from similar source types (both RSS or both API)
                    syndicated_count += 1
            else:
                # Exact duplicate (same title, summary, AND source)
                duplicates_count += 1
        
        # Extract unique articles from the dictionary
        unique_articles = list(seen_content.values())
        
        if duplicates_count > 0:
            logger.info(f"Removed {duplicates_count} exact duplicates")
        if api_preferred_count > 0:
            logger.info(f"Kept {api_preferred_count} API versions over RSS duplicates")
        if syndicated_count > 0:
            logger.info(f"Removed {syndicated_count} syndicated duplicates (same content, different sources)")
        
        return unique_articles
    
    def scrape_all(self, max_per_source: int = 200) -> List[Article]:
        """Scrape articles from all sources - only yesterday and today"""
        logger.info("=" * 60)
        logger.info("Starting news aggregation from all sources")
        logger.info("Filtering: Yesterday and Today only")
        logger.info("=" * 60)
        
        from datetime import timedelta
        
        # Calculate date filters: yesterday and today (timezone-naive)
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        
        logger.info(f"Date filter: {yesterday_start.date()} to {now.date()}")
        logger.info("=" * 60)
        
        # Scrape RSS feeds
        logger.info("\n📰 Scraping RSS Feeds...")
        for scraper in self.rss_scrapers:
            try:
                source_name = scraper.__class__.__name__.replace('Scraper', '')
                logger.info(f"\nScraping {source_name}...")
                articles = scraper.scrape(max_articles=max_per_source)
                
                # Filter articles from yesterday and today only
                filtered_articles = []
                for article in articles:
                    article_date = article.published_date
                    # Make timezone-naive for comparison
                    if article_date.tzinfo is not None:
                        article_date = article_date.replace(tzinfo=None)
                    
                    if article_date >= yesterday_start:
                        filtered_articles.append(article)
                
                self.all_articles.extend(filtered_articles)
                logger.info(f"✓ {source_name}: {len(filtered_articles)} articles (filtered from {len(articles)})")
            except Exception as e:
                logger.error(f"✗ Error with {scraper.__class__.__name__}: {e}")
        
        # Scrape APIs
        logger.info("\n🔌 Scraping APIs...")
        for scraper in self.api_scrapers:
            try:
                source_name = scraper.__class__.__name__.replace('Scraper', '')
                logger.info(f"\nScraping {source_name}...")
                articles = scraper.scrape(max_articles=max_per_source)
                
                # Filter articles from yesterday and today only
                filtered_articles = []
                for article in articles:
                    article_date = article.published_date
                    # Make timezone-naive for comparison
                    if article_date.tzinfo is not None:
                        article_date = article_date.replace(tzinfo=None)
                    
                    if article_date >= yesterday_start:
                        filtered_articles.append(article)
                
                self.all_articles.extend(filtered_articles)
                logger.info(f"✓ {source_name}: {len(filtered_articles)} articles (filtered from {len(articles)})")
            except Exception as e:
                logger.error(f"✗ Error with {scraper.__class__.__name__}: {e}")
        
        logger.info("\n" + "=" * 60)
        logger.info(f"Total articles scraped: {len(self.all_articles)}")
        logger.info("=" * 60)
        
        # Remove exact duplicates (prioritizes API sources over RSS)
        self.all_articles = self.remove_duplicates(self.all_articles)
        
        logger.info(f"After exact deduplication: {len(self.all_articles)} articles")
        logger.info("=" * 60)
        logger.info("Note: Similarity-based deduplication will be handled by MongoDB Vector Search")
        
        return self.all_articles
    
    def save_to_json(self, filename: str = None):
        """Save scraped articles to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'data/articles_{timestamp}.json'
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Convert articles to dictionaries
        articles_data = [article.to_dict() for article in self.all_articles]
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(articles_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n💾 Saved {len(articles_data)} articles to {filename}")
        return filename
    
    def get_statistics(self):
        """Get statistics about scraped articles"""
        if not self.all_articles:
            return {}
        
        sources = {}
        categories = {}
        
        for article in self.all_articles:
            # Count by source
            sources[article.source] = sources.get(article.source, 0) + 1
            
            # Count by category
            if article.category:
                categories[article.category] = categories.get(article.category, 0) + 1
        
        # Get date range, handling timezone-aware and naive datetimes
        dates = [a.published_date for a in self.all_articles if a.published_date]
        if dates:
            # Make all dates timezone-naive for comparison
            from datetime import timezone
            dates_naive = []
            for d in dates:
                if d.tzinfo is not None:
                    dates_naive.append(d.replace(tzinfo=None))
                else:
                    dates_naive.append(d)
            
            earliest = min(dates_naive)
            latest = max(dates_naive)
        else:
            earliest = latest = datetime.now()
        
        stats = {
            'total_articles': len(self.all_articles),
            'sources': sources,
            'categories': categories,
            'date_range': {
                'earliest': earliest.isoformat(),
                'latest': latest.isoformat()
            }
        }
        
        return stats
    
    def print_statistics(self):
        """Print statistics about scraped articles"""
        stats = self.get_statistics()
        
        if not stats:
            logger.info("No articles scraped yet.")
            return
        
        logger.info("\n" + "=" * 60)
        logger.info("SCRAPING STATISTICS")
        logger.info("=" * 60)
        logger.info(f"\n📊 Total Articles: {stats['total_articles']}")
        
        logger.info("\n📰 By Source:")
        for source, count in sorted(stats['sources'].items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  • {source}: {count}")
        
        logger.info("\n📁 By Category:")
        for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  • {category}: {count}")
        
        logger.info(f"\n📅 Date Range:")
        logger.info(f"  • Earliest: {stats['date_range']['earliest']}")
        logger.info(f"  • Latest: {stats['date_range']['latest']}")
        logger.info("=" * 60)


def main():
    """Main execution function"""
    try:
        # Load environment variables (optional for local dev)
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        
        # Create aggregator
        aggregator = NewsAggregator()
        
        # Scrape all sources (increased limit for more articles)
        articles = aggregator.scrape_all(max_per_source=200)
        
        # Print statistics
        aggregator.print_statistics()
        
        # Save to JSON
        if articles:
            filename = aggregator.save_to_json()
            logger.info(f"\n✅ Success! Articles saved to: {filename}")
        else:
            logger.warning("\n⚠️  No articles were scraped.")
        
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Scraping interrupted by user.")
    except Exception as e:
        logger.error(f"\n❌ Error during scraping: {e}")
        raise


if __name__ == "__main__":
    main()
