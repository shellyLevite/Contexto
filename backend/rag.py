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

import json
import logging
import os
import re

from dotenv import load_dotenv

load_dotenv()

from llama_index.core import VectorStoreIndex, PromptTemplate
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq
from llama_index.vector_stores.supabase import SupabaseVectorStore

logger = logging.getLogger(__name__)

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Number of chunks to retrieve per query — higher catches exact-keyword matches
# that fall outside the top semantic nearest-neighbours.
TOP_K = 20

# Custom QA prompt that instructs the LLM to respect exact Hebrew tokens & dates.
_QA_PROMPT = PromptTemplate(
    "Below are excerpts from personal WhatsApp conversations and documents.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "You are a personal assistant. Rules:\n"
    "- Pay close attention to EXACT dates, times, sender names, and specific "
    "Hebrew slang words present in the context.\n"
    "- Answer in the same language as the question (Hebrew or English).\n"
    "- If the answer is explicitly present in the context, quote the relevant "
    "line(s) verbatim.\n"
    "- If the context does not contain the answer, say so honestly — do not "
    "hallucinate.\n"
    "Question: {query_str}\n"
    "Answer: "
)

# ── Keyword extraction helpers ─────────────────────────────────────────────────

# Matches DD.MM.YYYY or DD/MM/YYYY or DD.MM.YY etc.
_DATE_RE = re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b")

# Minimum token length to treat a non-ASCII word as a hard keyword worth
# exact-matching (filters out short Hebrew particles like "ב", "של", "מה").
# Specifically targets the Hebrew Unicode blocks (U+0590-U+05FF, U+FB1D-U+FB4F).
_HEBREW_WORD_RE = re.compile(r"[\u0590-\u05FF\uFB1D-\uFB4F]{3,}")

# BiDi control characters that browsers/WhatsApp may silently embed in RTL text.
_BIDI_RE = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")


def _extract_hard_tokens(question: str) -> list[str]:
    """
    Return terms from question worth exact-matching:
      - Quoted exact phrases (e.g. "some phrase")
      - Dates: DD.MM.YYYY / DD/MM/YYYY
      - Hebrew words >= 3 chars (Hebrew Unicode block only)
    BiDi control characters are stripped first.
    """
    clean_q = _BIDI_RE.sub("", question)
    tokens: list[str] = []

    # 1. Quoted exact phrases
    for phrase in re.findall('"([^"]+)"', clean_q):
        phrase = phrase.strip()
        if phrase and phrase not in tokens:
            tokens.append(phrase)

    # 2. Dates
    for m in _DATE_RE.finditer(clean_q):
        if m.group() not in tokens:
            tokens.append(m.group())

    # 3. Hebrew words (Hebrew Unicode blocks only, >= 3 chars)
    for word in _HEBREW_WORD_RE.findall(clean_q):
        if word not in tokens:
            tokens.append(word)

    return tokens


def _exact_fetch(hard_tokens: list[str], limit: int = 50) -> list[NodeWithScore]:
    """
    Query vecs.documents directly via psycopg2 ILIKE for each hard token.
    Returns a deduplicated list of NodeWithScore objects (score=1.0, ranked
    above vector results).
    """
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        return []

    try:
        import psycopg2
    except ImportError:
        logger.warning("psycopg2 not installed -- skipping exact-match fetch.")
        return []

    SQL = """
        SELECT id, metadata
        FROM vecs.documents
        WHERE metadata::text ILIKE %(pattern)s
        LIMIT %(limit)s
    """

    seen_ids: set[str] = set()
    nodes: list[NodeWithScore] = []

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        for token in hard_tokens:
            cur.execute(SQL, {"pattern": f"%{token}%", "limit": limit})
            for row_id, metadata in cur.fetchall():
                if row_id in seen_ids:
                    continue
                seen_ids.add(row_id)

                node_content_raw = metadata.get("_node_content", "{}")
                try:
                    node_obj = json.loads(node_content_raw)
                    text = node_obj.get("text") or node_obj.get("content") or ""
                except (json.JSONDecodeError, TypeError):
                    text = str(node_content_raw)

                file_name = metadata.get("file_name", "")
                file_path = metadata.get("file_path", "")

                node = TextNode(
                    text=text,
                    metadata={"file_name": file_name, "file_path": file_path},
                )
                nodes.append(NodeWithScore(node=node, score=1.0))
                logger.debug("Exact hit for %r: id=%s", token, row_id)

        cur.close()
        conn.close()
    except Exception as e:
        logger.warning("Exact-match fetch failed: %s", e)

    logger.info("Exact-match fetch: %d chunk(s) for tokens %s", len(nodes), hard_tokens)
    return nodes


