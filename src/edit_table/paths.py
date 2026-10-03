"""Resolve storage paths — local disk by default, /tmp on read-only serverless hosts
(Vercel, AWS Lambda…) where only /tmp is writable. Override with EDIT_TABLE_DATA_DIR."""
from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    override = os.getenv("EDIT_TABLE_DATA_DIR")
    if override:
        return Path(override)
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp/edit-table")
    return Path(".")


def data_path(filename: str) -> Path:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / filename
