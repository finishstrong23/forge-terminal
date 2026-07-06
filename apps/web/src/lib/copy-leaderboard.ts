/**
 * Copy Intelligence data layer.
 *
 * Responsibilities:
 * - REST: fetch the wallet leaderboard from /api/v1/copy/leaderboard and
 *   wallet detail from /api/v1/copy/wallets/{address}.
 * - Normalize: map nullable backend fields into the strict WalletRow shape
 *   the UI consumes. Drops malformed rows with a console.warn.
 *
 * Polling orchestration lives in hooks/useLeaderboard.ts. There is no WS
 * channel for the leaderboard — rankings move on aggregation cadence, not
 * per-event, so REST polling at LEADERBOARD_POLL_MS is sufficient.
 */
import { apiUrl } from "./api";
import type {
  ApiLeaderboardEntry,
  ApiLeaderboardResponse,
  ApiWalletDetailResponse,
} from "./types";

/** Leaderboard REST polling cadence. Backend caches for 60s; match it. */
export const LEADERBOARD_POLL_MS = 60_000;

export type LeaderboardWindow = "24h" | "7d" | "30d";

export const LEADERBOARD_WINDOWS: LeaderboardWindow[] = ["24h", "7d", "30d"];

/** Strict UI row shape — nulls coerced except win_rate/last_active, where
 * "no data yet" is meaningful and rendered as an em dash. */
export interface WalletRow {
  rank: number;
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
  sustainability_grade: string;
  is_clustered: boolean;
  last_active: string | null;
}

export function normalizeWalletRow(
  e: ApiLeaderboardEntry | null | undefined,
): WalletRow | null {
  if (!e || typeof e !== "object") {
    console.warn("[copy-leaderboard] dropping malformed entry (not an object):", e);
    return null;
  }
  if (typeof e.wallet_address !== "string" || typeof e.rank !== "number") {
    console.warn("[copy-leaderboard] dropping malformed entry (missing required fields):", e);
    return null;
  }
  return {
    rank: e.rank,
    wallet_address: e.wallet_address,
    total_trades: e.total_trades ?? 0,
    buy_count: e.buy_count ?? 0,
    sell_count: e.sell_count ?? 0,
    tokens_traded: e.tokens_traded ?? 0,
    closed_positions: e.closed_positions ?? 0,
    wins: e.wins ?? 0,
    win_rate: typeof e.win_rate === "number" ? e.win_rate : null,
    sol_in: e.sol_in ?? 0,
    sol_out: e.sol_out ?? 0,
    net_sol: e.net_sol ?? 0,
    active_days: e.active_days ?? 0,
    sustainability_score: e.sustainability_score ?? 0,
    sustainability_grade: e.sustainability_grade ?? "D",
    is_clustered: Boolean(e.is_clustered),
    last_active: e.last_active ?? null,
  };
}

export interface FetchLeaderboardOptions {
  window: LeaderboardWindow;
  limit?: number;
  excludeClustered?: boolean;
}

/** Fetch the leaderboard. Throws on non-2xx HTTP or network errors. */
export async function fetchLeaderboard(
  opts: FetchLeaderboardOptions,
): Promise<WalletRow[]> {
  const params = new URLSearchParams({
    window: opts.window,
    limit: String(opts.limit ?? 50),
  });
  if (opts.excludeClustered) params.set("exclude_clustered", "true");
  const url = apiUrl(`/api/v1/copy/leaderboard?${params.toString()}`);
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`leaderboard fetch failed: HTTP ${response.status}`);
  }
  const data = (await response.json()) as ApiLeaderboardResponse;
  const rows: WalletRow[] = [];
  for (const e of data.entries || []) {
    const norm = normalizeWalletRow(e);
    if (norm) rows.push(norm);
  }
  return rows;
}

/** Fetch one wallet's stats + recent history. Throws on non-2xx/network errors. */
export async function fetchWalletDetail(
  walletAddress: string,
  window: LeaderboardWindow,
): Promise<ApiWalletDetailResponse> {
  const url = apiUrl(
    `/api/v1/copy/wallets/${encodeURIComponent(walletAddress)}?window=${window}`,
  );
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`wallet detail fetch failed: HTTP ${response.status}`);
  }
  return (await response.json()) as ApiWalletDetailResponse;
}

/** "3m ago" / "2.1h ago" / "1.2d ago" — or an em dash for null. */
export function formatRelativeTime(iso: string | null): string {
  if (!iso) return "—";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "—";
  const minutes = Math.max(0, (Date.now() - then) / 60_000);
  if (minutes < 60) return `${Math.round(minutes)}m ago`;
  if (minutes < 1440) return `${(minutes / 60).toFixed(1)}h ago`;
  return `${(minutes / 1440).toFixed(1)}d ago`;
}

/** Signed SOL amount, e.g. "+2.35 SOL" / "-0.50 SOL". */
export function formatSol(n: number): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)} SOL`;
}
