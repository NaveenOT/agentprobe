export const categories = [
  "instruction_based",
  "task_deflection",
  "repetition",
  "context_switching",
  "variable_code_based",
  "formatting",
  "obfuscation",
  "cognitive_role_based",
  "indirect",
] as const;

export type RunStatus =
  | "queued"
  | "profiling"
  | "running"
  | "reporting"
  | "completed"
  | "failed";

export interface Evaluation {
  success: boolean;
  severity: number;
  confidence: number;
  rationale: string;
  evidence: string;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  calls: number;
}

export interface TargetProfile {
  domain: string;
  purpose: string;
  intended_audience: string;
  capabilities: string[];
  interaction_style: string;
  observed_constraints: string[];
  context_summary: string;
  sample_response: string;
}

export interface Attempt {
  id: string;
  template_id: string;
  category: string;
  technique: string;
  source: string;
  prompt: string;
  response: string;
  duration_ms: number;
  evaluation: Evaluation;
  token_usage: Record<string, TokenUsage>;
}

export interface Report {
  total_attacks: number;
  successful_attacks: number;
  attack_success_rate: number;
  average_severity: number;
  category_vulnerability: Record<string, number>;
  duration_ms: number;
  recommendations: string[];
  token_usage: Record<string, TokenUsage>;
  total_tokens: number;
}

export interface ScanRun {
  id: string;
  name: string;
  status: RunStatus;
  requested_outcome: string;
  effective_objective: string;
  objective_mode: "attack" | "refusal_control";
  target: { type: "api" | "browser"; url: string };
  profile: TargetProfile | null;
  attempts: Attempt[];
  report: Report | null;
  error: string | null;
  created_at: string;
  metadata: {
    live_exchange?: {
      stage: string;
      category: string;
      input: string;
      output: string;
    };
    profiling_exchange?: {
      target_input: string;
      target_output: string;
      target_duration_ms: number;
      agent_input: string;
      agent_output: string;
      used_fallback: boolean;
    };
  };
}

export interface SystemStatus {
  groq_configured: boolean;
  target_provider: string;
  agent_model: string;
  target_model: string;
  ai_dom_detection: boolean;
  template_backend: string;
  template_count: number;
  dataset: {
    enabled: boolean;
    path: string;
    exists: boolean;
    loaded_templates: number;
    total_rows: number;
    successful_rows: number;
    error: string | null;
  };
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "content-type": "application/json", ...options?.headers },
  });
  if (!response.ok) {
    const body = await response.text();
    try {
      const parsed = JSON.parse(body) as { detail?: string };
      throw new Error(parsed.detail || body);
    } catch (error) {
      if (error instanceof SyntaxError) throw new Error(body);
      throw error;
    }
  }
  return response.json() as Promise<T>;
}

export const api = {
  listRuns: () => request<ScanRun[]>("/runs"),
  getStatus: () => request<SystemStatus>("/system/status"),
  createRun: (payload: unknown) =>
    request<ScanRun>("/runs", { method: "POST", body: JSON.stringify(payload) }),
  openBrowserSession: (url: string) =>
    request<{ status: string; message: string }>("/browser/session", {
      method: "POST",
      body: JSON.stringify({ url, authorization_confirmed: true }),
    }),
};
