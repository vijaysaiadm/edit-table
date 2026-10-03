"""LLM access layer.

- RealLLM: any OpenAI-compatible endpoint (OpenAI, OpenRouter, Groq, local vLLM...).
- MockLLM: deterministic heuristic responses so the full pipeline can be tested offline.

Both expose the same async interface: chat(system, user, json_mode=False) -> str.
"""
from __future__ import annotations

import asyncio
import json
import re

from .config import Settings


def _extract_json(text: str) -> dict:
    """Tolerate models that wrap JSON in prose or markdown fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # find the outermost {...} block and retry
        start, depth = None, 0
        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
        raise ValueError(f"Model did not return valid JSON:\n{text[:500]}")


class RealLLM:
    def __init__(self, settings: Settings):
        from openai import AsyncOpenAI  # imported lazily so mock mode needs no deps

        self.s = settings
        self.client = AsyncOpenAI(api_key=settings.api_key, base_url=settings.base_url)
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def chat(self, system: str, user: str, json_mode: bool = False,
                   model: str | None = None, max_retries: int = 3) -> str:
        kwargs: dict = {"model": model or self.s.model, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        delay = 2.0
        for attempt in range(max_retries):
            try:
                async with self._semaphore:
                    resp = await self.client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content or ""
            except Exception:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(delay)
                delay *= 2

    async def chat_json(self, system: str, user: str, model: str | None = None) -> dict:
        return _extract_json(await self.chat(system, user, json_mode=True, model=model))

    async def chat_markdown(self, system: str, user: str, model: str | None = None) -> str:
        """Free-form markdown output (deep review / development modes)."""
        return await self.chat(system, user, json_mode=False, model=model)


class MockLLM:
    """Offline stand-in: pattern-based responses so every pipeline stage runs without a key."""

    async def chat(self, system: str, user: str, json_mode: bool = False,
                   model: str | None = None, max_retries: int = 3) -> str:
        await asyncio.sleep(0.01)  # simulate latency, keep concurrency paths exercised
        return json.dumps(self._reply(system, user))

    async def chat_markdown(self, system: str, user: str, model: str | None = None) -> str:
        tag = _tag(system)
        return (f"# MOCK {tag.upper()} REPORT\n\nConnect a real LLM for the full "
                f"{tag} analysis. Input received: {len(user)} chars.\n\n"
                "## A. REVIEW SCOPE\nMock mode.\n\n## B. EXECUTIVE DIAGNOSIS\nMock mode.")

    async def chat_json(self, system: str, user: str, model: str | None = None) -> dict:
        return self._reply(system, user)

    # -- heuristic replies keyed off the system prompt's role tag ------------
    def _reply(self, system: str, user: str) -> dict:  # noqa: C901
        tag = _tag(system)
        if tag == "lead_brief":
            return {
                "one_line_story": "A determined protagonist confronts an escalating conflict "
                                  "and must transform to prevail (mock analysis).",
                "core_conflict": "Protagonist vs. antagonist, escalating stakes.",
                "hero_arc": "INTRODUCTION → DESIRE → CONFLICT → DECISION → CHANGE",
                "antagonist_arc": "THREAT → PRESSURE → REVERSAL → DOWNFALL",
                "emotional_core": "Courage (VEERA) with emotional (KARUNA) beats.",
                "genre_mix": ["drama", "action", "thriller"],
                "story_priorities": ["hero introduction", "interval block", "climax payoff"],
                "global_notes": ["Mock brief — connect a real LLM for production analysis."],
            }
        if tag == "scene_worker":
            num = _first_int(user, default=1)
            return {
                "scene_number": num,
                "scene_purpose": "Advances the central conflict and reveals character.",
                "conflict": "Protagonist blocked from goal; stakes rise.",
                "emotional_state": "Tension building toward pressure.",
                "audience_expectation": "Question raised about the protagonist's next move.",
                "scene_hook": "Ends on an unresolved question.",
                "turning_point": "Mid-scene reversal of expectation.",
                "payoff": "Partial payoff; larger question remains.",
                "weak_point": "Dialogue repeats information the audience already has.",
                "editing_opportunity": "Enter later; trim the explanatory exchange.",
                "recommended_cut": "TRIM",
                "recommended_trim": "20–30% of dialogue; protect reaction shots.",
                "transition": "L-CUT into the following scene.",
                "bgm_requirement": "Low tension pulse, building; drop at the turn.",
                "sound_design": "Room tone; silence before the turn for emphasis.",
                "tempo": "medium, accelerating into the turn",
                "estimated_runtime": 2.5,
                "problem_class": "EDITING",
                "notes": "Mock scene analysis.",
            }
        if tag == "genre_specialist":
            return {"findings": [
                {"scene_number": _first_int(user, default=1),
                 "finding": f"Mock {user.splitlines()[0][:40]} finding: check repetition and pacing.",
                 "severity": "medium"}]}
        if tag == "character_arcs":
            return {"characters": [
                {"name": "PROTAGONIST",
                 "arc": "INTRODUCTION → DESIRE → CONFLICT → DECISION → CONSEQUENCE → CHANGE",
                 "missing_beats": ["a quiet decision scene before the climax"],
                 "repeated_behaviour": ["re-states goal in every second scene"]}]}
        if tag == "runtime_estimate":
            return {"total_pages_note": "mock", "notes": "Use MINUTES_PER_PAGE heuristic in mock mode."}
        if tag == "bgm_map":
            return {"bgm_map": [
                {"section": "opening", "tempo_bpm": 90, "note": "light pulse, no melody"},
                {"section": "interval block", "tempo_bpm": 100, "note": "build to hard cut at interval"},
                {"section": "climax", "tempo_bpm": 120, "note": "full score, no drops until payoff"}]}
        if tag == "reconcile":
            return {
                "conflicts_detected": [],
                "final_verdicts": [
                    {"scene_number": n, "verdict": "TRIM",
                     "action": "Trim explanatory dialogue; protect reactions.",
                     "reason": "Information already established earlier.",
                     "safe_vs_aggressive": "safe"} for n in range(1, 4)
                ],
                "top_opportunities": [
                    "Tighten dialogue scenes that restate established information.",
                    "Add reaction shots at each turning point.",
                    "Hold silence before major reveals — BGM drop, not swell.",
                ],
                "final_edit_plan": "Mock edit plan: pass 1 — remove repetition; "
                                   "pass 2 — protect emotional beats; pass 3 — rhythm map.",
                "emotional_graph": [
                    {"position_pct": p, "energy": e, "label": lbl}
                    for p, e, lbl in [(0, 40, "setup"), (25, 65, "build"),
                                      (50, 90, "interval"), (75, 70, "pressure"), (100, 100, "climax")]
                ],
            }
        return {"note": f"mock fallback for tag={tag}"}


def _tag(system: str) -> str:
    m = re.search(r"\[\[ROLE:(\w+)\]\]", system)
    return m.group(1) if m else ""


def _first_int(text: str, default: int) -> int:
    m = re.search(r"\d+", text)
    return int(m.group(0)) if m else default


def make_llm(settings: Settings):
    return MockLLM() if settings.mock else RealLLM(settings)
