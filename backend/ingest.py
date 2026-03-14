"""
ingest.py — ETL pipeline for the Personal Context Engine.

Reads all supported files from data_export/, parses them with the
appropriate parser (WhatsApp, PDF, or generic), embeds them with a
local HuggingFace model, and upserts into Supabase.

Supported types: .txt (plain or WhatsApp export), .json, .csv, .pdf

Run with:
    cd backend
    .\\venv\\Scripts\\activate   # Windows
    python ingest.py
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.supabase import SupabaseVectorStore

from db import supabase
from parsers import load_documents

# ── Config ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data_export"
SUPPORTED_EXTS = [".txt", ".json", ".csv", ".pdf"]
COLLECTION_NAME = "documents"
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_DIM = 384
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50


# ── Helpers ───────────────────────────────────────────────────────────────────

def _doc_type(file_path: str) -> str:
    """Return the normalised document type from a file extension."""
    suffix = Path(file_path).suffix.lower().lstrip(".")
    return suffix if suffix in ("txt", "json", "csv", "pdf") else "txt"


def _record_metadata(source: str, doc_type: str) -> None:
    """Insert a row in public.documents_metadata (skip if already present)."""
    existing = (
        supabase.table("documents_metadata")
        .select("id")
        .eq("source", source)
        .execute()
    )
    if existing.data:
        logger.info("Metadata already recorded for %s — skipping.", source)
        return

    supabase.table("documents_metadata").insert(
        {"source": source, "doc_type": doc_type}
    ).execute()
    logger.info("Recorded metadata: %s  [%s]", source, doc_type)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── 0. Pre-flight checks ──────────────────────────────────────────────────
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise EnvironmentError(
            "SUPABASE_DB_URL is not set in backend/.env.\n"
            "Use the direct connection string from Supabase Dashboard → Settings → Database:\n"
            "  postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres"
        )

    if not DATA_DIR.exists():
        logger.warning("data_export/ directory not found at %s — nothing to ingest.", DATA_DIR)
        return

    supported_files = [f for f in DATA_DIR.iterdir() if f.suffix.lower() in SUPPORTED_EXTS]
    if not supported_files:
        logger.warning(
            "No supported files (.txt / .json / .csv / .pdf) found in %s — nothing to ingest.",
            DATA_DIR,
        )
        return

    logger.info("Found %d file(s) to ingest in %s", len(supported_files), DATA_DIR)

    # ── 1. Load documents (routing: WhatsApp / PDF / generic) ───────────────────────
    logger.info("Loading documents ...")
    documents = []
    for f in supported_files:
        documents.extend(load_documents(f))
    logger.info("Loaded %d document(s) total.", len(documents))

    # ── 2. Record file-level metadata (once per source file, not per chunk) ───
    seen_sources: set[str] = set()
    for doc in documents:
        source = doc.metadata.get("file_path") or doc.metadata.get("file_name", "unknown")
        if source not in seen_sources:
            seen_sources.add(source)
            _record_metadata(source, _doc_type(source))

    # ── 3. Embed model ────────────────────────────────────────────────────────
    logger.info("Loading embedding model: %s  (this downloads on first run)", EMBED_MODEL)
    embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)

    # ── 4. Vector store ───────────────────────────────────────────────────────
    logger.info(
        "Connecting to Supabase vector store (collection=%s, dim=%d) ...",
        COLLECTION_NAME,
        EMBED_DIM,
    )
    vector_store = SupabaseVectorStore(
        postgres_connection_string=db_url,
        collection_name=COLLECTION_NAME,
        dimension=EMBED_DIM,
    )

    # ── 5. Chunk → embed → upsert ─────────────────────────────────────────────
    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    logger.info(
        "Chunking (size=%d, overlap=%d), embedding, and upserting — this may take a while ...",
        CHUNK_SIZE,
        CHUNK_OVERLAP,
    )
    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
        transformations=[splitter],
        show_progress=True,
    )

    logger.info("✅  Ingestion complete.")


if __name__ == "__main__":
    main()
