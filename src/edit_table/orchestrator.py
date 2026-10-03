"""The swarm orchestrator.

Pipeline (all stages):
  Stage 1  load + split screenplay            (heuristic, local)
  Stage 2  lead brief → parallel per-scene workers (judge against the shared brief)
  Stage 3  parallel genre specialists (only genres in the brief)
           + parallel utility workers (character arcs, runtime, continuity, BGM map)
  Final    lead reconciliation: resolve contradictions, final verdict table, edit plan

Everything is one asyncio loop; LLM calls fan out under a concurrency semaphore.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from .config import Settings
from .llm import make_llm
from .models import (AnalysisResult, Brief, Conflict, FinalVerdict, GenreFinding,
                     SceneAnalysis, UtilityResult)
from .prompts.doctor import (compare_prompt, develop_prompt, doctor_prompt,
                             revise_prompt)
from .prompts.genre import SPECIALISTS, genre_prompt
from .prompts.lead import lead_brief_prompt
from .prompts.reconcile import reconcile_prompt, stage1_full_prompt
from .prompts.scene import scene_worker_prompt
from .prompts.utility import (bgm_map_prompt, character_arc_prompt,
                              continuity_prompt, runtime_prompt)
from .screenplay import load_screenplay


async def run_analysis(path: str | Path, settings: Settings,
                       target_runtime: float | None = None,
                       stages: tuple[int, ...] = (1, 2, 3)) -> AnalysisResult:
    llm = make_llm(settings)
    t0 = time.time()

    # ── Stage 1: load & split ────────────────────────────────────────────────
    sp = load_screenplay(path, settings)
    result = AnalysisResult(
        screenplay_title=sp.title,
        tenant_id=settings.tenant_id,
        brief=Brief(target_runtime_min=target_runtime or sp.estimated_runtime,
                    current_runtime_min=sp.estimated_runtime),
        scene_analyses=[], genre_findings=[], utilities={},
        conflicts=[], final_verdicts=[], stages=[],
    )
    result.scene_texts = {s.number: s.text for s in sp.scenes}  # for report excerpts
    result.stages.append(f"stage1: split into {len(sp.scenes)} scenes "
                         f"(~{sp.estimated_runtime:.0f} min estimated) [{time.time()-t0:.1f}s]")

    # Solo mode: skip the swarm entirely
    if stages == (1,):
        system, user = stage1_full_prompt(sp.raw_text, sp.title)
        data = await llm.chat_json(system, user)
        result.final_edit_plan = data.get("final_edit_plan", "")
        tops = data.get("top_opportunities", [])
        result.top_opportunities = [tops] if isinstance(tops, str) else tops
        result.emotional_graph = data.get("emotional_graph", [])
        result.final_verdicts = [FinalVerdict(**{k: v for k, v in fv.items()
                                                 if k in FinalVerdict.__dataclass_fields__})
                                 for fv in data.get("final_verdicts", [])]
        result.stages.append(f"stage1-solo: full single-agent analysis [{time.time()-t0:.1f}s]")
        return result

    # ── Stage 2a: lead brief (single call, full script) ─────────────────────
    t = time.time()
    system, user = lead_brief_prompt(sp.title, sp.raw_text[:60000], target_runtime)
    brief_data = await llm.chat_json(system, user)
    for k, v in brief_data.items():
        if hasattr(result.brief, k):
            setattr(result.brief, k, v)
    result.stages.append(f"stage2a: lead brief [{time.time()-t:.1f}s]")

    # ── Stage 2b: per-scene workers in parallel ─────────────────────────────
    t = time.time()

    async def analyze_scene(i: int) -> SceneAnalysis:
        scene = sp.scenes[i]
        prev_tail = sp.scenes[i - 1].text[-200:] if i > 0 else ""
        next_head = sp.scenes[i + 1].text[:200] if i < len(sp.scenes) - 1 else ""
        s, u = scene_worker_prompt(result.brief, scene, prev_tail, next_head)
        data = await llm.chat_json(s, u, model=settings.worker_model)
        known = {k: v for k, v in data.items() if k in SceneAnalysis.__dataclass_fields__}
        known.setdefault("scene_number", scene.number)
        return SceneAnalysis(**known)

    result.scene_analyses = sorted(
        await asyncio.gather(*[analyze_scene(i) for i in range(len(sp.scenes))]),
        key=lambda a: a.scene_number,
    )
    result.stages.append(
        f"stage2b: {len(result.scene_analyses)} scene workers in parallel [{time.time()-t:.1f}s]")

    # ── Stage 3a: genre specialists (only genres present) + utilities ───────
    t = time.time()
    present = {g for g in result.brief.genre_mix if g in SPECIALISTS}
    present |= {g for g in SPECIALISTS if g in sp.raw_text.lower()}  # cheap text sniff

    async def run_specialist(g: str) -> list[GenreFinding]:
        s, u = genre_prompt(g, result.brief, sp)
        data = await llm.chat_json(s, u)
        return [GenreFinding(specialist=g, **{k: v for k, v in f.items()
                                              if k in GenreFinding.__dataclass_fields__})
                for f in data.get("findings", [])]

    async def run_utility(name: str, builder) -> tuple[str, UtilityResult]:
        s, u = builder(result.brief, sp)
        return name, UtilityResult(worker=name, payload=await llm.chat_json(s, u))

    genre_tasks = [run_specialist(g) for g in sorted(present)]
    utility_builders = {
        "character_arcs": character_arc_prompt,
        "runtime": runtime_prompt,
        "continuity": continuity_prompt,
        "bgm_map": bgm_map_prompt,
    }
    utility_tasks = [run_utility(n, b) for n, b in utility_builders.items()]

    gathered = await asyncio.gather(*(genre_tasks + utility_tasks))
    for item in gathered:
        if isinstance(item, list):
            result.genre_findings.extend(item)
        else:
            name, util = item
            result.utilities[name] = util
    result.stages.append(
        f"stage3: {len(genre_tasks)} genre specialists + {len(utility_tasks)} utility workers "
        f"[{time.time()-t:.1f}s]")

    # ── Final: reconciliation by the lead agent ─────────────────────────────
    t = time.time()
    s, u = reconcile_prompt(result.brief, result.scene_analyses,
                            result.genre_findings, result.utilities)
    final = await llm.chat_json(s, u)
    result.conflicts = [Conflict(**{k: v for k, v in c.items()
                                    if k in Conflict.__dataclass_fields__})
                        for c in final.get("conflicts_detected", [])]
    result.final_verdicts = [FinalVerdict(**{k: v for k, v in fv.items()
                                             if k in FinalVerdict.__dataclass_fields__})
                             for fv in final.get("final_verdicts", [])]
    tops = final.get("top_opportunities", [])
    result.top_opportunities = [tops] if isinstance(tops, str) else tops
    result.final_edit_plan = final.get("final_edit_plan", "")
    result.emotional_graph = final.get("emotional_graph", [])
    result.stages.append(f"reconcile: lead resolved {len(result.conflicts)} conflict(s) "
                         f"[{time.time()-t:.1f}s]")
    return result


async def run_doctor(path: str | Path, settings: Settings,
                     target_runtime: float | None = None,
                     holistic: bool = False) -> str:
    """Deep editorial review (spec-compliant ANALYZE package) as raw Markdown.

    holistic=True treats the file as a multi-episode package and produces ONE
    consolidated season-level report (episode map, cross-episode ledgers).
    """
    llm = make_llm(settings)
    sp = load_screenplay(path, settings)
    system, user = doctor_prompt(sp.raw_text[:240000] if holistic else sp.raw_text[:60000],
                                 sp.title, target_runtime, holistic=holistic)
    return await llm.chat_markdown(system, user)


async def run_develop(logline: str, settings: Settings,
                      fmt: str = "feature") -> str:
    """Logline/premise → full development package (spec §11) as Markdown."""
    llm = make_llm(settings)
    system, user = develop_prompt(logline, fmt)
    return await llm.chat_markdown(system, user)


async def run_revise(path: str | Path, settings: Settings, instruction: str,
                     target_runtime: float | None = None) -> str:
    """REVISE mode: source-aware rewrite with dependency audit, as Markdown."""
    llm = make_llm(settings)
    sp = load_screenplay(path, settings)
    system, user = revise_prompt(sp.raw_text[:60000], instruction, sp.title,
                                 target_runtime)
    return await llm.chat_markdown(system, user)


async def run_compare(path_a: str | Path, path_b: str | Path,
                      settings: Settings) -> str:
    """COMPARE mode: two versions → improvements/regressions, as Markdown."""
    llm = make_llm(settings)
    a = load_screenplay(path_a, settings)
    b = load_screenplay(path_b, settings)
    system, user = compare_prompt(a.raw_text[:45000], b.raw_text[:45000],
                                  a.title, b.title)
    return await llm.chat_markdown(system, user)
