# Implementation Plan — Ask & Think (Minokane)

**Source PRD:** `/Users/msr/msr/minokane/prd_ask_think.md`
**Author:** Staff Eng (AI agent)
**Status:** Ready to execute
**Scope:** Backend only. Ask is largely complete; the bulk of this work is the **Think** stage — decomposition into a market-backed tree with real Metaculus/Manifold data and inline probability `time_series`.

---

## 0. Software requirements

Unchanged from the repo root `README.md`. Verify before running:

| Tool | Required | Check |
|---|---|---|
| Python | 3.12+ | `python3 --version` |
| Conda (Miniconda) | latest | `conda --version` |
| Env | `minokane` | `conda activate minokane` |

No new third-party packages are required. `httpx>=0.28` is already in `backend/requirements.txt` and is the async HTTP client used by the new integrations. All external market APIs used for reads are **public** (Manifold) or **token-gated** (Metaculus — see §7).

Run everything from `/Users/msr/msr/minokane/backend` with the `minokane` env active.

---

## 1. Decisions on PRD §13 open questions (locked)

The PRD states a default for each. I lock them in as the "how":

1. **Schema naming** — recursive `components[]` + `type` discriminator (`"major_category"` / `"minor_category"`), matching `sample_forecast_data.json`. ✅
2. **Tree bounds** — 3–5 majors × 0–4 minors per major. ✅
3. **Series cadence** — weekly resample (forward-filled) over each market's available history. ✅
4. **Web-search grounding** — stays ON for the Operationalizer (already implemented). ✅
5. **Synthesizer (James)** — **removed from the `/select` critical path**; the node code (`synthesizer.py`) is kept intact but no longer wired into the graph. `final_summary` is `None` on new sessions. Deferred to Show. ✅
6. **Match-score threshold** — Anika's pick returns `match_confidence ∈ {high,medium,low}` + `no_match`. Only picks with confidence ≥ `MARKET_MATCH_MIN_CONFIDENCE` (default `medium`) proceed to Marcus's relevance validation. ✅

### 1a. Discovered constraint — Metaculus now requires auth (NEW, deviates from PRD §9)

Live probing shows the Metaculus API (`/api2/questions/` and `/api/posts/`) now returns `Permission Error: The API is only available to authenticated users`. The PRD §9 assumed a public read API. Resolution:

- Add optional `METACULUS_API_TOKEN` env var. Requests send `Authorization: Token <token>`.
- **If the token is absent, Metaculus search returns `[]`** and the tree is built from **Manifold only** — graceful degradation, honest `coverage`, no hard failure (aligns with PRD risk mitigations). Manifold alone satisfies every Think acceptance criterion (real market, real series).
- The Metaculus parser is written defensively (tolerant field access, try/except → `[]`) because the exact authenticated response shape can't be validated in this environment without a token.

---

## 2. End-to-end shape of the change

**Ask** (unchanged behavior): `POST /api/questions` → operationalizer → critic → interrupt.

**Think** (rebuilt): `PUT /api/questions/{id}/select` resumes the graph through a new subgraph:

```
wait_for_selection → decompose (Anika, pass 1) → market_match (service) → END
```

- `decompose` produces a **proposed tree**: 3–5 majors, each with 0–4 *ideal sub-questions* (drafts, no markets yet) plus tags.
- `market_match` runs the deterministic orchestrator: for each ideal sub-question (and each atomic-major candidate) → search Manifold+Metaculus → Anika picks best real market (or no-match) → Marcus validates relevance → fetch full weekly `time_series` → attach. Drops anything without an accepted, live market. Dedupes markets. Emits `coverage`.

The `synthesizer` node is dropped from the graph.

---

## 3. Files to CREATE

Absolute paths:

- `/Users/msr/msr/minokane/backend/app/integrations/__init__.py`
- `/Users/msr/msr/minokane/backend/app/integrations/models.py`
  - `@dataclass MarketCandidate` (source, market_id, question, url, probability, status, description)
  - `@dataclass TimeSeriesPoint` (date, probability)
- `/Users/msr/msr/minokane/backend/app/integrations/_http.py`
  - Shared async httpx GET with retry/backoff + per-call timeout.
  - Module-level TTL response cache (asyncio-lock guarded).
  - `resample_weekly(raw_points) -> list[TimeSeriesPoint]` (sort → forward-fill at 7-day cadence → round 1 dp → cap length).
- `/Users/msr/msr/minokane/backend/app/integrations/manifold.py`
  - `search_markets(client, term, limit) -> list[MarketCandidate]` (binary only; status from `isResolved`/`closeTime`).
  - `fetch_time_series(client, market_id) -> list[TimeSeriesPoint]` (paginate `/bets`, `probAfter`×100 → weekly).
  - `url_is_live(client, url) -> bool` (HTTP 200 liveness).
- `/Users/msr/msr/minokane/backend/app/integrations/metaculus.py`
  - Same interface, token-gated; returns `[]` when `METACULUS_API_TOKEN` unset. Parses community-prediction history defensively.
