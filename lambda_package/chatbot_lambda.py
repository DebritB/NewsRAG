"""
Chatbot Lambda (V2)
LangChain ONLY — using:
from langchain.chat_models import Bedrock as LangchainBedrock

MongoDB vector search stays the same.
"""

import os
import json
import boto3
from pymongo import MongoClient

# LangChain imports (your requested version)
from langchain.chat_models import Bedrock as LangchainBedrock
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate


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
# CATEGORY DATA
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
    for cat, terms in SUPPORTED.items():
        if any(t in q for t in terms):
            supported.append(cat)

    if supported:
        return supported

    if any(t in q for t in UNSUPPORTED):
        return ["other"]

    return []


# ---------------------------------------------------------------------
# EMBEDDING (Titan v2)
# ---------------------------------------------------------------------
def generate_embedding(text):
    payload = {"inputText": text}
    resp = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps(payload)
    )
    return json.loads(resp["body"].read())["embedding"]


# ---------------------------------------------------------------------
# VECTOR SEARCH (MongoDB)
# ---------------------------------------------------------------------
def search_articles(collection, embedding, max_results=5):
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


# ---------------------------------------------------------------------
# CONTEXT BUILDER
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
# PROMPT TEMPLATE (LangChain)
# ---------------------------------------------------------------------
PROMPT_TEMPLATE = """
You are a precise news assistant.

Rules:
- Use ONLY the provided context.
- Do not add outside information.
- Keep the answer short (2–3 sentences).
- Do NOT include URLs.
- If the context does not contain enough information, reply EXACTLY:
"{FALLBACK_TEXT}"

NEVER repeat or paraphrase this fallback sentence accidentally.

Context:
{context}

User Question:
{query}
""".strip()


PROMPT = PromptTemplate(
    input_variables=["context", "query"],
    template=PROMPT_TEMPLATE
)


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

    # Connect MongoDB
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

    # Build context
    context_text = build_context(articles)

    # LangChain Bedrock LLM
    llm = LangchainBedrock(
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        client=bedrock,
        model_kwargs={"temperature": 0.2, "max_tokens": 400}
    )

    chain = LLMChain(prompt=PROMPT, llm=llm)
    answer = chain.run({"query": query, "context": context_text})

    # strict fallback check (exact match)
    if answer.strip().lower() == FALLBACK_TEXT.lower():
        return response(200, {"response": FALLBACK_TEXT, "articles_used": len(articles)})

    sources = [a.get("title", "Unknown") for a in articles]

    return response(200, {
        "response": answer,
        "articles_used": len(articles),
        "sources": sources
    })


# ---------------------------------------------------------------------
# RESPONSE WRAPPER
# ---------------------------------------------------------------------
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
