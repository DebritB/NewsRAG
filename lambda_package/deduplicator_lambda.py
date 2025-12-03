"""
AWS Lambda handler for deduplicating articles in MongoDB.

This function connects to MongoDB and uses a vector search index to find
and consolidate duplicate articles based on semantic similarity.
"""
import os
from datetime import datetime
from pymongo import MongoClient

# --- Configuration ---
MONGODB_URI = os.environ.get('MONGODB_URI')
MONGODB_DATABASE = os.environ.get('MONGODB_DATABASE', 'news_rag')
MONGODB_COLLECTION = os.environ.get('MONGODB_COLLECTION', 'articles')
SIMILARITY_THRESHOLD = 0.85  # 85% similarity = same story
# ---------------------

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
        result = deduplicate_articles()
        return {
            'statusCode': 200,
            'body': result
        }
    except Exception as e:
        print(f"❌ An error occurred during deduplication: {e}")
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }
