"""
rag.py — RAG query engine for the Personal Context Engine.

Exposes a single public function:

    result = query("What did I write about X?")
    # result = {"answer": "...", "sources": [...]}

Flow:
    User question
        → embed (HuggingFace local)
        → similarity search (Supabase pgvector, top-K)
        → retrieved chunks injected into prompt
        → Groq API (Llama 3) → answer

The query engine is built lazily on the first call and cached for the
lifetime of the process (important for FastAPI — no cold start on every
request after the first one).
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from llama_index.core import VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq
from llama_index.vector_stores.supabase import SupabaseVectorStore

logger = logging.getLogger(__name__)

# ── Lazy singleton ─────────────────────────────────────────────────────────────
_query_engine = None


def _build_query_engine():
    """Validate env, wire up models + vector store, return a query engine."""
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise EnvironmentError(
            "SUPABASE_DB_URL is not set in backend/.env.\n"
            "Find it in: Supabase Dashboard → Settings → Database → Connection string (URI)."
        )

    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key or groq_api_key == "your_groq_api_key":
        raise EnvironmentError(
            "GROQ_API_KEY is not set in backend/.env.\n"
            "Get one at https://console.groq.com/keys"
        )

    embed_model_name = os.environ.get("EMBED_MODEL_NAME", "BAAI/bge-small-en-v1.5")
    llm_model = os.environ.get("LLM_MODEL", "llama3-8b-8192")
    top_k = int(os.environ.get("TOP_K", "5"))

    logger.info("Initialising RAG engine (embed=%s, llm=%s, top_k=%d) ...",
                embed_model_name, llm_model, top_k)

    # Local embedding model — same model used by ingest.py
    embed_model = HuggingFaceEmbedding(model_name=embed_model_name)

    # Groq LLM
    llm = Groq(model=llm_model, api_key=groq_api_key)

    # Connect to the existing vecs.documents collection created by ingest.py
    vector_store = SupabaseVectorStore(
        postgres_connection_string=db_url,
        collection_name="documents",
        dimension=384,
    )

    # Load index from the existing vector store — no re-embedding
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
    )

    query_engine = index.as_query_engine(
        llm=llm,
        similarity_top_k=top_k,
    )

    logger.info("RAG engine ready.")
    return query_engine


# ── Public API ─────────────────────────────────────────────────────────────────

def query(question: str) -> dict:
    """
    Embed *question*, retrieve the most relevant chunks from Supabase,
    generate an answer via Groq, and return:

        {"answer": str, "sources": list[str]}

    The query engine is built on the first call and reused afterward.
    """
    global _query_engine
    if _query_engine is None:
        _query_engine = _build_query_engine()

    logger.info("RAG query: %r", question)
    response = _query_engine.query(question)

    answer = str(response).strip()

    # Collect source file paths from retrieved nodes — deduplicated, order preserved
    seen: set[str] = set()
    sources: list[str] = []
    for node in response.source_nodes:
        src = (
            node.metadata.get("file_path")
            or node.metadata.get("file_name")
            or "unknown"
        )
        if src not in seen:
            seen.add(src)
            sources.append(src)

    logger.info("Answer length: %d chars, sources: %s", len(answer), sources)
    return {"answer": answer, "sources": sources}


# ── CLI smoke-test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    question = " ".join(sys.argv[1:]) or "What is in my personal data?"
    result = query(question)
    print("\nAnswer:\n", result["answer"])
    print("\nSources:", result["sources"])
