"""
AWS Lambda handler for managing the MongoDB Vector Search Index.

This function can operate in two modes, determined by the 'mode' key
in the input event:
1. 'check': Checks if the 'vector_index' exists and returns a boolean.
2. 'create': Creates the 'vector_index' and polls until it is active.
"""
import os
import time
import json
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel
from pymongo.errors import ConnectionFailure

# --- Configuration ---
MONGODB_URI = os.environ.get("MONGODB_URI")
DATABASE_NAME = os.environ.get("MONGODB_DATABASE", "news_rag")
COLLECTION_NAME = os.environ.get("MONGODB_COLLECTION", "articles")
# The index config will be packaged with the Lambda
INDEX_CONFIG_FILE = "vector_search_index_config.json" 
# ---------------------

def check_index(collection):
    """Checks if the vector search index exists."""
    for index in collection.list_search_indexes():
        if index['name'] == 'vector_index':
            print("✅ Index 'vector_index' already exists.")
            return True
    print("ℹ️  Index 'vector_index' does not exist.")
    return False

def create_index(collection):
    """Creates the vector search index and waits for it to be ready."""
    # Load the index definition from the packaged JSON file
    try:
        with open(INDEX_CONFIG_FILE, 'r') as f:
            index_definition_from_file = json.load(f)
            index_definition = index_definition_from_file.get('mappings')
        
        if not index_definition:
             raise KeyError("'mappings' key not found in index configuration.")

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"❌ Error parsing index configuration file: {e}")
        raise ValueError(f"Could not load index definition from {INDEX_CONFIG_FILE}") from e

    # Create the search index model
    search_index_model = SearchIndexModel(
        definition=index_definition,
        name="vector_index",
        type="vectorSearch"
    )

    # The name is defined in the model above, so we can use it directly in the log.
    print(f"Creating search index 'vector_index'...")
    result_name = collection.create_search_index(model=search_index_model)
    print(f"✅ Index creation process for '{result_name}' started.")

    # Poll until the index is ready
    print("Polling to check if the index is ready. This may take a few minutes...")
    while True:
        status = list(collection.list_search_indexes(name=result_name))
        if len(status):
            current_status = status[0].get('status', 'PENDING')
            if status[0].get('queryable') is True:
                print(f"✅ Index '{result_name}' is ready for querying.")
                return True
            elif current_status == 'FAILED':
                print(f"❌ Index '{result_name}' failed to build. Check the Atlas UI.")
                raise Exception(f"Index creation failed for {result_name}")
            print(f"  - Status: {current_status}. Waiting...")
        else:
            print("  - Waiting for index status to become available...")
        
        time.sleep(15) # Wait 15 seconds between polls

def lambda_handler(event, context):
    """
    Lambda handler for the Index Manager.
    
    :param event: A dict containing a 'mode' key ('check' or 'create').
    :return: A dict with the result of the operation.
    """
    mode = event.get('mode', 'check') # Default to 'check'
    print(f"--- Index Manager Lambda ---")
    print(f"  - Operation Mode: {mode}")
    
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI environment variable not set.")

    try:
        client = MongoClient(MONGODB_URI)
        database = client[DATABASE_NAME]
        collection = database[COLLECTION_NAME]
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        raise

    if mode == 'check':
        index_exists = check_index(collection)
        client.close()
        return {'indexExists': index_exists}
    
    elif mode == 'create':
        if not check_index(collection):
            create_index(collection)
        else:
            print("Index already existed, no creation needed.")
        client.close()
        return {'status': 'Completed'}
        
    else:
        client.close()
        raise ValueError(f"Invalid mode '{mode}'. Must be 'check' or 'create'.")
