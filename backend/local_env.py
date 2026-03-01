"""
Minimal local .env loader for the Flask app.

This keeps backend config working in local development without depending on a
fresh shell session or an extra dotenv package.
"""

from __future__ import annotations

import os
from pathlib import Path


def _parse_env_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return

    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if not key or key in os.environ:
                continue

            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]

            os.environ[key] = value
    except Exception:
        # Ignore malformed local env files and fall back to real process env.
        return


def load_local_env() -> None:
    backend_dir = Path(__file__).resolve().parent
    repo_root = backend_dir.parent

    # Load repo-level .env first, then backend/.env for backend-only overrides.
    _parse_env_file(repo_root / ".env")
    _parse_env_file(backend_dir / ".env")
