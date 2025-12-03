"""
local_lambda_tester.py
Mimics the NewsRAG Lambda cleanup logic locally.
- Inserts dummy articles with dates from last week into MongoDB
- Runs the same rolling window deletion logic
- Prints before/after counts and deleted articles
"""
import random
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()
# Set environment variables from .env file
MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DATABASE = "news_rag"
MONGODB_COLLECTION = "articles"

if not MONGODB_URI:
    raise ValueError("MONGODB_URI not found in .env file. Please set it.")

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
db = client[MONGODB_DATABASE]
collection = db[MONGODB_COLLECTION]

# Insert dummy articles from last week
print("Inserting dummy articles...")
for i in range(7):
    pub_date = (datetime.utcnow().date() - timedelta(days=i+2))  # 2 to 8 days ago
    pub_datetime = datetime.combine(pub_date, datetime.min.time())
    article = {
        "title": f"Dummy Article {i+1}",
        "published_at": pub_datetime,
        "content": f"This is dummy content for article {i+1}.",
        "category": random.choice(["politics", "business", "sports", "other"])
    }
    collection.insert_one(article)
print("Dummy articles inserted.")

# Show count before deletion
count_before = collection.count_documents({})
print(f"Total articles before cleanup: {count_before}")

# Run rolling window deletion logic (same as Lambda)
today = datetime.utcnow().date()
yesterday = today - timedelta(days=1)
cutoff = datetime.combine(yesterday, datetime.min.time())
result = collection.delete_many({"published_at": {"$lt": cutoff}})
print(f"Deleted {result.deleted_count} articles older than {cutoff}")

# Show count after deletion
count_after = collection.count_documents({})
print(f"Total articles after cleanup: {count_after}")

client.close()
