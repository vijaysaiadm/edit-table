"""Multi-tenant registry.

Each tenant (filmmaker, editor, studio…) gets:
  - api_token      presented as X-API-Key / --tenant-token; never an LLM key
  - llm_api_key    that tenant's own LLM credentials (or null → inherit server default)
  - llm_model / llm_base_url overrides (or null → inherit)

Storage is a JSON file (default tenants.json, gitignored — it holds secrets).
For production, swap this file for a database — the Tenant interface won't change.
"""
from __future__ import annotations

import json
import secrets
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_TENANTS_FILE = "tenants.json"


@dataclass
class Tenant:
    tenant_id: str
    display_name: str
    api_token: str
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    # per-tenant runtime knobs (None → server default)
    max_concurrency: int | None = None
    minutes_per_page: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def has_own_llm(self) -> bool:
        return bool(self.llm_api_key)


class TenantRegistry:
    def __init__(self, path: str | Path = DEFAULT_TENANTS_FILE):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._tenants: dict[str, Tenant] = {}
        self._by_token: dict[str, str] = {}
        if self.path.exists():
            self.reload()

    def reload(self) -> None:
        with self._lock:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._tenants, self._by_token = {}, {}
            for tid, rec in data.get("tenants", {}).items():
                known = {k: v for k, v in rec.items() if k in Tenant.__dataclass_fields__ and k != "extra"}
                tenant = Tenant(tenant_id=tid, **known)
                self._tenants[tid] = tenant
                self._by_token[tenant.api_token] = tid

    def get(self, tenant_id: str) -> Tenant | None:
        return self._tenants.get(tenant_id)

    def by_token(self, api_token: str) -> Tenant | None:
        tid = self._by_token.get(api_token)
        return self._tenants.get(tid) if tid else None

    def list(self) -> list[Tenant]:
        return list(self._tenants.values())

    # ── management helpers (CLI: edit-table tenant …) ──────────────────────
    def _save(self) -> None:
        payload = {"tenants": {t.tenant_id: {
            "display_name": t.display_name, "api_token": t.api_token,
            "llm_api_key": t.llm_api_key, "llm_model": t.llm_model,
            "llm_base_url": t.llm_base_url, "max_concurrency": t.max_concurrency,
            "minutes_per_page": t.minutes_per_page, **t.extra,
        } for t in self._tenants.values()}}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def create(self, tenant_id: str, display_name: str, llm_api_key: str | None = None,
               llm_model: str | None = None, llm_base_url: str | None = None) -> Tenant:
        if tenant_id in self._tenants:
            raise ValueError(f"tenant '{tenant_id}' already exists")
        tenant = Tenant(tenant_id=tenant_id, display_name=display_name,
                        api_token="tok_" + secrets.token_urlsafe(24),
                        llm_api_key=llm_api_key, llm_model=llm_model, llm_base_url=llm_base_url)
        with self._lock:
            self._tenants[tenant_id] = tenant
            self._by_token[tenant.api_token] = tenant_id
            self._save()
        return tenant

    def delete(self, tenant_id: str) -> bool:
        with self._lock:
            t = self._tenants.pop(tenant_id, None)
            if t:
                self._by_token.pop(t.api_token, None)
                self._save()
            return t is not None
