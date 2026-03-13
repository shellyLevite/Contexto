# Personal Context Engine — Implementation Reference

A local-first, privacy-focused RAG system that indexes personal data and allows querying it via a chat interface.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, Uvicorn |
| Frontend | React 19, Vite 8, Tailwind CSS |
| Database | Supabase (PostgreSQL + pgvector) |
| LLM | Groq Cloud API (Llama 3) |
| Embeddings | HuggingFace SentenceTransformers (local) |
| RAG / ETL | LlamaIndex |

---

## Project Structure

```
FinalBoss/
├── .gitignore
├── PHASES.md                     ← this file
├── data_export/                  ← drop raw .txt / .json / .csv files here
├── backend/
│   ├── venv/                     ← Python virtual environment (gitignored)
│   ├── requirements.txt
│   ├── .env                      ← secrets (gitignored)
│   ├── .env.example              ← template (committed)
│   ├── sql/
│   │   └── schema.sql            ← Supabase SQL — run once in the SQL editor
│   ├── db.py                     ← Supabase client singleton
│   ├── ingest.py                 ← ETL pipeline (Phase 3)
│   ├── rag.py                    ← RAG query engine (Phase 4)
│   └── main.py                   ← FastAPI app + routes (Phase 5)
└── frontend/
    ├── .env                      ← VITE_API_BASE_URL
    ├── .env.example
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx               ← root component (Phase 6)
        ├── components/
        │   ├── ChatWindow.jsx    ← message history (Phase 6)
        │   └── ChatInput.jsx     ← input bar (Phase 6)
        └── api/
            └── chat.js           ← fetch wrapper for POST /api/chat (Phase 6)
```

---

## Phase 1 — Project Setup & Infrastructure ✅

### What was done
- Created monorepo with `backend/` and `frontend/` folders
- Initialized Python 3.13 virtual environment (`backend/venv/`)
- Installed all backend dependencies (`requirements.txt`)
- Scaffolded React 19 + Vite 8 frontend with `npx create-vite`
- Created `.env` / `.env.example` for both backend and frontend
- Created root `.gitignore` (ignores `venv/`, `.env`, `node_modules/`, `data_export/*`)
- Created `data_export/` directory for raw personal data files

### Key files
| File | Purpose |
|---|---|
| `backend/requirements.txt` | All Python dependencies |
| `backend/.env` | Fill in `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GROQ_API_KEY` |
| `frontend/.env` | `VITE_API_BASE_URL=http://localhost:8000` |
| `.gitignore` | Prevents secrets and build artifacts from being committed |

### Environment variables (`backend/.env`)
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
GROQ_API_KEY=your-groq-api-key
EMBED_MODEL_NAME=BAAI/bge-small-en-v1.5
TOP_K=5
LLM_MODEL=llama3-8b-8192
```

---

## Phase 2 — Database & Vector Setup (Supabase) ✅

### What was done
- Created `backend/sql/schema.sql` — run this once in the Supabase SQL Editor
- Created `backend/db.py` — Supabase client singleton used across the backend

### How to apply the schema
1. Go to **Supabase Dashboard → SQL Editor → New query**
2. Paste the contents of `backend/sql/schema.sql` and click **Run**
3. This creates:
   - The `vector` extension (pgvector)
   - The `vecs` schema (used by LlamaIndex's Supabase vector store)
   - The `documents_metadata` table (stores file-level metadata)

### Key files
| File | Purpose |
|---|---|
| `backend/sql/schema.sql` | Run once in Supabase SQL Editor to set up tables |
| `backend/db.py` | `from db import supabase` — use this everywhere |

### Database tables
| Table | Schema | Purpose |
|---|---|---|
| `documents_metadata` | `public` | Tracks ingested files (source, type, timestamp) |
| `documents` | `vecs` | Auto-created by LlamaIndex — stores text chunks + `vector(384)` embeddings |

---

## Phase 3 — Data Ingestion Pipeline (ETL & Embeddings) ✅

### Plan
- `backend/ingest.py` reads all files from `data_export/`
- Supported types: `.txt`, `.json`, `.csv`
- Uses **LlamaIndex `SimpleDirectoryReader`** to load documents
- Uses **LlamaIndex `SentenceSplitter`** to chunk text (~512 tokens, 50 overlap)
- Uses **`HuggingFaceEmbedding`** (`BAAI/bge-small-en-v1.5`, 384-dim, local, no API key)
- Uses **`SupabaseVectorStore`** to upsert chunks into `vecs.documents`
- Records metadata per file in `public.documents_metadata`

### Key files
| File | Purpose |
|---|---|
| `backend/ingest.py` | Run with: `python ingest.py` (activate venv first) |
| `data_export/` | Drop `.txt`, `.json`, `.csv` files here before running |

### How to run (once implemented)
```bash
cd backend
.\venv\Scripts\activate   # Windows
python ingest.py
```

---

## Phase 4 — Retrieval & AI Generation (The RAG Core) ✅

### Plan
- `backend/rag.py` exposes a single `query(question: str) -> str` function
- Embedding the user's question using the same `HuggingFaceEmbedding` model
- Performing cosine similarity search in `vecs.documents` — returns top-K chunks
- Building a prompt that injects the retrieved context around the user question
- Calling the **Groq API** (`llama3-8b-8192`) to generate the final answer
- Returning the answer string

### Key files
| File | Purpose |
|---|---|
| `backend/rag.py` | Core RAG logic — `from rag import query` |

### RAG Flow
```
User question
    → embed (HuggingFace local)
    → similarity search (Supabase pgvector, top-K=5)
    → retrieved chunks → inject into prompt
    → Groq API (Llama 3) → answer
