"""
test_db.py — Verify stored chunks by searching raw text in vecs.documents.

Bypasses the embedding pipeline entirely; queries PostgreSQL directly via
the SUPABASE_DB_URL connection string.

How chunks are stored by llama_index's SupabaseVectorStore:
  Table : vecs.documents
  Column: metadata  (JSONB)
            └─ "_node_content"  →  JSON string containing the chunk text

Usage:
    cd backend
    .\\venv\\Scripts\\activate
    python test_db.py [search_term]

    # Default search term is "בעלולי" if none is provided.
    python test_db.py
    python test_db.py "צליל גרימברג"
    python test_db.py "25.2.2026"
"""

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
SEARCH_TERM = sys.argv[1] if len(sys.argv) > 1 else "בעלולי"
DB_URL = os.environ.get("SUPABASE_DB_URL")

if not DB_URL:
    print("ERROR: SUPABASE_DB_URL is not set in backend/.env")
    sys.exit(1)

# ── Connect ───────────────────────────────────────────────────────────────────
try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 is not installed.")
    print("  Run: pip install psycopg2-binary")
    sys.exit(1)

print(f"Searching vecs.documents for: {SEARCH_TERM!r}\n")

try:
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
except Exception as e:
    print(f"ERROR: Could not connect to database: {e}")
    sys.exit(1)

# ── Query ─────────────────────────────────────────────────────────────────────
# llama_index stores the node text inside metadata->>'_node_content' as a JSON
# string.  We cast the whole metadata column to text for the ILIKE so we catch
# the term whether it's in the node content or in any other metadata field.
SQL = """
SELECT
    id,
    metadata->>'_node_content' AS node_content_json,
    metadata - '_node_content'  AS other_metadata
FROM vecs.documents
WHERE metadata::text ILIKE %(pattern)s
ORDER BY id
LIMIT 50;
"""

try:
    cur.execute(SQL, {"pattern": f"%{SEARCH_TERM}%"})
    rows = cur.fetchall()
except Exception as e:
    print(f"ERROR running query: {e}")
    cur.close()
    conn.close()
    sys.exit(1)

cur.close()
conn.close()

# ── Output ────────────────────────────────────────────────────────────────────
if not rows:
    print(f"NO RESULTS — '{SEARCH_TERM}' was not found in any stored chunk.")
    print("\nPossible causes:")
    print("  • The file was not ingested yet (run ingest.py or re-upload via the UI).")
    print("  • The parser did not match this line (regex issue in parsers.py).")
    print("  • The chunk was split across two chunks by the sentence splitter.")
else:
    print(f"Found {len(rows)} chunk(s) containing '{SEARCH_TERM}':\n")
    print("=" * 72)
    for i, (row_id, node_content_json, other_meta) in enumerate(rows, 1):
        # node_content_json is itself a JSON string; decode it to get the text
        try:
            node_obj = json.loads(node_content_json) if node_content_json else {}
            text = node_obj.get("text") or node_obj.get("content") or node_content_json
        except (json.JSONDecodeError, TypeError):
            text = node_content_json or "(empty)"

        print(f"[{i}] ID: {row_id}")
        print(f"    Text:\n{text}")
        if other_meta:
            # Print a neat subset of the metadata (skip embeddings-related keys)
            clean = {k: v for k, v in other_meta.items()
                     if k not in ("_node_type", "relationships")}
            print(f"    Metadata: {json.dumps(clean, ensure_ascii=False)}")
        print("-" * 72)
