"""Stage 2 per-scene workers: each analyzes ONE scene against the shared brief."""
from __future__ import annotations

from ..models import Brief, Scene
from . import EDITOR_CORE

FIELDS = """  "scene_number": int,
  "scene_purpose": "what the scene is FOR narratively",
  "conflict": "who wants what, blocked by what",
  "emotional_state": "dominant energy (VEERA/RAUDRA/KARUNA/ADHBHUTA/HASYA/...)",
  "audience_expectation": "what the audience now anticipates",
  "scene_hook": "the curiosity engine of the scene",
  "turning_point": "where the scene turns",
  "payoff": "what pays off here — and which later scene it sets up, if any",
  "weak_point": "the weakest element, honestly",
  "editing_opportunity": "the strongest improvement available at the edit table",
  "recommended_cut": "KEEP | TRIM | MERGE | RESTRUCTURE | MOVE | REMOVE",
  "recommended_trim": "what to trim and roughly how much — protect reactions",
  "transition": "motivated transition in/out, with WHY",
  "bgm_requirement": "BGM start/build/drop/stop behaviour",
  "sound_design": "ambience, SFX hits, silence",
  "tempo": "scene tempo and BPM intuition if relevant (anchors, not targets)",
  "estimated_runtime": number,
  "problem_class": "STORY|SCREENPLAY|SCENE|EDITING|PERFORMANCE|BGM|PACING or NONE",
  "notes": "anything the lead agent must know when reconciling this scene with its neighbours"
"""


def scene_worker_prompt(brief: Brief, scene: Scene, context_prev: str = "",
                        context_next: str = "") -> tuple[str, str]:
    system = EDITOR_CORE + """
[[ROLE:scene_worker]]
You are a PER-SCENE EDITING WORKER. You see ONE scene plus the lead brief.
Judge the scene ONLY against the brief's priorities — not in isolation.
Be concrete and practical, like an editor holding this scene's footage.
"""
    neighbours = ""
    if context_prev or context_next:
        neighbours = (f"PREVIOUS SCENE (last line): {context_prev[:300]}\n"
                      f"NEXT SCENE (first line): {context_next[:300]}\n")
    user = f"""LEAD BRIEF (authoritative global judgment):
---
{brief.as_prompt_block()}
---
{neighbours}
YOUR SCENE (#{scene.number}) {scene.heading}
---
{scene.text}
---

Return STRICT JSON with exactly these fields:
{{
{FIELDS}}}"""
    return system, user
