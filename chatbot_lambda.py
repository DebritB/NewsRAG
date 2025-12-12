"""
Chatbot Lambda (V2) — LangChain frontend, MongoDB vector search backend.

Option A: keep your existing MongoDB vector search and embeddings.
This Lambda:
 - generates query embedding via Bedrock
 - runs your existing $vectorSearch to get relevant articles
 - uses LangChain LLMChain (Bedrock wrapper) with a clean prompt
 - falls back to direct Bedrock call when langchain is unavailable
"""

import os
import json
import boto3
from pymongo import MongoClient

# Try to import LangChain; if not available, we'll fallback to direct Bedrock SDK calls.
try:
    from langchain.chat_models import Bedrock as LangchainBedrock
    from langchain.chains import LLMChain
    from langchain.prompts import PromptTemplate
    LANGCHAIN_AVAILABLE = True
except Exception:
    LANGCHAIN_AVAILABLE = False

# Environment
MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "news_rag")
MONGODB_COLLECTION = os.environ.get("MONGODB_COLLECTION", "articles")
MIN_VECTOR_SEARCH_SCORE = float(os.environ.get("MIN_VECTOR_SEARCH_SCORE", "0.0"))
ALLOW_SOFT_FALLBACK = os.environ.get("ALLOW_SOFT_FALLBACK", "true").lower() in ("1", "true", "yes")

# Bedrock client for direct calls & embeddings
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("BEDROCK_REGION", "us-east-1"))

# Simple category detection (keeps behavior from your original code)
FINANCE_KEYWORDS = ["finance", "financial", "economy", "economic", "market", "markets", "stock", "stocks", "business", "bank", "inflation"]
SPORTS_KEYWORDS = ["sport", "sports", "match", "game", "football", "soccer", "cricket", "tennis", "basketball", "rugby"]
MUSIC_KEYWORDS = ["music", "musician", "song", "album", "concert", "band", "singer"]
LIFESTYLE_KEYWORDS = ["lifestyle", "health", "wellness", "travel", "fitness", "diet", "living"]

SUPPORTED = {
    "finance": FINANCE_KEYWORDS,
    "sports": SPORTS_KEYWORDS,
    "music": MUSIC_KEYWORDS,
    "lifestyle": LIFESTYLE_KEYWORDS,
}

UNSUPPORTED_HINTS = ["politic", "gov", "election", "technology", "tech", "science", "war", "crypto", "climate", "weather"]
GENERIC_WORDS = {"give", "tell", "say", "news", "update", "anything", "something"}

FALLBACK_SENTENCE = "The provided articles do not contain enough information to answer that."

def detect_categories(query: str):
    q = (query or "").lower()
    found = []
    for cat, keys in SUPPORTED.items():
        if any(k in q for k in keys):
            found.append(cat)
    if found:
        return found
    if any(k in q for k in UNSUPPORTED_HINTS):
        return ["other"]
    return []

# ----------------------
# MongoDB retrieval (unchanged)
# ----------------------
def search_articles(collection, embedding, max_results=5, min_score=0.0):
    try:
        pipeline = [
            {"$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": 100,
                "limit": max_results
            }},
            {"$project": {
                "_id": 0,
                "title": 1,
                "content": 1,
                "summary": 1,
                "source": 1,
                "published_at": 1,
                "category": 1,
                "score": {"$meta": "vectorSearchScore"}
            }}
        ]
        results = list(collection.aggregate(pipeline))
        if min_score and float(min_score) > 0:
            results = [r for r in results if float(r.get("score", 0)) >= float(min_score)]
        return results
    except Exception as e:
        print("Vector search failed:", e)
        return []

# ----------------------
# Embedding (re-use your Bedrock Titan v2 call)
# ----------------------
def generate_embedding(text: str):
    payload = {"inputText": text}
    resp = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps(payload)
    )
    return json.loads(resp["body"].read())["embedding"]

# ----------------------
# LangChain prompt template (minimal and strict)
# ----------------------
LC_PROMPT_TEMPLATE = """
You are a concise news assistant.

Use ONLY the provided article context to answer the user's question in 2-3 short sentences.
If the context does not contain enough information, reply exactly: "{fallback}"

Do NOT include URLs or fabricate information.
Include a small Sources line listing article titles used (titles only), if applicable.

Context:
{context}

Question:
{query}
""".strip()

