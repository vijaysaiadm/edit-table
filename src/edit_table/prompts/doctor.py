"""Deep editorial review (Senior Screen Editor framework) and logline development modes.

Both prompt frameworks are loaded verbatim from prompts-source/ — those files are the
single source of truth; this module only wraps them with role markers and input.
"""
from __future__ import annotations

from pathlib import Path

_SOURCE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts-source"


def _load(name: str) -> str:
    return (_SOURCE_DIR / name).read_text(encoding="utf-8")


def doctor_prompt(screenplay_text: str, title: str,
                  target_runtime: float | None) -> tuple[str, str]:
    """Whole-script deep editorial review following the A–O report order."""
    system = "[[ROLE:doctor]]\n" + _load("SENIOR_EDITOR_AGENT.txt") + """

You are running inside edit-table as the DEEP REVIEW agent. Your review mode is SCRIPT MODE
(assess narrative, editability, prospective rhythm, coverage needs, estimated runtime).
Work at PROJECT → ACT → SEQUENCE → SCENE level. Produce your full A–O report in Markdown.
Never invent dialogue, scenes, or footage; label proposals as proposals.
"""
    target = f"Target runtime: {target_runtime:.0f} minutes." if target_runtime else ""
    user = f"""SCREENPLAY TITLE: {title}
{target}

FULL SCREENPLAY:
---
{screenplay_text[:60000]}
---

Produce the complete A–O report in Markdown, exactly in the specified order
(A. REVIEW SCOPE through O. OPEN DECISIONS). Account for every scene in the edit table."""
    return system, user


def develop_prompt(logline: str, fmt: str = "feature") -> tuple[str, str]:
    """Logline/premise → full development package (Delivery Order K)."""
    system = "[[ROLE:develop]]\n" + _load("LOGLINE_TO_SCREENPLAY.txt") + """

You are running inside edit-table as the DEVELOPMENT agent. Deliver the full package in the
FINAL DELIVERY ORDER (1–11) in Markdown. Distinguish supplied facts from your creative
assumptions (label them). If the premise has a fundamental weakness, say so directly and
propose repairs before developing. Do not claim the result is flawless or guaranteed."""
    user = f"""FORMAT: {fmt} (feature / web series / tv serial / sitcom / short film)

LOGLINE / PREMISE:
---
{logline}
---

Deliver items 1–11 of the Final Delivery Order in Markdown. For the screenplay draft (item 8),
write the opening sequences in full screenplay format and continue in numbered batches,
clearly stating what is complete and what remains — never present a partial draft as complete."""
    return system, user
