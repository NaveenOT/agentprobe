import type { ScanRun, SystemStatus } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "content-type": "application/json", ...options?.headers },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listRuns: () => request<ScanRun[]>("/runs"),
  getStatus: () => request<SystemStatus>("/system/status"),
  getRun: (id: string) => request<ScanRun>(`/runs/${id}`),
  createRun: (payload: unknown) =>
    request<ScanRun>("/runs", { method: "POST", body: JSON.stringify(payload) }),
};