# -- Lazy singletons -----------------------------------------------------------
_retriever = None
_llm_singleton = None


def _build_engine():
    """Validate env, wire up models + vector store, return (retriever, llm)."""
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        raise EnvironmentError(
            "SUPABASE_DB_URL is not set in backend/.env.\n"
            "Find it in: Supabase Dashboard -> Settings -> Database -> Connection string (URI)."
        )

    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key or groq_api_key == "your_groq_api_key":
        raise EnvironmentError(
            "GROQ_API_KEY is not set in backend/.env.\n"
            "Get one at https://console.groq.com/keys"
        )

    # llama3-8b-8192 was decommissioned by Groq; llama-3.1-8b-instant is the replacement.
    llm_model = os.environ.get("LLM_MODEL", "llama-3.1-8b-instant")

    logger.info("Initialising RAG engine (embed=%s, llm=%s, top_k=%d) ...",
                EMBED_MODEL, llm_model, TOP_K)

    embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
    llm = Groq(model=llm_model, api_key=groq_api_key)

    vector_store = SupabaseVectorStore(
        postgres_connection_string=db_url,
        collection_name="documents",
        dimension=384,
    )

    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
    )

    # Bare retriever: pure vector lookup, no internal LLM calls.
    retriever = index.as_retriever(similarity_top_k=TOP_K)

    logger.info("RAG engine ready.")
    return retriever, llm


# -- Public API ----------------------------------------------------------------

def query(question: str) -> dict:
    """
    Hybrid search: exact-match pre-fetch (dates / Hebrew words) merged with
    vector retrieval, then a single LLM call for synthesis.

    Returns: {"answer": str, "sources": list[str]}
    """
    global _retriever, _llm_singleton
    if _retriever is None:
        _retriever, _llm_singleton = _build_engine()

    logger.info("RAG query: %r", question)

    # 1. Extract hard tokens (dates, quoted phrases, Hebrew words)
    hard_tokens = _extract_hard_tokens(question)
    print(f"EXTRACTED TOKENS: {hard_tokens}", flush=True)

    # 2. Exact-match DB fetch (bypasses embedding entirely)
    exact_nodes: list[NodeWithScore] = _exact_fetch(hard_tokens) if hard_tokens else []
    print(f"EXACT FETCH FOUND: {len(exact_nodes)} chunks", flush=True)

    # 3. Vector retrieval -- pure retrieval, no LLM calls
    vector_nodes: list[NodeWithScore] = _retriever.retrieve(question)
    logger.info("Vector retrieval: %d chunks", len(vector_nodes))

    # 4. Merge: exact hits first, then vector hits (dedup by text prefix)
    seen_texts: set[str] = set()
    merged: list[NodeWithScore] = []

    for nws in exact_nodes + vector_nodes:
        key = nws.node.text[:120]
        if key not in seen_texts:
            seen_texts.add(key)
            merged.append(nws)

    logger.info("Merged context: %d chunks (%d exact + %d vector)",
                len(merged), len(exact_nodes), len(vector_nodes))

    # 5. Single LLM call with full merged context
    context_str = "\n\n---\n\n".join(nws.node.text for nws in merged[:TOP_K])
    prompt = _QA_PROMPT.format(context_str=context_str, query_str=question)
    llm_response = _llm_singleton.complete(prompt)
    answer = llm_response.text.strip()
    logger.info("Answer: %d chars", len(answer))

    # 6. Collect unique sources
    seen_src: set[str] = set()
    sources: list[str] = []
    for nws in merged:
        file_src = (
            nws.node.metadata.get("file_path")
            or nws.node.metadata.get("file_name")
            or "unknown"
        )
        if file_src not in seen_src:
            seen_src.add(file_src)
            sources.append(file_src)

    logger.info("Sources: %s", sources)
    return {"answer": answer, "sources": sources}


# -- CLI smoke-test ------------------------------------------------------------
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
