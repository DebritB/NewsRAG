"""
AWS Lambda handler for NewsRAG Chatbot.
Improved version: safer prompting, clean source link handling,
edge-case reasoning examples, and more reliable Claude responses.
"""
import json
import os
import boto3
from pymongo import MongoClient
import re


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
            return _response(200, {
                "query": "",
                "response": "Please enter a query so I can search the news.",
                "articles_used": 0,
                "sources": []
            })

        client = MongoClient(MONGODB_URI)
        collection = client[MONGODB_DATABASE][MONGODB_COLLECTION]

        query_embedding = generate_embedding(query)
        relevant_articles = search_articles(collection, query_embedding, max_results)

        if not relevant_articles:
            return _response(200, {
                "query": query,
                "response": "No relevant news found for your query. Try rephrasing.",
                "articles_used": 0,
                "sources": []
            })

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
# Embeddings
# ---------------------------------------------------------------------------
def generate_embedding(text):
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


# ---------------------------------------------------------------------------
# Claude Response Generator
# ---------------------------------------------------------------------------
def generate_response(query, articles):
    context_parts = []
    titles = []  # Track titles so we can detect which one Claude summarized

    for article in articles:
        title = article.get("title", "N/A")
        source = article.get("source", "N/A")
        published = article.get("published_at", "N/A")
        summary = article.get("summary") or (article.get("content") or "")[:300]
        url = article.get("url", "")

        titles.append((title.lower(), url))

        context_parts.append(
            f"Title: {title}\n"
            f"Source: {source}\n"
            f"Published: {published}\n"
            f"Summary: {summary}\n"
        )

    context_block = "\n\n".join(context_parts)

    # Final prompt
    prompt = f"""
You are a precise, factual news assistant.

General Rules:
- Interpret the user's intent (topic, timeframe, detail).
- Keep your response short: 2–3 sentences.
- Never hallucinate or use outside knowledge.
- Never include URLs.
- Answer ONLY using the article context.
- If none of the articles relate to the user's query, you must return EXACTLY: "The provided articles do not contain enough information to answer that."

User Question: {query}

Article Context:
{context_block}
"""

    # Claude call
    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 800,
            "temperature": 0.3,
            "system": (
                "Answer ONLY from the provided article context. "
                "Do not speculate or add outside knowledge."
            ),
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ]
        })
    )

    body = json.loads(response["body"].read())
    model_answer = body["content"][0]["text"].strip()

    # Remove any accidental "Sources:" text Claude might produce
    model_answer = model_answer.replace("Sources:", "").strip()

    FALLBACK_MSG = "The provided articles do not contain enough information to answer that."

    # ---- FALLBACK HANDLING ----
    if FALLBACK_MSG.lower() in model_answer.lower():
        return FALLBACK_MSG, None   # NO SOURCE LINK

    # ---- CORRECT SOURCE DETECTION ----
    # Find which article Claude summarized by matching the title
    selected_url = None
    answer_lower = model_answer.lower()

    for title_lower, url in titles:
        if title_lower in answer_lower:
            selected_url = url
            break

    # If no specific article matched, do not show a source
    if not selected_url:
        return model_answer, None

    # Append correct source link
    model_answer += f"\n\nSources:\n[Click here]({selected_url})"

    return model_answer, selected_url



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


def handle_options():
    return _response(200, {})


def main(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return handle_options()
    return lambda_handler(event, context)
