/**
 * Discovery feed data layer.
 *
 * Responsibilities:
 * - REST: fetch the initial feed from /api/v1/discovery/feed.
 * - Normalize: map nullable backend fields into the strict TokenSignal shape
 *   the UI consumes. Drops malformed tokens with a console.warn.
 * - Merge: dedupe incoming WS tokens against the current list, prepend new ones,
 *   cap the list at MAX_TOKENS_IN_MEMORY (prune-on-add).
 * - WS URL: build the discovery socket URL from NEXT_PUBLIC_API_URL.
 *
 * The state-machine orchestration (LIVE/POLLING/OFFLINE transitions, reconnect
 * backoff, REST failure counting) lives in hooks/useDiscoveryFeed.ts. This
 * module is pure-ish — easier to unit test if we add Vitest later.
 */
import type { TokenSignal } from "@/components/discovery/signal-table";
import { apiUrl, wsUrl } from "./api";
import { authHeaders, getToken } from "./auth";
import type { ApiFeedResponse, ApiTokenFeedItem } from "./types";

/** Maximum number of tokens held in memory client-side. Prune oldest on add. */
export const MAX_TOKENS_IN_MEMORY = 100;

/** Initial REST polling cadence when WS is down. Doubles on consecutive failures. */
export const POLL_INTERVAL_MS = 5_000;

/** Max polling cadence after exponential backoff on consecutive REST failures. */
export const POLL_BACKOFF_CAP_MS = 60_000;

/** Initial delay before retrying a dropped WS connection. */
export const WS_RECONNECT_BASE_MS = 1_000;

/** Max WS reconnect delay after exponential backoff. */
export const WS_RECONNECT_CAP_MS = 30_000;

/** Number of consecutive REST polling failures before flipping to OFFLINE. */
export const REST_FAILURES_BEFORE_OFFLINE = 3;

export type FeedStatus = "loading" | "live" | "polling" | "offline";

/**
 * Map a wire-format ApiTokenFeedItem (nullable fields) to the strict frontend
 * TokenSignal shape. Coerces nulls to neutral defaults so UI cell renderers
 * don't have to handle nulls — at the cost of conflating "real zero" with
 * "missing data". Task 5 may revisit this distinction.
 *
 * Returns null and logs a warning if required fields are missing/malformed.
 */
export function normalizeToken(t: ApiTokenFeedItem | null | undefined): TokenSignal | null {
  if (!t || typeof t !== "object") {
    console.warn("[discovery-feed] dropping malformed token (not an object):", t);
    return null;
  }
  if (
    typeof t.id !== "string" ||
    typeof t.scan_timestamp !== "string" ||
    typeof t.momentum_score !== "number" ||
    typeof t.rug_risk_score !== "number"
  ) {
    console.warn(
      "[discovery-feed] dropping malformed token (missing required fields):",
      t,
    );
    return null;
  }
  return {
    id: t.id,
    token_address: t.token_address ?? "",
    symbol: t.symbol ?? "UNKNOWN",
    name: t.name ?? "Unknown",
    price_usd: t.price_usd ?? 0,
    market_cap: t.market_cap ?? 0,
    volume_1h: t.volume_1h ?? 0,
    liquidity_usd: t.liquidity_usd ?? 0,
    rug_risk_score: t.rug_risk_score,
    momentum_score: t.momentum_score,
    confidence_score: t.confidence_score ?? 0,
    age_minutes: t.age_minutes ?? 0,
    holder_count: t.holder_count ?? 0,
    buy_ratio_1h: t.buy_ratio_1h ?? 0,
    is_honeypot: Boolean(t.is_honeypot),
    flags: Array.isArray(t.flags) ? t.flags : [],
  };
}

/**
 * Fetch the initial feed via REST. Throws on non-2xx HTTP or network errors.
 * Caller is responsible for catching and translating into UI status.
 */
export async function fetchInitialFeed(limit = 50): Promise<TokenSignal[]> {
  const url = apiUrl(`/api/v1/discovery/feed?limit=${limit}`);
  // Tier matters: paid accounts get realtime, free/anonymous a delayed feed.
  const response = await fetch(url, { cache: "no-store", headers: authHeaders() });
  if (!response.ok) {
    throw new Error(`feed fetch failed: HTTP ${response.status}`);
  }
  const data = (await response.json()) as ApiFeedResponse;
  const tokens: TokenSignal[] = [];
  for (const t of data.tokens || []) {
    const norm = normalizeToken(t);
    if (norm) tokens.push(norm);
  }
  return tokens.slice(0, MAX_TOKENS_IN_MEMORY);
}

/**
 * Merge a single incoming token (from WS push) into the current list.
 * - If id already exists: replace in place, preserve position.
 * - Otherwise: prepend (newest first) and cap at MAX_TOKENS_IN_MEMORY.
 *
 * Returns a NEW array so React state-comparison sees the change.
 */
export function mergeIncomingToken(
  current: TokenSignal[],
  incoming: TokenSignal,
): TokenSignal[] {
  const existingIdx = current.findIndex((x) => x.id === incoming.id);
  if (existingIdx >= 0) {
    const next = current.slice();
    next[existingIdx] = incoming;
    return next;
  }
  const prepended = [incoming, ...current];
  if (prepended.length > MAX_TOKENS_IN_MEMORY) {
    prepended.length = MAX_TOKENS_IN_MEMORY;
  }
  return prepended;
}

/** Full WS URL for the discovery channel (JWT as query param — browsers
 * can't set an Authorization header on a WebSocket handshake). */
export function discoveryWsUrl(): string {
  const token = getToken();
  return wsUrl(
    token ? `/ws/discovery?token=${encodeURIComponent(token)}` : "/ws/discovery",
  );
}
