"""Vercel serverless entry point.

Vercel's Python builder imports this module and serves the `app` object (an ASGI app).
Everything runs from /tmp on Vercel: tenant registry, server settings and reports are
ephemeral — see README "Deploying to Vercel" for what that means.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from edit_table.server import create_app  # noqa: E402

# app factory resolves tenants/settings files + reports dir under /tmp automatically
app = create_app()
