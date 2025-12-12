"""
Chatbot Lambda (V2) — LangChain + MongoDB vector search.
Option A: Keep existing embeddings + existing MongoDB $vectorSearch.

Improvements:
- Strong grounding prompt
- Correct fallback detection
- Clean context building
- Category intent detection
- No hallucination phrasing
- No duplicate or partial fallback triggers
"""

import os
import json
import boto3
from pymongo import MongoClient

# Try to load LangChain (optional)
try:
    from langchain.chat_models import Bedrock as LangchainBedrock
    from langchain.chains import LLMChain
    from langchain.prompts import PromptTemplate
    LANGCHAIN_AVAILABLE = True
except Exception:
    LANGCHAIN_AVAILABLE = False

# ---------------------------------------------------------------------
# ENVIRONMENT
# ---------------------------------------------------------------------
MONGODB_URI = os.environ.get("MONGODB_URI")
MONGODB_DB = os.environ.get("MONGODB_DATABASE", "news_rag")
MONGODB_COLL = os.environ.get("MONGODB_COLLECTION", "articles")
MIN_VECTOR_SCORE = float(os.environ.get("MIN_VECTOR_SEARCH_SCORE", "0.0"))

bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("BEDROCK_REGION", "us-east-1"))

FALLBACK_TEXT = "The provided articles do not contain enough information to answer that."


# ---------------------------------------------------------------------
# CATEGORY DEFINITIONS (kept, but simplified usage)
# ---------------------------------------------------------------------
FINANCE = ["finance", "financial", "economy", "market", "stock", "business", "bank"]
SPORTS = ["sport", "sports", "match", "game", "football", "soccer", "cricket", "tennis"]
MUSIC = ["music", "musician", "song", "album", "concert", "band"]
LIFESTYLE = ["lifestyle", "health", "wellness", "travel", "fitness", "diet", "living"]

SUPPORTED = {
    "finance": FINANCE,
    "sports": SPORTS,
    "music": MUSIC,
    "lifestyle": LIFESTYLE,
}

UNSUPPORTED = ["politic", "election", "war", "science", "tech", "bitcoin", "crypto"]
GENERIC = {"give", "tell", "say", "news", "update", "anything", "something"}


def detect_categories(query: str):
    q = query.lower()

    supported = []
    for category, terms in SUPPORTED.items():
        if any(t in q for t in terms):
            supported.append(category)

    if supported:
        return supported

    if any(t in q for t in UNSUPPORTED):
        return ["other"]

    return []


# ---------------------------------------------------------------------
# EMBEDDING (reuse Titan v2)
# ---------------------------------------------------------------------
def generate_embedding(text):
    payload = {"inputText": text}
    resp = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps(payload)
    )
    return json.loads(resp["body"].read())["embedding"]


# ---------------------------------------------------------------------
# VECTOR SEARCH (unchanged MongoDB integration)
# ---------------------------------------------------------------------
def search_articles(collection, embedding, max_results=5):
    try:
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": embedding,
                    "numCandidates": 200,
                    "limit": max_results
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "title": 1,
                    "summary": 1,
                    "content": 1,
                    "source": 1,
                    "published_at": 1,
                    "category": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            }
        ]

        results = list(collection.aggregate(pipeline))

        if MIN_VECTOR_SCORE > 0:
            results = [r for r in results if r.get("score", 0) >= MIN_VECTOR_SCORE]

        return results

    except Exception as e:
        print("Vector search error:", e)
        return []


# ---------------------------------------------------------------------
# CONTEXT BUILDER (short, summarised)
# ---------------------------------------------------------------------
def build_context(articles):
    blocks = []
    for a in articles:
        title = a.get("title", "Untitled")
        summary = a.get("summary") or (a.get("content", "")[:300] or "No summary available.")
        src = a.get("source", "Unknown")
        pub = a.get("published_at", "Unknown")
        blocks.append(f"Title: {title}\nSource: {src}\nPublished: {pub}\nSummary: {summary}")
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------
# LANGCHAIN PROMPT (clean + hallucination-proof)
# ---------------------------------------------------------------------
PROMPT_TEMPLATE = """
You are a precise, concise news assistant.

RULES:
- Use ONLY the provided context.
- DO NOT add external facts.
- DO NOT include URLs.
- Write a short answer (2–3 sentences).
- If the context does not include enough information, reply EXACTLY:
"{fallback}"

NEVER repeat or paraphrase the fallback sentence unless it is the ONLY answer.

Context:
{context}

User Question:
{query}
""".strip()


PROMPT = PromptTemplate(
    input_variables=["context", "query"],
    template=PROMPT_TEMPLATE.replace("{fallback}", FALLBACK_TEXT)
)


def run_langchain_llm(query, context):
    try:
        llm = LangchainBedrock(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            temperature=0.2
        )
        chain = LLMChain(llm=llm, prompt=PROMPT)
        return chain.run({"query": query, "context": context})
    except Exception as e:
        print("LangChain failed:", e)
        return None


# ---------------------------------------------------------------------
# DIRECT BEDROCK FALLBACK
# ---------------------------------------------------------------------
def run_direct_bedrock(query, context):
    prompt = PROMPT_TEMPLATE.replace("{fallback}", FALLBACK_TEXT).format(
        context=context, query=query
    )

    try:
        resp = bedrock.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 400,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
            })
        )
        return json.loads(resp["body"].read())["content"][0]["text"].strip()
    except Exception as e:
        print("Direct Bedrock failed:", e)
        return None


# ---------------------------------------------------------------------
# LAMBDA HANDLER
# ---------------------------------------------------------------------
def lambda_handler(event, context):

    body = json.loads(event.get("body", "{}"))
    query = body.get("query", "").strip()
    max_results = int(body.get("max_results", 5))

    # meaningless queries
    if not query or query.lower() in GENERIC:
        return response(200, {"response": "Please enter a more specific query.", "articles_used": 0})

    categories = detect_categories(query)

    if categories == ["other"]:
        return response(200, {
            "response": "The provided articles only cover finance, sports, music, or lifestyle topics.",
            "articles_used": 0
        })

    # MongoDB connection
    client = MongoClient(MONGODB_URI)
    coll = client[MONGODB_DB][MONGODB_COLL]

    # Embedding + search
    emb = generate_embedding(query)
    articles = search_articles(coll, emb, max_results=max_results)

    if not articles:
        return response(200, {
            "response": "No relevant news found for your query.",
            "articles_used": 0
        })

    context_text = build_context(articles)

    # Try LangChain first
    answer = run_langchain_llm(query, context_text) if LANGCHAIN_AVAILABLE else None

    # Fallback to direct Bedrock
    if not answer:
        answer = run_direct_bedrock(query, context_text)

    # Final fallback safety: exact match required
    if answer.strip().lower() == FALLBACK_TEXT.lower():
        return response(200, {"response": FALLBACK_TEXT, "articles_used": len(articles)})

    sources = [a.get("title", "Unknown") for a in articles]

    return response(200, {
        "response": answer,
        "articles_used": len(articles),
        "sources": sources
    })


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "*"
        },
        "body": json.dumps(body),
    }


def main(event, context):
    return lambda_handler(event, context)
