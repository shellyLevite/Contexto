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

print("[STARTUP] db.py: Starting imports...", flush=True)
from dotenv import load_dotenv
from supabase import create_client, Client
print("[STARTUP] db.py: Imports done, loading .env...", flush=True)

# Load variables from backend/.env
load_dotenv()

logger = logging.getLogger(__name__)


def _init_client() -> Client:
    """Read credentials from environment and return a Supabase client."""
    print("[STARTUP] db.py: _init_client() called", flush=True)
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        msg = "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in backend/.env"
        print(f"[STARTUP] db.py: ERROR - {msg}", flush=True)
        raise EnvironmentError(msg)

    print(f"[STARTUP] db.py: Creating Supabase client with URL: {url}", flush=True)
    client = create_client(url, key)
    print("[STARTUP] db.py: Supabase client created successfully", flush=True)
    logger.info("Supabase client initialized.")
    return client


# ── Singleton (lazy initialization) ───────────────────────────────────────────
# Imported by ingest.py, rag.py, main.py, etc.
# Initialized on first access, not at import time
_supabase_instance = None


def get_supabase() -> Client:
    """Get the Supabase client, initializing it lazily on first access."""
    global _supabase_instance
    if _supabase_instance is None:
        print("[STARTUP] db.py: Lazy-initializing supabase...", flush=True)
        _supabase_instance = _init_client()
    return _supabase_instance


# For backward compatibility: supabase = get_supabase() but accessed lazily
class SupabaseLazy:
    """Lazy proxy to Supabase client."""
    def __getattr__(self, name):
        return getattr(get_supabase(), name)


supabase = SupabaseLazy()
print("[STARTUP] db.py: Supabase lazy singleton created ✅", flush=True)


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
