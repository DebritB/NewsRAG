"""
Automates the creation of the MongoDB Atlas Vector Search index using pymongo.

This script uses the collection.create_search_index() method available in
recent versions of the pymongo driver, which is simpler than using the Admin API.
"""
import os
import time
import json
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel
from pymongo.errors import ConnectionFailure

# --- Configuration ---
load_dotenv()
MONGODB_URI = os.environ.get("MONGODB_URI")
DATABASE_NAME = "news_rag"
COLLECTION_NAME = "articles"
INDEX_CONFIG_FILE = "vector_search_index_config.json"
# ---------------------

def main():
    """Main function to create the index."""
    print("="*60)
    print("MONGO-DB ATLAS VECTOR INDEX CREATOR (using pymongo)")
    print("="*60)

    if not MONGODB_URI:
        print("❌ Error: MONGODB_URI not found in your .env file.")
        return

    try:
        print("Connecting to MongoDB...")
        client = MongoClient(MONGODB_URI)
        client.admin.command('ping') # Check connection
        print("✅ Connection successful.")
    except ConnectionFailure as e:
        print(f"❌ Could not connect to MongoDB: {e}")
        return

    database = client[DATABASE_NAME]
    collection = database[COLLECTION_NAME]

    # Check if the index already exists
    for index in collection.list_search_indexes():
        if index['name'] == 'vector_index':
            print("ℹ️  Index 'vector_index' already exists. No action needed.")
            client.close()
            return
            
    # Load the index definition from the JSON file
    try:
        with open(INDEX_CONFIG_FILE, 'r') as f:
            index_definition_from_file = json.load(f)
            # The API payload has 'mappings', but the driver model uses 'definition'
            index_definition = index_definition_from_file.get('mappings')

    except FileNotFoundError:
        print(f"❌ Error: Index configuration file not found at '{INDEX_CONFIG_FILE}'")
        client.close()
        return
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ Error parsing index configuration file: {e}")
        client.close()
        return

    # Create the vector search index model
    search_index_model = SearchIndexModel(
        definition=index_definition,
        name="vector_index", # The name from your config file
        type="vectorSearch"
    )

    print(f"Creating search index '{search_index_model.name}'...")
    result = collection.create_search_index(model=search_index_model)
    print(f"✅ Index creation process for '{result}' started.")

    # Wait for the index to become ready
    print("Polling to check if the index is ready. This may take a few minutes...")
    while True:
        try:
            status = list(collection.list_search_indexes(name=result))
            if len(status) and status[0].get('queryable') is True:
                print(f"✅ Index '{result}' is ready for querying.")
                break
            elif len(status) and status[0].get('status') == 'FAILED':
                 print(f"❌ Index '{result}' failed to build. Check the Atlas UI.")
                 break
            print(f"  - Status: {status[0].get('status', 'PENDING')}. Waiting...")
            time.sleep(10)
        except Exception as e:
            print(f"An error occurred while polling for index status: {e}")
            break

    client.close()
    print("="*60)

if __name__ == "__main__":
    main()
