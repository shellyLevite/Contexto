"""
main.py — FastAPI application for the Personal Context Engine.

Routes:
    POST /api/chat    { "question": "..." }  →  { "answer": "...", "sources": [...] }
    POST /api/ingest  multipart files        →  { "ingested": [...], "skipped": [...] }
    GET  /api/files                          →  { "files": [...] }
    GET  /health                             →  { "status": "ok" }

Start with:
    cd backend
    .\\venv\\Scripts\\activate   # Windows
    uvicorn main:app --reload --port 8000
"""

import logging
import shutil
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ingest import (
    COLLECTION_NAME,
    DATA_DIR,
    EMBED_DIM,
    SUPPORTED_EXTS,
    _doc_type,
    _record_metadata,
)
from rag import query as rag_query

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Personal Context Engine",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Vite dev server and any local production build to reach the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

# ── Request logging middleware ────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s  →  %d  (%.0f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


# ── Pydantic models ───────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
def health():
    """Simple liveness check."""
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
def chat(body: ChatRequest):
    """
    Accepts a natural-language question, runs it through the RAG pipeline,
    and returns the generated answer together with the source file paths that
    were retrieved from the vector store.
    """
    logger.info("Question: %r", body.question)
    result = rag_query(body.question)
    return ChatResponse(answer=result["answer"], sources=result["sources"])


# ── Ingest routes ─────────────────────────────────────────────────────────────

ALLOWED_SUFFIXES = set(SUPPORTED_EXTS)  # {".txt", ".json", ".csv"}
MAX_FILE_SIZE = 10 * 1024 * 1024        # 10 MB per file


class IngestResponse(BaseModel):
    ingested: list[str]
    skipped: list[str]


class FileListResponse(BaseModel):
    files: list[dict]


@app.get("/api/files", response_model=FileListResponse, tags=["ingest"])
def list_files():
    """Return all files currently sitting in data_export/."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(DATA_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in ALLOWED_SUFFIXES:
            files.append({"name": f.name, "size": f.stat().st_size, "type": f.suffix.lstrip(".")})
    return FileListResponse(files=files)


@app.post("/api/ingest", response_model=IngestResponse, tags=["ingest"])
async def ingest_files(files: list[UploadFile]):
    """
    Upload one or more .txt / .json / .csv files to data_export/ and run
    the embedding + upsert pipeline on each accepted file.
    """
    import os
    from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from llama_index.vector_stores.supabase import SupabaseVectorStore

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="SUPABASE_DB_URL not configured.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    ingested: list[str] = []
    skipped: list[str] = []

    saved_paths: list[Path] = []

    for upload in files:
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            skipped.append(f"{upload.filename} (unsupported type)")
            continue

        dest = DATA_DIR / upload.filename
        content = await upload.read()

        if len(content) > MAX_FILE_SIZE:
            skipped.append(f"{upload.filename} (exceeds 10 MB limit)")
            continue

        dest.write_bytes(content)
        saved_paths.append(dest)
        logger.info("Saved upload: %s (%d bytes)", dest.name, len(content))

    if not saved_paths:
        return IngestResponse(ingested=[], skipped=skipped)

    # Run embedding pipeline on the newly saved files only
    embed_model_name = os.environ.get("EMBED_MODEL_NAME", "BAAI/bge-small-en-v1.5")
    embed_model = HuggingFaceEmbedding(model_name=embed_model_name)

    vector_store = SupabaseVectorStore(
        postgres_connection_string=db_url,
        collection_name=COLLECTION_NAME,
        dimension=EMBED_DIM,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)

    reader = SimpleDirectoryReader(input_files=[str(p) for p in saved_paths])
    documents = reader.load_data()

    for doc in documents:
        src = doc.metadata.get("file_path") or doc.metadata.get("file_name", "unknown")
        _record_metadata(src, _doc_type(src))

    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
        transformations=[splitter],
        show_progress=False,
    )

    ingested = [p.name for p in saved_paths]
    logger.info("Ingest complete: %s", ingested)
    return IngestResponse(ingested=ingested, skipped=skipped)
