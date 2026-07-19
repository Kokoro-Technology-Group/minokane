/**
 * Client-side session store shared across the Ask / Think / Show phase islands.
 *
 * Astro bundles each island's <script> separately, but Vite dedupes imported
 * modules, so this module is a single shared instance within the page. The Ask
 * phase writes the live `ForecastSession`; Think and Show read the derived
 * `Forecast` tree when they come on screen (`testdraft:entered`).
 */
import type { ForecastSession } from "./api";
import { buildForecast, type Forecast } from "../data/forecast";

let session: ForecastSession | null = null;
let forecast: Forecast | null = null;

export function setSession(s: ForecastSession): void {
  session = s;
  forecast =
    s.components?.length && s.core_question
      ? buildForecast(s.components, s.core_question)
      : null;
}

export function getSession(): ForecastSession | null {
  return session;
}

export function getForecast(): Forecast | null {
  return forecast;
}

export function clearSession(): void {
  session = null;
  forecast = null;
}
