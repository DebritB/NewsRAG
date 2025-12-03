"""Test script to verify API scrapers are working"""

import os
from dotenv import load_dotenv
from scrapers import (
    GNewsAPIScraper,
    NewsDataIOScraper, GuardianAPIScraper
)

# Load environment variables
load_dotenv()

def test_api(scraper_class, name):
    """Test a single API scraper"""
    print(f"\n{'='*60}")
    print(f"Testing {name}...")
    print(f"{'='*60}")
    
    try:
        scraper = scraper_class()
        articles = scraper.scrape(max_articles=5)  # Just get 5 articles for testing
        
        if articles:
            print(f"✅ SUCCESS: Found {len(articles)} articles")
            print(f"\nSample article:")
            print(f"  Title: {articles[0].title}")
            print(f"  Source: {articles[0].source}")
            print(f"  URL: {articles[0].url}")
            print(f"  Date: {articles[0].published_date}")
        else:
            print(f"❌ FAILED: No articles returned")
    
    except Exception as e:
        print(f"❌ ERROR: {e}")

def main():
    print("Testing API Scrapers...")
    print("This will test each API with a small request to verify they work.\n")
    
    # Test each API
    test_api(GNewsAPIScraper, "GNews API")
    test_api(NewsDataIOScraper, "NewsData.io API")
    test_api(GuardianAPIScraper, "The Guardian API")
    
    print(f"\n{'='*60}")
    print("API Testing Complete!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
