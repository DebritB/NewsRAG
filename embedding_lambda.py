"""
AWS Lambda handler dedicated to generating vector embeddings.

This function queries MongoDB for articles marked with 'embedding_status': 'pending',
generates embeddings for them using Amazon Bedrock, and updates their status.
"""
import os
import time
from pymongo import MongoClient
from bedrock_embeddings import BedrockEmbeddings, BedrockThrottlingError # Assumes this is in the lambda_package

# --- Configuration ---
MONGODB_URI = os.environ.get('MONGODB_URI')
MONGODB_DATABASE = os.environ.get('MONGODB_DATABASE', 'news_rag')
MONGODB_COLLECTION = os.environ.get('MONGODB_COLLECTION', 'articles')
EMBEDDING_MAX_RETRY_COUNT = int(os.environ.get('EMBEDDING_MAX_RETRY_COUNT', '3'))
# ---------------------

def generate_embeddings_for_pending():
    """
    Finds articles pending embedding, generates the embeddings,
    and updates them in MongoDB.

    New behavior:
    - On Bedrock throttling, mark article back to 'pending' and increment a retry counter.
    - Abort processing early when persistent throttling is detected to avoid further throttles.
    """
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI environment variable not set.")

    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DATABASE]
    collection = db[MONGODB_COLLECTION]
    
    # Find articles that need embedding
    pending_articles = list(collection.find(
        {'embedding_status': 'pending'},
        {'_id': 1, 'title': 1, 'summary': 1, 'content': 1, 'embedding_retry_count': 1}
    ))
    
    if not pending_articles:
        print("✅ No articles are pending embedding. Exiting.")
        client.close()
        return {"articles_processed": 0}

    print(f"Found {len(pending_articles)} articles pending embedding. Starting generation...")
    
    embeddings_generator = BedrockEmbeddings(region_name='us-east-1')
    processed_count = 0
    
    for i, article in enumerate(pending_articles):
        try:
            # Add a small delay to respect API rate limits
            if i > 0:
                # Slightly larger default sleep to reduce chance of throttling
                time.sleep(2.5)

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
                },
                 '$unset': {'embedding_error': ''},
                 '$setOnInsert': {'embedding_retry_count': 0}}
            )
            processed_count += 1
            if (processed_count % 25) == 0:
                print(f"  - Processed {processed_count}/{len(pending_articles)} articles...")

        except BedrockThrottlingError as e:
            print(f"⚠️ Bedrock throttling encountered for article {article['_id']}: {e}")

            # Increment retry counter and re-queue the article
            result = collection.update_one(
                {'_id': article['_id']},
                {
                    '$inc': {'embedding_retry_count': 1},
                    '$set': {'embedding_status': 'pending', 'embedding_error': 'Throttled: will retry later'}
                }
            )

            # If we've retried too many times, mark as failed
            current_retries = (article.get('embedding_retry_count') or 0) + 1
            if current_retries >= EMBEDDING_MAX_RETRY_COUNT:
                collection.update_one(
                    {'_id': article['_id']},
                    {'$set': {'embedding_status': 'failed', 'embedding_error': 'Throttling persisted after retries'}}
                )
                print(f"❌ Article {article['_id']} marked failed after {current_retries} throttling attempts.")

            # Abort further processing to avoid worsening the throttle
            print("Aborting embedding run due to throttling. Will resume later.")
            break

        except Exception as e:
            print(f"❌ Error generating embedding for article {article['_id']}: {e}")
            # Mark the article as failed so we don't retry it indefinitely
            collection.update_one(
                {'_id': article['_id']},
                {'$set': {'embedding_status': 'failed', 'embedding_error': str(e)}}
            )
            continue # Continue to the next article

    client.close()
    
    summary = {"articles_processed": processed_count, "articles_found": len(pending_articles)}
    print(f"Embedding generation complete. Summary: {summary}")
    return summary

def lambda_handler(event, context):
    """Lambda handler for the embedding generator."""
    print("--- Embedding Generator Lambda ---")
    try:
        result = generate_embeddings_for_pending()
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
