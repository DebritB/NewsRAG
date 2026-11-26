"""
Compare Titan Text Embeddings V2 (Bedrock) vs voyage-4-lite (Voyage API) on your own articles.

Steps:
  1. Dump a sample of articles from MongoDB:
       python tests/eval/compare_embeddings.py dump --limit 200
  2. Write questions in tests/eval/questions.json (see questions.example.json),
     each pointing at the article id(s) that should answer it.
  3. Run the comparison:
       python tests/eval/compare_embeddings.py compare

Env vars:
  MONGODB_URI        - only for `dump`
  AWS_REGION         - Bedrock region (default ap-southeast-2); AWS credentials via `aws login` / CloudShell
  VOYAGE_API_KEY     - from https://dash.voyageai.com

Embeddings are cached in tests/eval/cache/ so re-runs cost nothing.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import requests

HERE = Path(__file__).parent

try:  # read MONGODB_URI / VOYAGE_API_KEY / AWS_REGION from the repo's .env (gitignored)
    from dotenv import load_dotenv
    load_dotenv(HERE.parent.parent / ".env")
except ImportError:
    pass
ARTICLES_FILE = HERE / "articles.json"
QUESTIONS_FILE = HERE / "questions.json"
CACHE_DIR = HERE / "cache"

TITAN_MODEL = "amazon.titan-embed-text-v2:0"
VOYAGE_MODEL = "voyage-4-lite"
DIMENSIONS = 1024
TOP_K = 5


# ---------------------------------------------------------------- data

def dump_articles(limit: int) -> None:
    from pymongo import MongoClient

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        sys.exit("Set MONGODB_URI first.")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    coll = client[os.environ.get("MONGODB_DATABASE", "news_rag")][os.environ.get("MONGODB_COLLECTION", "articles")]
    docs = coll.find({}, {"title": 1, "summary": 1, "content": 1, "category": 1}).limit(limit)
    articles = [
        {
            "id": str(d["_id"]),
            "title": d.get("title", ""),
            "summary": d.get("summary", ""),
            "content": (d.get("content") or "")[:2000],
            "category": d.get("category", ""),
        }
        for d in docs
    ]
    ARTICLES_FILE.write_text(json.dumps(articles, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(articles)} articles to {ARTICLES_FILE}")


def article_text(a: dict) -> str:
    # Same text the production embedding_lambda.py embeds.
    return f"{a.get('title', '')} {a.get('summary', '') or (a.get('content', '') or '')[:500]}"


# ---------------------------------------------------------------- embedders

def embed_titan(texts: list[str], kind: str) -> np.ndarray:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "ap-southeast-2"))
    out = []
    for i, t in enumerate(texts, 1):
        body = json.dumps({"inputText": t[:30000], "dimensions": DIMENSIONS, "normalize": True})
        resp = client.invoke_model(modelId=TITAN_MODEL, body=body)
        out.append(json.loads(resp["body"].read())["embedding"])
        if i % 50 == 0:
            print(f"  titan {kind}: {i}/{len(texts)}")
    return np.array(out, dtype=np.float32)


def embed_voyage(texts: list[str], kind: str) -> np.ndarray:
    key = os.environ.get("VOYAGE_API_KEY")
    if not key:
        sys.exit("Set VOYAGE_API_KEY first.")
    input_type = "query" if kind == "questions" else "document"
    out = []
    batch = 64
    for start in range(0, len(texts), batch):
        chunk = texts[start:start + batch]
        for attempt in range(6):
            r = requests.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {key}"},
                json={"input": chunk, "model": VOYAGE_MODEL, "input_type": input_type,
                      "output_dimension": DIMENSIONS},
                timeout=60,
            )
            if r.status_code == 429:  # free tier without payment method has low rate limits
                wait = 20 * (attempt + 1)
                print(f"  voyage rate-limited, waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            break
        else:
            sys.exit("Voyage kept rate-limiting; try again later or add a payment method.")
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        out.extend(d["embedding"] for d in data)
        print(f"  voyage {kind}: {min(start + batch, len(texts))}/{len(texts)}")
    return np.array(out, dtype=np.float32)


EMBEDDERS = {"titan": embed_titan, "voyage": embed_voyage}


def cached_embed(model: str, kind: str, texts: list[str]) -> np.ndarray:
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{model}_{kind}.npy"
    if path.exists():
        arr = np.load(path)
        if len(arr) == len(texts):
            return arr
    print(f"Embedding {len(texts)} {kind} with {model}...")
    arr = EMBEDDERS[model](texts, kind)
    np.save(path, arr)
    return arr


# ---------------------------------------------------------------- eval

def normalize(m: np.ndarray) -> np.ndarray:
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def compare(models: list[str]) -> None:
    articles = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    ids = [a["id"] for a in articles]
    id_set = set(ids)
    for q in questions:
        missing = [e for e in q["expected_ids"] if e not in id_set]
        if missing:
            sys.exit(f"Question {q['question']!r} points at ids not in articles.json: {missing}")

    doc_texts = [article_text(a) for a in articles]
    q_texts = [q["question"] for q in questions]
    titles = {a["id"]: a["title"] for a in articles}

    results = {}
    for model in models:
        docs = normalize(cached_embed(model, "articles", doc_texts))
        qs = normalize(cached_embed(model, "questions", q_texts))
        scores = qs @ docs.T  # cosine similarity
        ranks = []
        for qi, q in enumerate(questions):
            order = np.argsort(-scores[qi])
            ranked_ids = [ids[i] for i in order]
            best = min(ranked_ids.index(e) + 1 for e in q["expected_ids"])
            ranks.append(best)
        results[model] = ranks

    # Per-question table
    print("\nRank of the first correct article (1 = top result; lower is better)\n")
    header = f"{'#':>3}  " + "  ".join(f"{m:>7}" for m in models) + "  question"
    print(header)
    print("-" * len(header))
    for qi, q in enumerate(questions):
        row = "  ".join(f"{results[m][qi]:>7}" for m in models)
        print(f"{qi + 1:>3}  {row}  {q['question'][:70]}")

    # Summary
    print("\nSummary\n")
    print(f"{'model':>8}  {'hit@1':>6}  {'hit@' + str(TOP_K):>6}  {'MRR':>6}")
    for m in models:
        r = np.array(results[m])
        print(f"{m:>8}  {np.mean(r == 1):>6.0%}  {np.mean(r <= TOP_K):>6.0%}  {np.mean(1 / r):>6.3f}")
    print("\nhit@1 = correct article ranked first; hit@5 = in the top 5 (what the chatbot sees);"
          "\nMRR = mean reciprocal rank (1.0 is perfect).")

    # Show top results for questions where the models disagree most
    if len(models) == 2:
        a, b = models
        diffs = sorted(range(len(questions)), key=lambda i: -abs(results[a][i] - results[b][i]))[:3]
        print("\nBiggest disagreements:")
        for qi in diffs:
            q = questions[qi]
            print(f"\n  Q: {q['question']}")
            print(f"     expected: {titles[q['expected_ids'][0]][:80]}")
            print(f"     {a}: rank {results[a][qi]}   {b}: rank {results[b][qi]}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump", help="save a sample of articles from MongoDB to articles.json")
    d.add_argument("--limit", type=int, default=200)
    c = sub.add_parser("compare", help="embed and score")
    c.add_argument("--models", nargs="+", default=["titan", "voyage"], choices=list(EMBEDDERS))
    args = p.parse_args()

    if args.cmd == "dump":
        dump_articles(args.limit)
    else:
        compare(args.models)


if __name__ == "__main__":
    main()