- `/Users/msr/msr/minokane/backend/app/services/__init__.py`
- `/Users/msr/msr/minokane/backend/app/services/market_matching.py`
  - `async build_forecast_tree(proposed_majors, *, pick_fn, validate_fn) -> (components, coverage)` — orchestration, dedupe, coverage counting, bounded concurrency.
- `/Users/msr/msr/minokane/backend/tests/test_integrations.py` — pure-function tests (resample, normalization, status) with no network.
- `/Users/msr/msr/minokane/backend/tests/test_market_matching.py` — orchestrator tests with injected fake search/pick/validate/fetch (no network, no LLM).

## 4. Files to MODIFY

- `/Users/msr/msr/minokane/backend/app/config.py` — add market settings (§6).
- `/Users/msr/msr/minokane/backend/app/models/schemas.py` — add `TimeSeriesPoint`, recursive `ForecastComponent`, `Coverage`; extend `ForecastSession` with `core_question`, `components`, `coverage`.
- `/Users/msr/msr/minokane/backend/app/agents/state.py` — add `proposed_tree`, `forecast_components`, `coverage`.
- `/Users/msr/msr/minokane/backend/app/agents/personas/modularizer.py` — Anika evolves: `decompose_node` (pass 1, hierarchical majors+ideal sub-questions) and `async pick_best_market(...)` (pass 2).
- `/Users/msr/msr/minokane/backend/app/agents/personas/critic.py` — add `async validate_market_match(...)` (Marcus Think role). `critic_node` (Ask) unchanged.
- `/Users/msr/msr/minokane/backend/app/agents/personas/_test_mode.py` — add `make_test_proposed_tree()` and `make_test_forecast_tree()` (canned, no network).
- `/Users/msr/msr/minokane/backend/app/agents/graph.py` — rewire: `wait_for_selection → decompose → market_match → END`; drop `synthesizer` from the graph.
- `/Users/msr/msr/minokane/backend/app/routes/questions.py` — `/select` reads `forecast_components` + `coverage`; sets `core_question`; `final_summary=None`.
- `/Users/msr/msr/minokane/backend/tests/test_agents.py` — update node-name + decompose test-mode expectations; keep the rest.
- `/Users/msr/msr/minokane/backend/tests/test_routes.py` — `test_full_flow_live` asserts `components` + `coverage` instead of `final_summary`.
- `/Users/msr/msr/minokane/.env.example` and `/Users/msr/msr/minokane/backend/.env` — document new market vars.
- `/Users/msr/msr/minokane/backend/README.md` and `/Users/msr/msr/minokane/README.md` — document the Think pipeline + config (Phase 4).

## 5. Files to DELETE

None. `synthesizer.py` is retained (out-of-critical-path, deferred to Show).

---

## 6. New configuration (`config.py` / `.env`)

| Var | Default | Purpose |
|---|---|---|
| `MANIFOLD_BASE_URL` | `https://api.manifold.markets/v0` | Manifold REST base |
| `METACULUS_BASE_URL` | `https://www.metaculus.com/api2` | Metaculus REST base |
| `METACULUS_API_TOKEN` | `""` | Optional; enables Metaculus. Empty → Manifold-only |
| `MARKET_SEARCH_LIMIT` | `6` | Candidates per platform per sub-question |
| `MARKET_FETCH_CONCURRENCY` | `6` | Bounded async pool size |
| `MARKET_HTTP_TIMEOUT` | `15.0` | Per-call timeout (s) |
| `MARKET_CACHE_TTL` | `900` | Response cache TTL (s) |
| `MARKET_MAX_BETS` | `4000` | Manifold bet-history page cap |
| `MARKET_MATCH_MIN_CONFIDENCE` | `medium` | Min Anika pick confidence before Marcus review |
| `MAX_MAJORS` / `MAX_MINORS_PER_MAJOR` | `5` / `4` | Prompt guidance bounds |

---

## 7. Output contract (per PRD §7)

`ForecastSession` gains, on completion:
- `core_question: str` — selected operationalization text.
- `coverage: {sub_questions_proposed, markets_found, branches_dropped}`.
- `components: ForecastComponent[]` — recursive tree; a node is a **market** iff it has no `components` (carries `source`, `market_id`, `market_url`, `status`, `outcome_options`, `time_series`); otherwise a **rollup**.

Invariant enforced by the service: every **leaf** is a real, live market with a non-empty `time_series`; rollups with zero surviving market children are dropped; zero total markets → `components: []` + honest coverage.

Existing fields `modular_sub_questions` / `final_summary` are retained for backward-compat but are empty/`None` on new sessions (frontend Show update is out of scope).

---

## 8. Verify (Phase 3)

- `pytest tests/ -v` — offline unit tests (no network, no LLM). Must pass.
- Manual/live: `pytest tests/test_routes.py::test_full_flow_live` (needs `ANTHROPIC_API_KEY`; hits Manifold live). Confirms every shipped leaf has a live `market_url` + non-empty `time_series`.
- `TEST` sentinel question path stays fully offline (canned tree).

## 9. Risks

- **Metaculus token absent** → Manifold-only coverage (acceptable, honest).
- **Manifold rate limits / thin results** → cache + bounded concurrency + graceful drop.
- **LLM latency** on per-candidate pick/validate → async `ainvoke`, bounded pool, ≤5×4 caps.
