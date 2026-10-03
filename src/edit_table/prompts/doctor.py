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
- COMPLETENESS MANDATE (non-negotiable): the scene register lists EVERY scene as its
  own row — never '...' placeholder rows, never grouped summaries. Every scene whose
  disposition is not a clean KEEP gets its own intervention card. Runtime, sound/BGM,
  continuity, and setup/payoff tables carry a row per relevant scene or item. If length
  is tight, cut prose — never cut table rows.
- Card format: render each intervention/repair card as an expandable block —
  <details><summary>[EDIT-ID] — [operation] — [one-line purpose]</summary> followed by
  a two-column field table (Where / Current passage / Remove-change / Keep-protect /
  Why / After the edit / Proposed result / Feasibility / Risks / Dependencies /
  Duration / Validation). Quote source passages as blockquote excerpts (> ...).
"""


def _load(name: str) -> str:
    return (_SOURCE_DIR / name).read_text(encoding="utf-8")


def _framework() -> str:
    return (_load("SENIOR_EDITOR_AGENT.txt")
            + "\n\n--- OUTPUT CONTRACT (SCREEN_EDITOR_OUTPUT_SPEC.md) ---\n"
            + _load("SCREEN_EDITOR_OUTPUT_SPEC.md"))


def doctor_prompt(screenplay_text: str, title: str,
                  target_runtime: float | None,
                  holistic: bool = False) -> tuple[str, str]:
    """ANALYZE mode: evidence-based diagnosis + executable edit plan (spec §3 package).

    holistic=True: the text is a MULTI-EPISODE package (episodes separated by labeled
    markers) and the report must cover the whole season — spine, episode map,
    cross-episode continuity — not per-episode silos.
    """
    system = ("[[ROLE:doctor]]\n" + _framework()
              + _SPEC_RULES
              + "\nThis run's mode: ANALYZE (script) per spec §1 and §3.")
    target = f"Target runtime: {target_runtime:.0f} minutes." if target_runtime else ""
    if holistic:
        system += ("\nThis is a HOLISTIC multi-episode run: treat the package as ONE series. "
                   "Deliver a single consolidated report — season spine, sequence/episode map, "
                   "cross-episode setup/payoff and continuity ledgers, and scene/edit IDs that "
                   "carry their episode label (e.g. E2-S014). Never reset the analysis per file.")
        user = f"""INTAKE RECORD (pre-filled fields; label your assumptions for the rest):
- Project title: {title}
- Review mode: ANALYZE (script) — HOLISTIC multi-episode package
- {target}

MULTI-EPISODE PACKAGE (each episode starts with an ===== EPISODE n: <filename> ===== marker;
treat every episode as part of one continuous series):
---
{screenplay_text[:240000]}
---

Deliver the complete spec-compliant HOLISTIC report in Markdown: intake record, then
§3 items 1–14 in order as ONE consolidated package (season-level decision dashboard,
episode map, scene register spanning all episodes with episode-prefixed IDs, EDIT cards,
runtime report with per-episode AND season totals), then the §13 validation gates table.
Every inspected scene in every episode appears in the scene register."""
    else:
        user = f"""INTAKE RECORD (pre-filled fields; label your assumptions for the rest):
- Project title: {title}
- Review mode: ANALYZE (script)
- {target}

FULL SCREENPLAY:
---
{screenplay_text[:200000]}
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


def doctor_front_prompt(screenplay_text: str, title: str,
                        target_runtime: float | None,
                        holistic: bool) -> tuple[str, str]:
    """Pass A — sections 1–4: dashboard, source-integrity, diagnosis, structure map."""
    target = f"Target runtime: {target_runtime:.0f} minutes." if target_runtime else ""
    scope = ("HOLISTIC multi-episode package — judge season-level arcs and promise."
             if holistic else "single screenplay.")
    user = f"""PROJECT: {title} — {scope} {target}

FULL SCREENPLAY:
---
{screenplay_text[:120000]}
---

Deliver ONLY these sections of the spec §3 package, in this order, as Markdown with
'## N. …' headings — no other sections, no preamble:
## 1. Decision Dashboard  (priority table P0–P3 per §3.1 + strongest material to protect)
## 2. Source-Integrity Record  (§3.2 table)
## 3. Story and Character Diagnosis  (§3.3, evidence → problem → consequence → action, character table)
## 4. Structure Map  (§3.4 table)"""
    return ("[[ROLE:doctor_front]]\n" + _framework() + _SPEC_RULES), user


