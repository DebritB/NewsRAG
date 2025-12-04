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

# --- Database Connection ---
def get_database_connection():
    """Connects to MongoDB and returns the articles collection."""
    load_dotenv()
    mongodb_uri = os.environ.get('MONGODB_URI')
    if not mongodb_uri:
        st.error("MONGODB_URI environment variable not set. Cannot connect to the database.")
        st.stop()
    
    client = MongoClient(mongodb_uri)
    db = client["news_rag"]
    return db["articles"]

# --- Data Fetching ---
@st.cache_data(ttl=600) # Cache data for 10 minutes
def get_articles(_collection):
    """Fetches and processes all news articles."""
    
    # --- Fetch raw articles for the "News" view ---
    query = {}
    sort_order = [("occurrence_count", -1), ("published_at", -1)]
    articles = list(_collection.find(query).sort(sort_order))
    
    # Group articles by category for tabbed display
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

if view == "News":
    st.markdown("Displaying all news stories, grouped by category.")
    
    if not articles:
        st.warning("No recent articles found in the database. The ETL pipeline may be running or there might be no new news.")
    else:
        # --- Category Tabs ---
        st.subheader("Browse by Category")
        # Create a tab for each category
        categories = sorted(articles.keys())
        tabs = st.tabs(categories)
        
        for i, category in enumerate(categories):
            with tabs[i]:
                st.subheader(f"News in {category.capitalize()}")
                
                articles_in_category = articles[category]
                
                if not articles_in_category:
                    st.info("No articles found for this category.")
                    continue

                # Separate highlights and other articles
                highlights = [art for art in articles_in_category if art.get('highlight', False)]
                other_articles = [art for art in articles_in_category if not art.get('highlight', False)]
                
                # Display highlights first
                if highlights:
                    st.markdown("### BREAKING NEWS")
                    st.markdown("---")
                    for article in highlights:
                        title = article.get("title", "No Title Provided")
                        url = article.get("url", "#")
                        authors = article.get("authors", []) or ([article.get("author")] if article.get("author") else [])
                        author_str = ', '.join(authors) if authors else 'Unknown'
                        
                        st.markdown(f"### **{title}**")
                        
                        # --- Details Section ---
                        cols = st.columns([2, 1, 1])
                        
                        # Column 1: Sources
                        sources = article.get("source_list", [article.get("source", "N/A")])
                        cols[0].markdown(f"**[Source(s):]({url})** {', '.join(sources)}")
                        
                        # Column 2: Frequency
                        frequency = article.get("occurrence_count", 1)
                        cols[1].markdown(f"**Frequency:** `{frequency}`")
                        
                        # Column 3: Authors
                        cols[2].markdown(f"**Author(s):** `{author_str}`")
                        
                        st.markdown("---")
                
                # Display other articles
                if other_articles:
                    st.markdown("### Other News")
                    st.markdown("---")
                    for article in other_articles:
                        title = article.get("title", "No Title Provided")
                        url = article.get("url", "#")
                        authors = article.get("authors", []) or ([article.get("author")] if article.get("author") else [])
                        author_str = ', '.join(authors) if authors else 'Unknown'
                        
                        st.markdown(f"#### {title}")
                        
                        # --- Details Section ---
                        cols = st.columns([2, 1, 1])
                        
                        # Column 1: Sources
                        sources = article.get("source_list", [article.get("source", "N/A")])
                        cols[0].markdown(f"**[Source(s):]({url})** {', '.join(sources)}")
                        
                        # Column 2: Frequency
                        frequency = article.get("occurrence_count", 1)
                        cols[1].markdown(f"**Frequency:** `{frequency}`")
                        
                        # Column 3: Authors
                        cols[2].markdown(f"**Author(s):** `{author_str}`")
                        
                        st.markdown("---")



elif view == "Atlas Dashboard":

    st.markdown("Live Dashboard")

    # URL from user's provided iframe
    atlas_chart_url = os.environ.get('MONGODB_DASHBOARD_URL')
    
    st.components.v1.iframe(atlas_chart_url, height=1000, scrolling=True)

elif view == "Chat":
    st.markdown("### News Chatbot")
    st.write("Ask me anything about the latest news!")
    
    # Initialize chat history
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about news..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get bot response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    api_url = st.secrets["AWS_API_URL"]
                    
                    response = requests.post(
                        api_url,
                        json={"query": prompt},
                        headers={"Content-Type": "application/json"},
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        bot_response = data.get('response', 'Sorry, I couldn\'t generate a response.')
                    else:
                        bot_response = f"Error: {response.status_code} - {response.text}"
                        
                except Exception as e:
                    bot_response = f"Sorry, I encountered an error: {str(e)}"
                
                st.markdown(bot_response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": bot_response})

