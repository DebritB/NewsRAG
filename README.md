# App Guide: How to Use NewsRAG

When you open NewsRAG, you'll see a clean dashboard with all the latest news highlights. Here's how to explore and use the app:

## Navigation
- **Top Left Arrow:** Click the arrow in the top left corner to open the sidebar. This is your main navigation for switching views.

- **Sidebar Drop-down:** You'll find a drop-down menu with three options:
	- **News:** Shows all news stories, grouped by category. Browse headlines, sources, and authors. Breaking news is highlighted at the top.
	- **Atlas Dashboard:** Displays live charts and stats about the news database. You can see trends, counts, and other visual summaries.
	- **Chat:** Opens the chatbot. Type any question about the latest news and get instant answers from the AI assistant.

## News View
- Browse news by category using the tabs at the top.
- Each tab shows stories for that category. Breaking news appears first, followed by other articles.
- For each story, you can see the headline, source, frequency (how many sources reported it), and author.

## Atlas Dashboard View
- See live charts and stats about the news collection.
- Use this view to explore trends, counts, and other visual summaries of the news data.

## Chat View
- Ask questions about the news using the chatbot.
- Type your question in the box at the bottom and press Enter.
- The AI assistant will reply with answers based on the latest news stories.
- Previous chat messages are shown above, so you can follow the conversation.

---
# NewsRAG – AI-Powered News Aggregation & Chatbot

NewsRAG is a serverless, production-grade news aggregation system for Australian news, featuring AI-powered categorization, deduplication, vector search, and a Retrieval-Augmented Generation (RAG) chatbot. It leverages AWS Lambda, Step Functions, MongoDB Atlas, and Amazon Bedrock for scalable, low-cost operation.

---

## Features
- **Automated News Scraping:** Collects news from multiple sources on a schedule.
- **AI Categorization:** Uses Bedrock Claude for article classification.
- **Vector Embeddings:** Generates embeddings with Bedrock Titan for semantic search and deduplication.
- **Deduplication:** Groups and merges duplicate news stories across sources.
- **MongoDB Atlas Vector Search:** Stores articles and enables fast similarity search.
- **Streamlit Dashboard:** Visualizes news, trends, and provides a chatbot interface.
- **RAG Chatbot:** Ask questions about the latest news using a Bedrock-powered LLM.
- **Serverless & Automated:** Fully managed via AWS Lambda, Step Functions, and GitHub Actions.

---

## Architecture Overview
1. **GitHub Push** → triggers GitHub Actions CI/CD
2. **CI/CD** → deploys Lambda functions & Step Function via CloudFormation
3. **Step Function** orchestrates:
		- Scraping
		- Classification (Claude)
		- Embedding (Titan)
		- Index management
		- Deduplication
4. **MongoDB Atlas** stores articles, embeddings, and supports vector search
5. **Streamlit Dashboard** for news browsing and chatbot

---

## Project Structure
- `scrape_news.py` – Main news scraping entry point
- `lambda_function.py`, `embedding_lambda.py`, `index_manager_lambda.py`, `deduplicator_lambda.py`, `chatbot_lambda.py` – Lambda handlers
- `models/`, `scrapers/` – Data models and scraping logic
- `streamlit/dashboard.py` – Streamlit UI
- `statemachine/workflow.asl.json` – Step Function definition
- `vector_search_index_config.json` – MongoDB vector index config
- `requirements.txt` – Local dev dependencies
- `requirements-lambda.txt` – Lambda deployment dependencies

---

## Setup & Local Development
1. **Clone the repo:**
	 ```bash
	 git clone https://github.com/yourusername/NewsRAG.git
	 cd NewsRAG
	 ```
2. **Create virtual environment:**
	 ```bash
	 python -m venv .venv
	 .venv/Scripts/activate  # Windows
	 # or
	 source .venv/bin/activate  # macOS/Linux
	 ```
3. **Install dependencies:**
	 ```bash
	 pip install -r requirements.txt
	 ```
4. **Configure secrets:**
	 - Add your MongoDB URI and API endpoints to `.streamlit/secrets.toml` for Streamlit
	 - Add `.env` for local scripts if needed

---

## Cloud Deployment (AWS)
- **Automatic:** Every push to `main` triggers GitHub Actions to:
	1. Package Lambda code
	2. Deploy via CloudFormation
	3. Trigger the Step Function ETL pipeline
- **Manual:** You can run `.github/workflows/deploy.sh` locally with the required environment variables

---

## Streamlit Dashboard
- Run locally:
	```bash
	streamlit run streamlit/dashboard.py
	```
- Features:
	- Browse news by category
	- View deduplication and source stats
	- Chatbot: Ask questions about the latest news

---

## MongoDB Atlas Setup
- See `MONGODB_SETUP.md` (if present) or `vector_search_index_config.json` for index config
- Free M0 tier is sufficient for most use cases

---

## Environment Variables & Secrets
- `.streamlit/secrets.toml` (for Streamlit):
	```toml
	MONGODB_URI = "your_mongodb_uri"
	AWS_API_URL = "your_api_gateway_url"
	MONGODB_DASHBOARD_URL = "your_atlas_dashboard_url"
	```
- GitHub Actions secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `MONGODB_CONNECTION_STRING`, `S3_BUCKET_NAME`

---

## Cost & Scaling
- See `COST_ANALYSIS.md` for detailed breakdown
- Typical cost: ~$1/month for 12K+ articles (serverless, free MongoDB tier)

---

## License
MIT

---

## Acknowledgements
- AWS Bedrock, MongoDB Atlas, Streamlit, NewsAPI, The Guardian API
