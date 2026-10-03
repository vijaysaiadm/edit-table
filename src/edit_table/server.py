"""FastAPI server: multi-tenant REST API + web UI + admin settings UI.

Auth model:
  - tenants  → X-API-Key (per-tenant token)
  - operator → X-Admin-Key (auto-generated on first run, printed at startup,
                also stored in server_settings.json — see README)

LLM credential priority: tenant key > admin-set server default > env/.env.
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
from .server_settings import ServerSettingsStore
from .tenants import DEFAULT_TENANTS_FILE, Tenant, TenantRegistry

WEB_DIR = Path(__file__).parent / "web"
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

# per-tenant single-flight guards: tenants never see or block each other
_running: dict[str, bool] = {}


def create_app(tenants_file: str | Path = DEFAULT_TENANTS_FILE,
               settings_file: str | Path = "server_settings.json") -> FastAPI:
    registry = TenantRegistry(tenants_file)
    store = ServerSettingsStore(settings_file)
    app = FastAPI(title="edit-table", version="0.3.0")
    app.state.registry, app.state.settings_store = registry, store

    @app.on_event("startup")
    def announce_admin() -> None:
        print(f"\n  🔑 Admin UI: http://localhost:7100/admin  (X-Admin-Key: {store.ensure_admin_token()})\n")

    def current_tenant(token: str | None = Depends(api_key_header)) -> Tenant:
        if not token:
            raise HTTPException(401, "Missing X-API-Key header.")
        tenant = registry.by_token(token)
        if not tenant:
            raise HTTPException(401, "Unknown API key.")
        return tenant

    def admin(token: str | None = Depends(admin_key_header)) -> None:
        if not store.verify_admin(token):
            raise HTTPException(401, "Missing or invalid X-Admin-Key header.")

    class AnalyzeRequest(BaseModel):
        screenplay_text: str
        title: str = "Untitled Screenplay"
        target_runtime: float | None = None
        stage: str = "full"

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/admin")
    def admin_page() -> FileResponse:
        return FileResponse(WEB_DIR / "admin.html")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "tenants": len(registry.list())}

    # ── tenant analysis ─────────────────────────────────────────────────────
    async def _run(tenant: Tenant, tmp: str, target_runtime: float | None,
                   stage: str) -> JSONResponse:
        if _running.get(tenant.tenant_id):
            raise HTTPException(409, "This tenant already has an analysis running.")
        _running[tenant.tenant_id] = True
        try:
            settings = load_settings(tenant=tenant, server_defaults=store.get())
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

    # ── admin: server default LLM settings ──────────────────────────────────
    class SettingsRequest(BaseModel):
        llm_api_key: str | None = None
        llm_model: str | None = None
        llm_base_url: str | None = None

    @app.get("/api/admin/settings")
    def get_settings(_: None = Depends(admin)) -> dict:
        data = store.get()
        data["llm_api_key_set"] = bool(data.get("llm_api_key"))
        data["llm_api_key"] = ("••••" + data["llm_api_key"][-4:]) if data.get("llm_api_key") else None
        return data

    @app.post("/api/admin/settings")
    def update_settings(req: SettingsRequest, _: None = Depends(admin)) -> dict:
        store.update(llm_api_key=req.llm_api_key, llm_model=req.llm_model,
                     llm_base_url=req.llm_base_url)
        return {"ok": True}

    # ── admin: tenant management ────────────────────────────────────────────
    class TenantCreate(BaseModel):
        tenant_id: str
        display_name: str
        llm_api_key: str | None = None
        llm_model: str | None = None
        llm_base_url: str | None = None

    @app.get("/api/admin/tenants")
    def list_tenants(_: None = Depends(admin)) -> dict:
        return {"tenants": [{
            "tenant_id": t.tenant_id, "display_name": t.display_name,
            "api_token": t.api_token, "llm_model": t.llm_model,
            "has_own_key": t.has_own_llm(),
        } for t in registry.list()]}

    @app.post("/api/admin/tenants")
    def create_tenant(req: TenantCreate, _: None = Depends(admin)) -> dict:
        try:
            t = registry.create(req.tenant_id, req.display_name,
                                llm_api_key=req.llm_api_key, llm_model=req.llm_model,
                                llm_base_url=req.llm_base_url)
        except ValueError as e:
            raise HTTPException(409, str(e))
        return {"tenant_id": t.tenant_id, "api_token": t.api_token}

    @app.delete("/api/admin/tenants/{tenant_id}")
    def delete_tenant(tenant_id: str, _: None = Depends(admin)) -> dict:
        if not registry.delete(tenant_id):
            raise HTTPException(404, f"Tenant '{tenant_id}' not found.")
        return {"deleted": tenant_id}

    return app


app = create_app()  # default instance for `uvicorn edit_table.server:app`
