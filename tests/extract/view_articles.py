import json
import os
from glob import glob
# Find the latest articles file
data_files = glob('data/articles_*.json')
if not data_files:
    print("No scraped articles found. Run scrape_news.py first.")
    exit()
latest_file = max(data_files)
print(f"Reading: {latest_file}\n")
with open(latest_file, 'r', encoding='utf-8') as f:
    articles = json.load(f)
print(f"Total articles: {len(articles)}\n")
print("=" * 80)
# Display first 5 articles
for i, article in enumerate(articles[:5], 1):
    print(f"\n{i}. {article['title']}")
    print(f"   Source: {article['source']}")
    print(f"   Category: {article['category']}")
    print(f"   URL: {article['url']}")
    print(f"   Published: {article['published_date']}")
    print(f"   Summary: {article['summary'][:150]}..." if len(article['summary']) > 150 else f"   Summary: {article['summary']}")
    print("-" * 80)
# Category breakdown
categories = {}
for article in articles:
    cat = article.get('category', 'Unknown')
    categories[cat] = categories.get(cat, 0) + 1
print("\n" + "=" * 80)
print("Category Breakdown:")
for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
    print(f"  {cat}: {count} articles")
print("=" * 80)