```

---

## Phase 5 — API Endpoints (FastAPI) ✅

### Plan
- `backend/main.py` is the FastAPI application entry point
- Single route: `POST /api/chat`
  - Request body: `{ "question": "..." }`
  - Calls `rag.query(question)`
  - Response: `{ "answer": "...", "sources": [...] }`
- CORS middleware configured to allow requests from `http://localhost:5173`
- Request validation via Pydantic models
- Basic logging middleware

### Key files
| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app — start with `uvicorn main:app --reload` |

### How to run (once implemented)
```bash
cd backend
.\venv\Scripts\activate   # Windows
uvicorn main:app --reload --port 8000
```

---

## Phase 6 — Frontend Development (React + Tailwind) ✅

### Plan
- Install and configure **Tailwind CSS** in the Vite project
- Build three components:
  - `ChatWindow.jsx` — scrollable message history, styled message bubbles (user vs. AI)
  - `ChatInput.jsx` — text input + send button, handles Enter key
  - `App.jsx` — wires everything together, manages message state
- `src/api/chat.js` — thin fetch wrapper for `POST /api/chat`
- Loading spinner while waiting for AI response
- Error display if the API call fails

### Key files
| File | Purpose |
|---|---|
| `frontend/src/App.jsx` | Root component, owns all state |
| `frontend/src/components/ChatWindow.jsx` | Message history display |
| `frontend/src/components/ChatInput.jsx` | User input bar |
| `frontend/src/api/chat.js` | API fetch abstraction |

### How to run (once implemented)
```bash
cd frontend
npm run dev
# → opens http://localhost:5173
```

---

## Running the Full Stack

Once all phases are complete, start both servers together:

**Terminal 1 — Backend:**
```bash
cd backend
.\venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

---

## Phase 7 — Indexing UI (File Upload from Browser) ✅

### What was done
- Added `POST /api/ingest` endpoint to `backend/main.py` — accepts multipart file uploads (`.txt`, `.json`, `.csv`, max 10 MB each), saves to `data_export/`, and runs the embedding + upsert pipeline immediately
- Added `GET /api/files` endpoint — lists files currently in `data_export/`
- Created `frontend/src/api/ingest.js` — `uploadFiles()` and `listFiles()` fetch wrappers
- Created `frontend/src/components/UploadPage.jsx` — drag-and-drop file zone, staged upload queue, per-file remove, ingestion result banner, existing file list
- Added a **Chat / Upload Data** pill tab-bar to `App.jsx` to switch between the two views

### Key files
| File | Purpose |
|---|---|
| `backend/main.py` | `POST /api/ingest`, `GET /api/files` routes |
| `frontend/src/api/ingest.js` | Fetch wrappers for upload and file listing |
| `frontend/src/components/UploadPage.jsx` | Full drag-and-drop upload UI |
| `frontend/src/App.jsx` | Tab bar wiring Chat ↔ Upload views |

---

## Phase 8 — Advanced Data Sources (PDF & WhatsApp) ✅

### What was done
- Created `backend/parsers.py` — smart document loader dispatcher:
  - **PDF** → `PyMuPDF` (`fitz`), one Document per page
  - **WhatsApp export** → custom regex parser, one Document per message with timestamp + sender embedded in both text content and metadata (enables date-specific RAG queries)
  - **Everything else** → LlamaIndex `SimpleDirectoryReader` (as before)
- Updated `backend/ingest.py` — uses `parsers.load_documents()`, added `.pdf` to `SUPPORTED_EXTS`
- Updated `backend/main.py` — uses `parsers.load_documents()`, added `.pdf` to `ALLOWED_SUFFIXES`
- Updated `frontend/src/components/UploadPage.jsx` — file picker and filter now accept `.pdf`
- Added `pymupdf>=1.24.0` to `requirements.txt`

### New package to install
```bash
cd backend
.\venv\Scripts\activate
pip install pymupdf
```

### WhatsApp format autodetection
Drop any WhatsApp `.txt` export into `data_export/` (or upload via UI). The parser detects the WA timestamp pattern automatically and preserves each message as `[date time] Sender: text`, enabling queries like:
> *"Who talked to me on March 12th?"*
> *"What did John say last Tuesday?"*

### Key files
| File | Purpose |
|---|---|
| `backend/parsers.py` | Smart document loader (PDF, WhatsApp, generic) |
| `backend/ingest.py` | Updated to use parsers, supports .pdf |
| `backend/main.py` | Updated ingest route uses parsers |
