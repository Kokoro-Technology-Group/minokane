# Minokane — Ambient Superforecasting

> *Minokane blends Minerva (Roman goddess of strategic wisdom) with Omoikane (Japanese deity of collective intelligence and deep thought).*

An automated forecasting system that takes natural-language questions, operationalizes them into precise, resolvable forms, and decomposes them into modular sub-questions — powered by a multi-agent LLM pipeline (Claude Opus + Sonnet via LangGraph).

**Reference:** [Forethought — Tools for Strategic Awareness](https://www.forethought.org/research/design-sketches-tools-for-strategic-awareness)

---

## Software Requirements

| Tool | Required Version | Check Command | Install Docs |
|------|-----------------|---------------|--------------|
| Bash | 4.3+ | `bash --version` | macOS ships bash 3.2; install a modern bash with `brew install bash` ([Homebrew](https://brew.sh/)) |
| Python | 3.12+ | `python3 --version` | [python.org](https://www.python.org/downloads/) |
| Conda (Miniconda) | Latest | `conda --version` | [Miniconda Install](https://docs.anaconda.com/miniconda/install/) |
| Node.js | v22.12+ | `node --version` | [nodejs.org](https://nodejs.org/) |
| npm | 10+ | `npm --version` | Bundled with Node.js |

> **macOS note:** `dev.sh` uses `wait -n` (bash 4.3+) to surface backend/frontend crashes. Stock macOS bash is 3.2 — without an upgrade you'll see `wait: -n: invalid option` and the script will exit immediately. `brew install bash` puts a modern bash at `/opt/homebrew/bin/bash`, which the `#!/usr/bin/env bash` shebang picks up automatically.

---

## Setup

### One-command setup (recommended)

```bash
./setup.sh
```

This creates the `minokane` conda env (python 3.12) if missing, installs backend Python deps from `backend/requirements.txt`, installs frontend npm deps, and seeds `backend/.env` from `.env.example`. After it finishes, edit `backend/.env` to set your `ANTHROPIC_API_KEY`.

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic Claude API key — used for **all** agents (Opus for the Operationalizer, Sonnet for Critic/Modularizer/Synthesizer) |
| `OPUS_MODEL` | No | Override the Opus model id (default: `claude-opus-4-7`) |
| `SONNET_MODEL` | No | Override the Sonnet model id (default: `claude-sonnet-4-6`) |
| `API_KEY` | No | Simple auth header key for FastAPI routes (default: `minokane-dev-key`) |
| `LOG_LEVEL` | No | Backend log level (default: `INFO`). Logs are emitted as structured JSON. |
| `ENABLE_WEB_SEARCH` | No | Toggle Anthropic's native `web_search` server tool for the Operationalizer (default: `true`). |
| `WEB_SEARCH_MAX_USES` | No | Max `web_search` calls per operationalization (default: `3`). |

<details>
<summary><strong>Manual setup</strong></summary>

#### 1. Create conda environment

```bash
conda create -n minokane python=3.12 -y
conda activate minokane
```

#### 2. Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

Or use the full conda spec:

```bash
conda env update -f backend/environment.yml
```

#### 3. Configure environment variables

```bash
cp .env.example backend/.env
# Edit backend/.env — at minimum set ANTHROPIC_API_KEY
```

#### 4. Install frontend dependencies

```bash
cd frontend
npm install
```

</details>

---

## Running

### One-command launcher (recommended)

```bash
./dev.sh           # bash, prefixed interleaved logs
./dev.sh --tmux    # tmux split-pane variant (requires tmux)
```

The script activates the `minokane` conda env, starts the backend on `:8000` and the frontend on `:4321`, prefixes their output with `[backend]` / `[frontend]`, and tears both processes down cleanly on **CTRL+C** via process-group kill. If `frontend/node_modules` is missing, it runs `npm install` first.

Open [http://localhost:4321](http://localhost:4321) in your browser.

<details>
<summary><strong>Manual (two terminals)</strong></summary>

**Terminal 1 — Backend**
```bash
conda activate minokane
cd backend
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

Open [http://localhost:4321](http://localhost:4321) in your browser.

</details>

---

## Testing

### Light-touch smoke test (TEST mode)

Type `TEST` (case-insensitive — also accepts `test`, `Test`, `  TEST  `) into the question input on [http://localhost:4321](http://localhost:4321). Each of the four personas (Mira, Marcus, Anika, James) makes **one** low-effort adaptive-thinking Anthropic call to briefly introduce itself; canned data fills the rest of the schema. The full pipeline runs end-to-end — FastAPI routes, LangGraph state graph + interrupt, JSON store, frontend rendering — so any wiring failure (bad API key, network issue, broken reasoning-mode config, schema mismatch) surfaces immediately.

- Cost per TEST run: roughly **$0.10–$0.15** (vs. multi-dollar full-pipeline cost).
- Each persona's intro appears in the backend terminal as `[TEST mode] Message received. I'm <Name>; my focus is <focus>.`
- Mira / Anika / James also have their intros embedded in the user-visible operationalization / sub-question / summary fields. Marcus's intro is logs-only since `critic_feedback` is not currently rendered.
- TEST mode auto-approves the critic on the first pass, so the revision loop is **not** exercised — that's intentional. To exercise the revision loop, run a real question.

### Backend unit tests

```bash
conda activate minokane
cd backend
pytest tests/ -v
```

Live end-to-end test (requires `ANTHROPIC_API_KEY`):

```bash
pytest tests/test_routes.py::test_full_flow_live -v -s
```

### Frontend type check

```bash
cd frontend
npm run check
```

### API smoke test

```bash
# Submit a question
curl -X POST http://localhost:8000/api/questions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: minokane-dev-key" \
  -d '{"raw_question": "Will Moores law continue?"}'
```

---

## Architecture

```
User question → FastAPI → LangGraph pipeline (all via Anthropic Claude API):
  1. Operationalizer (Dr. Mira Chen, Claude Opus 4.7)
     → 2–3 candidate operationalizations (binary / categorical / date / numeric)
     → grounded with Anthropic's native web_search server tool (when enabled)
  2. Critic (Marcus Webb, Claude Sonnet 4.6)
     → approve / veto (max 3 rounds)
     → ranks the approved candidates by closeness to the user's original intent
  3. ⏸  Wait for user selection (human-in-the-loop)
     → user may attach an optional high-level feedback string at confirm time
  4. Modularizer (Dr. Anika Patel, Claude Sonnet 4.6)
     → decomposed sub-questions with domain/confidence/likelihood tags
     → incorporates the user's confirm-time feedback
  5. Synthesizer (James Harrington, Claude Sonnet 4.6)
     → executive summary, also informed by the user's feedback
```

### Personas

All four personas live in [`backend/app/agents/personas/`](backend/app/agents/personas/). Each is a LangGraph node that takes the shared `ForecastState` and returns a partial state update. Tool use is implemented via LangChain's [`with_structured_output(Schema)`](https://python.langchain.com/docs/how_to/structured_output/) binding (server-side Anthropic tool use under the hood); none of the personas call external tools (no web search, no MCP).

| Persona | Role | Function | Model | Reasoning mode (prod) | Structured output | Output schema |
|---------|------|----------|-------|----------------------|-------------------|----------------|
| **Dr. Mira Chen** | Operationalizer | Operationalize | Claude Opus 4.7 | On (forced by model) | Yes — tool use | `OperationalizationSchema` — 2–3 candidate operationalizations with `outcome_type` ∈ {binary, categorical, date, numeric}. Bound to Anthropic's `web_search` server tool for current-fact grounding. |
| **Marcus Webb** | Critic | Veto + rank | Claude Sonnet 4.6 | Off (temperature passed) | Yes — tool use | `CriticSchema` — `{approved, feedback, ranked_order}` where `ranked_order` is a permutation of candidate indices sorted by closeness to the user's original intent. |
| **Dr. Anika Patel** | Modularizer | Decompose | Claude Sonnet 4.6 | Off (temperature passed) | Yes — tool use | `ModularizationSchema` — atomic flag + 0–8 sub-questions. Receives optional `user_feedback` from the confirm step. |
| **James Harrington** | Synthesizer | Summarize | Claude Sonnet 4.6 | Off (temperature passed) | Yes — tool use | `SynthesisSchema` — `{summary}` (<300 words). Receives optional `user_feedback`. |

In **TEST mode** (raw question == `TEST`), every persona temporarily forces reasoning mode ON via Opus 4.7's adaptive thinking (`thinking={"type": "adaptive"}`, `output_config={"effort": "low"}`) and skips structured output — see [Testing](#testing).

### Directory layout

```
minokane/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Pydantic settings
│   │   ├── routes/questions.py  # REST endpoints
│   │   ├── models/schemas.py    # Pydantic models
│   │   ├── agents/
│   │   │   ├── graph.py         # LangGraph StateGraph
│   │   │   ├── state.py         # TypedDict state
│   │   │   └── personas/        # 4 agent files + LLM factory
│   │   └── storage/json_store.py
│   ├── data/questions.json      # Persisted sessions (overwritten)
│   ├── tests/
│   ├── environment.yml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/index.astro    # Main SPA page
│   │   ├── components/          # QuestionInput, Chooser, Results
│   │   ├── scripts/api.ts       # Typed fetch wrapper
│   │   └── styles/global.css
│   ├── astro.config.mjs
│   └── package.json
├── .env.example
└── global.css                   # Design tokens (source)
```

---

## API Reference

All routes require `X-API-Key` header (default: `minokane-dev-key`).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/questions` | Submit question → runs pipeline → returns operationalized options |
| `GET` | `/api/questions/{id}` | Get session state |
| `PUT` | `/api/questions/{id}/select` | User selects operationalization → runs modularizer + synthesizer |
| `GET` | `/api/questions/{id}/result` | Get completed session |
| `GET` | `/health` | Health check |

The `PUT /api/questions/{id}/select` body accepts an optional `user_feedback` string alongside `operationalized_question`; when present it's persisted on the session and threaded into the Modularizer and Synthesizer prompts.

---

## Outcome types

Each candidate operationalization carries an `outcome_type` that drives how the chooser renders the outcome field and how the resolved value should be interpreted:

| `outcome_type` | When to use | `outcome_options` | `outcome_unit` |
|---|---|---|---|
| `binary` | Default. "Will X happen by Y?" | `["Yes", "No"]` | `null` |
| `categorical` | 3+ named, mutually-exclusive buckets | Full list of bucket labels | `null` |
| `date` | "When will X happen?" — answer is a date | `[]` (or labeled buckets) | `null` |
| `numeric` | "How many / how much" — answer is a number | `[]` (or labeled buckets) | e.g. `"USD"`, `"%"`, `"bps"` |

The Operationalizer picks the type per candidate; the frontend swaps the editor (text box / date picker / number input) accordingly. The deadline field always represents the latest date by which the question must resolve or void.

---

## Logging

The backend emits structured JSON to stdout via [`python-json-logger`](https://github.com/madzak/python-json-logger). Every record carries:

- `request_id` — generated per HTTP request (or echoed from an inbound `X-Request-Id` header) and propagated across the async LangGraph pipeline via a `ContextVar`.
- `persona`, `model`, `elapsed_ms` — emitted on each agent's entry/exit by the `agent_log()` context manager in [`backend/app/logging_setup.py`](backend/app/logging_setup.py).
- `input_tokens`, `output_tokens` — extracted best-effort from LangChain's `response_metadata`.
- Persona-specific fields like `num_candidates`, `num_sub_questions`, `is_atomic`, `approved`, `revision_count`, `num_web_searches`.

Tune verbosity with `LOG_LEVEL` (default `INFO`). All log lines for a single forecast share the same `request_id`, making `jq 'select(.request_id == "<id>")'` filtering trivial.
