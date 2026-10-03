"""Stage 1+2 lead agent: reads the FULL script and produces the shared brief."""
from __future__ import annotations

from . import EDITOR_CORE


def lead_brief_prompt(title: str, full_text: str, target_runtime: float | None) -> tuple[str, str]:
    system = EDITOR_CORE + """
[[ROLE:lead_brief]]
You are the LEAD AGENT (editor-in-chief). You alone see the entire screenplay.
Every other worker will judge individual scenes ONLY against your brief — so be precise,
global, and honest. Do not flatter the script; if something is weak, say exactly why.
"""
    target = f"{target_runtime:.0f} minutes" if target_runtime else "a commercially effective length"
    user = f"""SCREENPLAY TITLE: {title}

Read the full screenplay below and produce the global editing brief as JSON:
{{
  "one_line_story": "...",
  "core_conflict": "...",
  "hero_arc": "INTRODUCTION → DESIRE → ...",
  "antagonist_arc": "...",
  "emotional_core": "primary story energy(ies) and emotional movement",
  "genre_mix": ["..."],
  "story_priorities": ["elements that must survive ANY edit — setups with late payoffs, emotional peaks, interval block, climax"],
  "global_notes": ["2-5 honest global weaknesses an editor should watch across the whole film"]
}}
Target runtime: {target}.

FULL SCREENPLAY:
---
{full_text}
---"""
    return system, user
