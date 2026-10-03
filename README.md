# 🎬 madhav-edit

**Agentic film-editing screenplay analysis** — a swarm architecture for the *MADHAV FILM EDITOR — MASTER AGENT* prompt (`prompts-source/MADHAV_MASTER_AGENT.txt`).

Built for Madhav Kumar's Telugu commercial cinema editing work: screenplay analysis, scene-by-scene edit tables, rhythm/tempo maps, BGM design, runtime reduction and commercial-cinema checks — produced by multiple cooperating agents and reconciled by a lead agent.

## Architecture

```
                 ┌──────────────────────────────┐
                 │  LEAD AGENT (editor-in-chief) │
                 │  sees the FULL script; owns   │
                 │  story judgment & final plan  │
                 └──────┬───────────────┬───────┘
        lead brief      │               │ delegates independent sub-analyses
        (stage 2a)      ▼               ▼
              ┌──────────────┐   ┌─────────────────────────┐
              │ SCENE WORKERS│   │  GENRE SPECIALISTS      │
              │ one per scene│   │  action / thriller /    │
              │ 20-field     │   │  romance / comedy       │
              │ edit-table   │   │  (only genres present)  │
              │ analysis     │   └─────────────────────────┘
              └──────────────┘   ┌─────────────────────────┐
                                 │  UTILITY WORKERS        │
                                 │  character-arc tracker  │
                                 │  runtime estimator      │
                                 │  continuity scanner     │
                                 │  BGM/tempo map designer │
                                 └─────────────────────────┘
                        │                 │
                        ▼                 ▼
                 ┌──────────────────────────────┐
                 │  LEAD RECONCILIATION         │
                 │  resolves worker conflicts   │
                 │  (e.g. one worker cuts what  │
                 │  another scene's payoff      │
                 │  depends on) → final A–P     │
                 │  edit report                 │
                 └──────────────────────────────┘
```

**Design principle:** swarm the mechanical and genre-deep work; never swarm the judgment.
Every worker judges against the lead's *shared brief*, so scene verdicts stay globally coherent.
A `--stage 1` solo mode runs the classic single-agent pipeline for comparison.

## Setup

```bash
cd madhav-edit
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then put your key in .env — never commit it
```

`.env`:

```ini
LLM_API_KEY=sk-your-key-here
LLM_BASE_URL=https://api.openai.com/v1   # any OpenAI-compatible endpoint works
LLM_MODEL=gpt-4o
LLM_MODEL_WORKER=                        # optional cheaper model for per-scene workers
MAX_CONCURRENCY=6
```

## Usage

```bash
# Full swarm (stages 1+2+3) — the complete A–P edit report
madhav-edit analyze screenplay.txt --target-runtime 150

# Solo single-agent mode (stage 1)
madhav-edit analyze screenplay.txt --stage 1

# Offline test without an API key (deterministic mock workers)
madhav-edit analyze examples/sample_screenplay.txt --mock

# Web UI
madhav-edit serve    # http://localhost:7100
```

Outputs land in `reports/` as a Markdown edit report (sections A–P from the master prompt)
plus the full JSON data for downstream tooling.

Supported inputs: `.txt`, `.md`, `.fountain`, `.pdf`.

## The report

The report follows the master prompt's output format: one-line story, core conflict,
hero/antagonist arcs, emotional graph, runtime & repetition problems, top-10 editing
opportunities, scene-by-scene edit table (KEEP / TRIM / MERGE / RESTRUCTURE / MOVE /
REMOVE, separated into *safe* vs *aggressive* edits), BGM/tempo map, genre-specialist
findings, character arcs, reconciliation notes, and the final pass-by-pass edit plan.

## Tests

```bash
python tests/test_pipeline.py        # offline, no API key needed
```

## Project layout

```
src/madhav_edit/
  config.py        settings from environment (.env); keys never live in code
  llm.py           OpenAI-compatible client (async, retried, concurrency-capped) + MockLLM
  screenplay.py    loader + heuristic scene splitter (INT./EXT., SCENE n, సీన్ n)
  models.py        dataclasses for every pipeline artifact
  prompts/         prompt builders; doctrine condensed from the master prompt
  orchestrator.py  the swarm: brief → parallel workers → specialists → reconciliation
  report.py        A–P markdown report renderer
  cli.py           `madhav-edit analyze|serve`
  server.py        FastAPI REST API + embedded web UI (web/index.html)
prompts-source/MADHAV_MASTER_AGENT.txt   the source-of-truth master prompt
examples/        sample screenplay for testing
tests/           offline pipeline tests (mock mode)
```

## Notes for real use

- Quality scales with the model. Use the strongest model you can afford for the lead
  agent; a cheaper/faster model is usually fine for per-scene workers (`LLM_MODEL_WORKER`).
- Very long screenplays: the lead brief truncates at ~60k chars and workers see one scene
  each — raise truncation limits in `orchestrator.py` if your scripts are longer.
- The splitter is heuristic. If your scripts use unusual formatting, adjust `HEADING_RE`
  in `screenplay.py` (Telugu scene headings `సీన్` are already supported).
