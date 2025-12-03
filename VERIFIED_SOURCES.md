# VERIFIED AUSTRALIAN NEWS SOURCES

## ✅ WORKING RSS FEEDS (16 sources)

### Major National News
1. **ABC News**
   - Just In: https://www.abc.net.au/news/feed/51120/rss.xml (25 articles)
   - Top Stories: https://www.abc.net.au/news/feed/45910/rss.xml (25 articles)

2. **The Guardian Australia**
   - All News: https://www.theguardian.com/au/rss (112 articles)
   - Australia News: https://www.theguardian.com/australia-news/rss (23 articles)

3. **News.com.au**
   - Breaking News: https://www.news.com.au/content-feeds/latest-news-national/ (30 articles)
   - Travel: https://www.news.com.au/content-feeds/latest-news-travel/ (30 articles)

4. **Sydney Morning Herald (SMH)**
   - Latest News: https://www.smh.com.au/rss/feed.xml (20 articles)
   - National: https://www.smh.com.au/rss/national.xml (20 articles)

5. **The Age**
   - Latest: https://www.theage.com.au/rss/feed.xml (20 articles)
   - National: https://www.theage.com.au/rss/national.xml (20 articles)

6. **SBS News**
   - Latest: https://www.sbs.com.au/news/feed (24 articles)

7. **9News**
   - National: https://www.9news.com.au/rss (17 articles)

8. **7News**
   - Latest: https://7news.com.au/feed (100 articles)

9. **Brisbane Times**
   - Latest: https://www.brisbanetimes.com.au/rss/feed.xml (20 articles)

10. **WA Today**
    - Latest: https://www.watoday.com.au/rss/feed.xml (20 articles)

11. **Canberra Times**
    - Latest: https://www.canberratimes.com.au/rss.xml (17 articles)

---

## ❌ FAILED RSS FEEDS
- The Australian (Paywall/Premium - XML parsing error)
- NT News (XML parsing error)

---

## 🔌 AVAILABLE APIs

### 1. NewsAPI.org
- **Status**: Free tier available (100 requests/day)
- **Coverage**: Includes Australian sources
- **Documentation**: https://newsapi.org/docs
- **Requires**: API Key (sign up at newsapi.org)
- **Sources Include**:
  - ABC News Australia
  - Various international sources covering Australia
- **Endpoint**: `https://newsapi.org/v2/top-headlines?country=au`

### 2. The Guardian API
- **Status**: Free for non-commercial use
- **Coverage**: Excellent Australian coverage
- **Documentation**: https://open-platform.theguardian.com/
- **Requires**: API Key (free registration)
- **Endpoint**: `https://content.guardianapis.com/search`
- **Features**: 
  - Full article content
  - Rich metadata
  - Historical data access

### 3. GNews API
- **Status**: Free tier (100 requests/day)
- **Coverage**: International + Australian news
- **Documentation**: https://gnews.io/docs/v4
- **Requires**: API Key
- **Endpoint**: `https://gnews.io/api/v4/top-headlines?country=au`

### 4. Currents API
- **Status**: Free tier (600 requests/day)
- **Coverage**: Global news including Australia
- **Documentation**: https://currentsapi.services/en
- **Requires**: API Key
- **Endpoint**: `https://api.currentsapi.services/v1/latest-news?country=AU`

---

## 📊 RECOMMENDED SCRAPING STRATEGY

### For Maximum Coverage:

**RSS Feeds (Primary - No rate limits):**
- ABC News (Just In + Top Stories)
- The Guardian AU (All)
- News.com.au (Breaking News)
- SMH (Latest)
- The Age (Latest)
- SBS News
- 9News
- 7News
- Brisbane Times
- WA Today
- Canberra Times

**APIs (Secondary - For additional coverage):**
- NewsAPI.org (Australian sources)
- The Guardian API (for full content)

### Estimated Total Daily Articles:
- RSS Feeds: ~400-500 articles per scrape
- APIs: ~100-200 additional articles
- **Total: ~600-700 articles per run**

---

## 🎯 NEXT STEPS

1. ✅ Update scrapers to use verified RSS feeds
2. ✅ Remove category filtering - scrape ALL news
3. ✅ Integrate working APIs (optional)
4. Build categorization system (ML/keywords)
5. Implement deduplication
6. Store in MongoDB
