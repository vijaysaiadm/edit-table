"""FastAPI server: REST API + embedded web UI for the analysis pipeline."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .config import load_settings
from .orchestrator import run_analysis
from .report import render_report, save_outputs

app = FastAPI(title="madhav-edit", version="0.1.0")
WEB_DIR = Path(__file__).parent / "web"

# single-flight guard: one analysis at a time keeps LLM quota sane
_running = False


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
    return {"status": "ok", "mock": False}


@app.post("/api/analyze")
async def analyze_text(req: AnalyzeRequest) -> JSONResponse:
    global _running
    if _running:
        raise HTTPException(409, "An analysis is already running — wait for it to finish.")
    _running = True
    try:
        settings = load_settings()
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(req.screenplay_text)
            tmp = f.name
        stages = (1,) if req.stage == "1" else (1, 2, 3)
        result = await run_analysis(tmp, settings, target_runtime=req.target_runtime,
                                    stages=stages)
        md, js = save_outputs(result, "reports")
        return JSONResponse({"report_md": render_report(result),
                             "report_path": str(md), "data_path": str(js),
                             "stages": result.stages})
    finally:
        _running = False


@app.post("/api/analyze-file")
async def analyze_file(file: UploadFile = File(...),
                       target_runtime: float | None = Form(None),
                       stage: str = Form("full")) -> JSONResponse:
    global _running
    if _running:
        raise HTTPException(409, "An analysis is already running.")
    _running = True
    try:
        settings = load_settings()
        suffix = Path(file.filename or "script.txt").suffix or ".txt"
        with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as f:
            f.write(await file.read())
            tmp = f.name
        stages = (1,) if stage == "1" else (1, 2, 3)
        result = await run_analysis(tmp, settings, target_runtime=target_runtime,
                                    stages=stages)
        md, js = save_outputs(result, "reports")
        return JSONResponse({"report_md": render_report(result),
                             "report_path": str(md), "data_path": str(js),
                             "stages": result.stages})
    finally:
        _running = False
