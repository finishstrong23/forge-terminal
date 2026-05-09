export interface TokenSignal {
  id: string;
  symbol: string;
  name: string;
  token_address: string;
  price_usd: number;
  market_cap: number;
  volume_1h: number;
  liquidity_usd: number;
  rug_risk_score: number;
  momentum_score: number;
  confidence_score: number;
  age_minutes: number;
  holder_count: number;
  buy_ratio_1h: number;
  is_honeypot: boolean;
  flags: string[];
  explainability?: ExplainabilityData;
}

export interface ExplainabilityData {
  promising: string[];
  risks: string[];
  upgrades: string[];
}

export interface User {
  id: string;
  email: string;
  role: "user" | "admin" | "owner";
  subscription_tier: SubscriptionTier;
  is_trial: boolean;
  trial_ends_at: string | null;
}

export type SubscriptionTier = "free" | "trader" | "pro" | "desk";

export interface Subscription {
  id: string;
  user_id: string;
  tier: SubscriptionTier;
  billing_cycle: "monthly" | "annual";
  status: "active" | "trialing" | "canceled" | "past_due" | "incomplete";
  current_period_start: string;
  current_period_end: string;
}

export interface WalletLeaderboardEntry {
  address: string;
  label: string | null;
  sustainability_score: number;
  sustainability_grade: string;
  pnl_30d: number;
  win_rate_30d: number;
  avg_hold_minutes: number;
  trade_count_30d: number;
}

export interface CopySubscription {
  id: string;
  wallet_address: string;
  mode: "shadow" | "copy";
  status: "active" | "paused" | "stopped";
  max_position_usd: number;
  daily_loss_cap_usd: number;
}

export interface ExecutedTrade {
  id: string;
  token_address: string;
  trade_type: "buy" | "sell";
  source: "manual" | "copy" | "auto_snipe";
  sol_amount: number;
  usd_value: number;
  status: "pending" | "submitted" | "confirmed" | "failed";
  signature: string | null;
  executed_at: string | null;
}

export interface Alert {
  id: string;
  token_address: string;
  alert_type: string;
  delivery_method: string;
  delivery_status: string;
  momentum_score: number;
  rug_risk_score: number;
  message: string;
  created_at: string;
}

export interface HealthCheck {
  status: "healthy" | "degraded";
  database: "connected" | "disconnected";
  version: string;
}

export interface SignalsResponse {
  signals: TokenSignal[];
  total: number;
  page: number;
  per_page: number;
}
