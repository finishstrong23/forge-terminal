/**
 * Execution data layer (M3 — non-custodial swaps).
 * Source of truth: apps/api/routes/execute.py.
 */
import { apiUrl } from "./api";
import { authHeaders } from "./auth";

export type SwapSide = "buy" | "sell";

export interface SwapQuote {
  input_mint: string;
  output_mint: string;
  side: SwapSide;
  in_amount: string | null;
  out_amount: string | null;
  other_amount_threshold: string | null;
  price_impact_pct: string | null;
  slippage_bps: number;
  route_labels: (string | null)[];
  quote_response?: Record<string, unknown>;
}

async function parseOrThrow<T>(response: Response, what: string): Promise<T> {
  if (!response.ok) {
    let detail = `${what} failed: HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

/** Mint decimals from the backend lookup; null = unknown (UI falls back
 * to the 6-decimals assumption with its caveat). */
export async function fetchTokenDecimals(mint: string): Promise<number | null> {
  try {
    const response = await fetch(
      apiUrl(`/api/v1/execute/token-meta?mint=${encodeURIComponent(mint)}`),
      { cache: "no-store" },
    );
    if (!response.ok) return null;
    const body = (await response.json()) as { decimals: number | null };
    return typeof body.decimals === "number" ? body.decimals : null;
  } catch {
    return null;
  }
}

export async function fetchSolPrice(): Promise<number> {
  const response = await fetch(apiUrl("/api/v1/execute/price"), { cache: "no-store" });
  const body = await parseOrThrow<{ sol_usd: number }>(response, "price");
  return body.sol_usd;
}

export async function fetchQuote(input: {
  tokenMint: string;
  side: SwapSide;
  amount: number; // SOL for buys, tokens for sells
  slippageBps: number;
  tokenDecimals?: number;
}): Promise<SwapQuote> {
  const params = new URLSearchParams({
    token_mint: input.tokenMint,
    side: input.side,
    slippage_bps: String(input.slippageBps),
    include_raw: "true",
  });
  if (input.side === "buy") {
    params.set("amount_sol", String(input.amount));
  } else {
    params.set("amount_tokens", String(input.amount));
    params.set("token_decimals", String(input.tokenDecimals ?? 6));
  }
  const response = await fetch(apiUrl(`/api/v1/execute/quote?${params}`), {
    cache: "no-store",
  });
  return parseOrThrow<SwapQuote>(response, "quote");
}

export async function buildSwapTransaction(
  quoteResponse: Record<string, unknown>,
  userPublicKey: string,
): Promise<{ swap_transaction: string; last_valid_block_height: number | null }> {
  const response = await fetch(apiUrl("/api/v1/execute/swap-transaction"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quote_response: quoteResponse,
      user_public_key: userPublicKey,
    }),
  });
  return parseOrThrow(response, "swap build");
}

export async function recordManualTrade(input: {
  token_address: string;
  trade_type: "buy" | "sell";
  sol_amount: number;
  /** Quoted token quantity — received on buys, spent on sells. Feeds
   * position quantity/PnL math; omit when unknown. */
  token_amount?: number;
  signature: string;
  slippage_bps?: number;
}): Promise<void> {
  const response = await fetch(apiUrl("/api/v1/execute/trades"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(input),
  });
  // 409 = already recorded (e.g. double-click) — not an error worth surfacing.
  if (!response.ok && response.status !== 409) {
    throw new Error(`trade recording failed: HTTP ${response.status}`);
  }
}

export interface ApiPosition {
  token_address: string;
  trade_count: number;
  last_trade_at: string | null;
  bought_sol: number;
  sold_sol: number;
  net_tokens: number | null;
  cost_basis_sol: number | null;
  realized_pnl_sol: number | null;
  token_price_usd: number | null;
  value_sol: number | null;
  unrealized_pnl_sol: number | null;
}

export interface PositionsResponse {
  positions: ApiPosition[];
  count: number;
  sol_usd: number | null;
}

export async function fetchPositions(): Promise<PositionsResponse> {
  const response = await fetch(apiUrl("/api/v1/execute/positions"), {
    cache: "no-store",
    headers: authHeaders(),
  });
  return parseOrThrow<PositionsResponse>(response, "positions");
}

/** Decode Jupiter's base64 transaction without relying on Buffer polyfills. */
export function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}
