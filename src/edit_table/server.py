"""FastAPI server: multi-tenant REST API + web UI + admin settings UI.

Auth model:
  - tenants  → X-API-Key (per-tenant token)
  - operator → X-Admin-Key (auto-generated on first run, printed at startup,
                also stored in server_settings.json — see README)

LLM credential priority: tenant key > admin-set server default > env/.env.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from .config import load_settings
from .llm import make_llm
from .orchestrator import run_analysis, run_develop, run_doctor
from .paths import data_path
from .report import render_report, save_outputs
from .server_settings import DEFAULT_SETTINGS_FILE, ServerSettingsStore
from .tenants import DEFAULT_TENANTS_FILE, Tenant, TenantRegistry

WEB_DIR = Path(__file__).parent / "web"
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

# per-tenant single-flight guards: tenants never see or block each other
_running: dict[str, bool] = {}


# Pydantic models must live at module scope: with postponed annotation evaluation,
# FastAPI cannot resolve locally-defined classes and misparses them as query params.
class AnalyzeRequest(BaseModel):
    screenplay_text: str
    title: str = "Untitled Screenplay"
    target_runtime: float | None = None
    stage: str = "full"
    mode: str = "analyze"      # analyze | doctor | develop
    fmt: str = "feature"       # feature / web series / tv serial / sitcom / short film


class AskRequest(BaseModel):
    """Follow-up Q&A on a generated report — stateless (client resends report+history)."""
    question: str
    report_md: str
    history: list[dict] = []


class SettingsRequest(BaseModel):
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    open_access: bool | None = None


class TenantCreate(BaseModel):
    tenant_id: str
    display_name: str
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None


# shared identity used when open access is enabled — no token needed at all
PUBLIC_TENANT = Tenant(tenant_id="public", display_name="Shared (open access)",
                       api_token="")


def create_app(tenants_file: str | Path | None = None,
               settings_file: str | Path | None = None) -> FastAPI:
    registry = TenantRegistry(tenants_file or data_path(DEFAULT_TENANTS_FILE))
    store = ServerSettingsStore(settings_file or data_path(DEFAULT_SETTINGS_FILE))
    app = FastAPI(title="edit-table", version="0.3.0")
    app.state.registry, app.state.settings_store = registry, store

    @app.on_event("startup")
    def announce_admin() -> None:
        print(f"\n  🔑 Admin UI: /admin on this server  (X-Admin-Key: {store.ensure_admin_token()})\n")

    def current_tenant(token: str | None = Depends(api_key_header)) -> Tenant:
        if store.get().get("open_access"):
            tenant = registry.by_token(token) if token else None
            return tenant or PUBLIC_TENANT   # no token needed; valid tokens still work
        if not token:
            raise HTTPException(401, "Missing X-API-Key header.")
        tenant = registry.by_token(token)
        if not tenant:
            hint = ""
            if token.startswith("adm_"):
                hint = " That looks like an ADMIN key — tenant access tokens start with 'tok_'."
            elif token.startswith("tok_"):
                hint = " This token isn't registered — create/get a fresh one on the admin page."
            raise HTTPException(401, "Unknown API key." + hint)
        return tenant

    def admin(token: str | None = Depends(admin_key_header)) -> None:
        if not store.verify_admin(token):
            raise HTTPException(401, "Missing or invalid X-Admin-Key header.")

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
    async def _save_markdown(tenant: Tenant, md_text: str, kind: str,
                             title: str) -> JSONResponse:
        out = data_path("reports") / tenant.tenant_id
        out.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:60] or kind
        path = out / f"{safe}_{kind}_report.md"
        path.write_text(md_text, encoding="utf-8")
        return JSONResponse({"tenant": tenant.tenant_id, "report_md": md_text,
                             "report_path": str(path), "mode": kind})

    async def _run(tenant: Tenant, tmp: str, target_runtime: float | None,
                   stage: str, mode: str = "analyze") -> JSONResponse:
        shared = tenant.tenant_id == PUBLIC_TENANT.tenant_id
        # shared/open-access traffic must not serialize: skip the single-flight guard
        if not shared:
            if _running.get(tenant.tenant_id):
                raise HTTPException(409, "This tenant already has an analysis running.")
            _running[tenant.tenant_id] = True
        try:
            settings = load_settings(tenant=tenant, server_defaults=store.get())
            if mode == "doctor":   # deep editorial review → raw markdown A–O report
                md_text = await run_doctor(tmp, settings, target_runtime=target_runtime)
                return await _save_markdown(tenant, md_text, "doctor", Path(tmp).stem)
            stages = (1,) if stage == "1" else (1, 2, 3)
            result = await run_analysis(tmp, settings, target_runtime=target_runtime,
                                        stages=stages)
            md, js = save_outputs(result, data_path("reports"))
            return JSONResponse({"tenant": tenant.tenant_id,
                                 "report_md": render_report(result),
                                 "report_path": str(md), "data_path": str(js),
                                 "stages": result.stages, "mode": "analyze"})
        finally:
            if not shared:
                _running[tenant.tenant_id] = False

    @app.post("/api/analyze")
    async def analyze_text(req: AnalyzeRequest,
                           tenant: Tenant = Depends(current_tenant)) -> JSONResponse:
        if req.mode == "develop":   # logline → development package; text IS the input
            settings = load_settings(tenant=tenant, server_defaults=store.get())
            md_text = await run_develop(req.screenplay_text, settings, fmt=req.fmt)
            return await _save_markdown(tenant, md_text, "develop", "logline_development")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8") as f:
            f.write(req.screenplay_text)
            tmp = f.name
        return await _run(tenant, tmp, req.target_runtime, req.stage, mode=req.mode)

    @app.post("/api/analyze-file")
    async def analyze_file(file: UploadFile = File(...),
                           target_runtime: float | None = Form(None),
                           stage: str = Form("full"),
                           mode: str = Form("analyze"),
                           tenant: Tenant = Depends(current_tenant)) -> JSONResponse:
        tmp = await _spool(file)
        return await _run(tenant, tmp, target_runtime, stage, mode=mode)

    async def _spool(file: UploadFile) -> str:
        """Stream upload to a temp file in 1 MB chunks — no in-memory size limit."""
        suffix = Path(file.filename or "script.txt").suffix or ".txt"
        with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as f:
            while chunk := await file.read(1024 * 1024):
                f.write(chunk)
        return f.name

    @app.post("/api/analyze-files")
    async def analyze_files(files: list[UploadFile] = File(...),
                            target_runtime: float | None = Form(None),
                            stage: str = Form("full"),
                            mode: str = Form("analyze"),
                            tenant: Tenant = Depends(current_tenant)) -> JSONResponse:
        """Analyze many attachments in one request, sequentially, per-tenant guard held
        for the whole batch. Returns one result per file (failures don't stop the rest)."""
        results = []
        for file in files:
            name = file.filename or "script.txt"
            try:
                tmp = await _spool(file)
                r = await _run(tenant, tmp, target_runtime, stage, mode=mode)
                payload = json.loads(r.body.decode())
                payload["filename"] = name
                results.append(payload)
            except HTTPException as e:
                results.append({"filename": name, "error": e.detail})
            except Exception as e:  # one bad file shouldn't kill the batch
                results.append({"filename": name, "error": f"{type(e).__name__}: {e}"})
        return JSONResponse({"tenant": tenant.tenant_id, "results": results})

    # ── follow-up Q&A on a generated report ─────────────────────────────────
    @app.post("/api/ask")
    async def ask(req: AskRequest,
                  tenant: Tenant = Depends(current_tenant)) -> JSONResponse:
        """Ask questions about a report, or request dynamic expansion of its sections.
        Stateless: the client resends the report and the conversation each call, so
        nothing report-specific is stored server-side between turns."""
        settings = load_settings(tenant=tenant, server_defaults=store.get())
        llm = make_llm(settings)
        system = (
            "[[ROLE:ask]]\nYou are the edit-table analysis assistant. The user has a report "
            "(below) produced by a screenplay analysis pipeline and wants to go deeper. Rules:\n"
            "- Ground every answer in the report; quote or reference the section you draw on.\n"
            "- When asked to EXPAND a section, produce ready-to-insert Markdown under a clear "
            "heading (e.g. expanded scene-by-scene tables with timings, extended BGM maps, "
            "detailed fix lists). The horizon of the report expands dynamically this way.\n"
            "- Be concrete: scene numbers, minute marks, priorities, examples.\n"
            "- If the report lacks the answer, say so plainly instead of inventing content.\n"
            "Output Markdown."
        )
        turns = "\n\n".join(f"**{h.get('role','?').upper()}:** {h.get('content','')}"
                            for h in req.history[-10:]
                            if h.get("role") in ("user", "assistant") and h.get("content"))
        user = (f"REPORT:\n---\n{req.report_md[:50000]}\n---\n\n"
                f"CONVERSATION SO FAR:\n{turns or '(none)'}\n\n"
                f"NEW QUESTION:\n{req.question}")
        answer = await llm.chat_markdown(system, user)
        return JSONResponse({"tenant": tenant.tenant_id, "answer": answer})

    # ── admin: server default LLM settings ──────────────────────────────────
    @app.get("/api/admin/settings")
    def get_settings(_: None = Depends(admin)) -> dict:
        data = store.get()
        data["llm_api_key_set"] = bool(data.get("llm_api_key"))
        data["llm_api_key"] = ("••••" + data["llm_api_key"][-4:]) if data.get("llm_api_key") else None
        return data

    @app.post("/api/admin/settings")
    def update_settings(req: SettingsRequest, _: None = Depends(admin)) -> dict:
        store.update(llm_api_key=req.llm_api_key, llm_model=req.llm_model,
                     llm_base_url=req.llm_base_url, open_access=req.open_access)
        return {"ok": True}

    # ── admin: tenant management ────────────────────────────────────────────
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
