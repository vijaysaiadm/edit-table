"""Configuration — all secrets come from the environment, never from code or prompts."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is optional — real env vars still work
    pass


@dataclass
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
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
                "LLM_API_KEY is not set.\n"
                "Copy .env.example to .env and add your key:\n"
                "  cp .env.example .env\n"
                "  # then edit .env — never commit it, .gitignore already excludes it."
            )


def load_settings(mock: bool = False) -> Settings:
    s = Settings()
    s.mock = mock
    s.require_key()
    return s
