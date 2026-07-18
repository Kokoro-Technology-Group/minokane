# Backend — Minokane

FastAPI service wrapping a LangGraph multi-agent pipeline. Assumes you've completed root-level setup (conda env, `.env`, dependencies).

---

## Directory layout

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, CORS, lifespan
│   ├── config.py                  # Pydantic settings (reads .env)
│   ├── routes/questions.py        # REST endpoints + API-key auth
│   ├── models/schemas.py          # Pydantic request/response models
│   ├── agents/
│   │   ├── graph.py               # LangGraph StateGraph wiring (Ask + Think)
│   │   ├── state.py               # ForecastState TypedDict
│   │   └── personas/
│   │       ├── _llm_factory.py    # Sonnet via OpenRouter or Anthropic
│   │       ├── operationalizer.py # Dr. Mira Chen — Claude Opus (Ask)
│   │       ├── critic.py          # Marcus Webb — Claude Sonnet (Ask rank + Think validate)
│   │       ├── modularizer.py     # Dr. Anika Patel — decompose + market-pick (Think)
│   │       └── synthesizer.py     # James Harrington — DEFERRED to Show (not in graph)
│   ├── integrations/              # Think: real prediction-market clients
│   │   ├── _http.py               # async client, TTL cache, weekly resampler
│   │   ├── models.py              # MarketCandidate, TimeSeriesPoint, MarketPick
│   │   ├── manifold.py            # public REST — search + bet-history series
│   │   └── metaculus.py           # token-gated reads (Manifold-only if unset)
│   ├── services/market_matching.py # Think: search→pick→validate→fetch→dedupe
│   └── storage/json_store.py      # Async-safe flat-file session store
├── data/questions.json            # Persisted sessions (auto-created)
├── tests/
│   ├── test_agents.py
│   └── test_routes.py
├── environment.yml
└── requirements.txt
```

---

## Agent pipeline

```
POST /api/questions                          ── ASK ──
  │
  ▼
operationalizer (Opus) → 2–3 candidate operationalizations
  │
  ▼
critic (Sonnet) ──── approved or ≥3 revisions ──────────────────┐
  │                                                              │
  └──── veto (revision < 3) → back to operationalizer           │
                                                                 ▼
                                                   ⏸ wait_for_selection
                                                   (LangGraph interrupt)
                                                                 │
PUT /api/questions/{id}/select (user picks one)   ── THINK ──    │
                                                                 ▼
                                                   decompose (Anika, Sonnet)
                                                   → 3–5 majors, each with
                                                     0–4 ideal sub-questions
                                                                 │
                                                                 ▼
                                                   market_match (service)
                                                   per sub-question:
                                                     search Metaculus+Manifold
                                                     → Anika picks best real market
                                                     → Marcus validates relevance
                                                     → fetch weekly time_series
                                                   → market-backed tree + coverage
