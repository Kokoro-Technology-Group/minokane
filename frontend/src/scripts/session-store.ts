/**
 * Client-side session store shared across the Ask / Think / Show phase islands.
 *
 * Astro bundles each island's <script> separately, but Vite dedupes imported
 * modules, so this module is a single shared instance within the page. The Ask
 * phase writes the live `ForecastSession`; Think and Show read the derived
 * `Forecast` tree when they come on screen (`testdraft:entered`).
 *
 * Persistence: the most recent session is a token-addressed record. On every
 * `setSession` we save `{ token, session, savedAt }` to `localStorage` and drop
 * the token in a `minokane_session` cookie, then `hydrate()` restores it on the
 * next page load so a reload resumes where the user left off. The cookie lets
 * the backend `GET /api/questions/latest` fallback kick in even if localStorage
 * was cleared. Everything degrades gracefully to in-memory-only if storage is
 * unavailable (private mode, disabled cookies, quota).
 */
import type { ForecastSession } from "./api";
import { buildForecast, type Forecast } from "../data/forecast";

const STORAGE_KEY = "minokane.session.v1";
const COOKIE_NAME = "minokane_session";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 days, in seconds

interface PersistedSession {
  token: string; // == session.id — the session token
  session: ForecastSession;
  savedAt: string; // ISO-8601
}

let session: ForecastSession | null = null;
let forecast: Forecast | null = null;

function deriveForecast(s: ForecastSession): Forecast | null {
  return s.components?.length && s.core_question
    ? buildForecast(s.components, s.core_question)
    : null;
}

export function setSession(s: ForecastSession): void {
  session = s;
  forecast = deriveForecast(s);
  persist(s);
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
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable — nothing to clear */
  }
  deleteCookie(COOKIE_NAME);
}

/** The most recent session token, from memory or the surviving cookie. */
export function getPersistedToken(): string | null {
  return session?.id ?? readCookie(COOKIE_NAME);
}

// ─── Persistence internals ───────────────────────────────────────────────────

function persist(s: ForecastSession): void {
  const payload: PersistedSession = {
    token: s.id,
    session: s,
    savedAt: new Date().toISOString(),
  };
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    /* quota / disabled — fall back to in-memory + cookie token only */
  }
  writeCookie(COOKIE_NAME, s.id);
}

/** Restore the most recent session from localStorage into the in-memory store. */
function hydrate(): void {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return; // storage blocked — stay in-memory
  }
  if (!raw) return;
  try {
    const parsed = JSON.parse(raw) as PersistedSession;
    const s = parsed?.session;
    if (!s?.id) return;
    // Derive first so a malformed tree throws before we half-populate state.
    const f = deriveForecast(s);
    session = s;
    forecast = f;
  } catch {
    // Corrupt or incompatible payload — drop it so we don't wedge every load.
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }
}

// ─── Cookie helpers ──────────────────────────────────────────────────────────

function writeCookie(name: string, value: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`;
}

function deleteCookie(name: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; path=/; max-age=0; SameSite=Lax`;
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

// Island scripts run in the browser only, but guard for safety.
if (typeof window !== "undefined") {
  hydrate();
}
