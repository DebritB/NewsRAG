"""
AWS Lambda handler for NewsRAG Chatbot.
Improved version: safer prompting, clean source link handling,
and more reliable Claude responses.
"""
import json
import os
import boto3
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


# ---------------------------------------------------------------------------
# Claude Response Generator
# ---------------------------------------------------------------------------
def generate_response(query, articles):
    """
    Build a safer prompt, generate answer with Claude,
    and return a single source link.
    """

    # Build compact summaries
    context_parts = []
    source_link = None

    for i, article in enumerate(articles):
        title = article.get("title", "N/A")
        source = article.get("source", "N/A")
        published = article.get("published_at", "N/A")
        summary = article.get("summary") or (article.get("content") or "")[:300]
        url = article.get("url", "")

        if i == 0 and url:
            source_link = url  # Use only the first link

        context_parts.append(
            f"Title: {title}\n"
            f"Source: {source}\n"
            f"Published: {published}\n"
            f"Summary: {summary}\n"
        )

    context_block = "\n\n".join(context_parts)

    # Final prompt for Claude
    prompt = f"""
You are a precise, factual news assistant.

Examples of how to interpret user intent (these are examples only — use them to understand the idea but always interpret the ACTUAL user query):

- Query: "best finance news"
  Interpretation: summarize the most important or relevant finance-related articles.

- Query: "finance update?"
  Interpretation: provide a concise summary of the most relevant finance articles.

- Query: "give me detail about economy"
  Interpretation: expand on the finance/economy-related articles returned.

- Query: "tell me something about football"
  Interpretation: summarize the most relevant sports-related articles.

- Query: "top news?"
  Interpretation: choose the most significant articles overall and summarize them.

- Query: "give me full detail about this specific event"
  Interpretation: use all matching articles to produce a more detailed explanation.

If NONE of the articles contain information relevant to the user’s query, respond:
"The provided articles do not contain enough information to answer that."

Rules:
- First, interpret what the user is really asking (topic, time frame, and intent: summary vs detail).
- Only respond with "The provided articles do not contain enough information to answer that" if NONE of the articles relate to the user's topic.
- Answer ONLY using the provided article context.
- Keep your response short: 2–3 sentences.
- Do NOT invent details not found in the context.
- Do NOT include URLs inside your summary.
- Do NOT write "Sources:" anywhere. The system will add sources automatically.

User Question: {query}

Article Context:
{context_block}
"""

    # Call Claude
    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 800,
            "temperature": 0.3,
            "system": (
                "You must answer only using the provided article context. "
                "Do not speculate, do not hallucinate, and do not add outside knowledge."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}]
                }
            ]
        })
    )

    body = json.loads(response["body"].read())
    model_answer = body["content"][0]["text"].strip()

    model_answer = model_answer.replace("Sources:", "").strip()

    # Append source link manually
    if source_link:
        model_answer += f"\n\nSources:\n[Click here]({source_link})"
    else:
        model_answer += "\n\nSources:\nNo sources available"

    return model_answer, source_link



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
