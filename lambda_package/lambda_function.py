"""
AWS Lambda handler for NewsRAG scraper
Hybrid classification: TF-IDF keywords first, Claude for low-confidence articles
"""

import json
import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
import time
from scrape_news import NewsAggregator
from bedrock_embeddings import BedrockEmbeddings
from keyword_classifier import KeywordClassifier

# MongoDB imports (will be installed via requirements.txt)
try:
    from pymongo import MongoClient, errors
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    print("WARNING: pymongo not available")

# Configuration from environment variables
MONGODB_URI = os.environ.get('MONGODB_URI')
MONGODB_DATABASE = os.environ.get('MONGODB_DATABASE', 'news_rag')
MONGODB_COLLECTION = os.environ.get('MONGODB_COLLECTION', 'articles')
CONFIDENCE_THRESHOLD = 0.15  # Articles below this need Claude classification

def get_secrets():
    """Retrieve API keys from AWS Secrets Manager"""
    secret_name = "newsrag/api-keys"
    region_name = "us-east-1"
    
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = json.loads(get_secret_value_response['SecretString'])
        print("Successfully retrieved API keys from AWS Secrets Manager")
        return secret
    except ClientError as e:
        print(f"Error retrieving secrets: {e}")
        return {}

def lambda_handler(event, context):
    """
    AWS Lambda handler - Scrapes and Classifies articles.
    1. Scrape articles
    2. Use TF-IDF keyword classifier
    3. Use Claude for low-confidence articles
    4. Store classified articles to MongoDB with 'embedding_status': 'pending'
    """
    
    try:
        print("=== NEWSRAG SCRAPE AND CLASSIFY HANDLER ===")
        
        # ... (Validate MongoDB config and get secrets - no changes here)
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI environment variable not set")
        if not PYMONGO_AVAILABLE:
            raise ImportError("pymongo package not installed")
        secrets = get_secrets()
        for key, value in secrets.items():
            os.environ[key] = value
        
        # Cleanup: Remove articles older than yesterday
        print("Cleaning up old articles...")
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        cutoff = datetime.combine(yesterday, datetime.min.time())
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGODB_DATABASE]
        collection = db[MONGODB_COLLECTION]
        deleted = collection.delete_many({"published_at": {"$lt": cutoff}}).deleted_count
        print(f"Deleted {deleted} old articles (before {cutoff})")
        
        # Scrape articles
        print("Starting news scraping...")
        aggregator = NewsAggregator()
        articles = aggregator.scrape_all(max_per_source=200)
        print(f"Successfully scraped {len(articles)} articles")

        if not articles:
            client.close()
            return {'statusCode': 200, 'body': json.dumps({'message': 'No articles scraped'})}
        
        # --- Classification Step ---
        print(f"Classifying {len(articles)} articles...")
        keyword_classifier = KeywordClassifier()
        embeddings_generator = BedrockEmbeddings(region_name='us-east-1')
        
        high_confidence_articles = []
        low_confidence_articles = []
        
        for article in articles:
            # Classify using the TF-IDF model first
            category, confidence = keyword_classifier.classify(
                title=article.title or "", content=article.content or "", summary=article.summary or ""
            )

            if confidence >= 0.5:  # High confidence
                article.category = category
                article.confidence = confidence
                high_confidence_articles.append(article)
                print(f"✅ Classified '{article.title[:30]}...' as '{category}' with high confidence ({confidence:.2f})")
            
            elif 0.3 <= confidence < 0.5:  # Close miss, send to Claude
                article.confidence = confidence # Keep original confidence for logging
                low_confidence_articles.append(article)
                print(f"⚠️ Close miss for '{article.title[:30]}...' ({confidence:.2f}). Needs Claude classification.")
            
            else:  # Low confidence, ignore article
                print(f"❌ Low confidence for '{article.title[:30]}...' ({confidence:.2f}). Ignoring article.")
                # The article is simply dropped from the pipeline and not added to any list
        
        print(f"\n--- Classification Summary ---")
        print(f"High-Confidence (TF-IDF only): {len(high_confidence_articles)} articles")
        print(f"Needs Claude (Close Miss): {len(low_confidence_articles)} articles")
        print(f"Ignored (Low Confidence): {len(articles) - len(high_confidence_articles) - len(low_confidence_articles)} articles")
        print(f"---------------------------------\n")

        # --- Process Low-Confidence Articles with Claude ---
        final_classified_articles = list(high_confidence_articles) # Start with the ones we're sure about
        
        if low_confidence_articles:
            print(f"Processing {len(low_confidence_articles)} close-miss articles with Claude...")
            for article in low_confidence_articles:
                try:
                    time.sleep(2) # Rate limit
                    content_for_claude = article.summary or article.content[:1000]
                    new_category = embeddings_generator.classify_category(
                        title=article.title, content=content_for_claude
                    )
                    if new_category:
                        article.category = new_category
                        article.confidence = 0.9 # Mark as high confidence after Claude's review
                        final_classified_articles.append(article)
                        print(f"🤖 Claude classified '{article.title[:30]}...' as '{new_category}'")
                    else:
                        print(f"🤔 Claude could not classify '{article.title[:30]}...'. Discarding.")
                except Exception as e:
                    print(f"💥 Error classifying with Claude for '{article.title[:30]}...': {e}")
                    continue # Move to the next article
        
        print(f"\nSuccessfully classified a total of {len(final_classified_articles)} articles.")
        
        # --- Load Step ---
        print(f"Saving {len(final_classified_articles)} articles to MongoDB...")
        inserted_count = 0
        updated_count = 0
        for article in final_classified_articles:
            doc = article.to_dict()
            doc['embedding_status'] = 'pending' # Set status for the next Lambda
            doc['created_at'] = datetime.utcnow()
            
            result = collection.update_one(
                {'url': doc['url']},
                {'$set': doc, '$setOnInsert': {'first_seen': datetime.utcnow()}},
                upsert=True
            )
            if result.upserted_id:
                inserted_count += 1
            elif result.modified_count > 0:
                updated_count += 1
        
        client.close()
        
        print(f"Saved to DB: {inserted_count} new, {updated_count} updated.")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Scrape and classification complete.',
                'articles_scraped': len(articles),
                'articles_classified_and_saved': len(final_classified_articles),
                'inserted': inserted_count,
                'updated': updated_count
            })
        }
            
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        # ... (traceback remains the same)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

if __name__ == "__main__":
    """For local testing"""
    # Load environment variables from .env file for local testing
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check if the variable is loaded
    mongodb_uri = os.environ.get('MONGODB_URI')
    if not mongodb_uri:
        raise ValueError("MONGODB_URI not found in .env file or environment variables.")
    
    result = lambda_handler({}, {})
    print(json.dumps(result, indent=2))

