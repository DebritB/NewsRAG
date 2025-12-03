# MongoDB Atlas Setup Guide

## 1. Create Vector Search Index

### Step 1: Go to MongoDB Atlas UI
1. Navigate to your cluster: `clusterdb.dxlwsol.mongodb.net`
2. Click **Search** tab
3. Click **Create Search Index**
4. Select **JSON Editor**

### Step 2: Create Index Configuration
```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "embedding": {
        "type": "knnVector",
        "dimensions": 1024,
        "similarity": "cosine"
      },
      "source": {
        "type": "string"
      },
      "published_at": {
        "type": "date"
      },
      "category": {
        "type": "string"
      },
      "deduplicated": {
        "type": "boolean"
      }
    }
  }
}
```

### Step 3: Name and Create
- **Index Name:** `vector_index`
- **Database:** `newsrag`
- **Collection:** `articles`
- Click **Create Search Index**

**Note:** Index creation takes 5-10 minutes

---

## 2. Create Deduplication Trigger

### Step 1: Go to Triggers
1. In MongoDB Atlas UI, click **Triggers** (left sidebar)
2. Click **Add Trigger**

### Step 2: Configure Trigger
- **Trigger Type:** Scheduled
- **Name:** `deduplicate_articles`
- **Schedule Type:** Custom
- **Schedule (CRON):** `*/30 * * * *` (every 30 minutes)
- **Function:** Select "New Function"

### Step 3: Paste Function Code
Copy the entire content from `mongodb_dedup_trigger.js` and paste it into the function editor.

### Step 4: Link Data Source
- **Cluster:** Select your cluster
- **Service Name:** `mongodb-atlas`

### Step 5: Save and Enable
- Click **Save**
- Toggle **Enabled** to ON

---

## 3. Verify Setup

### Check Vector Search Index Status
```javascript
// Run in MongoDB Shell or Compass
db.articles.getSearchIndexes()
```

Should show status: `READY`

### Test Vector Search
```javascript
// Find similar articles (replace with actual embedding)
db.articles.aggregate([
  {
    $vectorSearch: {
      queryVector: [0.1, 0.2, ...], // 1024 dimensions
      path: "embedding",
      numCandidates: 100,
      limit: 5,
      index: "vector_index"
    }
  },
  {
    $project: {
      title: 1,
      source: 1,
      similarity: { $meta: "vectorSearchScore" }
    }
  }
])
```

### Monitor Trigger Execution
1. Go to **Triggers** → `deduplicate_articles`
2. Click **Logs** tab
3. Check execution history and console logs

---

## 4. Expected Behavior

### After Lambda Runs (Every 12 Hours):
1. Lambda scrapes ~300 articles
2. Generates embeddings via Bedrock
3. Inserts to MongoDB with `deduplicated: false`

### After Trigger Runs (Every 30 Minutes):
1. Finds unprocessed articles (`deduplicated: false`)
2. Performs vector search for each article
3. Groups articles with >85% similarity
4. Keeps best article, adds `source_list` and `occurrence_count`
5. Deletes duplicates
6. Marks all as `deduplicated: true`

### Example Output in MongoDB:
```json
{
  "_id": ObjectId("..."),
  "title": "Police bust satanic paedophile ring",
  "source": "abc_news",
  "source_list": ["abc_news", "7news", "smh"],
  "occurrence_count": 3,
  "embedding": [0.1, 0.2, ...],
  "deduplicated": true,
  "deduplicated_at": ISODate("2025-12-02T10:30:00Z")
}
```

---

## 5. Monitoring

### Check Deduplication Stats
```javascript
// Count deduplicated articles
db.articles.countDocuments({ deduplicated: true })

// Count multi-source articles
db.articles.countDocuments({ occurrence_count: { $gt: 1 } })

// View multi-source examples
db.articles.find(
  { occurrence_count: { $gt: 1 } },
  { title: 1, source_list: 1, occurrence_count: 1 }
).limit(10)
```

### Trigger Logs
- Go to Atlas UI → Triggers → deduplicate_articles → Logs
- Check for errors or processing stats

---

## 6. Cost

- **M0 Free Tier:** ✅ Supports Vector Search
- **Vector Search Operations:** 100/hour included (plenty for your use case)
- **Trigger Execution:** Free on M0 tier
- **Total MongoDB Cost:** $0/month 🎉

---

## Troubleshooting

### If vector search returns no results:
1. Check index status: `db.articles.getSearchIndexes()`
2. Wait 5-10 minutes for index to build
3. Verify embeddings exist: `db.articles.findOne({}, {embedding: 1})`
4. Check embedding dimensions: should be 1024

### If trigger doesn't run:
1. Check trigger is **Enabled**
2. View logs for errors
3. Verify cluster connection string is correct
4. Test function manually: Triggers → deduplicate_articles → Run

### If duplicates not removed:
1. Check similarity threshold (currently 85%)
2. Lower to 80% if too strict: `similarity: { $gte: 0.80 }`
3. Check source filtering is working
4. Verify embeddings are different between sources
