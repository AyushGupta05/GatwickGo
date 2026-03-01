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

    class _Query:
        def __init__(self, name: str):
            self.name = name
            self._method = "GET"
            self._payload: Optional[Dict[str, Any]] = None
            self._params: Dict[str, Any] = {}
            self._headers: Dict[str, str] = {}

        def select(self, columns: str = "*") -> "_Query":
            self._method = "GET"
            self._params["select"] = columns
            return self

        def insert(self, row: Dict[str, Any]) -> "_Query":
            self._method = "POST"
            self._payload = row
            # PostgREST expects return semantics via Prefer header, not a filter param.
            self._headers["Prefer"] = "return=representation"
            return self

        def update(self, row: Dict[str, Any]) -> "_Query":
            self._method = "PATCH"
            self._payload = row
            # PostgREST expects return semantics via Prefer header, not a filter param.
            self._headers["Prefer"] = "return=representation"
            return self

        def eq(self, column: str, value: Any) -> "_Query":
            self._params[column] = f"eq.{value}"
            return self

        def limit(self, count: int) -> "_Query":
            self._params["limit"] = str(count)
            return self

        def execute(self) -> Any:
            resp = requests.request(
                self._method,
                f"{rest_url}/{self.name}",
                params=self._params,
                headers={**default_headers, **self._headers},
                json=self._payload,
                timeout=15,
            )
            if resp.ok:
                if not resp.text:
                    return SimpleNamespace(data=[], error=None)
                return SimpleNamespace(data=resp.json(), error=None)
            return SimpleNamespace(data=None, error=resp.text)

    class _Client:
        def table(self, name: str) -> _Query:
            return _Query(name)

    return _Client()  # type: ignore
