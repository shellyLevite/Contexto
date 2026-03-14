# CONTEXTO - Personal Context Engine

CONTEXTO is a full-stack, privacy-oriented RAG app for asking questions over your own files.

You upload local data (TXT, JSON, CSV, PDF, and WhatsApp TXT exports), the backend embeds and indexes it in Supabase pgvector, and the chat UI answers with source citations.

## Features

- FastAPI backend with RAG endpoints
- React + Vite frontend with Chat and Upload tabs
- Local embeddings via SentenceTransformers (no embedding API key needed)
- Groq LLM integration for answer generation
- Supabase Postgres + pgvector vector search
- Upload, list, and delete indexed files from the UI
- WhatsApp export parsing (multi-format date/time patterns)
- PDF page-by-page ingestion

## Tech Stack

- Backend: Python, FastAPI, Uvicorn, LlamaIndex
- Frontend: React 19, Vite
- Database: Supabase Postgres + pgvector
- Embeddings: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- LLM: Groq (default model from env)

## Repository Layout

```text
FinalBoss/
|-- README.md
|-- PHASES.md
|-- data_export/                    # Uploaded and ingested files
|-- backend/
|   |-- main.py                     # FastAPI app and routes
|   |-- ingest.py                   # ETL: parse, chunk, embed, upsert
|   |-- rag.py                      # Retrieval + prompt + LLM response
|   |-- parsers.py                  # WhatsApp/PDF/generic loaders
|   |-- db.py                       # Lazy Supabase client
|   |-- requirements.txt
|   |-- .env.example
|   `-- sql/schema.sql
`-- frontend/
    |-- src/App.jsx
    |-- src/components/
    |-- src/api/chat.js
    |-- src/api/ingest.js
    |-- package.json
    `-- README.md
```

## Prerequisites

- Python 3.11+ (project currently uses 3.13)
- Node.js 18+
- npm
- Supabase project
- Groq API key

## Environment Variables

Create `backend/.env` from `backend/.env.example` and fill values:

```env
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
SUPABASE_DB_URL=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres
GROQ_API_KEY=...
LLM_MODEL=llama-3.1-8b-instant
EMBED_MODEL_NAME=BAAI/bge-small-en-v1.5
TOP_K=5
ENVIRONMENT=development
```

Create `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Database Setup (Supabase)

Run the SQL in `backend/sql/schema.sql` once in Supabase SQL Editor.

This will:

- Enable pgvector extension
- Create `vecs` schema
- Create `public.documents_metadata`
- Configure permissions for vector tables used by LlamaIndex

## Local Setup

### 1) Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend health check:

- GET http://localhost:8000/health
- Swagger docs: http://localhost:8000/docs

### 2) Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend dev server:

- http://localhost:5173

## How Ingestion Works

1. Upload files from the Upload tab (or place files in `data_export/`).
2. Backend validates extension and size (10 MB max per file in upload route).
3. Parser routing:
   - `.pdf` -> PyMuPDF parser, one document per page
   - WhatsApp `.txt` -> message-level parser with sender/date/time metadata
   - Other supported files -> generic loader
4. Text is chunked (SentenceSplitter), embedded, and inserted into Supabase vectors.
5. File-level metadata is tracked in `public.documents_metadata`.

## API Endpoints

- `GET /health` -> liveness check
- `POST /api/chat` -> ask a question
  - Request: `{ "question": "..." }`
  - Response: `{ "answer": "...", "sources": ["..."] }`
- `POST /api/ingest` -> upload and queue ingest
- `GET /api/files` -> list files from `data_export/`
- `DELETE /api/files/{filename}` -> delete file and vectors

## Typical Workflow

1. Start backend.
2. Start frontend.
3. Open Upload tab and ingest files.
4. Open Chat tab and ask questions.
5. Verify returned source file names in responses.

## Debugging

- If chat fails with environment errors:
  - Confirm `backend/.env` exists and values are valid.
  - Confirm `SUPABASE_DB_URL` uses direct Postgres URI.
- If exact keyword is missing:
  - Run `python backend/test_db.py "keyword"` to inspect stored chunks.
- If frontend cannot reach backend:
  - Check `VITE_API_BASE_URL` in `frontend/.env`.
  - Confirm CORS allows your frontend origin.

## Security Notes

- Do not commit `.env` files.
- Use service-role credentials only on backend.
- This project is intended for private/personal data workflows.

## Current Status

Core phases are implemented, including:

- Upload/list/delete UI
- Background ingest pipeline
- Hybrid retrieval behavior in `rag.py` (exact token fetch + vector retrieval)
- End-to-end chat responses with sources

See `PHASES.md` for implementation history and milestone notes.
