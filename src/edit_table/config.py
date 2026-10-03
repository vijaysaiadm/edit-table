"""Configuration — all secrets come from the environment, never from code or prompts.

Two layers:
  - server default (env / .env): used when a tenant has no own LLM credentials
  - per-tenant overrides (tenants.json via TenantRegistry): each tenant can bring
    their own API key, model, base URL and concurrency limits
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is optional — real env vars still work
    pass

DEFAULT_BASE_URL = "https://api.openai.com/v1"


@dataclass
class Settings:
    tenant_id: str = "default"      # who this run belongs to (data isolation + audit)
    display_name: str = "Default Tenant"
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o"))
    # Cheap/fast model for per-scene workers; falls back to `model` if unset.
    worker_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL_WORKER") or os.getenv("LLM_MODEL", "gpt-4o"))
    max_concurrency: int = field(default_factory=lambda: int(os.getenv("MAX_CONCURRENCY", "6")))
    minutes_per_page: float = field(default_factory=lambda: float(os.getenv("MINUTES_PER_PAGE", "1.0")))
    mock: bool = False  # offline heuristic mode for testing the pipeline end-to-end

    def require_key(self) -> None:
        if self.mock:
            return
        if not self.api_key:
            raise SystemExit(
                f"LLM_API_KEY is not set for tenant '{self.tenant_id}'.\n"
                "Either give the tenant an llm_api_key in tenants.json, or set a server\n"
                "default: cp .env.example to .env and add the key (never commit it)."
            )


def load_settings(mock: bool = False, tenant: "object | None" = None) -> Settings:
    """Server-default settings, optionally overridden by a Tenant record."""
    s = Settings()
    if tenant is not None:
        s.tenant_id = tenant.tenant_id
        s.display_name = tenant.display_name
        if tenant.llm_api_key:
            s.api_key = tenant.llm_api_key
        if tenant.llm_base_url:
            s.base_url = tenant.llm_base_url
        if tenant.llm_model:
            s.model = tenant.llm_model
            s.worker_model = tenant.llm_model
        if tenant.max_concurrency:
            s.max_concurrency = tenant.max_concurrency
        if tenant.minutes_per_page:
            s.minutes_per_page = tenant.minutes_per_page
    s.mock = mock
    s.require_key()
    return s
