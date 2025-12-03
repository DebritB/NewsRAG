"""
Script to verify RSS feeds and APIs from Australian news outlets
This will test actual URLs and confirm which ones work
"""

import feedparser
import requests
from typing import List, Dict
import time

class NewsSourceVerifier:
    """Verify RSS feeds and APIs for Australian news sources"""
    
    def __init__(self):
        self.results = {
            'rss': [],
            'api': []
        }
    
    def verify_rss_feed(self, source_name: str, feed_url: str) -> Dict:
        """Test if an RSS feed is working"""
        print(f"\nTesting {source_name}...")
        print(f"  URL: {feed_url}")
        
        try:
            feed = feedparser.parse(feed_url)
            
            if feed.bozo:  # Feed has errors
                return {
                    'source': source_name,
                    'url': feed_url,
                    'status': 'ERROR',
                    'error': str(feed.bozo_exception),
                    'articles_found': 0
                }
            
            articles_count = len(feed.entries)
            
            if articles_count > 0:
                # Get sample article
                sample = feed.entries[0]
                return {
                    'source': source_name,
                    'url': feed_url,
                    'status': 'WORKING',
                    'articles_found': articles_count,
                    'sample_title': sample.get('title', 'N/A'),
                    'sample_date': sample.get('published', 'N/A')
                }
            else:
                return {
                    'source': source_name,
                    'url': feed_url,
                    'status': 'EMPTY',
                    'articles_found': 0
                }
                
        except Exception as e:
            return {
                'source': source_name,
                'url': feed_url,
                'status': 'FAILED',
                'error': str(e),
                'articles_found': 0
            }
    
    def test_all_rss_feeds(self):
        """Test all known Australian news RSS feeds"""
        
        # List of Australian news sources with RSS feeds to test
        rss_feeds = [
            # ABC News
            ('ABC News - Just In', 'https://www.abc.net.au/news/feed/51120/rss.xml'),
            ('ABC News - Top Stories', 'https://www.abc.net.au/news/feed/45910/rss.xml'),
            
            # The Guardian Australia
            ('The Guardian AU - All', 'https://www.theguardian.com/au/rss'),
            ('The Guardian AU - Australia News', 'https://www.theguardian.com/australia-news/rss'),
            
            # News.com.au
            ('News.com.au - Breaking News', 'https://www.news.com.au/content-feeds/latest-news-national/'),
            ('News.com.au - Top Stories', 'https://www.news.com.au/content-feeds/latest-news-travel/'),
            
            # Sydney Morning Herald
            ('SMH - Latest News', 'https://www.smh.com.au/rss/feed.xml'),
            ('SMH - National', 'https://www.smh.com.au/rss/national.xml'),
            
            # The Age
            ('The Age - Latest', 'https://www.theage.com.au/rss/feed.xml'),
            ('The Age - National', 'https://www.theage.com.au/rss/national.xml'),
            
            # The Australian
            ('The Australian - All Stories', 'https://www.theaustralian.com.au/feed/'),
            
            # SBS News
            ('SBS News - Latest', 'https://www.sbs.com.au/news/feed'),
            
            # 9News
            ('9News - National', 'https://www.9news.com.au/rss'),
            
            # 7News
            ('7News - Latest', 'https://7news.com.au/feed'),
            
            # Brisbane Times
            ('Brisbane Times', 'https://www.brisbanetimes.com.au/rss/feed.xml'),
            
            # WA Today
            ('WA Today', 'https://www.watoday.com.au/rss/feed.xml'),
            
            # Canberra Times
            ('Canberra Times', 'https://www.canberratimes.com.au/rss.xml'),
            
            # NT News
            ('NT News', 'https://www.ntnews.com.au/rss'),
        ]
        
        print("=" * 80)
        print("TESTING AUSTRALIAN NEWS RSS FEEDS")
        print("=" * 80)
        
        for source, url in rss_feeds:
            result = self.verify_rss_feed(source, url)
            self.results['rss'].append(result)
            
            # Print result
            status_emoji = "✅" if result['status'] == 'WORKING' else "❌"
            print(f"  {status_emoji} Status: {result['status']}")
            if result['status'] == 'WORKING':
                print(f"     Articles: {result['articles_found']}")
                print(f"     Sample: {result['sample_title'][:60]}...")
            elif 'error' in result:
                print(f"     Error: {result['error'][:80]}")
            
            time.sleep(0.5)  # Be nice to servers
        
        print("\n" + "=" * 80)
        self.print_summary()
    
    def print_summary(self):
        """Print summary of verification results"""
        working_rss = [r for r in self.results['rss'] if r['status'] == 'WORKING']
        failed_rss = [r for r in self.results['rss'] if r['status'] != 'WORKING']
        
        print("\nSUMMARY:")
        print(f"  ✅ Working RSS Feeds: {len(working_rss)}")
        print(f"  ❌ Failed RSS Feeds: {len(failed_rss)}")
        
        if working_rss:
            print("\n✅ WORKING RSS FEEDS:")
            for feed in working_rss:
                print(f"  • {feed['source']}: {feed['articles_found']} articles")
                print(f"    {feed['url']}")
        
        if failed_rss:
            print("\n❌ FAILED RSS FEEDS:")
            for feed in failed_rss:
                print(f"  • {feed['source']} - {feed['status']}")
                print(f"    {feed['url']}")
    
    def save_working_feeds(self, filename='working_feeds.txt'):
        """Save working feeds to a file"""
        working = [r for r in self.results['rss'] if r['status'] == 'WORKING']
        
        with open(filename, 'w') as f:
            f.write("WORKING AUSTRALIAN NEWS RSS FEEDS\n")
            f.write("=" * 80 + "\n\n")
            for feed in working:
                f.write(f"Source: {feed['source']}\n")
                f.write(f"URL: {feed['url']}\n")
                f.write(f"Articles: {feed['articles_found']}\n")
                f.write("-" * 80 + "\n")
        
        print(f"\n💾 Working feeds saved to: {filename}")


def main():
    verifier = NewsSourceVerifier()
    verifier.test_all_rss_feeds()
    verifier.save_working_feeds()


if __name__ == "__main__":
    main()
