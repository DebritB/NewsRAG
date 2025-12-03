"""
Deletes all articles from the MongoDB collection.
"""
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import os

# --- Configuration ---
load_dotenv()
MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DATABASE = "news_rag"
MONGODB_COLLECTION = "articles"
# ---------------------

def clear_collection():
    """Connects to MongoDB and deletes all documents in the specified collection."""
    print(f"Connecting to MongoDB collection: '{MONGODB_COLLECTION}'...")
    
    if not MONGODB_URI:
        print("❌ MONGODB_URI not set. Skipping.")
        return
        
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        # The ismaster command is cheap and does not require auth.
        client.admin.command('ismaster')
    except ConnectionFailure as e:
        print(f"❌ Could not connect to MongoDB: {e}")
        return

    db = client[MONGODB_DATABASE]
    collection = db[MONGODB_COLLECTION]

    print("Connection successful.")
    
    # Get the count before deleting
    count_before = collection.count_documents({})
    if count_before == 0:
        print("✅ Collection is already empty. No action needed.")
        client.close()
        return

    print(f"Found {count_before} articles. Deleting all of them...")

    # Delete all documents in the collection
    result = collection.delete_many({})
    
    # Verify the deletion
    count_after = collection.count_documents({})
    
    print(f"Deleted {result.deleted_count} documents.")
    print(f"Articles remaining: {count_after}")

    if count_after == 0:
        print("✅ Successfully cleared the collection.")
    else:
        print("❌ Warning: Some documents were not deleted.")
        
    client.close()

if __name__ == "__main__":
    print("="*50)
    print("CLEAR MONGO-DB 'ARTICLES' COLLECTION")
    print("="*50)
    # Confirmation prompt
    confirm = input("Are you sure you want to delete ALL articles? (yes/no): ")
    if confirm.lower() == 'yes':
        clear_collection()
    else:
        print("Operation cancelled.")
    print("="*50)
