"""
main.py — FastAPI application for the Personal Context Engine.

Routes:
    POST /api/chat   { "question": "..." }  →  { "answer": "...", "sources": [...] }
    GET  /health                             →  { "status": "ok" }

Start with:
    cd backend
    .\\venv\\Scripts\\activate   # Windows
    uvicorn main:app --reload --port 8000
"""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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
    allow_methods=["GET", "POST"],
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
