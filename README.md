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

For a detailed progress report and history of changes, see `Progress_summary.txt` in the project root. This file documents major updates, bug fixes, and troubleshooting steps throughout development.

---


## Detailed Architecture & Data Flow

### 1. User Interaction (Streamlit Dashboard)
- Users interact with the Streamlit dashboard (`streamlit/dashboard.py`) to:
  - Browse categorized news
  - View analytics and trends
  - Chat with the AI assistant about the latest news

### 2. Chatbot Query Flow
- When a user asks a question in the dashboard:
  1. Streamlit sends the query to the Chatbot Lambda (via API Gateway or direct Lambda invoke)
  2. Chatbot Lambda:
	  - Retrieves relevant news articles and embeddings from MongoDB Atlas
	  - Uses AWS Bedrock (Claude) to generate a response based on retrieved news
	  - Returns the answer to Streamlit for display

### 3. ETL Pipeline (Automated News Processing)
- Every 12 hours, a scheduled Event triggers the Step Functions State Machine (`statemachine/workflow.asl.json`):
  1. **Scraping Lambda** (`scrape_news.py`):
	  - Collects news articles from APIs and RSS feeds
	  - Stores raw articles in MongoDB Atlas
  2. **Classification Lambda**:
	  - Uses Bedrock Claude to categorize articles (e.g., Politics, Tech)
	  - Updates article records in MongoDB with category labels
  3. **Embedding Lambda**:
	  - Uses Bedrock Titan to generate vector embeddings for each article
	  - Stores embeddings in MongoDB for semantic search
  4. **Index Manager Lambda**:
	  - Manages MongoDB Atlas vector index (creation, updates)
  5. **Deduplicator Lambda**:
	  - Detects and merges duplicate news stories using vector similarity
	  - Updates MongoDB to group/merge duplicates

### 4. Data Storage (MongoDB Atlas)
- All articles, categories, and embeddings are stored in MongoDB Atlas
- Vector search is enabled for semantic similarity and deduplication

### 5. Automation & Deployment
- **GitHub Actions**: On every push to `main`, CI/CD pipeline packages and deploys Lambda code and Step Function definitions via AWS SAM/CloudFormation
- **CloudFormation**: Manages all AWS resources as infrastructure-as-code

### 6. Summary of AWS Services Used
- **AWS Lambda**: Serverless compute for scraping, classification, embedding, deduplication, and chatbot
- **AWS Step Functions**: Orchestrates the ETL pipeline in sequence
- **AWS Bedrock (Claude, Titan)**: Provides LLM for classification and embeddings
- **AWS CloudFormation/SAM**: Infrastructure deployment and management
- **AWS CloudWatch**: Logging and monitoring for Lambda functions
- **MongoDB Atlas**: Persistent storage and vector search
- **GitHub Actions**: CI/CD automation

### 7. End-to-End Flow Example
1. User opens Streamlit dashboard → sees latest news (fetched from MongoDB)
2. User asks a question → Streamlit calls Chatbot Lambda → Lambda queries MongoDB, uses Bedrock Claude, returns answer
3. Every 12 hours → Step Function triggers ETL Lambdas in order (scrape → classify → embed → index → deduplicate) → MongoDB updated
4. All infrastructure and automation managed via CloudFormation and GitHub Actions

---

## Architecture 

![Your paragraph text (1)](https://github.com/user-attachments/assets/314604da-1eba-4703-a8c4-550be0c57910)

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
 - Live demo:
   https://debrit-newsrag.streamlit.app/
- Features:
	- Browse news by category
	- Live Dashboard
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

## Local Testing

You can run manual tests and utility scripts from the `tests` folder to verify scraping, vector search, index creation, and log access:

- `tests/extract/test_apis.py`: Test API scrapers and verify article fetching.
- `tests/extract/test_vector_search.py`: Test vector search for similar articles in MongoDB.
- `tests/local/create_vector_index.py`: Create or update the MongoDB Atlas vector index.
- `tests/local/check_logs.py`: Fetch recent logs from AWS Lambda functions via CloudWatch.

These scripts help you check that core features are working locally before deploying. For more robust testing, consider adding automated unit and integration tests.

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
