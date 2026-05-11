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
│   │   ├── graph.py               # LangGraph StateGraph wiring
│   │   ├── state.py               # ForecastState TypedDict
│   │   └── personas/
│   │       ├── _llm_factory.py    # Sonnet via OpenRouter or Anthropic
│   │       ├── operationalizer.py # Dr. Mira Chen — Claude Opus 4.7
│   │       ├── critic.py          # Marcus Webb — Claude Sonnet
│   │       ├── modularizer.py     # Dr. Anika Patel — Claude Sonnet
│   │       └── synthesizer.py     # James Harrington — Claude Sonnet
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
POST /api/questions
  │
  ▼
operationalizer (Opus 4.7) → 3–5 candidate operationalizations
  │
  ▼
critic (Sonnet) ──── approved or ≥3 revisions ──────────────────┐
  │                                                              │
  └──── veto (revision < 3) → back to operationalizer           │
                                                                 ▼
                                                   ⏸ wait_for_selection
                                                   (LangGraph interrupt)
                                                                 │
PUT /api/questions/{id}/select (user picks one)                  │
                                                                 ▼
                                                   modularizer (Sonnet)
                                                   → sub-questions with
                                                     domain/confidence/
                                                     likelihood tags
                                                                 │
                                                                 ▼
                                                   synthesizer (Sonnet)
                                                   → executive summary
```

The graph pauses at `wait_for_selection` via `langgraph.types.interrupt`. The thread ID is the session ID; the route layer calls `graph.invoke(Command(resume=…), config)` to continue.

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
| Operationalizer | `claude-opus-4-7` | Anthropic (direct) |
| Critic, Modularizer, Synthesizer | `anthropic/claude-sonnet-4-6` | OpenRouter (preferred) → Anthropic fallback |

Set `OPENROUTER_API_KEY` to route Sonnet agents through OpenRouter. If unset, they fall back to `ANTHROPIC_API_KEY` with a warning logged at startup.

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
