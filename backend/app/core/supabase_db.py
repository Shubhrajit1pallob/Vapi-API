"""
Supabase client for the FastAPI backend.
Uses the service role key (bypasses RLS) — server-side only.
"""
from __future__ import annotations

from typing import Optional

from supabase import create_client, Client

from backend.app.core.config import settings

_client: Optional[Client] = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        if not settings.supabase_url or not settings.supabase_service_key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in your .env file."
            )
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client
