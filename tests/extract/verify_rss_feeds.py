"""
Script to verify RSS feeds and APIs from Australian news outlets
This will test actual URLs and confirm which ones work
"""
import feedparser
import requests
from typing import List, Dict
import time

class NewsSourceVerifier:
    def __init__(self):
        self.feeds_to_test = [
            # ...list of RSS feeds to test...
        ]
        self.working_feeds = []

    def test_rss_feed(self, url: str) -> bool:
        """
        Test a single RSS feed URL
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            return bool(feed.entries)
        except Exception as e:
            print(f"Error testing {url}: {e}")
            return False

    def test_all_rss_feeds(self):
        """
        Test all RSS feeds in the list
        """
        for feed_url in self.feeds_to_test:
            if self.test_rss_feed(feed_url):
                self.working_feeds.append(feed_url)

    def save_working_feeds(self, filename: str = "working_feeds.txt"):
        """
        Save the list of working feeds to a file
        """
        with open(filename, "w") as file:
            for feed in self.working_feeds:
                file.write(f"{feed}\n")
        print(f"Working feeds saved to {filename}")

def main():
    verifier = NewsSourceVerifier()
    verifier.test_all_rss_feeds()
    verifier.save_working_feeds()

if __name__ == "__main__":
    main()
