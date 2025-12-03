"""
RAG Search - Query articles using MongoDB Vector Search
"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from bedrock_embeddings import BedrockEmbeddings
import json

load_dotenv()
MONGODB_URI = os.environ.get('MONGODB_URI')

def rag_search(query: str, category: str = None, limit: int = 5):
    """
    Search articles using vector similarity (RAG)
    
    Args:
        query: Natural language query
        category: Optional filter (sports/music/finance/lifestyle)
        limit: Number of results
    """
    print(f"\n🔍 Query: '{query}'")
    if category:
        print(f"📁 Category: {category}")
    
    # Generate query embedding
    embeddings = BedrockEmbeddings(region_name='us-east-1')
    query_embedding = embeddings.generate_embedding(query)
    
    if not query_embedding:
        print("❌ Could not generate embedding")
        return []
    
    # MongoDB vector search
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client['news_rag']
    collection = db['articles']
    
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 100,
                "limit": limit
            }
        },
        {
            "$project": {
                "title": 1,
                "summary": 1,
                "source": 1,
                "url": 1,
                "category": 1,
                "source_list": 1,
                "occurrence_count": 1,
                "similarity": {"$meta": "vectorSearchScore"}
            }
        }
    ]
    
    if category:
        pipeline.insert(1, {"$match": {"category": category}})
    
    results = list(collection.aggregate(pipeline))
    client.close()
    
    # Display results
    print(f"\n✅ Found {len(results)} results:\n")
    print("=" * 100)
    
    for i, article in enumerate(results, 1):
        sim = article.get('similarity', 0)
        title = article.get('title', 'N/A')
        sources = article.get('source_list', [article.get('source')])
        count = article.get('occurrence_count', 1)
        cat = article.get('category', 'N/A')
        summary = article.get('summary', 'N/A')[:150]
        
        print(f"\n{i}. {title}")
        print(f"   📊 Similarity: {sim:.4f}")
        print(f"   📁 Category: {cat}")
        print(f"   📰 Sources ({count}): {', '.join(sources)}")
        print(f"   📝 {summary}...")
        print(f"   🔗 {article.get('url', 'N/A')}")
    
    print("=" * 100)
    return results


if __name__ == "__main__":
    # Test queries
    print("\n" + "="*100)
    print("RAG SEARCH TEST")
    print("="*100)
    
    rag_search("AFL grand final", category="sports", limit=3)
    rag_search("Bitcoin cryptocurrency", category="finance", limit=3)
    rag_search("Taylor Swift", category="music", limit=3)
