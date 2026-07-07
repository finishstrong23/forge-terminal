/**
 * Copy-subscription + shadow-ledger data layer (authenticated endpoints).
 *
 * All calls attach the stored JWT via authHeaders(); callers should treat
 * a thrown "HTTP 401" as "signed out". FastAPI error bodies ({"detail"})
 * are surfaced as Error messages so the UI can show e.g. "Already
 * subscribed to this wallet" verbatim.
 */
import { apiUrl } from "./api";
import { authHeaders } from "./auth";
import type {
  ApiCopySubscription,
  ApiCopySubscriptionList,
  ApiShadowTradeList,
} from "./types";

export type SubscriptionAction = "pause" | "resume" | "stop";

export interface CreateSubscriptionInput {
  wallet_address: string;
  max_position_usd?: number;
  min_sustainability_score?: number;
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

export async function createSubscription(
  input: CreateSubscriptionInput,
): Promise<ApiCopySubscription> {
  const response = await fetch(apiUrl("/api/v1/copy/subscriptions"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(input),
  });
  return parseOrThrow<ApiCopySubscription>(response, "follow");
}

export async function listSubscriptions(): Promise<ApiCopySubscriptionList> {
  const response = await fetch(apiUrl("/api/v1/copy/subscriptions"), {
    headers: authHeaders(),
    cache: "no-store",
  });
  return parseOrThrow<ApiCopySubscriptionList>(response, "subscriptions fetch");
}

export async function patchSubscription(
  id: string,
  action: SubscriptionAction,
): Promise<ApiCopySubscription> {
  const response = await fetch(
    apiUrl(`/api/v1/copy/subscriptions/${encodeURIComponent(id)}`),
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ action }),
    },
  );
  return parseOrThrow<ApiCopySubscription>(response, action);
}

export async function listShadowTrades(limit = 100): Promise<ApiShadowTradeList> {
  const response = await fetch(apiUrl(`/api/v1/copy/trades?limit=${limit}`), {
    headers: authHeaders(),
    cache: "no-store",
  });
  return parseOrThrow<ApiShadowTradeList>(response, "trades fetch");
}