```

The graph pauses at `wait_for_selection` via `langgraph.types.interrupt`. The thread ID is the session ID; the route layer calls `graph.invoke(Command(resume=…), config)` to continue.

### Think stage — real markets only

Every **leaf** in the returned tree is a real, live prediction market (`source`,
`market_id`, `market_url`, `status`, `outcome_options`, and a normalized weekly
`time_series`); rollup majors only group market children. Sub-questions with no
acceptable market are **dropped** — the pipeline never invents a market or
synthesizes a probability series. A `coverage` object reports how many proposed
sub-questions found markets. See [`prd_ask_think.md`](../prd_ask_think.md) for the full contract.

- **Manifold** — public REST, always available (no key).
- **Metaculus** — reads now require `METACULUS_API_TOKEN`. When unset, the tree
  is built from **Manifold only** (honest partial coverage, never a hard failure).
- **James Harrington (Synthesizer)** — the executive summary is **deferred to
  Show**; `synthesizer.py` is retained but no longer wired into the graph, so
  completed sessions carry `final_summary: null`.

Type `TEST` as the question to exercise the full Ask+Think wiring offline with a
canned tree (one minimal reasoning-mode call per persona, no market network).

---

## Session lifecycle

| Status | Set when |
|--------|----------|
| `selecting` | `POST /api/questions` completes and graph is interrupted |
| `complete` | `PUT /api/questions/{id}/select` resumes and finishes |

Sessions are stored as a flat JSON object in `data/questions.json`, keyed by session UUID. Concurrent writes are serialized with `asyncio.Lock`.

---

## LLM routing

| Agent | Model | Provider |
|-------|-------|----------|
| Operationalizer (Mira) | `claude-opus-4-7` | Anthropic (direct) |
| Critic (Marcus), Decomposer/Matcher (Anika) | `claude-sonnet-4-6` | Anthropic (direct) |

The Sonnet factory (`_llm_factory.get_sonnet_llm`) currently uses the Anthropic
API directly. `OPENROUTER_*` settings remain in config for forward-compat.

---

## Configuration

All settings are read from `backend/.env` via Pydantic `BaseSettings` ([app/config.py](app/config.py)).

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required. Used by Operationalizer. |
| `OPENROUTER_API_KEY` | — | Optional. Routes Critic/Modularizer/Synthesizer via OpenRouter. |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Override if using a proxy. |
| `OPUS_MODEL` | `claude-opus-4-7` | Model ID for Operationalizer. |
| `SONNET_MODEL` | `anthropic/claude-sonnet-4-6` | Model ID for the three Sonnet agents. |
| `LLM_TEMPERATURE` | `0.7` | Shared temperature for all agents. |
| `LLM_MAX_TOKENS` | `4096` | Shared max tokens for all agents. |
| `DATA_FILE_PATH` | `./data/questions.json` | Relative to `backend/` working directory. |
| `API_KEY` | `minokane-dev-key` | Value expected in `X-API-Key` header. |
| `METACULUS_API_TOKEN` | — | Optional. Enables Metaculus reads; empty → Manifold-only. |
| `MANIFOLD_BASE_URL` | `https://api.manifold.markets/v0` | Manifold REST base. |
| `METACULUS_BASE_URL` | `https://www.metaculus.com/api2` | Metaculus REST base. |
| `MARKET_SEARCH_LIMIT` | `6` | Candidates per platform per sub-question. |
| `MARKET_FETCH_CONCURRENCY` | `6` | Bounded async pool for search/fetch. |
| `MARKET_HTTP_TIMEOUT` | `15.0` | Per-call HTTP timeout (seconds). |
| `MARKET_CACHE_TTL` | `900` | Market response cache TTL (seconds). |
| `MARKET_MAX_BETS` | `4000` | Manifold bet-history pagination cap. |
| `MARKET_MATCH_MIN_CONFIDENCE` | `medium` | Min Anika pick confidence before Marcus review. |
| `MAX_MAJORS` / `MAX_MINORS_PER_MAJOR` | `5` / `4` | Decomposition bounds. |

---

## Running

```bash
conda activate minokane
cd backend
uvicorn app.main:app --reload --port 8000
```

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Testing

```bash
conda activate minokane
cd backend

# Unit tests (no LLM calls)
pytest tests/ -v

# Live end-to-end (requires ANTHROPIC_API_KEY, hits real models)
pytest tests/test_routes.py::test_full_flow_live -v -s
```

---

## Adding a new persona

1. Create `app/agents/personas/your_agent.py` with a `your_agent_node(state: ForecastState) -> dict` function.
2. Wire it into `app/agents/graph.py` — add the node, edge, and any conditional routing.
3. Add fields to `ForecastState` in `app/agents/state.py` if the node produces new outputs.
4. Expose results via a new field on `ForecastSession` in `app/models/schemas.py` if the frontend needs them.

---

## Work log

Keep a terse, high-level record so the team doesn't re-walk the same paths.

### Think stage — market-backed decomposition (`prd_ask_think.md`)
- Replaced the flat modularizer→synthesizer tail with `decompose → market_match`.
  `decompose` (Anika) drafts 3–5 majors × 0–4 ideal sub-questions; `market_match`
  searches Manifold + Metaculus, has Anika pick the best real market, Marcus
  validate relevance, then fetches + normalizes a weekly `time_series`. Output is
  the recursive `components[]` tree + `coverage` (PRD §7).
- **Metaculus now requires an API token** (its public read API was retired) — the
  matcher degrades to **Manifold-only** when `METACULUS_API_TOKEN` is unset. The
  Metaculus parser is defensive because its authenticated shape couldn't be
  validated without a token in this environment.
- Series normalization is a forward-filled **weekly** resample (`_http.resample_weekly`);
  no interpolation, no synthesized values. Markets with an empty series are dropped.
- **Synthesizer (James)** removed from the graph (deferred to Show); file retained.
- Verified: 51 offline tests (integrations, orchestrator with injected fakes, and a
  fully-offline full-flow route test) + a live Manifold search/series integrity check.
  `PRD §13` assumptions locked in the root `implementation_plan.md`.
