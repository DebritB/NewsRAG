"""
A Streamlit web application to display the daily news highlights from the NewsRAG database.
"""
import streamlit as st
from pymongo import MongoClient
import os
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dotenv import load_dotenv
import pandas as pd
import matplotlib.pyplot as plt
import requests
import json

# --- Database Connection ---
def get_database_connection():
    """Connects to MongoDB and returns the articles collection."""
    load_dotenv()
    mongodb_uri = st.secrets.get('MONGODB_URI')
    if not mongodb_uri:
        st.error("MONGODB_URI not found in secrets or environment variables. Cannot connect to the database.")
        st.stop()
    
    client = MongoClient(mongodb_uri)
    db = client["news_rag"]
    return db["articles"]

# --- Data Fetching ---
@st.cache_data(ttl=600)  # Cache data for 10 minutes
def get_articles(_collection):
    """Fetches and processes all news articles."""
    
    # Fetch raw articles for the "News" view
    query = {}
    sort_order = [("occurrence_count", -1), ("published_at", -1)]
    articles = list(_collection.find(query).sort(sort_order))
    
    # Group articles by category
    categorized_articles = defaultdict(list)
    for article in articles:
        category = article.get("category", "Uncategorized")
        categorized_articles[category].append(article)
        
    return categorized_articles


# --- Streamlit UI ---
st.set_page_config(page_title="NewsRAG", layout="wide")
st.title("News247 - Daily News Highlights")

# --- Main Application ---
collection = get_database_connection()
articles = get_articles(collection)

# Dropdown for selecting view
view = st.sidebar.selectbox("Select View", ["News", "Atlas Dashboard", "Chat"])

# --- NEWS VIEW ---
if view == "News":
    st.markdown("Displaying all news stories, grouped by category.")
    
    if not articles:
        st.warning("No recent articles found in the database.")
    else:
        st.subheader("Browse by Category")
        categories = sorted(articles.keys())
        tabs = st.tabs(categories)
        
        for i, category in enumerate(categories):
            with tabs[i]:
                st.subheader(f"News in {category.capitalize()}")
                articles_in_category = articles[category]

                if not articles_in_category:
                    st.info("No articles found for this category.")
                    continue

                highlights = [a for a in articles_in_category if a.get('highlight', False)]
                other_articles = [a for a in articles_in_category if not a.get('highlight', False)]
                
                # --- HIGHLIGHTS ---
                if highlights:
                    st.markdown("### BREAKING NEWS")
                    st.markdown("---")
                    for article in highlights:
                        title = article.get("title", "No Title")
                        url = article.get("url", "#")
                        authors = article.get("authors", []) or ([article.get("author")] if article.get("author") else [])
                        author_str = ", ".join(authors) if authors else "Unknown"
                        
                        st.markdown(f"### **{title}**")
                        cols = st.columns([2, 1, 1])

                        sources = article.get("source_list", [article.get("source", "N/A")])
                        cols[0].markdown(f"**[Source(s):]({url})** {', '.join(sources)}")
                        cols[1].markdown(f"**Frequency:** `{article.get('occurrence_count', 1)}`")
                        cols[2].markdown(f"**Author(s):** `{author_str}`")

                        st.markdown("---")

                # --- OTHER NEWS ---
                if other_articles:
                    st.markdown("### Other News")
                    st.markdown("---")
                    for article in other_articles:
                        title = article.get("title", "No Title")
                        url = article.get("url", "#")
                        authors = article.get("authors", []) or ([article.get("author")] if article.get("author") else [])
                        author_str = ", ".join(authors) if authors else "Unknown"

                        st.markdown(f"#### {title}")
                        cols = st.columns([2, 1, 1])

                        sources = article.get("source_list", [article.get("source", "N/A")])
                        cols[0].markdown(f"**[Source(s):]({url})** {', '.join(sources)}")
                        cols[1].markdown(f"**Frequency:** `{article.get('occurrence_count', 1)}`")
                        cols[2].markdown(f"**Author(s):** `{author_str}`")

                        st.markdown("---")


# --- ATLAS DASHBOARD VIEW ---
elif view == "Atlas Dashboard":
    st.markdown("Live Dashboard")

    atlas_chart_url = st.secrets.get('MONGODB_DASHBOARD_URL') 
    
    if not atlas_chart_url:
        st.error("Dashboard URL not found.")
    else:
        st.components.v1.iframe(atlas_chart_url, height=1000, scrolling=True)


# --- CHATBOT VIEW ---
elif view == "Chat":
    st.markdown("### News Chatbot")
    st.write("Ask me anything about the latest news!")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask about news..."):

        # Store user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Call AWS Lambda
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    api_url = st.secrets.get('AWS_API_URL')

                    response = requests.post(
                        api_url,
                        data=json.dumps({"query": prompt}),
                        headers={"Content-Type": "application/json"},
                        timeout=30
                    )

                    if response.status_code == 200:
                        response_data = response.json()

                        # Extract ONLY the "response" field
                        if "response" in response_data:
                            bot_response = response_data["response"]

                        elif "body" in response_data:
                            inner_json = json.loads(response_data["body"])
                            bot_response = inner_json.get(
                                "response",
                                "Sorry, I couldn't parse the response."
                            )

                        else:
                            bot_response = "Sorry, I couldn't understand the server response."

                    else:
                        bot_response = f"Error: {response.status_code} - {response.text}"

                except Exception as e:
                    bot_response = f"An error occurred: {str(e)}"

                # Display clean final answer only
                st.markdown(bot_response)

        # Save assistant message
        st.session_state.messages.append({"role": "assistant", "content": bot_response})