def doctor_register_prompt(screenplay_text: str, title: str, scene_index: str,
                           n_scenes: int, holistic: bool) -> tuple[str, str]:
    """Pass B — section 5: complete scene register, EXACTLY one row per scene."""
    ep = ("Episode-prefixed IDs (E2-S014)." if holistic else
          "Stable IDs S001…S{n:03d}.".format(n=n_scenes))
    user = f"""PROJECT: {title}

DETECTED SCENES (exactly {n_scenes}; these are ALL the scenes — none may be skipped):
---
{scene_index}
---

FULL SCREENPLAY (for function/disposition judgment):
---
{screenplay_text[:120000]}
---

Deliver ONLY '## 5. Complete Scene Register' — ONE Markdown table per spec §4 with
EXACTLY {n_scenes} data rows, one per detected scene above, in order. No ellipsis rows,
no grouped summaries, no '…'. Columns: Stable ID ({ep}) | Source | Location/Time |
Function and scene turn | Disposition | Operation | Severity/Priority | Evidence conf.
| Timing conf. | Current/Proposed estimate | Edit ID. Every row must be complete."""
    return ("[[ROLE:doctor_register]]\n" + _framework() + _SPEC_RULES), user


def doctor_cards_prompt(scenes_block: str, holistic: bool) -> tuple[str, str]:
    """Pass C — sections 6–7: one expandable intervention card per scene in the batch."""
    user = f"""SCENES TO COVER (cover EVERY scene listed — one card each, no exceptions):
---
{scenes_block}
---

For EACH scene above deliver ONE expandable intervention card in Markdown:
<details>
<summary>[EDIT-ID] — [operation] — [one-line purpose]</summary>

> source excerpt (verified passage or labeled action paraphrase)

| Field | Content |
|---|---|
| Where | … |
| Current passage | … |
| Remove/change | … |
| Keep/protect | … |
| Why | … |
| After the edit | retained-beat → bridge → retained-beat |
| Proposed result | distinctly labeled proposal |
| Feasibility | … |
| Risks | … |
| Dependencies | setup/payoff IDs |
| Duration | before/removed/added/after/net + basis + confidence |
| Validation | concrete test |

If a scene is a clean KEEP, the card says so in the summary and keeps Keep/protect +
Duration rows honest (zero saving). If a scene needs new material, add its REPAIR card
(§6) right after, labeled NEW MATERIAL. Respect the boundary rule — exact units or
CONDITIONAL — BOUNDARIES REQUIRE VERIFICATION."""
    return ("[[ROLE:doctor_cards]]\n" + _framework() + _SPEC_RULES), user


def doctor_runtime_sound_prompt(screenplay_text: str, title: str, scene_index: str,
                                holistic: bool) -> tuple[str, str]:
    """Pass D1 — sections 8–9: runtime model + sound/BGM map."""
    user = f"""PROJECT: {title}

DETECTED SCENES:
---
{scene_index}
---

FULL SCREENPLAY:
---
{screenplay_text[:120000]}
---

Deliver ONLY these sections, Markdown, '## N. …' headings, one table ROW PER SCENE
(exactly as many rows as detected scenes — no ellipsis, no grouping):
## 8. Runtime Report  (§7: scene timing evidence table with Low/Base/High per scene,
change ledger per edit, {'episode totals + season totals' if holistic else 'project totals'})
## 9. Sound / BGM Map  (§8: one row per scene — dramatic purpose, entry beat, build,
drop/stop, music/silence/ambience/SFX, perspective/motif, risk; separate score from diegetic)"""
    return ("[[ROLE:doctor_runtime]]\n" + _framework() + _SPEC_RULES), user


def doctor_ledgers_gates_prompt(screenplay_text: str, title: str,
                                holistic: bool) -> tuple[str, str]:
    """Pass D2 — sections 10–13: ledgers, implementation, evidence note, validation gates."""
    user = f"""PROJECT: {title}

FULL SCREENPLAY:
---
{screenplay_text[:120000]}
---

Deliver ONLY these sections, Markdown, '## N. …' headings:
## 10. Location, Continuity, Knowledge and Setup/Payoff Ledgers  (§9 — all four ledgers
as tables; {'cross-episode entries included' if holistic else 'scene-anchored rows'})
## 11. Implementation and Testing  (§10 — ordered pass table: verification → causality →
rhythm → character/emotion → alternatives → sound → timed review → dependency audit;
plus the protection list)
## 12. Evidence Appendix  (brief — where source excerpts live, extraction caveats)
## 13. Validation Gates  (§13 — every gate PASS / FAIL / NOT VERIFIED with evidence;
never claim a pass without basis)"""
    return ("[[ROLE:doctor_ledgers]]\n" + _framework() + _SPEC_RULES), user


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
