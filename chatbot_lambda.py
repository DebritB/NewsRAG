"""
AWS Lambda handler for NewsRAG Chatbot.
Improved version: safer prompting, clean source link handling,
and more reliable Claude responses.
"""
import json
import os
import re
import boto3
from collections import OrderedDict
from pymongo import MongoClient

# Environment variables
MONGODB_URI = os.environ.get('MONGODB_URI')
MONGODB_DATABASE = os.environ.get('MONGODB_DATABASE', 'news_rag')
MONGODB_COLLECTION = os.environ.get('MONGODB_COLLECTION', 'articles')

# Bedrock client
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')


# ---------------------------------------------------------------------------
# Lambda Handler
# ---------------------------------------------------------------------------
def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        query = body.get('query', '').strip()
        max_results = body.get('max_results', 5)

        if not query:
            return _response(400, {"error": "Query is required"})

        # Connect to DB
        client = MongoClient(MONGODB_URI)
        collection = client[MONGODB_DATABASE][MONGODB_COLLECTION]

        # Generate embedding
        query_embedding = generate_embedding(query)

        # Search MongoDB vector index
        relevant_articles = search_articles(collection, query_embedding, max_results)

        if not relevant_articles:
            msg = "No relevant news found for your query. Try rephrasing."
            return _response(200, {
                "query": query,
                "response": msg,
                "articles_used": 0,
                "sources": []
            })

        # Generate answer
        answer_text, source_link = generate_response(query, relevant_articles)

        return _response(200, {
            "query": query,
            "response": answer_text,
            "articles_used": len(relevant_articles),
            "sources": [source_link] if source_link else []
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        return _response(500, {"error": "Internal server error"})


# ---------------------------------------------------------------------------
# Embedding Generator
# ---------------------------------------------------------------------------
def generate_embedding(text):
    """Generate vector embedding for text using Bedrock Titan."""
    payload = {"inputText": text}

    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps(payload)
    )

    body = json.loads(response["body"].read())
    return body["embedding"]


# ---------------------------------------------------------------------------
# MongoDB Vector Search
# ---------------------------------------------------------------------------
def search_articles(collection, query_embedding, max_results=5):
    try:
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": 100,
                    "limit": max_results
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "title": 1,
                    "content": 1,
                    "summary": 1,
                    "source": 1,
                    "published_at": 1,
                    "url": 1,
                    "category": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]

        return list(collection.aggregate(pipeline))

    except Exception as e:
        print("Vector Search Error:", e)
        return []
# Claude Response Generator
# ---------------------------------------------------------------------------
def generate_response(query, articles):
    """Generate a short factual response from Claude using the supplied articles.

    Returns tuple: (answer_text: str, sources_out: list[dict])
    """
    # Build context and dedup source list
    context_parts = []
    deduped_sources = OrderedDict()
    for article in articles:
        title = article.get('title', 'N/A')
        source = article.get('source', 'N/A')
        published = article.get('published_at', 'N/A')
        summary = article.get('summary') or (article.get('content') or '')[:400]
        url = article.get('url', '')
        context_parts.append(
            f"Title: {title}\nSource: {source}\nPublished: {published}\nSummary: {summary}\n"
        )
        if url and url not in deduped_sources:
            deduped_sources[url] = title

    context_block = "\n\n".join(context_parts)

    prompt = f"""
You are a concise, factual news assistant. Answer the user's question using ONLY the article context below.
Rules:
- Keep answers concise (2-3 sentences) unless the user asks for more.
- Do NOT include a 'Sources:' section or any URLs in the answer; the application will display sources seperately.
- If none of the articles provide relevant information, reply: "The provided articles do not contain enough information to answer that."

User Question: {query}

Article Context:
{context_block}
"""

    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 800,
                'temperature': 0.3,
                'system': 'You are a helpful assistant. Do not invent facts or include URLS in the reply',
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
    except Exception as e:
        print('Bedrock error:', e)
        return 'Sorry, I could not generate a response.', []

    body = json.loads(response['body'].read())
    model_answer = body['content'][0]['text'].strip()
    # Remove any 'Sources:' or 'Click here' instances if the model inserted them
    model_answer = re.sub(r'(?is)\bSources?:.*$', '', model_answer).strip()
    model_answer = re.sub(r'\[?click here\]?|https?://\S+', '', model_answer, flags=re.IGNORECASE).strip()

    sources_out = [{'title': title, 'url': url} for url, title in deduped_sources.items()]
    return model_answer, sources_out



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _response(status, body_dict):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "POST, OPTIONS"
        },
        "body": json.dumps(body_dict)
    }


# CORS preflight
def handle_options():
    return _response(200, {})


def main(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return handle_options()
    return lambda_handler(event, context)
