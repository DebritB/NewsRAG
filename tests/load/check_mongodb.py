"""
Check MongoDB articles
"""
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()
uri = os.environ.get('MONGODB_URI')

if uri is None:
    raise ValueError("No MongoDB URI found in environment variables.")

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
db = client['news_rag']
collection = db['articles']
total = collection.count_documents({})
print(f"📊 Total articles: {total}")
for category in ['sports', 'music', 'finance', 'lifestyle', 'other']:
    count = collection.count_documents({'category': category})
    print(f"  - {category}: {count}")
client.close()
