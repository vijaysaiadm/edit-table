"""Stage 3 genre specialists — run in parallel, only for genres present in the brief."""
from __future__ import annotations

from ..models import Brief, Screenplay
from . import EDITOR_CORE

SPECIALISTS: dict[str, str] = {
    "action": """Analyze fight/action scenes using: ESTABLISH → THREAT → FIRST IMPACT → ESCALATION →
REVERSAL → DOMINANCE SHIFT → FINAL PAYOFF. Check shot duration, geography, eyeline, impact timing,
reaction shots, SFX, BGM rhythm, hero elevation, villain threat, repetition.
Do NOT recommend excessive cutting that destroys spatial clarity.""",
    "thriller": """Analyze thriller/crime sequences using: Information → Suspicion → Misdirection →
Discovery → Threat → Reveal. Track whether the audience knows LESS THAN / EQUAL TO / MORE THAN the
character, and use that strategically. Do not reveal information unnecessarily early.""",
    "romance": """Analyze romance: chemistry, eye contact, silence, reaction shots, emotional progression,
repetition, montage rhythm, BGM transitions. Romance should evolve — never repeat the same emotional beat.
Working BPM intuition for romantic montage: ~82-92 (anchor, not target).""",
    "comedy": """Analyze comedy with: Setup → Expectation → Delay → Reaction → Punch → Release. Check
reaction timing, pause, cut timing, dialogue overlap, performance preservation. Never cut a comedy scene
just for slowness without checking the punchline rhythm.""",
}


def genre_prompt(specialist: str, brief: Brief, screenplay: Screenplay) -> tuple[str, str]:
    system = EDITOR_CORE + f"""
[[ROLE:genre_specialist]]
You are the {specialist.upper()} SPECIALIST agent. You scan the WHOLE screenplay for {specialist}
sequences and report concrete, scene-level editing findings. You do not rewrite the script —
you report what the edit table can do.
"""
    scenes_digest = "\n".join(
        f"#{s.number} {s.heading} (~{s.estimated_minutes:.1f} min): {s.text[:400]}"
        for s in screenplay.scenes
    )
    user = f"""BRIEF: {brief.as_prompt_block()}

SPECIALIST BRIEF: {SPECIALISTS[specialist]}

SCREENPLAY SCENES:
{scenes_digest}

Return STRICT JSON: {{"findings": [
  {{"scene_number": int, "finding": "concrete editing note with WHY",
    "severity": "low|medium|high"}}, ...
]}}
List at most the 10 most important findings. If this genre barely appears, say so in one finding."""
    return system, user
