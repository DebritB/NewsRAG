"""
AWS Lambda handler dedicated to generating vector embeddings.

This function queries MongoDB for articles marked with 'embedding_status': 'pending',
generates embeddings for them using Amazon Bedrock, and updates their status.
"""
import os
import time
from pymongo import MongoClient
from bedrock_embeddings import BedrockEmbeddings # Assumes this is in the lambda_package

# --- Configuration ---
MONGODB_URI = os.environ.get('MONGODB_URI')
MONGODB_DATABASE = os.environ.get('MONGODB_DATABASE', 'news_rag')
MONGODB_COLLECTION = os.environ.get('MONGODB_COLLECTION', 'articles')
# ---------------------

def generate_embeddings_for_pending():
    """
    Finds articles pending embedding, generates the embeddings,
    and updates them in MongoDB.
    """
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI environment variable not set.")

    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DATABASE]
    collection = db[MONGODB_COLLECTION]
    
    # Find a limited set of articles that need embedding
    batch_size = int(os.environ.get('EMBEDDING_BATCH_SIZE', '25'))
    pending_cursor = collection.find(
        {'embedding_status': 'pending'},
        {'_id': 1, 'title': 1, 'summary': 1, 'content': 1, 'embedding_attempts': 1}
    ).limit(batch_size)

    pending_articles = list(pending_cursor)

    if not pending_articles:
        print("✅ No articles are pending embedding. Exiting.")
        client.close()
        return {"articles_processed": 0}

    print(f"Found {len(pending_articles)} articles pending embedding (batch_size={batch_size}). Starting generation...")
    
    embeddings_generator = BedrockEmbeddings(region_name='us-east-1')
    processed_count = 0
    
    for i, article in enumerate(pending_articles):
        try:
            # Add a small delay to respect API rate limits
            if i > 0:
                time.sleep(1.5)

            # Prepare the text for embedding
            text_to_embed = f"{article.get('title', '')} {article.get('summary', '') or article.get('content', '')[:500]}"
            
            if not text_to_embed.strip():
                print(f"⚠️ Skipping article {article['_id']} due to empty content.")
                collection.update_one(
                    {'_id': article['_id']},
                    {'$set': {'embedding_status': 'failed', 'embedding_error': 'Empty content'}}
                )
                continue

            embedding = embeddings_generator.generate_embedding(text_to_embed)
            
            # Update the document in MongoDB
            collection.update_one(
                {'_id': article['_id']},
                {'$set': {
                    'embedding': embedding,
                    'embedding_status': 'complete'
                }}
            )
            processed_count += 1
            if (processed_count % 25) == 0:
                print(f"  - Processed {processed_count}/{len(pending_articles)} articles...")

        except Exception as e:
            err_text = str(e)
            print(f"❌ Error generating embedding for article {article['_id']}: {err_text}")

            # Increment attempt counter and leave as 'pending' for retry later
            collection.update_one(
                {'_id': article['_id']},
                {'$inc': {'embedding_attempts': 1},
                 '$set': {'last_embedding_error': err_text, 'last_embedding_attempted_at': __import__('datetime').datetime.utcnow()}}
            )

            # If we detect throttling, back off and exit early after a few occurrences to avoid timeout
            if 'throttle' in err_text.lower() or 'throttling' in err_text.lower():
                consecutive_throttle_count += 1
                print(f"⚠️ Bedrock throttling detected ({consecutive_throttle_count}).")
                if consecutive_throttle_count >= 3:
                    print("⚠️ Multiple throttling events detected. Exiting early to allow system to recover.")
                    break
            else:
                # Non-throttling error; continue to next article
                pass

            continue # Continue to the next article

    client.close()
    
    summary = {"articles_processed": processed_count, "articles_found": len(pending_articles)}
    print(f"Embedding generation complete. Summary: {summary}")
    return summary

def lambda_handler(event, context):
    """Lambda handler for the embedding generator."""
    print("--- Embedding Generator Lambda ---")
    try:
        result = generate_embeddings_for_pending(context=context)
        return {
            'statusCode': 200,
            'body': result
        }
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }
