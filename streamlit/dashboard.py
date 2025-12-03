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
def get_daily_highlights(_collection):
    """Fetches and processes the news highlights."""
    st.info("Fetching latest news highlights from the database...")
    
    # Query for all articles, sorted to show most frequent and newest first
    query = {'highlight': True}
    sort_order = [("occurrence_count", -1), ("published_at", -1)]
    
    articles = list(_collection.find(query).sort(sort_order))
    
    # Group articles by category
    categorized_articles = defaultdict(list)
    for article in articles:
        category = article.get("category", "Uncategorized")
        categorized_articles[category].append(article)
        
    # Calculate stats for charts
    category_counts = {category: len(articles) for category, articles in categorized_articles.items()}
    
    if not category_counts:
        return categorized_articles, pd.DataFrame()

    stats_df = pd.DataFrame.from_dict(category_counts, orient='index', columns=['count'])
    stats_df['percentage'] = (stats_df['count'] / stats_df['count'].sum() * 100).round(1)
    stats_df = stats_df.sort_values(by='count', ascending=False)
        
    return categorized_articles, stats_df

# --- Streamlit UI ---
st.set_page_config(page_title="NewsRAG Daily Highlights", layout="wide")
st.title("📰 NewsRAG Highlights")
st.markdown("Displaying the top news stories, grouped by category.")

# --- Main Application ---
collection = get_database_connection()
highlights, stats_df = get_daily_highlights(collection)

if not highlights:
    st.warning("No recent articles found in the database. The ETL pipeline may be running or there might be no new news.")
else:
    # --- Visualizations ---
    st.subheader("📊 News Distribution by Category")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("Number of Articles")
        st.bar_chart(stats_df['count'])
        
    with col2:
        st.write("Percentage of Articles")
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.pie(stats_df['percentage'], labels=stats_df.index, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        st.pyplot(fig)

    # --- Category Tabs ---
    st.subheader("📰 Browse by Category")
    # Create a tab for each category
    categories = sorted(highlights.keys())
    tabs = st.tabs(categories)
    
    for i, category in enumerate(categories):
        with tabs[i]:
            st.subheader(f"Top Stories in {category.capitalize()}")
            
            articles_in_category = highlights[category]
            
            if not articles_in_category:
                st.info("No articles found for this category in the last 48 hours.")
                continue

            # Display each article
            for article in articles_in_category:
                title = article.get("title", "No Title Provided")
                url = article.get("url", "#")
                
                st.markdown(f"#### [{title}]({url})")
                
                # --- Details Section ---
                cols = st.columns([2, 1, 1])
                
                # Column 1: Sources
                sources = article.get("source_list", [article.get("source", "N/A")])
                cols[0].markdown(f"**Source(s):** `{', '.join(sources)}`")
                
                # Column 2: Frequency
                frequency = article.get("occurrence_count", 1)
                cols[1].markdown(f"**Frequency:** `{frequency}`")
                
                # Column 3: Authors
                authors = article.get("authors", [])
                cols[2].markdown(f"**Author(s):** `{', '.join(authors) if authors else 'NA'}`")
                
                st.markdown("---")

