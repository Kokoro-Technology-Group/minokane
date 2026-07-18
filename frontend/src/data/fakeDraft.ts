/**
 * Fake data for the testdraft prototype (Ask / Think / Show).
 *
 * ROUGH DRAFT — this is placeholder content so every screen renders. A separate
 * person will deliver real fake data for the next phase. Keep this file the
 * single source of truth: swap the export, not the components.
 *
 * The `tree` object feeds BOTH the Think phase (bubbly d3 graph) and the Show
 * phase (collapsible accordion), so keep its shape stable.
 */

export interface MarketPoint {
  t: string; // label for the x point (date-ish)
  p: number; // probability 0..1
}

export interface Market {
  source: "Polymarket" | "Manifold" | "Metaculus";
  url: string;
  prob: number; // headline probability 0..1
  points: MarketPoint[]; // sparkline history
}

export interface TreeNode {
  id: string;
  label: string;
  prob: number; // aggregated probability 0..1
  color?: string; // branch color (set on the 3 main subquestions)
  market?: Market; // present on leaves that map to a real market
  children?: TreeNode[];
}

export interface RefineQuestion {
  id: string;
  prompt: string; // e.g. "By 'AI', do you mean frontier LLMs specifically?"
  yesLabel: string;
  noLabel: string;
  default: boolean; // default answer (yes = true)
}

export interface Source {
  label: string;
  url: string;
  kind: "market" | "article" | "dataset";
}

export interface FakeDraft {
  originalQuestion: string;
  defaultDeadline: string; // yyyy-mm-dd
  defaultOutcome: string;
  refineQuestions: RefineQuestion[];
  refinedQuestion: string;
  tree: TreeNode;
  finalAnswer: {
    headline: string;
    prob: number;
    summary: string;
    sources: Source[];
  };
}

// ─── Branch colors (main subquestions) ──────────────────────────────────────
export const BRANCH_COLORS = ["#12AEF5", "#F5A623", "#7ED321"] as const;

const spark = (start: number, end: number): MarketPoint[] => {
  const n = 8;
  return Array.from({ length: n }, (_, i) => {
    const frac = i / (n - 1);
    const noise = Math.sin(i * 1.7) * 0.04;
    return { t: `w${i + 1}`, p: Math.max(0, Math.min(1, start + (end - start) * frac + noise)) };
  });
};

export const fakeDraft: FakeDraft = {
  originalQuestion: "Will a major AI lab release a model beating humans at competitive math by end of 2026?",
  defaultDeadline: "2026-12-31",
  defaultOutcome: "Yes / No",

  refineQuestions: [
    {
      id: "rq1",
      prompt: "By 'major AI lab', do you mean the current frontier labs (OpenAI, Anthropic, Google DeepMind)?",
      yesLabel: "Yes — frontier labs only",
      noLabel: "No — any lab counts",
      default: true,
    },
    {
      id: "rq2",
      prompt: "By 'competitive math', do you mean IMO-level problems specifically?",
      yesLabel: "Yes — IMO level",
      noLabel: "No — any olympiad math",
      default: true,
    },
    {
      id: "rq3",
      prompt: "Does 'beating humans' require beating the gold-medal threshold (not just median)?",
      yesLabel: "Yes — gold-medal threshold",
      noLabel: "No — median human is enough",
      default: false,
    },
  ],

  refinedQuestion:
    "Will OpenAI, Anthropic, or Google DeepMind release a model that clears the IMO gold-medal threshold before 2026-12-31?",

  tree: {
    id: "root",
    label: "Model clears IMO gold before 2027?",
    prob: 0.62,
    children: [
      {
        id: "a",
        label: "Will compute scale enough in time?",
        prob: 0.78,
        color: BRANCH_COLORS[0],
        children: [
          {
            id: "a1",
            label: "Next-gen training clusters online by mid-2026?",
            prob: 0.82,
            market: { source: "Polymarket", url: "https://polymarket.com", prob: 0.82, points: spark(0.6, 0.82) },
          },
          {
            id: "a2",
            label: "Inference-time compute keeps scaling returns?",
            prob: 0.74,
            market: { source: "Manifold", url: "https://manifold.markets", prob: 0.74, points: spark(0.55, 0.74) },
          },
        ],
      },
      {
        id: "b",
        label: "Will math reasoning methods mature?",
        prob: 0.58,
        color: BRANCH_COLORS[1],
        children: [
          {
            id: "b1",
            label: "Verifier/RL approaches generalize to proofs?",
            prob: 0.53,
            market: { source: "Metaculus", url: "https://metaculus.com", prob: 0.53, points: spark(0.4, 0.53) },
          },
          {
            id: "b2",
            label: "Formal-math (Lean) integration lands?",
            prob: 0.63,
            market: { source: "Manifold", url: "https://manifold.markets", prob: 0.63, points: spark(0.5, 0.63) },
          },
        ],
      },
      {
        id: "c",
        label: "Will a lab actually attempt + publish?",
        prob: 0.71,
        color: BRANCH_COLORS[2],
        children: [
          {
            id: "c1",
            label: "A lab targets IMO publicly before 2027?",
            prob: 0.8,
            market: { source: "Polymarket", url: "https://polymarket.com", prob: 0.8, points: spark(0.65, 0.8) },
          },
          {
            id: "c2",
            label: "Result is externally verified (not just PR)?",
            prob: 0.64,
            market: { source: "Metaculus", url: "https://metaculus.com", prob: 0.64, points: spark(0.5, 0.64) },
          },
        ],
      },
    ],
  },

  finalAnswer: {
    headline: "Likely — about 62%",
    prob: 0.62,
    summary:
      "Compute and lab intent both point yes; the swing factor is whether math-reasoning methods generalize from contest-style answers to verifiable proofs at gold-medal difficulty. Watch formal-math integration and the first publicly verified IMO attempt.",
    sources: [
      { label: "Polymarket — IMO gold by 2027", url: "https://polymarket.com", kind: "market" },
      { label: "Manifold — formal math integration", url: "https://manifold.markets", kind: "market" },
      { label: "Metaculus — AI proof verification", url: "https://metaculus.com", kind: "market" },
      { label: "Recent olympiad-math eval results", url: "https://example.com/eval", kind: "article" },
    ],
  },
};
