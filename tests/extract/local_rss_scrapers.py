"""
Local RSS scrapers tester: runs all scraper classes defined in `scrapers/rss_scrapers.py` and prints summary stats.

Usage:
  python tests/extract/local_rss_scrapers.py --max 10

This script is intended for local testing only.
"""

import argparse
import logging
import json
import os
import sys
from typing import List
# Ensure repo root is on Python path when running from `tests/extract` directly
THIS_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
# also include the repo root top-level for 'scrapers' package and lambda_package
REPO_ROOT_TOP = os.path.abspath(os.path.join(THIS_DIR, '..'))
for path in (REPO_ROOT, REPO_ROOT_TOP):
    if path not in sys.path:
        sys.path.insert(0, path)

from scrapers.html_extractor import extract_full_content_from_url, is_placeholder_text, sanitize_text

# NOTE: sys.path insertion is above so scrapers import works

# Import scrapers
from scrapers.rss_scrapers import (
    ABCNewsScraper,
    GuardianAUScraper,
    NewsDotComAUScraper,
    SMHScraper,
    TheAgeScraper,
    SBSNewsScraper,
    NineNewsScraper,
    SevenNewsScraper,
    BrisbaneTimesScraper,
    WATodayScraper,
    CanberraTimesScraper,
    AustralianSportsScraper,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SCRAPERS = [
    ABCNewsScraper,
    GuardianAUScraper,
    NewsDotComAUScraper,
    SMHScraper,
    TheAgeScraper,
    SBSNewsScraper,
    NineNewsScraper,
    SevenNewsScraper,
    BrisbaneTimesScraper,
    WATodayScraper,
    CanberraTimesScraper,
    AustralianSportsScraper,
]


def run_all(max_articles: int = 10, save_output: str | None = None, full_extract: bool = False):
    all_results = []

    for scraper_cls in SCRAPERS:
        name = scraper_cls.__name__
        logger.info(f"Running scraper: {name}")
        try:
            scraper = scraper_cls()
            articles = scraper.scrape(max_articles=max_articles)
            logger.info(f"{name} returned {len(articles)} articles")

            # Print first few titles as quick sanity check
            for i, a in enumerate(articles[:3], 1):
                title = getattr(a, 'title', 'No title')
                url = getattr(a, 'url', '')
                src = getattr(a, 'source', '')
                logger.info(f"  [{name}] {i}. {title} ({src}) - {url}")

            # If requested, attempt a full HTML extraction per article (optional)
            samples = []
            for a in articles[:10]:
                content_source = 'rss'
                content_len = len(getattr(a, 'content', '') or '')
                extracted_strategy = None
                extracted_len = 0
                if full_extract:
                    try:
                        full_content, strategy = extract_full_content_from_url(getattr(a, 'url', ''))
                        if full_content and not is_placeholder_text(full_content):
                            # Replace content if extraction produced a full article
                            content_source = 'html'
                            extracted_strategy = strategy
                            extracted_len = len(full_content)
                            a.content = full_content
                        else:
                            extracted_strategy = strategy
                            extracted_len = len(full_content)
                    except Exception as e:
                        logger.error(f"Error extracting full content for {getattr(a, 'url', '')}: {e}")
                # Persist extraction strategy info onto the Article object for reporting
                try:
                    a.extraction_strategy = extracted_strategy or (('html' if content_source == 'html' else 'rss'))
                    a._extracted_len = extracted_len
                    a._original_len = content_len
                except Exception:
                    pass

            # Save basic stats and sample
            result = {
                'scraper': name,
                'count': len(articles),
                'sample': []
            }
            for a in articles[:10]:
                # If Article object has a `to_dict()` method, use it to get the canonical fields
                if hasattr(a, 'to_dict'):
                    try:
                        ad = a.to_dict()
                        # Ensure published_date is isoformat string
                        if isinstance(ad.get('published_date'), (str,)):
                            # already iso string
                            published = ad.get('published_date')
                        else:
                            pd = ad.get('published_date')
                            published = pd.isoformat() if pd else None
                        ad['published_date'] = published
                    except Exception:
                        ad = None
                else:
                    ad = None

                if ad is None:
                    # Fallback: create a dict with most common fields
                    ad = {
                        'title': getattr(a, 'title', ''),
                        'url': getattr(a, 'url', ''),
                        'source': getattr(a, 'source', ''),
                        'published_date': getattr(a, 'published_date', '').isoformat() if getattr(a, 'published_date', None) else None,
                        'content': getattr(a, 'content', ''),
                        'summary': getattr(a, 'summary', ''),
                        'author': getattr(a, 'author', ''),
                        'category': getattr(a, 'category', None),
                        'keywords': getattr(a, 'keywords', None),
                        'image_url': getattr(a, 'image_url', None),
                        'source_list': getattr(a, 'source_list', None),
                        'occurrence_count': getattr(a, 'occurrence_count', None),
                    }

                # Sanitize content & summary
                try:
                    if isinstance(ad.get('summary', None), str):
                        ad['summary'] = sanitize_text(ad['summary'])
                except Exception:
                    pass
                try:
                    if isinstance(ad.get('content', None), str):
                        ad['content'] = sanitize_text(ad['content'])
                except Exception:
                    pass

                # Add extractor metadata
                ad['extraction_strategy'] = getattr(a, 'extraction_strategy', None)
                ad['original_content_len'] = getattr(a, '_original_len', None)
                ad['extracted_len'] = getattr(a, '_extracted_len', None)
                # Truncate large content for safety in JSON if needed; keep content, but optionally also add preview
                try:
                    content_val = ad.get('content', '')
                    if content_val and isinstance(content_val, str) and len(content_val) > 20000:
                        ad['content_preview'] = content_val[:2000]
                    else:
                        ad['content_preview'] = content_val[:2000] if isinstance(content_val, str) else content_val
                except Exception:
                    ad['content_preview'] = None

                result['sample'].append(ad)
            all_results.append(result)
        except Exception as e:
            logger.error(f"Error running {name}: {e}")

    if save_output:
        try:
            with open(save_output, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved output to: {save_output}")
        except Exception as e:
            logger.error(f"Error saving output: {e}")

    return all_results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max', type=int, default=10, help='Max articles per scraper')
    parser.add_argument('--out', type=str, default=None, help='Save JSON output to this file')
    parser.add_argument('--full', action='store_true', help='Try a full HTML extraction for each article')
    args = parser.parse_args()

    run_all(max_articles=args.max, save_output=args.out, full_extract=args.full)


if __name__ == '__main__':
    main()
