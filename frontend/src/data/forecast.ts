/**
 * Adapter over the live backend forecast tree.
 *
 * Source shape (ForecastSession.components, see scripts/api.ts):
 *   core_question
 *   └─ components[] (major_category rollup)
 *        └─ components[] (minor_category market)  — each carries a weekly
 *           probability `time_series` (probability is 0..100).
 *
 * We normalize probabilities to 0..1 and expose a nested tree that drives BOTH
 * the Think phase (rectangular treemap) and the Show phase (accordion +
 * sparklines), plus helpers to read aggregated probability at any timeline
 * index.
 *
 * NOTE: this is a pure transform — feed it `session.components`. Nothing here is
 * read at build time.
 */
import type { ForecastComponent } from "../scripts/api";

export const BRANCH_COLORS = ["#12AEF5", "#F5A623", "#7ED321", "#B76EF0", "#F55B7A"] as const;

export interface Pt {
  date: string;
  p: number; // 0..1
}

export interface Minor {
  id: string;
  label: string;
  series: Pt[];
  max: number; // max prob across the series (stable layout weight)
  final: number; // last prob
  source: string; // market source label (e.g. "Metaculus")
  url: string | null; // market url, if any
}

export interface Major {
  id: string;
  label: string;
  color: string;
  minors: Minor[];
}

export interface Forecast {
  core: string;
  dates: string[];
  majors: Major[];
}

function sourceLabel(c: ForecastComponent): string {
  if (!c.source) return "market";
  return c.source.charAt(0).toUpperCase() + c.source.slice(1);
}

/** Build a Minor from a market leaf node (a minor, or an atomic major). */
function toMinor(node: ForecastComponent): Minor {
  const series: Pt[] = (node.time_series ?? []).map((t) => ({
    date: t.date,
    p: t.probability / 100,
  }));
  const ps = series.map((s) => s.p);
  const max = ps.length ? Math.max(...ps) : 0.0001;
  return {
    id: node.id,
    label: node.component,
    series,
    max: max || 0.0001,
    final: series.length ? series[series.length - 1].p : 0,
    source: sourceLabel(node),
    url: node.market_url ?? null,
  };
}

/** Adapt a backend forecast tree (`session.components`) into a `Forecast`. */
export function buildForecast(components: ForecastComponent[], core: string): Forecast {
  const majors: Major[] = components.map((maj, mi) => {
    const children = maj.components ?? [];
    // A major is either a rollup (has child minors) or an atomic market node
    // (no children but its own time_series) — in that case it IS its one leaf.
    const minors: Minor[] = children.length
      ? children.map(toMinor)
      : maj.time_series?.length
        ? [toMinor(maj)]
        : [];
    return {
      id: maj.id,
      label: maj.component,
      color: BRANCH_COLORS[mi % BRANCH_COLORS.length],
      minors,
    };
  });

  // Timeline dates — series share a weekly grid; take the longest to be safe.
  const dates =
    majors
      .flatMap((m) => m.minors)
      .map((mn) => mn.series.map((s) => s.date))
      .sort((a, b) => b.length - a.length)[0] ?? [];

  return { core, dates, majors };
}

// ─── Aggregation helpers ────────────────────────────────────────────────────
// A category's probability at a timeline index is the mean of its leaves.

export function minorProbAt(m: Minor, i: number): number {
  if (!m.series.length) return 0;
  const idx = Math.min(i, m.series.length - 1);
  return m.series[idx].p;
}

export function majorProbAt(m: Major, i: number): number {
  if (!m.minors.length) return 0;
  const vals = m.minors.map((mn) => minorProbAt(mn, i));
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

export function coreProbAt(f: Forecast, i: number): number {
  const all = f.majors.flatMap((m) => m.minors);
  if (!all.length) return 0;
  return all.reduce((a, mn) => a + minorProbAt(mn, i), 0) / all.length;
}

export function lastIndex(f: Forecast): number {
  return Math.max(0, f.dates.length - 1);
}

export function pct(p: number): string {
  return `${Math.round(p * 100)}%`;
}
