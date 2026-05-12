/**
 * Types mirroring the backend API surface.
 *
 * Source of truth: apps/api/schemas/discovery.py (TokenFeedItem, FeedResponse).
 * These are the "wire" types consumed at the network boundary; UI components
 * use the normalized TokenSignal type (apps/web/src/components/discovery/signal-table.tsx)
 * which has strict non-nullable fields after passing through normalizeToken().
 */

export interface ApiTokenFeedItem {
  id: string;
  token_address: string | null;
  symbol: string | null;
  name: string | null;
  scan_timestamp: string; // ISO 8601 datetime
  age_minutes: number | null;
  age_seconds: number | null;
  price_usd: number | null;
  market_cap: number | null;
  volume_1h: number | null;
  liquidity_usd: number | null;
  rug_risk_score: number; // backend filters NULLs out of the feed
  momentum_score: number; // backend filters NULLs out of the feed
  confidence_score: number | null;
  holder_count: number | null;
  buy_ratio_1h: number | null;
  is_honeypot: boolean;
  flags: string[];
  source_dex: string;
  explainability?: unknown;
}

export interface ApiFeedResponse {
  tokens: ApiTokenFeedItem[];
  count: number;
  has_more: boolean;
}

/** Envelope shape for messages over the /ws/discovery channel. */
export interface WsTokenEnvelope {
  type: "token";
  data: ApiTokenFeedItem;
}
