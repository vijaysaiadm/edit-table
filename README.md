# 🎬 edit-table

**Multi-tenant agentic film-editing screenplay analysis** — a swarm architecture built around the
*FILM EDITOR — MASTER AGENT* prompt (`prompts-source/MASTER_AGENT.txt`). The original
prompt was written for one editor; this application serves **any filmmaker, editor or studio** — each
tenant gets isolated credentials, isolated reports, and an optional per-tenant LLM key/model.

Built for commercial Indian cinema editing work: screenplay analysis, scene-by-scene edit tables,
rhythm/tempo maps, BGM design, runtime reduction and commercial-cinema checks — produced by multiple
cooperating agents and reconciled by a lead agent.

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

## Multi-tenancy & access modes

**Just want you and your team to use it without tokens? Enable OPEN ACCESS** in the admin
page ("Open access" checkbox): anyone can analyze immediately, everyone shares the server
default key, and concurrent users aren't blocked. Turn it off later when you onboard
tenants who need separate keys/billing.

- **Open access ON** → no token needed; valid tenant tokens still work (tenants with their
  own key are billed to that key)
- **Open access OFF** → every user needs a tenant token (`tok_…`)

Tenants (for separate keys/billing when you need them) are managed with `edit-table tenant`
or the admin UI, stored in `tenants.json` (gitignored — copy `tenants.example.json` to start):
  ```bash
  cp tenants.example.json tenants.json
  edit-table tenant list
  edit-table tenant create studio-a "Studio A" --llm-api-key sk-their-own-key --llm-model gpt-4o
  ```
  Each tenant gets an auto-generated `api_token`. A tenant may bring its **own LLM key and model**
  (billed to them) or inherit the server default from `.env`.
- **Isolation:**
  - CLI: `edit-table analyze script.txt --tenant studio-a` → settings + `reports/studio-a/`
  - Web/API: clients present their token as the `X-API-Key` header; unknown tokens get 401;
    every artifact is written under `reports/<tenant_id>/`
  - Per-tenant single-flight guards — tenants never see or block each other
- The registry is a JSON file by default; swap it for a database in production behind the same
  `TenantRegistry` interface.

## Where the API key lives

Three layers, highest priority wins:

| Layer | Where | Set via |
|---|---|---|
| 1. Tenant's own key | `tenants.json` (gitignored) | Admin UI → Tenants, or `edit-table tenant create --llm-api-key` |
| 2. Server default | `server_settings.json` (gitignored) | **Admin UI → Server default LLM settings** |
| 3. Fallback | `.env` → `LLM_API_KEY` | text editor |

**Admin UI** (`/admin`, linked from the main page): on first server start an admin key
(`adm_…`) is generated, printed to the console, and stored in `server_settings.json`.
With that key you can paste the server-default API key, choose the model, and create /
delete tenants (each gets an access token to share). Keys are write-only through the API —
the admin page only ever shows the last 4 characters.

## Setup

```bash
cd edit-table
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
edit-table analyze screenplay.txt --target-runtime 150

# As a specific tenant (own key/model, reports/<tenant>/ folder)
edit-table analyze screenplay.txt --tenant studio-a

# Manage tenants
edit-table tenant list
edit-table tenant create editor-b "Independent Editor B"

# Solo single-agent mode (stage 1)
edit-table analyze screenplay.txt --stage 1

# Offline test without an API key (deterministic mock workers)
edit-table analyze examples/sample_screenplay.txt --mock

# Multi-tenant web UI (clients sign in with their X-API-Key token)
edit-table serve    # http://localhost:7100
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
src/edit_table/
  config.py        settings resolution: tenant > admin server settings > env/.env
  server_settings.py  admin-managed server defaults + admin token (server_settings.json)
  tenants.py       multi-tenant registry: tokens, per-tenant LLM keys/models, isolation
  llm.py           OpenAI-compatible client (async, retried, concurrency-capped) + MockLLM
  screenplay.py    loader + heuristic scene splitter (INT./EXT., SCENE n, సీన్ n)
  models.py        dataclasses for every pipeline artifact
  prompts/         prompt builders; doctrine condensed from the master prompt
  orchestrator.py  the swarm: brief → parallel workers → specialists → reconciliation
  report.py        A–P markdown report renderer
  cli.py           `edit-table analyze|serve`
  server.py        FastAPI REST API + embedded web UI (web/index.html)
prompts-source/MASTER_AGENT.txt   the source-of-truth master prompt
examples/        sample_screenplay.txt (clean) · flawed_screenplay.txt (7 planted defects
                 listed at the end — use it to verify the pipeline catches them)
tests/           offline pipeline tests (mock mode)
```

## Deploying to Vercel

The app ships with a serverless adapter (`api/index.py` + `vercel.json`). Two ways to deploy:

**A. Dashboard (recommended, 2 minutes)**
1. Push this repo to GitHub (already done if you're reading this there)
2. [vercel.com/new](https://vercel.com/new) → Import `vijaysaiadm/edit-table` → Deploy
3. Vercel auto-detects `vercel.json`; no env vars are required to boot —
   set the LLM key afterwards via the **Admin UI** it prints, or add `LLM_API_KEY`
   in Project → Settings → Environment Variables and redeploy

**B. CLI**
```bash
npm i -g vercel
vercel login
vercel --prod
```

**Serverless constraints — read before relying on it:**
- ⏱ **Function timeout**: full-swarm analyses (stages 1+2+3) make many LLM calls and
  usually exceed Vercel's limits (Hobby 60 s max; Pro 300 s). On Hobby, use
  **Stage 1 mode** in the UI, or deploy the server to a long-running host
  (Render/Railway/Fly — `edit-table serve` works unchanged) for full swarm runs.
- 🗂 **Ephemeral storage**: `tenants.json`, `server_settings.json` and reports live in
  `/tmp` on Vercel and disappear between invocations/cold starts. Tenants and the
  admin key must be recreated on each cold start, and old reports are not retrievable.
  For durable multi-tenancy, run the server app instead — or point the code at external
  storage by extending `paths.py`.

## Notes for real use

- Quality scales with the model. Use the strongest model you can afford for the lead
  agent; a cheaper/faster model is usually fine for per-scene workers (`LLM_MODEL_WORKER`).
- Very long screenplays: the lead brief truncates at ~60k chars and workers see one scene
  each — raise truncation limits in `orchestrator.py` if your scripts are longer.
- The splitter is heuristic. If your scripts use unusual formatting, adjust `HEADING_RE`
  in `screenplay.py` (Telugu scene headings `సీన్` are already supported).
