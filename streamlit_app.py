"""
A Streamlit web application for performing vector search on the NewsRAG database.
"""
import streamlit as st
from pymongo import MongoClient
import os
import boto3

# --- AWS Bedrock Client ---
# It's good practice to initialize this once
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')

def get_embedding(text):
    """Generates an embedding for the given text using Amazon Titan."""
    body = f'{{"inputText": "{text}"}}'
    response = bedrock_client.invoke_model(
        body=body,
        modelId='amazon.titan-embed-text-v2:0',
        accept='application/json',
        contentType='application/json'
    )
    response_body = response['body'].read().decode('utf-8')
    # Simple parsing, assuming valid JSON
    embedding = eval(response_body)['embedding']
    return embedding

# --- Streamlit UI ---
st.set_page_config(page_title="NewsRAG Search", layout="wide")
st.title("📰 NewsRAG: Vector Search")
st.markdown("Search for news articles based on semantic similarity using a vector search index in MongoDB Atlas.")

# Get MongoDB URI from environment variable
# For local development, it will be loaded from the .env file
from dotenv import load_dotenv
load_dotenv()
MONGODB_URI = os.environ.get('MONGODB_URI')
DATABASE_NAME = "news_rag"
COLLECTION_NAME = "articles"

# User input
search_query = st.text_input("Enter your search query:", "latest developments in artificial intelligence")

if st.button("Search"):
    if not MONGODB_URI:
        st.error("MONGODB_URI environment variable not set. Please create a .env file.")
    elif not search_query:
        st.warning("Please enter a search query.")
    else:
        try:
            with st.spinner("Connecting to database and generating embedding..."):
                # Connect to MongoDB
                client = MongoClient(MONGODB_URI)
                db = client[DATABASE_NAME]
                collection = db[COLLECTION_NAME]

                # Generate embedding for the user's query
                query_embedding = get_embedding(search_query)
                st.success("Embedding generated successfully!")

            with st.spinner("Performing vector search..."):
                # Define the vector search pipeline
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": "vector_index",
                            "path": "embedding",
                            "queryVector": query_embedding,
                            "numCandidates": 150,
                            "limit": 5
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "title": 1,
                            "url": 1,
                            "source": 1,
                            "category": 1,
                            "published_at": 1,
                            "score": {
                                "$meta": "vectorSearchScore"
                            }
                        }
                    }
                ]

                # Execute the search
                results = list(collection.aggregate(pipeline))

            st.subheader("Search Results")
            if results:
                for result in results:
                    st.markdown(f"#### [{result['title']}]({result['url']})")
                    st.caption(f"Source: {result['source']} | Category: {result['category']} | Similarity Score: {result['score']:.4f}")
                    st.markdown("---")
            else:
                st.info("No matching articles found.")
        
        except Exception as e:
            st.error(f"An error occurred: {e}")
