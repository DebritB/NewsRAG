---

## Local Testing

You can run manual tests and utility scripts from the `tests` folder to verify scraping, vector search, index creation, and log access:

- `tests/extract/test_apis.py`: Test API scrapers and verify article fetching.
- `tests/extract/test_vector_search.py`: Test vector search for similar articles in MongoDB.
- `tests/local/create_vector_index.py`: Create or update the MongoDB Atlas vector index.
- `tests/local/check_logs.py`: Fetch recent logs from AWS Lambda functions via CloudWatch.

These scripts help you check that core features are working locally before deploying. For more robust testing, consider adding automated unit and integration tests.

---

# NewsRAG – AI-Powered News Aggregator and Chatbot

NewsRAG aggregates news from multiple sources, organizes and categorizes them, and enables semantic search or conversational queries using a retrieval-augmented generation (RAG) approach. It serves as a unified news reader + AI summarizer + chatbot for a curated feed of news.

---

## App Guide

When you open NewsRAG, you’ll see a clean dashboard designed for easy news exploration and conversation.

### Navigation

- **Sidebar Arrow (Top Left):**  
	Click the arrow in the top left corner to open the sidebar. This is your main navigation panel.

- **Sidebar Drop-down Menu:**  
	The sidebar has a drop-down menu with three options:
	- **News:**  
		Browse all news stories, organized by category.  
		- At the top, you’ll see “Breaking News” highlights.
		- Below, stories are grouped into tabs by category (e.g., Politics, Technology, Local).
		- Each story shows its headline, source, frequency (how many sources reported it), and author.
	- **Atlas Dashboard:**  
		View live charts and stats about the news collection.  
		- See trends, counts, and visual summaries of the news data.
	- **Chat:**  
		Use the chatbot to ask questions about the latest news.  
		- Type your question in the box at the bottom and press Enter.
		- The AI assistant will reply with answers based on the most recent news.
		- Previous chat messages are shown above, so you can follow the conversation.

### News View

- Use the tabs at the top to switch between categories.
- Breaking news is highlighted first.
- Click on headlines to see more details about each story.

### Atlas Dashboard View

- Explore visual summaries and trends in the news database.
- Charts update live as new articles are added.

### Chat View

- Ask questions about the news in natural language.
- Get instant answers from the AI assistant.
- Scroll through your chat history to review previous questions and answers.

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

## Progress & History

For a detailed progress report and history of changes, see `CHANGELOG.txt` in the project root. This file documents major updates, bug fixes, and troubleshooting steps throughout development.

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

## Acknowledgements
- AWS Bedrock, MongoDB Atlas, Streamlit, NewsAPI, The Guardian API

---

## License
This project is licensed under the [MIT License](LICENSE).

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
This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgements
- AWS Bedrock, MongoDB Atlas, Streamlit, NewsAPI, The Guardian API
