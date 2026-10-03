"""FastAPI server: multi-tenant REST API + embedded web UI.

Auth: every client presents its tenant token as `X-API-Key`. The token maps to a
tenant record; each tenant may carry its own LLM key/model, and every artifact is
written under reports/<tenant_id>/. Unknown tokens get 401.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from .config import load_settings
from .orchestrator import run_analysis
from .report import render_report, save_outputs
from .tenants import DEFAULT_TENANTS_FILE, Tenant, TenantRegistry

WEB_DIR = Path(__file__).parent / "web"
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# per-tenant single-flight guards: tenants never see or block each other
_running: dict[str, bool] = {}


def create_app(tenants_file: str | Path = DEFAULT_TENANTS_FILE) -> FastAPI:
    registry = TenantRegistry(tenants_file)
    app = FastAPI(title="edit-table", version="0.2.0")
    app.state.registry = registry

    def current_tenant(token: str | None = Depends(api_key_header)) -> Tenant:
        if not token:
            raise HTTPException(401, "Missing X-API-Key header.")
        tenant = registry.by_token(token)
        if not tenant:
            raise HTTPException(401, "Unknown API key.")
        return tenant

    class AnalyzeRequest(BaseModel):
        screenplay_text: str
        title: str = "Untitled Screenplay"
        target_runtime: float | None = None
        stage: str = "full"

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "tenants": len(registry.list())}

    async def _run(tenant: Tenant, tmp: str, target_runtime: float | None,
                   stage: str) -> JSONResponse:
        if _running.get(tenant.tenant_id):
            raise HTTPException(409, "This tenant already has an analysis running.")
        _running[tenant.tenant_id] = True
        try:
            settings = load_settings(tenant=tenant)
            stages = (1,) if stage == "1" else (1, 2, 3)
            result = await run_analysis(tmp, settings, target_runtime=target_runtime,
                                        stages=stages)
            md, js = save_outputs(result, "reports")
            return JSONResponse({"tenant": tenant.tenant_id,
                                 "report_md": render_report(result),
                                 "report_path": str(md), "data_path": str(js),
                                 "stages": result.stages})
        finally:
            _running[tenant.tenant_id] = False

    @app.post("/api/analyze")
    async def analyze_text(req: AnalyzeRequest,
                           tenant: Tenant = Depends(current_tenant)) -> JSONResponse:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8") as f:
            f.write(req.screenplay_text)
            tmp = f.name
        return await _run(tenant, tmp, req.target_runtime, req.stage)

    @app.post("/api/analyze-file")
    async def analyze_file(file: UploadFile = File(...),
                           target_runtime: float | None = Form(None),
                           stage: str = Form("full"),
                           tenant: Tenant = Depends(current_tenant)) -> JSONResponse:
        suffix = Path(file.filename or "script.txt").suffix or ".txt"
        with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as f:
            f.write(await file.read())
            tmp = f.name
        return await _run(tenant, tmp, target_runtime, stage)

    return app


app = create_app()  # default instance for `uvicorn edit_table.server:app`
