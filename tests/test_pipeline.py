"""Offline tests — run with: python -m pytest tests/ -v   (or python tests/test_pipeline.py)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from edit_table.config import Settings  # noqa: E402
from edit_table.models import Brief, Scene  # noqa: E402
from edit_table.orchestrator import run_analysis, run_develop, run_doctor  # noqa: E402
from edit_table.report import render_report, save_outputs  # noqa: E402
from edit_table.screenplay import load_screenplay, split_scenes  # noqa: E402

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


def test_multi_tenant_isolation(tmp_path):
    """Two tenants: own keys/models, token lookup, per-tenant report folders."""
    import asyncio
    from edit_table.config import load_settings
    from edit_table.tenants import TenantRegistry

    reg = TenantRegistry(tmp_path / "tenants.json")
    a = reg.create("studio-a", "Studio A", llm_api_key="sk-a", llm_model="gpt-4o")
    b = reg.create("editor-b", "Editor B")  # no own key → inherits server default
    assert reg.by_token(a.api_token).tenant_id == "studio-a"
    assert reg.by_token(b.api_token).tenant_id == "editor-b"

    sa = load_settings(mock=True, tenant=reg.by_token(a.api_token))
    sb = load_settings(mock=True, tenant=reg.by_token(b.api_token))
    assert sa.tenant_id == "studio-a" and sa.model == "gpt-4o" and sa.api_key == "sk-a"
    assert sb.tenant_id == "editor-b" and sb.api_key != "sk-a"  # isolated

    ra = asyncio.run(run_analysis(SAMPLE, sa, stages=(1, 2, 3)))
    rb = asyncio.run(run_analysis(SAMPLE, sb, stages=(1, 2, 3)))
    mda, _ = save_outputs(ra, tmp_path / "reports")
    mdb, _ = save_outputs(rb, tmp_path / "reports")
    assert mda.parent.name == "studio-a" and mdb.parent.name == "editor-b"
    assert mda != mdb


def test_server_settings_priority(tmp_path):
    """Admin-set server default overrides env; tenant key overrides the server default."""
    import os
    from edit_table.config import load_settings
    from edit_table.server_settings import ServerSettingsStore

    os.environ["LLM_API_KEY"] = "sk-from-env"
    store = ServerSettingsStore(tmp_path / "server_settings.json")
    assert store.ensure_admin_token().startswith("adm_")
    store.update(llm_api_key="sk-admin-set", llm_model="admin-model")
    store.reload()

    s = load_settings(server_defaults=store.get())
    assert s.api_key == "sk-admin-set" and s.model == "admin-model"

    tenant = type("T", (), {"tenant_id": "x", "display_name": "X",
                            "llm_api_key": "sk-tenant", "llm_base_url": None,
                            "llm_model": None, "max_concurrency": None,
                            "minutes_per_page": None})()
    s2 = load_settings(tenant=tenant, server_defaults=store.get())
    assert s2.api_key == "sk-tenant" and s2.model == "admin-model"

    masked_view = store.get()
    assert store.verify_admin(store.ensure_admin_token())
    assert not store.verify_admin("wrong")


def test_doctor_and_develop_mock():
    """New modes return raw markdown, work offline in mock mode."""
    import asyncio
    s = Settings(mock=True)
    md = asyncio.run(run_doctor(SAMPLE, s, target_runtime=150))
    assert isinstance(md, str) and "MOCK DOCTOR" in md   # multi-pass: front/register/cards/runtime/ledgers
    dev = asyncio.run(run_develop("A disgraced boxer gets one last shot at the title.",
                                  s, fmt="feature"))
    assert isinstance(dev, str) and "MOCK DEVELOP REPORT" in dev


def test_revise_and_compare_mock():
    """REVISE and COMPARE modes return raw markdown, work offline in mock mode."""
    import asyncio
    from edit_table.orchestrator import run_compare, run_revise
    s = Settings(mock=True)
    rv = asyncio.run(run_revise(SAMPLE, s, "Make the antagonist more sympathetic"))
    assert isinstance(rv, str) and "MOCK REVISE REPORT" in rv
    cp = asyncio.run(run_compare(SAMPLE, SAMPLE, s))
    assert isinstance(cp, str) and "MOCK COMPARE REPORT" in cp


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
