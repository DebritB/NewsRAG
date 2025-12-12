"""
Chatbot Lambda (V2, Corrected for your LangChain version)
Uses:
- PromptTemplate (NOT ChatPromptTemplate)
- init_chat_model
- LCEL (prompt | llm)
- MongoDB vector search
"""

import os
import json
import boto3
from pymongo import MongoClient

from langchain.chat_models import init_chat_model
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
# CATEGORY KEYWORDS
# ---------------------------------------------------------------------
SUPPORTED = {
    "finance": ["finance", "market", "economy", "bank", "stocks"],
    "sports": ["sports", "football", "soccer", "tennis", "cricket"],
    "music": ["music", "album", "song", "concert", "band"],
    "lifestyle": ["lifestyle", "health", "fitness", "diet", "travel"],
}

UNSUPPORTED = ["politic", "tech", "war", "election", "crypto"]
GENERIC = {"give", "tell", "say", "news", "update", "anything", "something"}


def detect_categories(query: str):
    q = query.lower()

    found = []
    for cat, terms in SUPPORTED.items():
        if any(t in q for t in terms):
            found.append(cat)

    if found:
        return found

    tokens = q.split()
    if any(t in tokens for t in terms):
        return ["other"]

    return []


# ---------------------------------------------------------------------
# EMBEDDING (Titan v2)
# ---------------------------------------------------------------------
def generate_embedding(text):
    resp = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text})
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
        results = [r for r in results if r["score"] >= MIN_VECTOR_SCORE]

    return results


# ---------------------------------------------------------------------
# CONTEXT BUILDER
# ---------------------------------------------------------------------
def build_context(articles):
    blocks = []
    for a in articles:
        blocks.append(
            f"Title: {a.get('title','N/A')}\n"
            f"Source: {a.get('source','Unknown')}\n"
            f"Published: {a.get('published_at','Unknown')}\n"
            f"Summary: {a.get('summary') or a.get('content','')[:300]}"
        )
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------
# PROMPT TEMPLATE (String → LLM)
# ---------------------------------------------------------------------
PROMPT_TEMPLATE = """
You are a precise news assistant.

Rules:
- Use ONLY the article context.
- NEVER add outside info.
- Keep answers 2–3 sentences.
- Do NOT include URLs.
- If the context includes some information, summarize ONLY what is present.
- If the context is completely unrelated or empty, reply EXACTLY:
"{fallback}"

Context:
{context}

User Question:
{query}
"""

prompt = PromptTemplate(
    template=PROMPT_TEMPLATE,
    input_variables=["context", "query"],
    partial_variables={"fallback": FALLBACK_TEXT}
)


# ---------------------------------------------------------------------
# LAMBDA HANDLER
# ---------------------------------------------------------------------
def lambda_handler(event, context):

    body = json.loads(event.get("body", "{}"))
    query = body.get("query", "").strip()
    max_results = int(body.get("max_results", 5))

    if not query or query.lower() in GENERIC:
        return response(200, {"response": "Please enter a more specific query.", "articles_used": 0})

    categories = detect_categories(query)

    if categories == ["other"]:
        return response(200, {
            "response": "The provided articles only cover finance, sports, music, or lifestyle topics.",
            "articles_used": 0
        })

    client = MongoClient(MONGODB_URI)
    coll = client[MONGODB_DB][MONGODB_COLL]

    emb = generate_embedding(query)
    articles = search_articles(coll, emb, max_results=max_results)

    if not articles:
        return response(200, {"response": "No relevant news found.", "articles_used": 0})

    context_text = build_context(articles)

    # LangChain Bedrock LLM
    llm = init_chat_model(
        "bedrock:anthropic.claude-3-sonnet-20240229-v1:0",
        temperature=0.3,
    )

    chain = prompt | llm
    # Run LangChain chain
    answer_msg = chain.invoke({"query": query, "context": context_text})

    # Extract text from AIMessage
    answer_text = answer_msg.content if hasattr(answer_msg, "content") else str(answer_msg)

    # strict fallback check
    if answer_text.strip().lower() == FALLBACK_TEXT.lower():
        return response(200, {"response": FALLBACK_TEXT, "articles_used": len(articles)})

    sources = [a.get("title", "Unknown") for a in articles]

    return response(200, {
        "response": answer_text,
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
