const API_BASE = "/api";
const API_KEY = import.meta.env.PUBLIC_API_KEY ?? "minokane-dev-key";

const headers = {
  "Content-Type": "application/json",
  "X-API-Key": API_KEY,
};

export interface QuestionInput {
  raw_question: string;
  deadline?: string | null;
  outcome_description?: string | null;
}

export type OutcomeType = "binary" | "categorical" | "date" | "numeric";

export interface OperationalizedQuestion {
  id: string;
  text: string;
  resolution_criteria: string;
  resolution_source: string;
  deadline: string;
  outcome_type: OutcomeType;
  outcome_options: string[];
  outcome_unit: string | null;
  void_conditions: string;
}

export interface ModularSubQuestion {
  id: string;
  parent_id: string;
  text: string;
  explanation: string;
  domain_tag: string;
  confidence_of_importance: "high" | "medium" | "low";
  llm_baseline_likelihood: "high" | "medium" | "low";
}

export type Confidence = "high" | "medium" | "low";
export type MarketSource = "metaculus" | "manifold" | "estimate";
export type MarketStatus = "open" | "resolved" | "closed" | "estimate";

export interface TimeSeriesPoint {
  date: string; // "YYYY-MM-DD"
  probability: number; // P(Yes) as a percent, 0..100
}

/**
 * A node in the Think forecast tree. A node is a market leaf iff it has no
 * `components` (then it carries source/market_id/market_url/status/
 * outcome_options/time_series); otherwise it is a rollup grouping node.
 */
export interface ForecastComponent {
  id: string;
  type: "major_category" | "minor_category";
  component: string; // for market nodes: the market's canonical question
  domain_tag: string;
  confidence_of_importance: Confidence;
  llm_baseline_likelihood: Confidence | null;

  // Market fields — present only on market leaf nodes.
  source?: MarketSource | null;
  market_id?: string | null;
  market_url?: string | null;
  status?: MarketStatus | null;
  outcome_options?: string[] | null;
  time_series?: TimeSeriesPoint[] | null;

  // Rollup field — present only on grouping nodes.
  components?: ForecastComponent[] | null;
}

export interface Coverage {
  sub_questions_proposed: number;
  markets_found: number;
  branches_dropped: number;
}

export interface ForecastSession {
  id: string;
  thread_id: string;
  created_at: string;
  original_question: QuestionInput;
  operationalized_options: OperationalizedQuestion[];
  selected_operationalization_id: string | null;
  core_question: string | null;
  user_feedback: string | null;
  components: ForecastComponent[];
  coverage: Coverage | null;
  modular_sub_questions: ModularSubQuestion[];
  final_summary: string | null;
  status: "intake" | "operationalizing" | "selecting" | "modularizing" | "complete";
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers, ...(options?.headers ?? {}) },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(detail?.detail ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function submitQuestion(input: QuestionInput): Promise<ForecastSession> {
  return request<ForecastSession>("/questions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getSession(id: string): Promise<ForecastSession> {
  return request<ForecastSession>(`/questions/${id}`);
}

/** The most recently saved session on the backend. Rejects (404) if none. */
export function getLatestSession(): Promise<ForecastSession> {
  return request<ForecastSession>("/questions/latest");
}

export function selectOperationalization(
  sessionId: string,
  operationalized_question: OperationalizedQuestion,
  user_feedback?: string | null,
): Promise<ForecastSession> {
  return request<ForecastSession>(`/questions/${sessionId}/select`, {
    method: "PUT",
    body: JSON.stringify({ operationalized_question, user_feedback: user_feedback ?? null }),
  });
}

export function getResult(id: string): Promise<ForecastSession> {
  return request<ForecastSession>(`/questions/${id}/result`);
}
