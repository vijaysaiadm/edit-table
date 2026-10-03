"""Data models for the pipeline. Plain dataclasses — no heavy validation deps."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Scene:
    number: int
    heading: str            # e.g. "INT. COFFEE SHOP - DAY"
    text: str               # full scene body
    estimated_minutes: float = 0.0


@dataclass
class Screenplay:
    title: str
    raw_text: str
    scenes: list[Scene]
    estimated_runtime: float  # minutes
    preamble: str = ""        # title page / notes before the first scene heading


@dataclass
class Brief:
    """Stage 2 'shared brief' — the lead agent's global judgment every worker judges against."""
    one_line_story: str = ""
    core_conflict: str = ""
    hero_arc: str = ""
    antagonist_arc: str = ""
    emotional_core: str = ""
    target_runtime_min: float = 0.0
    current_runtime_min: float = 0.0
    genre_mix: list[str] = field(default_factory=list)
    story_priorities: list[str] = field(default_factory=list)
    global_notes: list[str] = field(default_factory=list)

    def as_prompt_block(self) -> str:
        return (
            f"ONE-LINE STORY: {self.one_line_story}\n"
            f"CORE CONFLICT: {self.core_conflict}\n"
            f"HERO ARC: {self.hero_arc}\n"
            f"ANTAGONIST ARC: {self.antagonist_arc}\n"
            f"EMOTIONAL CORE: {self.emotional_core}\n"
            f"RUNTIME: current ~{self.current_runtime_min:.0f} min, target {self.target_runtime_min:.0f} min\n"
            f"GENRE MIX: {', '.join(self.genre_mix) or 'drama'}\n"
            f"STORY PRIORITIES (protect these): {', '.join(self.story_priorities)}\n"
            f"GLOBAL NOTES: {'; '.join(self.global_notes)}"
        )


@dataclass
class SceneAnalysis:
    """The 20-field edit-table analysis for a single scene (Section 2 of the master prompt)."""
    scene_number: int
    scene_purpose: str = ""
    conflict: str = ""
    emotional_state: str = ""
    audience_expectation: str = ""
    scene_hook: str = ""
    turning_point: str = ""
    payoff: str = ""
    weak_point: str = ""
    editing_opportunity: str = ""
    recommended_cut: str = ""       # KEEP / TRIM / MERGE / RESTRUCTURE / MOVE / REMOVE
    recommended_trim: str = ""
    transition: str = ""
    bgm_requirement: str = ""
    sound_design: str = ""
    tempo: str = ""
    estimated_runtime: float = 0.0
    problem_class: str = ""         # STORY/SCREENPLAY/SCENE/EDITING/PERFORMANCE/BGM/PACING or NONE
    notes: str = ""


@dataclass
class GenreFinding:
    specialist: str          # action / thriller / romance / comedy
    scene_number: int | None
    finding: str
    severity: str = "medium"  # low / medium / high


@dataclass
class UtilityResult:
    worker: str              # character_arcs / runtime / continuity / bgm_map
    payload: dict[str, Any]


@dataclass
class Conflict:
    """A contradiction caught by the reconciliation pass."""
    scene_number: int
    worker_a: str
    worker_b: str
    issue: str
    resolution: str = ""


@dataclass
class FinalVerdict:
    scene_number: int
    verdict: str             # KEEP / TRIM / MERGE / RESTRUCTURE / MOVE / REMOVE
    action: str              # concrete edit instruction
    reason: str = ""
    safe_vs_aggressive: str = "safe"


@dataclass
class AnalysisResult:
    screenplay_title: str
    tenant_id: str = "default"   # isolation: every artifact is scoped to a tenant
    brief: Brief = field(default_factory=lambda: Brief())
    scene_analyses: list[SceneAnalysis] = field(default_factory=list)
    genre_findings: list[GenreFinding] = field(default_factory=list)
    utilities: dict[str, UtilityResult] = field(default_factory=dict)
    conflicts: list[Conflict] = field(default_factory=list)
    final_verdicts: list[FinalVerdict] = field(default_factory=list)
    emotional_graph: list[dict[str, Any]] = field(default_factory=list)
    final_edit_plan: str = ""
    top_opportunities: list[str] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)  # which stages ran

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
