"""Offline tests — run with: python -m pytest tests/ -v   (or python tests/test_pipeline.py)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from madhav_edit.config import Settings  # noqa: E402
from madhav_edit.models import Brief, Scene  # noqa: E402
from madhav_edit.orchestrator import run_analysis  # noqa: E402
from madhav_edit.report import render_report, save_outputs  # noqa: E402
from madhav_edit.screenplay import load_screenplay, split_scenes  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "examples" / "sample_screenplay.txt"


def test_scene_splitter():
    s = Settings(mock=True)
    sp = load_screenplay(SAMPLE, s)
    assert len(sp.scenes) >= 7, f"expected >=7 scenes, got {len(sp.scenes)}"
    assert sp.scenes[0].heading.startswith("EXT.")
    assert sp.estimated_runtime > 0


def test_brief_prompt_block():
    b = Brief(one_line_story="X", core_conflict="Y", target_runtime_min=140,
              current_runtime_min=160, genre_mix=["thriller"])
    block = b.as_prompt_block()
    assert "140" in block and "thriller" in block


def test_full_pipeline_mock():
    s = Settings(mock=True)
    result = __import__("asyncio").run(
        run_analysis(SAMPLE, s, target_runtime=130, stages=(1, 2, 3)))
    assert result.brief.one_line_story
    assert len(result.scene_analyses) >= 7
    assert len(result.genre_findings) > 0          # genre specialists ran
    assert set(result.utilities) >= {"character_arcs", "runtime", "continuity", "bgm_map"}
    assert len(result.final_verdicts) > 0
    assert result.final_edit_plan
    for st in result.stages:
        assert st.startswith(("stage", "reconcile"))


def test_report_render_and_save(tmp_path):
    s = Settings(mock=True)
    import asyncio
    result = asyncio.run(run_analysis(SAMPLE, s, stages=(1, 2, 3)))
    md = render_report(result)
    for section in ["A. One-line story", "K. Runtime problem", "N. Scene-by-scene",
                    "O. BGM / tempo map", "P. Final edit plan"]:
        assert section in md, f"missing section {section}"
    md_path, js_path = save_outputs(result, tmp_path)
    assert md_path.exists() and js_path.exists()


def test_solo_stage1_mock():
    import asyncio
    s = Settings(mock=True)
    result = asyncio.run(run_analysis(SAMPLE, s, stages=(1,)))
    assert result.final_edit_plan and result.final_verdicts


if __name__ == "__main__":
    for name, fn in [(n, f) for n, f in list(globals().items()) if n.startswith("test_")]:
        if fn.__code__.co_argcount == 0:
            fn()
            print(f"✔ {name}")
        else:
            import tempfile
            with tempfile.TemporaryDirectory() as d:
                fn(Path(d))
            print(f"✔ {name}")
    print("All tests passed.")
