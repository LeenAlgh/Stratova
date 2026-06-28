# Stratova (sratovazip)

Stratova is a **Go-To-Market (GTM) multi-agent AI system** that turns a product brief into research, strategy, content, brand alignment, and performance analysis. This copy is organized for packaging and submission.

## Project layout

```
sratovazip/
├── 01_data/                 # Datasets, knowledge-base files, and run outputs
│   ├── dataset/             # Campaign / GTM datasets (.xlsx)
│   ├── knowledge_base/
│   │   └── documents/       # Brand PDFs, chunks.json, Chroma index
│   └── outputs/             # ORCA pipeline run artifacts
├── 02_src/                  # Application source code
│   ├── agents/              # GTM agent modules
│   ├── api/                 # FastAPI backend
│   ├── ui/                  # Streamlit dashboard
│   ├── knowledge_base/      # RAG and brand-identity Python modules
│   ├── scripts/             # Utility scripts
│   └── project_paths.py     # Central path configuration
├── 03_assets/               # Images and UI visuals
│   ├── logo.svg
│   ├── beam_data_logo.png
│   └── ui/                  # Streamlit logo and styles
├── requirements.txt
└── README.md
```

---

## Prerequisites

- Python 3.10+
- [OpenAI API key](https://platform.openai.com/api-keys) (required)
- [Serper](https://serper.dev/) API key (recommended for web research)
- PostgreSQL (optional, for long-term memory)

---

## Installation

```powershell
cd C:\Users\Geela\Documents\GitHub\sratovazip

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

If you see import errors for LangGraph or LangChain:

```powershell
pip install langgraph langchain langchain-community pandas
```

---

## Configuration

Create a `.env` file in the **project root** (`sratovazip/`, next to `01_data/`):

```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
SERPER_API_KEY=your-serper-key
STRATOVA_API_URL=http://127.0.0.1:8000
```

---

## Knowledge base setup

Brand PDFs and document chunks live in `01_data/knowledge_base/documents/`.

Rebuild the Chroma vector index after adding PDFs:

```powershell
cd 02_src
python knowledge_base/rebuild_chroma.py
```

To extract text from PDFs into `chunks.json`:

```powershell
python 01_data/knowledge_base/documents/text_extraction.py
```

---

## Running the project

*to create the virtual environment 
run python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

All commands below assume your virtual environment is active and your shell is in `02_src/`.

### 1. Start the API

```powershell
cd 02_src
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: http://127.0.0.1:8000/health

### 2. Start the Streamlit UI

In a second terminal:

```powershell
cd 02_src
streamlit run ui/app.py
```

Open http://localhost:8501 — use **New Run** to submit a GTM brief and **Dashboard** to browse outputs from `01_data/outputs/`.

### 3. Run the full pipeline from the CLI

```powershell
cd 02_src
python orca_orchestrator.py
```

---

## What each folder contains

| Folder | Contents |
|--------|----------|
| `01_data/dataset/` | `beamdata_gtm_professional_dataset.xlsx` and other input data |
| `01_data/knowledge_base/documents/` | Brand identity PDF, `chunks.json`, Chroma DB |
| `01_data/outputs/` | Timestamped ORCA run JSON for the dashboard |
| `02_src/` | Agents, API, UI, orchestrator, and shared Python modules |
| `03_assets/` | Logos, brand PNG, and Streamlit CSS |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Set OPENAI_API_KEY in .env` | Add `OPENAI_API_KEY` to `.env` in the project root |
| Streamlit cannot reach API | Start FastAPI from `02_src` first |
| Empty RAG results | Run `python knowledge_base/rebuild_chroma.py` from `02_src` |
| Missing `chunks.json` | Run `text_extraction.py` in `01_data/knowledge_base/documents/` |