PROMPT = PromptTemplate(input_variables=["context", "query"], template=LC_PROMPT_TEMPLATE.replace("{fallback}", FALLBACK_SENTENCE))

# ----------------------
# LLM invoke via LangChain (preferred) or direct Bedrock (fallback)
# ----------------------
def run_langchain_llm(query: str, context_text: str):
    try:
        lc_llm = LangchainBedrock(model_id="anthropic.claude-3-sonnet-20240229-v1:0", temperature=0.2)
        chain = LLMChain(llm=lc_llm, prompt=PROMPT)
        result = chain.run({"query": query, "context": context_text})
        return result
    except Exception as e:
        print("LangChain LLMChain failed:", e)
        return None

def run_direct_bedrock(prompt_text: str):
    try:
        resp = bedrock.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 400,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt_text}]}]
            })
        )
        return json.loads(resp["body"].read())["content"][0]["text"].strip()
    except Exception as e:
        print("Direct Bedrock call failed:", e)
        return None

# ----------------------
# Build context block (keeps it short)
# ----------------------
def build_context_from_articles(articles):
    parts = []
    for a in articles:
        title = a.get("title", "N/A")
        summary = a.get("summary") or (a.get("content") or "")[:300]
        src = a.get("source", "N/A")
        published = a.get("published_at", "N/A")
        parts.append(f"Title: {title}\nSource: {src}\nPublished: {published}\nSummary: {summary}")
    return "\n\n".join(parts)

# ----------------------
# Lambda handler
# ----------------------
def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        query = (body.get("query", "") or "").strip()
        max_results = int(body.get("max_results", 5))

        if not query or query.lower() in GENERIC_WORDS:
            return _response(200, {"query": query, "response": "Please enter a more specific query.", "articles_used": 0})

        categories = detect_categories(query)
        if categories == ["other"]:
            return _response(200, {"query": query, "response": "The provided articles only cover finance, sports, music, or lifestyle topics.", "articles_used": 0})

        # connect DB
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI not set")
        client = MongoClient(MONGODB_URI)
        collection = client[MONGODB_DATABASE][MONGODB_COLLECTION]

        # embedding + search (same as V1)
        query_embedding = generate_embedding(query)
        articles = search_articles(collection, query_embedding, max_results=max_results, min_score=MIN_VECTOR_SEARCH_SCORE)
        print(f"Vector search returned {len(articles)} articles (min_score={MIN_VECTOR_SEARCH_SCORE})")

        if not articles:
            client.close()
            return _response(200, {"query": query, "response": "No relevant news found for your query. Try rephrasing.", "articles_used": 0})

        # build context and run LLM (LangChain preferred)
        context_text = build_context_from_articles(articles)

        answer = None
        if LANGCHAIN_AVAILABLE:
            try:
                answer = run_langchain_llm(query, context_text)
            except Exception as e:
                print("LangChain path errored:", e)
                answer = None

        if not answer:
            # fallback to direct Bedrock invocation with the same (minimal) prompt
            prompt_text = LC_PROMPT_TEMPLATE.replace("{fallback}", FALLBACK_SENTENCE).format(context=context_text, query=query)
            answer = run_direct_bedrock(prompt_text)

        client.close()

        if not answer:
            return _response(200, {"query": query, "response": "An error occurred while generating the answer.", "articles_used": len(articles)})

        # soft fallback enforcement: if answer exactly equals fallback, return fallback
        if answer.strip().lower() == FALLBACK_SENTENCE.lower():
            return _response(200, {"query": query, "response": FALLBACK_SENTENCE, "articles_used": len(articles)})

        # Build a simple sources list (titles only)
        sources = [a.get("title", "Unknown") for a in articles]

        return _response(200, {"query": query, "response": answer, "articles_used": len(articles), "sources": sources})

    except Exception as e:
        print("ERROR in chatbot_v2:", e)
        return _response(500, {"error": "Internal server error"})

# ----------------------
# Response wrapper
# ----------------------
def _response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
        },
        "body": json.dumps(body),
    }

# Backwards-compatible entrypoint name
def main(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return _response(200, {})
    return lambda_handler(event, context)
