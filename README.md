# IntelliGraph — Knowledge Graph-Driven Information Extraction for Unstructured Documents

This repository contains a production-ready implementation that builds a Neo4j-powered knowledge graph from unstructured documents (current use-case: resumes), augments it with a RAG pipeline for question answering, and exposes a FastAPI backend with a lightweight UI.

The codebase includes:
- FastAPI API for uploads, processing, querying, and ATS analysis
- Neo4j graph modeling and entity/relation creation
- RAG pipeline (LangChain + Sentence Transformers/FAISS) to query graph-backed context
- Simple static UI (HTML/CSS/JS) and a dev server for local testing

> Note: The repo name references “Sentiment Extraction.” This implementation focuses on information extraction and candidate analysis; you can extend prompts/pipelines to sentiment tasks as needed.

## Features
- Knowledge graph construction from resume entities and relationships (Neo4j)
- RAG-driven querying across graph and text chunks
- ATS analysis for job description fit and recommendations
- Batch and single-file upload flows with background processing
- REST endpoints for health checks, candidate listings, and analytics

## Tech Stack
- Python, FastAPI, Pydantic
- Neo4j (py2neo)
- LangChain ecosystem, SentenceTransformers, FAISS
- Google Generative AI (Gemini) for entity extraction
- Simple static UI served via a small Python HTTP server

## Requirements
- Python 3.10+
- Neo4j running locally (default: bolt://localhost:7687)
- A Google API key for Gemini placed in a `.env` file

## Quickstart
1. Create and activate a virtual environment
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   ```
2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment
   - Create a `.env` in the project root:
     ```env
     GOOGLE_API_KEY=your_google_api_key
     # Optional overrides if not using defaults in code:
     NEO4J_URI=bolt://localhost:7687
     NEO4J_USER=neo4j
     NEO4J_PASSWORD=********
     ```
4. Ensure Neo4j is running and accessible.
5. Start the FastAPI backend
   ```bash
   python fastapi_app.py
   # Server runs on http://localhost:8000
   ```
6. Start the local UI server (optional)
   ```bash
   python serve_ui.py
   # UI opens at http://localhost:3000 and targets the FastAPI backend
   ```

## API Overview
- `GET /health` — system health (Neo4j, RAG, API key)
- `POST /upload-resume` — upload a single PDF
- `POST /upload-multiple-resumes` — upload multiple PDFs
- `POST /query` — RAG question answering over graph + text
- `POST /ats-analysis` — ATS analysis for all resumes against a JD
- `POST /ats-single` — ATS score for a single resume text + JD
- `GET /processing-status` — processed/failed resume details
- `GET /candidates` — list all candidates with key attributes
- `GET /candidate/{name}` — detailed candidate profile

## Project Structure
```
.
├─ fastapi_app.py          # FastAPI app with endpoints and lifecycle
├─ database.py             # Neo4j connector (py2neo)
├─ knowledge_graph.py      # Graph building and relationships
├─ rag_system.py           # RAG setup and query processing
├─ resume_parser.py        # Parsing and Gemini-based entity extraction
├─ resume_processor.py     # Directory processing and status helpers
├─ ats_analyzer.py         # ATS scoring utilities
├─ index.html | styles.css | script.js  # Simple UI
├─ serve_ui.py             # Local static UI server (port 3000)
├─ requirements.txt        # Python dependencies
├─ resumes/                # Sample PDFs (ignored by git)
├─ chroma_db/, chroma_resume/, rag_chroma/  # Vector DBs (ignored)
└─ .env                    # Secrets (ignored)
```

## Data and Privacy
- The `.gitignore` excludes `.env`, vector DBs, and `resumes/` to avoid committing secrets and large/PII files.
- Review `.gitignore` and adjust per your deployment needs.

## Troubleshooting
- Neo4j connection: update credentials in code or via env vars.
- Google API key: ensure `GOOGLE_API_KEY` exists in `.env`.
- CORS: current dev setup allows all origins; tighten for production.

## Contributing
- Use conventional commits (e.g., `feat:`, `fix:`, `chore:`).
- Open issues/PRs with clear descriptions and steps to reproduce.

## License
Specify a license if you plan to open source. By default this project is unlicensed.
