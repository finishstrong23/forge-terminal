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
const REFRESH_KEY = "forge_refresh";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

/** Persist both halves of a token pair (refresh half may be absent). */
export function setSession(tokens: ApiTokenResponse): void {
  setToken(tokens.access_token);
  if (typeof window === "undefined") return;
  if (tokens.refresh_token) {
    window.localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  }
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

/**
 * Exchange the stored refresh token for a new pair; null when there is no
 * refresh token or it was rejected (caller signs the user out).
 */
export async function apiRefresh(): Promise<ApiTokenResponse | null> {
  if (typeof window === "undefined") return null;
  const refreshToken = window.localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) return null;
  try {
    const response = await fetch(apiUrl("/api/v1/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) return null;
    const tokens = (await response.json()) as ApiTokenResponse;
    setSession(tokens);
    return tokens;
  } catch {
    return null;
  }
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

/** Request a reset email. Backend always answers 200 (no account leaking). */
export async function apiForgotPassword(email: string): Promise<void> {
  const response = await fetch(apiUrl("/api/v1/auth/forgot-password"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) {
    throw new Error(await errorDetail(response, `request failed: HTTP ${response.status}`));
  }
}

/** Set a new password using an emailed reset token. */
export async function apiResetPassword(token: string, newPassword: string): Promise<void> {
  const response = await fetch(apiUrl("/api/v1/auth/reset-password"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  if (!response.ok) {
    throw new Error(await errorDetail(response, `reset failed: HTTP ${response.status}`));
  }
}

/** Confirm an emailed verification token. */
export async function apiVerifyEmail(token: string): Promise<void> {
  const response = await fetch(
    apiUrl(`/api/v1/auth/verify-email?token=${encodeURIComponent(token)}`),
  );
  if (!response.ok) {
    throw new Error(await errorDetail(response, `verification failed: HTTP ${response.status}`));
  }
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
