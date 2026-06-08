"""Naver session cache, persisted to disk.

Stores Playwright storage_state (cookies) per login id so we don't re-login on
every apply. Seeded once via `python -m app.seed_session`, reused afterwards.

Files live under gateway/sessions/ with 0600 perms (they contain cookies).
"""

import hashlib
import json
import os
import time
from pathlib import Path

from app.config import get_settings

settings = get_settings()
SESSIONS_DIR = Path(__file__).resolve().parents[1] / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)


def _path(login_id: str) -> Path:
    digest = hashlib.sha256(login_id.encode()).hexdigest()[:16]
    return SESSIONS_DIR / f"{digest}.json"


class SessionStore:
    def get(self, login_id: str) -> str | None:
        path = _path(login_id)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                if time.time() - data.get("saved_at", 0) <= settings.session_ttl_seconds:
                    return json.dumps(data["state"])
            except (ValueError, OSError):
                pass
        # Fallback: reuse the desktop app's login session (single-tenant).
        desktop = Path.home() / ".smartplace_beta" / "session.json"
        if desktop.exists():
            try:
                return desktop.read_text()
            except OSError:
                pass
        return None

    def put(self, login_id: str, storage_state_json: str) -> None:
        path = _path(login_id)
        payload = {"saved_at": time.time(), "state": json.loads(storage_state_json)}
        path.write_text(json.dumps(payload))
        os.chmod(path, 0o600)

    def has(self, login_id: str) -> bool:
        return self.get(login_id) is not None

    def invalidate(self, login_id: str) -> None:
        _path(login_id).unlink(missing_ok=True)


_store = SessionStore()


def get_session_store() -> SessionStore:
    return _store
