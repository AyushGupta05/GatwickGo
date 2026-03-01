"""
Lightweight Supabase client helpers.

Uses the anon key only (never service role) and scopes PostgREST auth to the
caller-provided JWT so that RLS is enforced per-user.
"""

from __future__ import annotations

import os
try:
    from supabase import Client, create_client
except ImportError:  # Fallback when supabase-py is unavailable
    Client = None  # type: ignore
    create_client = None  # type: ignore

import requests
from types import SimpleNamespace
from typing import Any, Dict, Optional

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")


def _require_env() -> tuple[str, str]:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_ANON_KEY is not set")
    return SUPABASE_URL, SUPABASE_ANON_KEY


def get_anon_client() -> Client:
    """Return a Supabase client authenticated with the public anon key."""
    url, key = _require_env()
    if create_client is None:
        raise ImportError("supabase package not installed; install with `pip install supabase`")
    return create_client(url, key)


def supabase_as_user(jwt: str) -> Client:
    """Return a per-request client with the caller's JWT applied for RLS."""
    if not jwt:
        raise ValueError("JWT is required to build a Supabase user client")
    url, key = _require_env()

    if create_client is not None:
        client = create_client(url, key)
        client.postgrest.auth(jwt)
        return client

    # Minimal HTTP fallback when supabase-py is unavailable.
    rest_url = url.rstrip("/") + "/rest/v1"
    default_headers = {
        "apikey": key,
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    class _Table:
        def __init__(self, name: str):
            self.name = name

        def insert(self, row: Dict[str, Any]) -> Any:
            resp = requests.post(
                f"{rest_url}/{self.name}",
                params={"return": "representation"},
                headers=default_headers,
                json=row,
                timeout=15,
            )
            if resp.ok:
                return SimpleNamespace(data=resp.json(), error=None)
            return SimpleNamespace(data=None, error=resp.text)

    class _Client:
        def table(self, name: str) -> _Table:
            return _Table(name)

    return _Client()  # type: ignore
