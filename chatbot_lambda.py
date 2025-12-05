"""
AWS Lambda handler for NewsRAG Chatbot.
This function handles user queries about news by searching relevant articles
and using AWS Bedrock to generate AI-powered responses.
"""
import json
import os
import boto3
from pymongo import MongoClient
from datetime import datetime, timedelta

# Environment variables
MONGODB_URI = os.environ.get('MONGODB_URI')
MONGODB_DATABASE = os.environ.get('MONGODB_DATABASE', 'news_rag')
MONGODB_COLLECTION = os.environ.get('MONGODB_COLLECTION', 'articles')

# Bedrock client
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def lambda_handler(event, context):
    """
    Main Lambda handler for chatbot queries.
    
    Expected event format:
    {
        "query": "What are the latest developments in AI?",
        "max_results": 5  # Optional, default 5
    }
    """
    try:
        # Parse input
        body = json.loads(event.get('body', '{}'))
        query = body.get('query', '').strip()
        max_results = body.get('max_results', 5)
        
        if not query:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Query is required'})
            }
        
        # Connect to MongoDB
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DATABASE]
        collection = db[MONGODB_COLLECTION]
        
        # Generate embedding for the query using Bedrock Titan
        query_embedding = generate_embedding(query)
        
        # Search for relevant articles using vector similarity
        relevant_articles = search_articles(collection, query_embedding, max_results)
        
        if not relevant_articles:
            response_text = "I couldn't find any relevant news articles for your query. Please try rephrasing or check back later for new articles."
        else:
            # Generate AI response using Bedrock
            response_text = generate_response(query, relevant_articles)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'query': query,
                'response': response_text,
                'articles_used': len(relevant_articles)
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }

def generate_embedding(text):
    """Generate vector embedding for text using Bedrock Titan."""
    try:
        response = bedrock.invoke_model(
            modelId='amazon.titan-embed-text-v2:0',
            body=json.dumps({
                'inputText': text
            })
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['embedding']
    except Exception as e:
        print(f"Embedding generation error: {str(e)}")
        raise

def search_articles(collection, query_embedding, max_results=5):
    """Search for relevant articles using vector similarity."""
    try:
        pipeline = [
            {
                '$vectorSearch': {
                    'index': 'vector_index',  # Your vector search index name
                    'path': 'embedding',
                    'queryVector': query_embedding,
                    'numCandidates': 100,
                    'limit': max_results
                }
            },
            {
                '$project': {
                    '_id': 0,
                    'title': 1,
                    'content': 1,
                    'summary': 1,
                    'source': 1,
                    'published_at': 1,
                    'url': 1,
                    'category': 1,
                    'score': {'$meta': 'vectorSearchScore'}
                }
            }
        ]
        
        results = list(collection.aggregate(pipeline))
        return results
    except Exception as e:
        print(f"Vector search error: {str(e)}")
        return []

def generate_response(query, articles):
    """Generate AI response using Claude 3 Sonnet based on relevant articles."""
    try:
        # Prepare a compact context from articles (title, source, summary, url)
        context_entries = []
        sources_list = []
        for article in articles:
            title = article.get('title', 'N/A')
            source = article.get('source', 'N/A')
            summary = article.get('summary') or (article.get('content') or "")[:500]
            published = article.get('published_at', 'N/A')
            url = article.get('url', '')
            context_entries.append(f"Title: {title}\nSource: {source}\nPublished: {published}\nSummary: {summary}\n")
            if url:
                sources_list.append(f"{title} — {url}")
        context = "\n\n".join(context_entries)
        
        # Create prompt for Claude
        user_prompt = f"""You are a concise and accurate news assistant. Use the following article summaries to answer the user's question.

    Instructions:
    - Provide a short (2-3 sentence) summary answering the user. Do not reference article numbers (e.g., "Article 1").
    - Include a 'Sources:' section after the summary listing each article title and a link to the original article.
    - Avoid repeating long blocks of text from the articles. If the articles do not fully answer the question, state that and suggest next steps.

    User Question: {query}

    Article Context:
    {context}

    Sources:
    {"\n".join(sources_list)}
    """
        
        # Invoke Claude 3 Sonnet
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "system": "You are a helpful news assistant. Provide accurate, well-cited answers based on the news articles provided. Keep responses concise but comprehensive.",
                "messages": [
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                "temperature": 0.3
            })
        )
        
        response_body = json.loads(response['body'].read())
        generated_text = response_body['content'][0]['text']
        
        return generated_text.strip()
        
    except Exception as e:
        print(f"Response generation error: {str(e)}")
        return "Sorry, I encountered an error generating a response. Please try again."

# Handle CORS preflight requests
def handle_options():
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST, OPTIONS'
        },
        'body': json.dumps({})
    }

# Main entry point for API Gateway
def main(event, context):
    if event.get('httpMethod') == 'OPTIONS':
        return handle_options()
    return lambda_handler(event, context)