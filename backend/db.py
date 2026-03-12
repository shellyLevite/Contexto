"""
db.py — Supabase client singleton.

Initializes a single Supabase client using credentials from the .env file.
Import `supabase` from this module in any other backend file that needs DB access.

Usage:
    from db import supabase
    result = supabase.table("documents_metadata").select("*").execute()
"""

import os
import logging

from dotenv import load_dotenv
from supabase import create_client, Client

# Load variables from backend/.env
load_dotenv()

logger = logging.getLogger(__name__)


def _init_client() -> Client:
    """Read credentials from environment and return a Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in backend/.env"
        )

    client = create_client(url, key)
    logger.info("Supabase client initialized.")
    return client


# ── Singleton ─────────────────────────────────────────────────────────────────
# Imported by ingest.py, rag.py, main.py, etc.
supabase: Client = _init_client()


if __name__ == "__main__":
    # Quick connection test — run with: .\venv\Scripts\python db.py
    logging.basicConfig(level=logging.INFO)
    try:
        # Ping the DB by listing tables in the public schema
        result = supabase.table("documents_metadata").select("id").limit(1).execute()
        print("✅ Supabase connection successful!")
        print(f"   documents_metadata rows returned: {len(result.data)}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
