"""
Deduplicate articles using vector similarity
Finds duplicate news from different sources and consolidates them
"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime

load_dotenv()
MONGODB_URI = os.environ.get('MONGODB_URI')
SIMILARITY_THRESHOLD = 0.85  # 85% similarity = same story

def deduplicate_articles():
    """Find and consolidate duplicate articles"""
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI not set.")
        
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client['news_rag']
    collection = db['articles']
    
    # Get all articles with embeddings
    articles = list(collection.find(
        {'embedding': {'$exists': True, '$ne': None}},
        {'_id': 1, 'title': 1, 'source': 1, 'embedding': 1, 'url': 1}
    ))
    
    print(f"📊 Checking {len(articles)} articles for duplicates...")
    print(f"🎯 Similarity threshold: {SIMILARITY_THRESHOLD * 100}%\n")
    
    duplicates_found = 0
    duplicates_removed = 0
    
    for i, article in enumerate(articles):
        # Skip if already processed
        if collection.count_documents({'_id': article['_id']}) == 0:
            continue
        
        # Vector search for similar articles
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": article['embedding'],
                    "numCandidates": 50,
                    "limit": 10
                }
            },
            {
                "$project": {
                    "title": 1,
                    "source": 1,
                    "url": 1,
                    "published_at": 1,
                    "embedding": 1,
                    "similarity": {"$meta": "vectorSearchScore"}
                }
            },
            {
                "$match": {
                    "similarity": {"$gte": SIMILARITY_THRESHOLD},
                    "_id": {"$ne": article['_id']}  # Exclude self
                }
            }
        ]
        
        similar = list(collection.aggregate(pipeline))
        
        if similar:
            duplicates_found += 1
            sources = [article['source']] + [s['source'] for s in similar]
            sources = list(set(sources))  # Remove duplicates
            
            print(f"\n🔍 Duplicate found: {article['title'][:60]}...")
            print(f"   📰 Sources ({len(sources)}): {', '.join(sources)}")
            
            # Update main article with all sources
            collection.update_one(
                {'_id': article['_id']},
                {
                    '$set': {
                        'source_list': sources,
                        'occurrence_count': len(sources),
                        'deduplicated': True,
                        'deduplicated_at': datetime.utcnow()
                    }
                }
            )
            
            # Delete duplicate articles
            duplicate_ids = [s['_id'] for s in similar]
            result = collection.delete_many({'_id': {'$in': duplicate_ids}})
            duplicates_removed += result.deleted_count
            
            print(f"   ✅ Consolidated into 1 article, removed {len(duplicate_ids)} duplicates")
        
        if (i + 1) % 20 == 0:
            print(f"\n⏳ Progress: {i + 1}/{len(articles)} articles checked...")
    
    client.close()
    
    print("\n" + "=" * 80)
    print("DEDUPLICATION COMPLETE")
    print("=" * 80)
    print(f"✅ Duplicate groups found: {duplicates_found}")
    print(f"🗑️  Articles removed: {duplicates_removed}")
    print(f"💾 Articles remaining: {len(articles) - duplicates_removed}")
    print("=" * 80)


if __name__ == "__main__":
    print("=" * 80)
    print("NEWS DEDUPLICATION - Vector Similarity Based")
    print("=" * 80)
    deduplicate_articles()
