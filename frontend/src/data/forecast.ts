/**
 * Adapter over the real sample forecast data.
 *
 * Shape of the source JSON:
 *   core_question
 *   └─ components[] (major_category)
 *        └─ components[] (minor_category)  — each a market with a weekly
 *           probability time_series (probability is 0..100)
 *
 * We normalize probabilities to 0..1 and expose:
 *   - a nested tree for the Think phase circle-packing (core → majors → minors)
 *   - weekly `dates` for timeline playback
 *   - helpers to read aggregated probability at any timeline index
 *   - the same tree drives the Show accordion + sparklines.
 */
import raw from "./sample_forecast_data.json";

export const BRANCH_COLORS = ["#12AEF5", "#F5A623", "#7ED321"] as const;

export interface Pt {
  date: string;
  p: number; // 0..1
}

export interface Minor {
  id: string;
  label: string;
  series: Pt[];
  max: number; // max prob across the series (for a stable pack layout)
  final: number; // last prob
  source: string; // synthesized market label
}

export interface Major {
  id: string;
  label: string;
  color: string;
  minors: Minor[];
}

export interface Forecast {
  core: string;
  createdAt: string;
  dates: string[];
  majors: Major[];
}

const MARKETS = ["Polymarket", "Manifold", "Metaculus"];

function build(): Forecast {
  const majors: Major[] = raw.components.map((maj: any, mi: number) => {
    const minors: Minor[] = maj.components.map((min: any, ni: number) => {
      const series: Pt[] = min.time_series.map((t: any) => ({
        date: t.date,
        p: t.probability / 100,
      }));
      const max = Math.max(...series.map((s) => s.p));
      return {
        id: min.id,
        label: min.component,
        series,
        max,
        final: series[series.length - 1].p,
        source: MARKETS[(mi + ni) % MARKETS.length],
      };
    });
    return {
      id: maj.id,
      label: maj.component,
      color: BRANCH_COLORS[mi % BRANCH_COLORS.length],
      minors,
    };
  });

  // Timeline dates — assume all series share the same weekly grid; take the
  // longest to be safe.
  const dates =
    majors
      .flatMap((m) => m.minors)
      .map((mn) => mn.series.map((s) => s.date))
      .sort((a, b) => b.length - a.length)[0] ?? [];

  return {
    core: raw.core_question,
    createdAt: raw.created_at,
    dates,
    majors,
  };
}

export const forecast: Forecast = build();

// ─── Aggregation helpers ────────────────────────────────────────────────────
// A category's probability at a timeline index is the mean of its leaves.

export function minorProbAt(m: Minor, i: number): number {
  const idx = Math.min(i, m.series.length - 1);
  return m.series[idx].p;
}

export function majorProbAt(m: Major, i: number): number {
  const vals = m.minors.map((mn) => minorProbAt(mn, i));
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

export function coreProbAt(f: Forecast, i: number): number {
  const all = f.majors.flatMap((m) => m.minors);
  return all.reduce((a, mn) => a + minorProbAt(mn, i), 0) / all.length;
}

export const LAST_INDEX = forecast.dates.length - 1;

export function pct(p: number): string {
  return `${Math.round(p * 100)}%`;
}
