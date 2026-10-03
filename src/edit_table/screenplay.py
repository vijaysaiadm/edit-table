"""Screenplay loading and scene splitting.

Stage 1 (heuristic): pattern-based scene-heading detection works for standard
screenplay formatting (INT./EXT.) and numbered scripts (SCENE 12 / సీన్ 12).
Stage 2 (optional, with LLM): re-segment messy/irregularly formatted scripts.
"""
from __future__ import annotations

import re
from pathlib import Path

from .config import Settings
from .models import Scene, Screenplay

HEADING_RE = re.compile(
    r"^(?:"
    r"(?:SCENE|సీన్|సీన)\s*[:]?\s*\d+"          # SCENE 12 / సీన్ 12
    r"|(?:INT|EXT|INT\./EXT|I/E)\b[.\s].{0,90}"   # INT. COFFEE SHOP - DAY
    r")$",
    re.IGNORECASE,
)

SUPPORTED = {".txt", ".md", ".pdf", ".fountain"}


def load_screenplay(path: str | Path, settings: Settings) -> Screenplay:
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED:
        raise SystemExit(f"Unsupported format {path.suffix}. Use: {sorted(SUPPORTED)}")
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    else:
        text = path.read_text(encoding="utf-8")
    title = _guess_title(text) or path.stem
    scenes, preamble = split_scenes(text, settings)
    runtime = sum(s.estimated_minutes for s in scenes)
    return Screenplay(title=title, raw_text=text, scenes=scenes,
                      estimated_runtime=runtime, preamble=preamble)


def split_scenes(text: str, settings: Settings) -> tuple[list[Scene], str]:
    """Heuristic splitter: paragraph-level, on scene-heading patterns.
    Returns (scenes, preamble) — preamble = title page / notes before scene 1."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", text) if p.strip()]
    scenes: list[Scene] = []
    preamble: list[str] = []
    current_heading, current_body = "", []
    seen_first_heading = False

    def flush(heading: str, body: list[str]) -> None:
        body_text = "\n\n".join(body).strip()
        if not heading and not body_text:
            return
        num = len(scenes) + 1
        est = estimate_scene_minutes(body_text, settings.minutes_per_page)
        scenes.append(Scene(number=num, heading=heading or f"UNHEADED BLOCK {num}",
                            text=body_text, estimated_minutes=est))

    for para in paragraphs:
        para_one_line = " ".join(para.split())
        if HEADING_RE.match(para_one_line):
            flush(current_heading, current_body)
            current_heading, current_body = para_one_line, []
            seen_first_heading = True
        elif not seen_first_heading:
            # title page / author notes — not a scene
            preamble.append(para)
        else:
            current_body.append(para)
    flush(current_heading, current_body)

    # If no headings matched at all, fall back: treat each paragraph block as a scene
    if len(scenes) <= 1 and len(paragraphs) > 4:
        scenes = [
            Scene(number=i + 1, heading=f"BLOCK {i + 1}", text=p,
                  estimated_minutes=estimate_scene_minutes(p, settings.minutes_per_page))
            for i, p in enumerate(paragraphs)
        ]
    return scenes, "\n\n".join(preamble)


def estimate_scene_minutes(text: str, minutes_per_page: float = 1.0) -> float:
    """Industry rule of thumb: 1 page ≈ 1 minute. Approximate page = ~55 lines / ~750 words."""
    words = len(text.split())
    return round(max(0.25, (words / 750.0) * minutes_per_page), 2)


def _guess_title(text: str) -> str | None:
    for line in text.splitlines()[:15]:
        line = line.strip()
        if 2 < len(line) < 80 and line.isupper() and not HEADING_RE.match(line):
            return line.title()
    return None
