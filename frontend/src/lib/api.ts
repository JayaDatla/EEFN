// UPGRADE_PLAN.md H.5: single source of truth for the backend base URL.
// Replaces 17 hardcoded http://127.0.0.1:8000 call sites across 12 files so the
// app can actually be deployed against a non-localhost backend.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(apiUrl(path), init);
}
