"""
AWS Lambda handler for deduplicating articles in MongoDB.

This function connects to MongoDB and uses a vector search index to find
and consolidate duplicate articles based on semantic similarity.
"""
import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from collections import defaultdict
import re

# --- Configuration ---
MONGODB_URI = os.environ.get('MONGODB_URI')
MONGODB_DATABASE = os.environ.get('MONGODB_DATABASE', 'news_rag')
MONGODB_COLLECTION = os.environ.get('MONGODB_COLLECTION', 'articles')
SIMILARITY_THRESHOLD = 0.85  # 85% similarity = same story

# --- Highlight Logic ---
HIGHLIGHT_KEYWORDS = [
    'breaking', 'alert', 'exclusive', 'just in', 'major', 'urgent'
]
KEYWORD_WEIGHT = 0.6
FREQUENCY_WEIGHT = 0.4
HIGHLIGHT_COUNT = 5

def calculate_highlight_score(article):
    """Calculates a highlight score for an article."""
    score = 0
    
    # Keyword score
    title = (article.get('title') or '').lower()
    summary = (article.get('summary') or '').lower()
    content = f"{title} {summary}"
    
    keyword_hits = sum(1 for keyword in HIGHLIGHT_KEYWORDS if re.search(r'\b' + keyword + r'\b', content))
    if keyword_hits > 0:
        score += KEYWORD_WEIGHT
        
    # Frequency score
    frequency = article.get('occurrence_count', 1)
    # Normalize frequency (simple normalization, can be improved)
    normalized_freq = min(frequency / 10.0, 1.0) # Cap at 10 occurrences
    score += normalized_freq * FREQUENCY_WEIGHT
    
    return score

def update_highlights(collection):
    """Identifies and flags top 5 articles per category as highlights."""
    print("--- Updating Highlights ---")
    
    # 1. Fetch all articles from the last 48 hours
    cutoff_date = datetime.utcnow() - timedelta(days=2)
    query = {"published_date": {"$gte": cutoff_date.isoformat()}}
    articles = list(collection.find(query))
    
    if not articles:
        print("No recent articles found to highlight.")
        return 0, 0
        
    # 2. Group by category
    categorized_articles = defaultdict(list)
    for article in articles:
        category = article.get('category', 'Uncategorized')
        categorized_articles[category].append(article)
        
    highlighted_ids = set()
    
    # 3. Calculate scores and identify top 5 in each category
    for category, articles_in_cat in categorized_articles.items():
        for article in articles_in_cat:
            article['highlight_score'] = calculate_highlight_score(article)
            
        sorted_articles = sorted(articles_in_cat, key=lambda x: x['highlight_score'], reverse=True)
        top_5 = sorted_articles[:HIGHLIGHT_COUNT]
        
        for article in top_5:
            highlighted_ids.add(article['_id'])
            
    # 4. Update database
    # Reset all recent articles to highlight: false
    reset_result = collection.update_many(
        query,
        {'$set': {'highlight': False}}
    )
    
    # Set highlight: true for the top 5 in each category
    update_result = collection.update_many(
        {'_id': {'$in': list(highlighted_ids)}},
        {'$set': {'highlight': True}}
    )
    
    print(f"Reset highlights for {reset_result.modified_count} articles.")
    print(f"Set {update_result.modified_count} articles as new highlights.")
    
    return reset_result.modified_count, update_result.modified_count

# --- Main Deduplication Logic ---
def deduplicate_articles():
    """Finds and consolidates duplicate articles in the collection."""
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI environment variable not set.")

    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DATABASE]
    collection = db[MONGODB_COLLECTION]
    
    # Get all articles that have embeddings and haven't been checked before
    articles_to_check = list(collection.find(
        {'embedding': {'$exists': True, '$ne': None}},
        {'_id': 1, 'title': 1, 'source': 1, 'embedding': 1}
    ))
    
    print(f"Checking {len(articles_to_check)} articles for duplicates...")
    
    duplicates_found = 0
    duplicates_removed = 0
    
    for article in articles_to_check:
        # Check if the article still exists (it might have been removed as a duplicate)
        if collection.count_documents({'_id': article['_id']}) == 0:
            continue
            
        # Perform vector search to find similar articles
        pipeline = [
            {"$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": article['embedding'],
                "numCandidates": 100,
                "limit": 10
            }},
            {"$project": {
                "_id": 1,
                "source": 1,
                "title": 1,
                "similarity": {"$meta": "vectorSearchScore"}
            }},
            {"$match": {
                "similarity": {"$gte": SIMILARITY_THRESHOLD},
                "_id": {"$ne": article['_id']}  # Exclude the article itself
            }}
        ]
        
        similar_articles = list(collection.aggregate(pipeline))
        
        if similar_articles:
            duplicates_found += len(similar_articles)
            
            # Combine all sources into the main article
            original_sources = {article['source']}
            for sim in similar_articles:
                original_sources.add(sim['source'])
            
            print(f"Found {len(similar_articles)} duplicates for: '{article['title'][:70]}...'")
            
            collection.update_one(
                {'_id': article['_id']},
                {'$set': {
                    'source_list': list(original_sources),
                    'occurrence_count': len(original_sources),
                    'deduplicated_at': datetime.utcnow()
                }}
            )
            
            # Remove the duplicate articles
            duplicate_ids = [s['_id'] for s in similar_articles]
            result = collection.delete_many({'_id': {'$in': duplicate_ids}})
            duplicates_removed += result.deleted_count
    
    client.close()
    
    summary = {
        "articles_checked": len(articles_to_check),
        "duplicate_groups_found": duplicates_found,
        "articles_removed": duplicates_removed
    }
    print(f"Deduplication summary: {summary}")
    return summary

def lambda_handler(event, context):
    """Lambda handler for the deduplicator."""
    print("--- Deduplicator Lambda ---")
    try:
        dedup_result = deduplicate_articles()
        
        # --- Run Highlight Logic After Deduplication ---
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DATABASE]
        collection = db[MONGODB_COLLECTION]
        _, highlights_set = update_highlights(collection)
        client.close()
        # ---------------------------------------------

        final_result = {
            "deduplication": dedup_result,
            "highlights_updated": highlights_set
        }
        
        return {
            'statusCode': 200,
            'body': final_result
        }
    except Exception as e:
        print(f"❌ An error occurred during deduplication: {e}")
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }
