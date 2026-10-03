"""Deep editorial review, logline development, revision, and comparison modes.

The prompt frameworks live verbatim in prompts-source/ (single source of truth):
  - SENIOR_EDITOR_AGENT.txt      master editorial instructions
  - LOGLINE_TO_SCREENPLAY.txt    development-mode instructions
  - SCREEN_EDITOR_OUTPUT_SPEC.md output contract for EVERY deliverable (modes, evidence
                                 labels, package orders, EDIT-card schema, runtime
                                 ledgers, validation gates)

This module only wraps them with role markers, mode selection, and input.
"""
from __future__ import annotations

from pathlib import Path

_SOURCE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts-source"

_SPEC_RULES = """
--- OPERATING RULES FOR THIS RUN (from SCREEN_EDITOR_OUTPUT_SPEC.md) ---
- Follow the output spec for every deliverable: complete the applicable sections in the
  specified order and pass the §13 validation gates before delivery.
- Tag every consequential claim SOURCE FACT / INTERPRETATION / PROPOSAL / UNKNOWN, with a
  usable source anchor (scene label / page / identifiable opening-closing beat).
- Every proposed edit is an executable intervention card with a stable EDIT ID (§5):
  Where / Current passage / Remove-change / Keep-protect / Why / After the edit /
  Proposed result / Feasibility / Risks / Dependencies / Duration / Validation.
- BOUNDARY RULE: "trim the argument" is a diagnosis, not an instruction. Specify the
  affected unit and retained connection, or mark CONDITIONAL — BOUNDARIES REQUIRE
  VERIFICATION. Never invent source lines, timecodes, or measurements.
- Runtime arithmetic in seconds, displayed minutes:seconds; low/base/high scenarios;
  change ledger with net savings; never sum mutually exclusive edits.
- Scene register separates Disposition (RETAIN/DELETE CANDIDATE/MERGE CANDIDATE/REPLACE
  CANDIDATE/UNDECIDED) from Operation (NONE/TRIM/EXPAND/REORDER/INTERCUT/REWRITE/ADR/
  PICKUP/SOUND CHANGE) and Priority (P0–P3); colors always carry written labels.
- Separate score from diegetic music; count packaging blocks separately; maintain a
  protection list of material that must survive any cut.
- End with the §13 validation gates table: each gate PASS / FAIL / NOT VERIFIED with
  evidence. A failed gate is repaired or visibly marked unresolved — never hidden.
"""


def _load(name: str) -> str:
    return (_SOURCE_DIR / name).read_text(encoding="utf-8")


def _framework() -> str:
    return (_load("SENIOR_EDITOR_AGENT.txt")
            + "\n\n--- OUTPUT CONTRACT (SCREEN_EDITOR_OUTPUT_SPEC.md) ---\n"
            + _load("SCREEN_EDITOR_OUTPUT_SPEC.md"))


def doctor_prompt(screenplay_text: str, title: str,
                  target_runtime: float | None) -> tuple[str, str]:
    """ANALYZE mode: evidence-based diagnosis + executable edit plan (spec §3 package)."""
    system = ("[[ROLE:doctor]]\n" + _framework()
              + _SPEC_RULES
              + "\nThis run's mode: ANALYZE (script) per spec §1 and §3.")
    target = f"Target runtime: {target_runtime:.0f} minutes." if target_runtime else ""
    user = f"""INTAKE RECORD (pre-filled fields; label your assumptions for the rest):
- Project title: {title}
- Review mode: ANALYZE (script)
- {target}

FULL SCREENPLAY:
---
{screenplay_text[:60000]}
---

Deliver the complete spec-compliant ANALYZE package in Markdown: intake record, then
§3 items 1–14 in order (decision dashboard → evidence appendix), then the §13 validation
gates table. Every inspected scene appears in the scene register."""
    return system, user


