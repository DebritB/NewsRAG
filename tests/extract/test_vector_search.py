"""
Test vector search using existing article embeddings (no Bedrock needed)
"""
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()
MONGODB_URI = os.environ.get('MONGODB_URI')

def test_vector_search():
    """Test vector search by finding similar articles to an existing one"""
    if not MONGODB_URI:
        print("❌ MONGODB_URI not set. Skipping test.")
        return
        
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client['news_rag']
    collection = db['articles']
    sample = collection.find_one(
        {'embedding': {'$exists': True}, 'category': 'sports'},
        {'title': 1, 'embedding': 1, 'category': 1, 'source': 1}
    )
    if not sample:
        print("❌ No articles with embeddings found")
        client.close()
        return
    print("=" * 100)
    print("VECTOR SEARCH TEST")
    print("=" * 100)
    print(f"\n🔍 Finding articles similar to:")
    print(f"   Title: {sample['title']}")
    print(f"   Category: {sample['category']}")
    print(f"   Source: {sample['source']}")
    try:
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": sample['embedding'],
                    "numCandidates": 50,
                    "limit": 5
                }
            },
            {
                "$project": {
                    "title": 1,
                    "source": 1,
                    "category": 1,
                    "url": 1,
                    "summary": 1,
                    "similarity": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        results = list(collection.aggregate(pipeline))
        print(f"\n✅ Found {len(results)} similar articles:\n")
        print("=" * 100)
        for i, article in enumerate(results, 1):
            sim = article.get('similarity', 0)
            title = article.get('title', 'N/A')
            source = article.get('source', 'N/A')
            cat = article.get('category', 'N/A')
            print(f"\n{i}. {title}")
            print(f"   📊 Similarity: {sim:.4f}")
            print(f"   📁 Category: {cat}")
            print(f"   📰 Source: {source}")
            if i == 1 and sim > 0.99:
                print("   ℹ️  (This is the same article we searched with)")
        print("=" * 100)
        if len(results) > 0:
            print("\n✅ Vector search index is WORKING!")
        else:
            print("\n⚠️  No results - index might still be building")
    except Exception as e:
        if "vector_index" in str(e) or "not found" in str(e).lower():
            print("\n❌ Vector index not found or not ready yet")
            print("   Wait a few more minutes for index to finish building")
        else:
            print(f"\n❌ Error: {e}")
    client.close()

if __name__ == "__main__":
    test_vector_search()
