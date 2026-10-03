"""Operator-managed server settings — the layer between env vars and tenants.

Priority when resolving an LLM credential:
  1. tenant's own key (tenants.json)
  2. server settings set through the admin UI (server_settings.json)
  3. environment / .env defaults

server_settings.json is gitignored — it can hold the operator's API key.
"""
from __future__ import annotations

import json
import secrets
import threading
from pathlib import Path

DEFAULT_SETTINGS_FILE = "server_settings.json"


class ServerSettingsStore:
    def __init__(self, path: str | Path = DEFAULT_SETTINGS_FILE):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data: dict = {"llm_api_key": None, "llm_model": None, "llm_base_url": None}
        self._admin_token: str | None = None
        if self.path.exists():
            self.reload()

    def reload(self) -> None:
        with self._lock:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._data.update({k: raw.get(k) for k in self._data})
            self._admin_token = raw.get("admin_token")

    def _save(self) -> None:
        payload = dict(self._data)
        payload["admin_token"] = self._admin_token
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ── admin token ─────────────────────────────────────────────────────────
    def ensure_admin_token(self) -> str:
        """Return the admin token, generating+persisting one on first run."""
        with self._lock:
            if not self._admin_token:
                self._admin_token = "adm_" + secrets.token_urlsafe(24)
                self._save()
            return self._admin_token

    def verify_admin(self, token: str | None) -> bool:
        return bool(token) and token == self._admin_token

    # ── server default LLM settings ─────────────────────────────────────────
    def get(self) -> dict:
        return dict(self._data)

    def update(self, llm_api_key: str | None = None, llm_model: str | None = None,
               llm_base_url: str | None = None) -> dict:
        """Empty string / None leaves a field unchanged; use clear() to unset."""
        with self._lock:
            if llm_api_key:
                self._data["llm_api_key"] = llm_api_key
            if llm_model:
                self._data["llm_model"] = llm_model
            if llm_base_url:
                self._data["llm_base_url"] = llm_base_url
            self._save()
        return self.get()