def develop_prompt(logline: str, fmt: str = "feature") -> tuple[str, str]:
    """DEVELOP mode: logline/premise → full development package (spec §11)."""
    system = ("[[ROLE:develop]]\n" + _load("LOGLINE_TO_SCREENPLAY.txt")
              + "\n\n--- OUTPUT CONTRACT (SCREEN_EDITOR_OUTPUT_SPEC.md) ---\n"
              + _load("SCREEN_EDITOR_OUTPUT_SPEC.md")
              + """
--- OPERATING RULES FOR THIS RUN ---
- Mode: DEVELOP per spec §1 and §11. Deliver items 1–12 of the §11 delivery order in
  Markdown, ending with the §13 validation gates table.
- Use the §11 beat-sheet table format and development scene cards for the scene outline.
- State plainly whether the deliverable is an outline, treatment, partial screenplay, or
  complete draft; long scripts ship in numbered batches with a maintained story bible,
  outline coverage, continuity ledger, and completed scene list.
- Include the critical development pass (causality, agency, opposition, knowledge,
  setups/payoffs, coincidence, interval integrity, climax) and the producer package.
- Distinguish supplied facts from creative assumptions (label them); tag consequential
  claims SOURCE FACT / INTERPRETATION / PROPOSAL / UNKNOWN; never claim the result is
  flawless, guaranteed, or proven original without evidence.""")
    user = f"""INTAKE RECORD:
- Review mode: DEVELOP
- Format: {fmt} (feature / short / serialized series / ongoing serial / sitcom / anthology)

LOGLINE / PREMISE:
---
{logline}
---

Deliver §11 items 1–12 in Markdown. For the screenplay draft (item 9), write the opening
sequences in full screenplay format and continue in numbered batches, clearly stating
what is complete and what remains — never present a partial draft as complete."""
    return system, user


def revise_prompt(screenplay_text: str, instruction: str, title: str,
                  target_runtime: float | None = None) -> tuple[str, str]:
    """REVISE mode: source-aware rewrite of an existing screenplay (spec §1, §6)."""
    system = ("[[ROLE:revise]]\n" + _framework()
              + _SPEC_RULES
              + """
This run's mode: REVISE per spec §1: source-aware changes, proposed rewritten scenes,
and a dependency audit. Do not silently turn analysis into a rewrite, and do not hide a
new revelation, motive, pickup, or ADR line inside an "editing fix". Every piece of new
material carries a REPAIR ID and a distinct NEW MATERIAL / PROPOSED REPLACEMENT label.
For each proposed change: source problem and affected scene IDs; facts already
established vs still unknown; the actual proposed action/dialogue in screenplay format;
insertion/replacement point and connection on both sides; character motivation and
knowledge before/after; downstream changes (setup/payoff, continuity, knowledge ledger)
and validation; runtime delta in seconds or UNKNOWN with reason.""")
    target = f"Target runtime: {target_runtime:.0f} minutes." if target_runtime else ""
    user = f"""INTAKE RECORD:
- Project title: {title}
- Review mode: REVISE
- {target}

REWRITE REQUEST (from the user):
---
{instruction}
---

SOURCE SCREENPLAY (revise THIS — keep what works, protect the established facts):
---
{screenplay_text[:60000]}
---

Deliver the revision package in Markdown: brief diagnosis of what forces the rewrite,
then REPAIR cards with the actual proposed material, then the dependency audit
(setup/payoff, character-knowledge, continuity ledgers), then the §13 validation gates
table. Label every proposed passage distinctly as new material — never claim it existed
in the source."""
    return system, user


def compare_prompt(text_a: str, text_b: str, label_a: str,
                   label_b: str) -> tuple[str, str]:
    """COMPARE mode: two versions → improvements, regressions, unresolved issues."""
    system = ("[[ROLE:compare]]\n" + _framework()
              + _SPEC_RULES
              + """
This run's mode: COMPARE per spec §1. Anchor every claim to version A or B with scene
labels/pages; never invent differences. Structure: what improved, what regressed,
scenes changed / added / removed (with anchors), unresolved issues, and — where a
regression should be fixed — executable EDIT cards. End with the §13 validation gates
table.""")
    user = f"""VERSION A: {label_a}
---
{text_a[:45000]}
---

VERSION B: {label_b}
---
{text_b[:45000]}
---

Compare the two versions in Markdown per the COMPARE mode: improvements, regressions,
changed/new/removed scenes with anchors, unresolved issues, proposed fixes as EDIT
cards, then the §13 validation gates table."""
    return system, user
