# Stratova: AI-Powered Go-To-Market Agent

Stratova is an AI-powered Go-To-Market (GTM) orchestration platform that automates market research, competitive analysis, GTM strategy generation, content creation, brand alignment, and campaign performance analysis.

The project uses a multi-agent architecture powered by Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), LangGraph orchestration, FastAPI, and Streamlit.

---

## Features

* Automated market research and competitor analysis
* GTM strategy generation
* ICP and buyer persona creation
* Positioning and messaging development
* Marketing content generation
* Brand alignment evaluation
* Campaign performance analysis
* RAG-based company knowledge retrieval
* Streamlit user interface
* FastAPI backend
* LangGraph multi-agent workflow

---

## Specialized Agents

Stratova includes five specialized agents:

* **Research Agent**: Collects market insights, competitor information, company knowledge, opportunities, and risks.
* **Strategy Agent**: Converts research into positioning, personas, messaging pillars, channels, and GTM strategy.
* **Content Agent**: Generates content calendars, social posts, blog articles, emails, ads, and SEO assets.
* **Brand Alignment Agent**: Reviews generated content against brand voice, tone, positioning, and messaging.
* **Analysis Agent**: Analyzes campaign performance using metrics such as CTR, engagement, conversions, and ROI.

---

## RAG Knowledge Base

Stratova uses Retrieval-Augmented Generation to ground AI outputs in company knowledge.

The RAG pipeline retrieves relevant company information, adds it to the user request, and sends the enriched prompt to the LLM. This helps reduce generic responses and improves alignment with company context.

```text
Documents → Embeddings → ChromaDB → Retriever → LLM → Grounded Output
```

---

## Tech Stack

* Python
* OpenAI API
* LangChain
* LangGraph
* ChromaDB
* FastAPI
* Streamlit
* PostgreSQL
* Sentence Transformers
* BeautifulSoup
* Requests
* python-dotenv

---

## Project Structure

```text
Stratova/
├── 02_src/
│   ├── agents/
│   ├── api/
│   ├── knowledge_base/
│   ├── ui/
│   ├── orca_orchestrator.py
│   ├── memory_system.py
│   ├── postgres_memory.py
│   └── project_paths.py
│
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Create a virtual environment

```bash
python -m venv .venv
```

### 2. Activate the environment

Windows:

```bash
.venv\Scripts\activate
```

Mac/Linux:

```bash
source .venv/bin/activate
```

### 3. Install requirements

```bash
python -m pip install -r requirements.txt
```

### 4. Create a `.env` file

```env
OPENAI_API_KEY=your_openai_api_key_here
SERPAPI_API_KEY=your_serpapi_key_here
DATABASE_URL=your_database_url_here
POSTGRES_PASSWORD=your_postgres_password_here
```

Do not upload real API keys to GitHub.

---

## Running the App

Start the FastAPI backend:

```bash
cd 02_src
python -m uvicorn api.main:app --reload
```

Start the Streamlit frontend in another terminal:

```bash
cd 02_src/ui
python -m streamlit run app.py
```

---

## Example Prompt

```text
Product: Beam Data AI Hub

Audience: Enterprise data leaders, AI leaders, IT managers, and digital transformation leaders in Saudi Arabia.

Market: Saudi Arabia

Goal: Create a complete go-to-market strategy including market research, competitor insights, ICP, buyer personas, positioning, messaging pillars, recommended channels, content ideas, and campaign performance analysis.
```

---

## Expected Outputs

* Market research summary
* Competitor insights
* ICP and buyer personas
* Positioning statement
* Messaging pillars
* GTM strategy
* Content assets
* Brand alignment report
* Campaign performance analysis

---

## Screenshots

### Input Form
![Input Form](assets/screenshots/input.png)

### Research Agent
![Research Agent](assets/screenshots/research.png)

### Research Results
![Research Results](assets/screenshots/research_result.png)

### Strategy Agent
![Strategy Agent](assets/screenshots/strategy.png)

### Strategy Results
![Strategy Results](assets/screenshots/strategy_result.png)

### Buyer Personas and Channels
![Buyer Personas and Channels](assets/screenshots/strategy_result2.png)

### Content Agent
![Content Agent](assets/screenshots/content.png)

### Content Calendar
![Content Calendar](assets/screenshots/content_result.png)

### Content Gallery
![Content Gallery](assets/screenshots/content_result2.png)

### Brand Alignment Agent
![Brand Alignment Agent](assets/screenshots/brand_alignment.png)

### Brand Alignment Results
![Brand Alignment Results](assets/screenshots/brand_result.png)

### Analysis Dashboard
![Analysis Dashboard](assets/screenshots/analysis_result.png)

### Analysis Report
![Analysis Report](assets/screenshots/analysis_result2.png)

## Future Work

* Social media API integration
* Automated publishing after approval
* A/B testing
* CRM integration
* Advanced analytics dashboard

---

## Contributors

Developed by Group 01 as part of an AI systems bootcamp project.
