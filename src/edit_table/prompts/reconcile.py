"""Reconciliation: the lead agent resolves worker contradictions and owns the final plan."""
from __future__ import annotations

import json

from ..models import AnalysisResult, Brief, GenreFinding, SceneAnalysis, UtilityResult
from . import EDITOR_CORE


def reconcile_prompt(brief: Brief, analyses: list[SceneAnalysis],
                     findings: list[GenreFinding],
                     utilities: dict[str, UtilityResult]) -> tuple[str, str]:
    system = EDITOR_CORE + """
[[ROLE:reconcile]]
You are the LEAD AGENT in RECONCILIATION mode. Scene workers, genre specialists and utility
workers have done their jobs independently — their outputs WILL contradict each other
(one worker may cut what another scene's payoff depends on). Your job:
1. Detect every cross-scene contradiction (especially REMOVE vs. setup/payoff).
2. Resolve each one — the brief's STORY PRIORITIES win every argument.
3. Produce the final, scene-by-scene verdict table. Separate SAFE EDIT from AGGRESSIVE EDIT.
4. Produce the top-10 editing opportunities and the final edit plan.
"""
    digest = {
        "brief": brief.as_prompt_block(),
        "scene_analyses": [a.__dict__ for a in analyses],
        "genre_findings": [f.__dict__ for f in findings],
        "utilities": {k: v.payload for k, v in utilities.items()},
    }
    user = f"""ALL WORKER OUTPUTS (JSON):
---
{json.dumps(digest, indent=1, default=str)[:50000]}
---

Return STRICT JSON:
{{
  "conflicts_detected": [
    {{"scene_number": int, "worker_a": "...", "worker_b": "...", "issue": "...", "resolution": "..."}}],
  "final_verdicts": [
    {{"scene_number": int, "verdict": "KEEP|TRIM|MERGE|RESTRUCTURE|MOVE|REMOVE",
      "action": "one concrete edit instruction",
      "reason": "...", "safe_vs_aggressive": "safe|aggressive"}}],
  "top_opportunities": ["the 10 highest-leverage editing moves across the film"],
  "final_edit_plan": "pass-by-pass edit plan: pass 1 repetition, pass 2 rhythm, pass 3 emotion/BGM",
  "emotional_graph": [{{"position_pct": 0-100, "energy": 0-100, "label": "..."}}]
}}"""
    return system, user


def stage1_full_prompt(screenplay_text: str, title: str) -> tuple[str, str]:
    """Stage 1 fallback: single agent does everything (the classic 'one strong agent' mode)."""
    system = EDITOR_CORE + """
[[ROLE:reconcile]]
You are the SOLO EDITOR AGENT (Stage 1 mode). Do the full analysis yourself in one pass.
"""
    user = f"""SCREENPLAY: {title}
---
{screenplay_text[:40000]}
---
Produce the full A–P output as JSON with keys: one_line_story, core_conflict, hero_arc,
antagonist_arc, emotional_graph, runtime_problem, repetition_problem, top_opportunities,
final_edit_plan, and final_verdicts (scene_number, verdict, action, reason, safe_vs_aggressive)."""
    return system, user
