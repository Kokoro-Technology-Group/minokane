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

export interface ForecastSession {
  id: string;
  thread_id: string;
  created_at: string;
  original_question: QuestionInput;
  operationalized_options: OperationalizedQuestion[];
  selected_operationalization_id: string | null;
  user_feedback: string | null;
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
