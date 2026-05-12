/**
 * Backend URL helpers.
 *
 * Reads NEXT_PUBLIC_API_URL (set in Vercel for prod, .env.local for dev).
 * Falls back to localhost:8000 for unset envs so `next dev` doesn't crash —
 * fetch will simply fail at request time and the discovery feed will show
 * its OFFLINE state, which is the correct UX signal.
 *
 * WS URL is derived from the API URL by swapping the http(s) scheme.
 * Assumes NEXT_PUBLIC_API_URL is protocol+host with no path prefix
 * (e.g. https://forge-terminal-production.up.railway.app, NOT
 *  https://example.com/api). If the deploy ever moves behind a path prefix,
 * revisit this and split into two env vars.
 */

const API_URL_RAW = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Strip trailing slash so apiUrl("/path") doesn't produce a double-slash.
const API_URL = API_URL_RAW.replace(/\/+$/, "");

export function apiUrl(path: string): string {
  return `${API_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export function wsUrl(path: string): string {
  const wsBase = API_URL.replace(/^http/, "ws");
  return `${wsBase}${path.startsWith("/") ? path : `/${path}`}`;
}
