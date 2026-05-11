# Frontend — Minokane

> Assumes you have already read the root `README.md` for setup, running, and architecture overview.

**Stack:** [Astro 5.7](https://astro.build/) · TypeScript · vanilla CSS (design tokens from `../global.css`)

---

## Directory layout

```
frontend/
├── src/
│   ├── pages/
│   │   └── index.astro              # Single-page app — owns all state + 3-step flow
│   ├── components/
│   │   ├── QuestionInput.astro      # Step 1: form (raw question, optional deadline + outcome)
│   │   ├── OperationalizationChooser.astro  # Step 2: radio cards + inline editing
│   │   ├── ModularQuestionsView.astro       # Step 3: sub-questions + summary display
│   │   └── LoadingSpinner.astro     # Shared spinner
│   ├── layouts/
│   │   └── Layout.astro             # HTML shell, imports global CSS
│   ├── scripts/
│   │   └── api.ts                   # Typed fetch wrapper + all shared interfaces
│   └── styles/
│       global.css                   # Per-page overrides (design tokens live at root)
├── astro.config.mjs                 # Astro + Vite proxy config
└── package.json
```

---

## UI flow

The page renders three `<div class="step">` containers — only one is visible at a time.

| Step | Component | What happens |
|------|-----------|--------------|
| 1 | `QuestionInput` | User submits a raw question → `POST /api/questions` → session created |
| 2 | `OperationalizationChooser` | User picks (and optionally edits inline) one of 3–5 operationalizations → `PUT /api/questions/{id}/select` |
| 3 | `ModularQuestionsView` | Displays the selected operationalization, executive summary, and decomposed sub-questions with domain/importance/likelihood tags |

All step transitions and API calls are handled in the `<script>` block of `index.astro`.

---

## API client (`src/scripts/api.ts`)

All backend communication goes through this module. It exports:

- **Interfaces:** `QuestionInput`, `OperationalizedQuestion`, `ModularSubQuestion`, `ForecastSession`
- **Functions:** `submitQuestion`, `getSession`, `selectOperationalization`, `getResult`

Requests are proxied to `http://localhost:8000` via Vite's dev proxy (configured in `astro.config.mjs`) — no CORS issues in dev.

---

## Environment variable

| Variable | Default | Description |
|----------|---------|-------------|
| `PUBLIC_API_KEY` | `minokane-dev-key` | Value sent as `X-API-Key` header on every request. Prefix `PUBLIC_` is required by Astro to expose it to client-side scripts. |

Create `frontend/.env` (not committed) to override:

```
PUBLIC_API_KEY=your-key-here
```

---

## Scripts

```bash
npm run dev      # Dev server on http://localhost:4321 (with /api proxy)
npm run build    # Production build → dist/
npm run preview  # Serve the production build locally
npm run check    # TypeScript type-check via astro check
```
