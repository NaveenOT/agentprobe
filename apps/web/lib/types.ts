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
  target: { type: "api" | "browser"; url: string };
  attempts: Attempt[];
  report: Report | null;
  error: string | null;
  created_at: string;
}

export interface SystemStatus {
  groq_configured: boolean;
  target_provider: string;
  agent_model: string;
  target_model: string;
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
