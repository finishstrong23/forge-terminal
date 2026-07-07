/**
 * Auth data layer: token storage + auth API calls.
 *
 * The JWT lives in localStorage under TOKEN_KEY. All helpers are
 * SSR-safe (no-ops server-side); session state orchestration lives in
 * hooks/useAuth.tsx.
 */
import { apiUrl } from "./api";
import type { ApiTokenResponse, ApiUser } from "./types";

const TOKEN_KEY = "forge_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

/** Authorization header for authenticated fetches ({} when signed out). */
export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Extract FastAPI's {"detail": ...} error message, with a fallback. */
async function errorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    /* non-JSON error body */
  }
  return fallback;
}

async function authRequest(
  path: string,
  email: string,
  password: string,
): Promise<ApiTokenResponse> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new Error(await errorDetail(response, `auth failed: HTTP ${response.status}`));
  }
  return (await response.json()) as ApiTokenResponse;
}

export function apiLogin(email: string, password: string): Promise<ApiTokenResponse> {
  return authRequest("/api/v1/auth/login", email, password);
}

export function apiRegister(email: string, password: string): Promise<ApiTokenResponse> {
  return authRequest("/api/v1/auth/register", email, password);
}

/** Resolve the stored token to the current user. Throws on 401/network. */
export async function fetchMe(): Promise<ApiUser> {
  const response = await fetch(apiUrl("/api/v1/auth/me"), {
    headers: authHeaders(),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`me fetch failed: HTTP ${response.status}`);
  }
  return (await response.json()) as ApiUser;
}
