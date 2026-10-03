"""Stage 3 utility workers — mechanical/analytical jobs that don't need global judgment."""
from __future__ import annotations

from ..models import Brief, Screenplay
from . import EDITOR_CORE


def character_arc_prompt(brief: Brief, screenplay: Screenplay) -> tuple[str, str]:
    system = EDITOR_CORE + """
[[ROLE:character_arcs]]
You are the CHARACTER ARC TRACKER. For every major character map:
INTRODUCTION → DESIRE → CONFLICT → DECISION → CONSEQUENCE → CHANGE.
Flag missing emotional beats, repeated behaviour, weak transformation, unmotivated payoffs.
"""
    user = f"""BRIEF: {brief.as_prompt_block()}

SCREENPLAY:
{screenplay.raw_text[:20000]}

Return STRICT JSON: {{"characters": [
  {{"name": "...", "arc": "INTRODUCTION → ...",
    "missing_beats": ["..."], "repeated_behaviour": ["..."], "payoff_notes": "..."}}]}}"""
    return system, user


def runtime_prompt(brief: Brief, screenplay: Screenplay) -> tuple[str, str]:
    system = EDITOR_CORE + """
[[ROLE:runtime_estimate]]
You are the RUNTIME & PACING ESTIMATOR. Judge where the film drags and where it can breathe,
using scene purpose — never "cut everything" logic.
"""
    digest = "\n".join(f"#{s.number} {s.heading} (~{s.estimated_minutes:.1f} min)" for s in screenplay.scenes)
    user = f"""BRIEF: {brief.as_prompt_block()}
Current estimated runtime: {screenplay.estimated_runtime:.0f} min. Target: {brief.target_runtime_min:.0f} min.

SCENES:
{digest}

Return STRICT JSON: {{"slow_zones": ["scene ranges"], "fast_zones": ["..."],
  "trim_candidates": [{{"scene_number": int, "reason": "...", "est_savings_min": number}}],
  "est_final_runtime_min": number}}"""
    return system, user


def continuity_prompt(brief: Brief, screenplay: Screenplay) -> tuple[str, str]:
    system = EDITOR_CORE + """
[[ROLE:continuity_scan]]
You are the CONTINUITY & SETUP-PAYOFF SCANNER. Cross-reference the whole script: setups and their
payoffs, props, locations, time-of-day, character knowledge (who knows what when), and promised
questions the script never answers.
"""
    user = f"""SCREENPLAY:
{screenplay.raw_text[:24000]}

Return STRICT JSON: {{
  "unpaid_setups": [{{"setup_scene": int, "what_was_set_up": "...", "risk": "..."}}],
  "knowledge_errors": [{{"scene_number": int, "issue": "..."}}],
  "continuity_flags": [{{"scene_number": int, "issue": "..."}}],
  "broken_promises": ["questions raised but never paid off"]}}"""
    return system, user


def bgm_map_prompt(brief: Brief, screenplay: Screenplay) -> tuple[str, str]:
    system = EDITOR_CORE + """
[[ROLE:bgm_map]]
You are the BGM/TEMPO MAP DESIGNER. For each major section give BGM START/BUILD/DROP/STOP,
silence placements, SFX hits, ambience and dialogue emphasis. Romance working range ~78-96 BPM;
montage ~82-92 — anchors, not rules. Consider BGM + Dialogue + Ambience + Silence together.
"""
    digest = "\n".join(
        f"#{s.number} {s.heading} (~{s.estimated_minutes:.1f} min): {s.text[:200]}"
        for s in screenplay.scenes
    )
    user = f"""BRIEF: {brief.as_prompt_block()}

SCENES:
{digest}

Return STRICT JSON: {{"bgm_map": [
  {{"section": "opening|first-half|interval|post-interval|pre-climax|climax|scene range",
    "tempo_bpm": number, "bgm_start": "...", "bgm_build": "...", "bgm_drop": "...",
    "silence": "...", "sfx": "...", "note": "..."}}]}}"""
    return system, user
