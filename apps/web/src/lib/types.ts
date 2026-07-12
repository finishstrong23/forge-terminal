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
  image_uri: string | null;
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

/**
 * Copy Intelligence wire types.
 * Source of truth: apps/api/schemas/copy.py (LeaderboardEntry,
 * LeaderboardResponse, WalletActivityItem, WalletDetailResponse).
 */

export interface ApiWalletStats {
  wallet_address: string;
  total_trades: number;
  buy_count: number;
  sell_count: number;
  tokens_traded: number;
  closed_positions: number;
  wins: number;
  win_rate: number | null;
  sol_in: number;
  sol_out: number;
  net_sol: number;
  active_days: number;
  sustainability_score: number;
  sustainability_grade: string | null;
  is_clustered: boolean;
  last_active: string | null; // ISO 8601 datetime
}

export interface ApiLeaderboardEntry extends ApiWalletStats {
  rank: number;
}

export interface ApiLeaderboardResponse {
  entries: ApiLeaderboardEntry[];
  count: number;
  has_more: boolean;
  window: string;
}

export interface ApiWalletActivityItem {
  token_address: string;
  symbol: string | null;
  activity_type: string;
  sol_amount: number | null;
  signature: string | null;
  timestamp: string | null; // ISO 8601 datetime
}

export interface ApiWalletDetailResponse {
  wallet: ApiWalletStats;
  window: string;
  recent_activity: ApiWalletActivityItem[];
}

export interface ApiScoreSnapshot {
  scored_at: string; // ISO 8601 datetime
  total_score: number | null;
  grade: string | null;
  persistence_score: number | null;
  win_rate_score: number | null;
  hold_pattern_score: number | null;
  insider_penalty: number | null;
}

export interface ApiScoreHistoryResponse {
  wallet_address: string;
  snapshots: ApiScoreSnapshot[];
  count: number;
}

/**
 * Auth + copy-subscription wire types.
 * Source of truth: apps/api/schemas/auth.py and apps/api/schemas/copy.py.
 */

export interface ApiUser {
  id: string;
  email: string;
  email_verified?: boolean;
  role: string;
  subscription_tier: string;
  created_at: string; // ISO 8601 datetime
}

export interface ApiTokenResponse {
  access_token: string;
  token_type: string;
  refresh_token?: string | null;
  user: ApiUser;
}

export interface ApiCopySubscription {
  id: string;
  wallet_address: string;
  mode: string;
  status: string;
  max_position_usd: number | null;
  daily_loss_cap_usd: number | null;
  slippage_tolerance: number | null;
  min_sustainability_score: number | null;
  token_blacklist: string[] | null;
  started_at: string | null;
  paused_at: string | null;
  stopped_at: string | null;
  created_at: string;
}

export interface ApiCopySubscriptionList {
  subscriptions: ApiCopySubscription[];
  count: number;
}

export interface ApiShadowTrade {
  id: string;
  token_address: string;
  trade_type: string;
  source: string;
  sol_amount: number | null;
  usd_value?: number | null;
  price_at_trade: number | null;
  status: string;
  error_message: string | null;
  copy_subscription_id: string | null;
  rug_risk_at_trade: number | null;
  momentum_at_trade: number | null;
  executed_at: string | null;
  created_at: string;
}

export interface ApiShadowTradeList {
  trades: ApiShadowTrade[];
  count: number;
}
