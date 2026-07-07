/**
 * Billing data layer (authenticated endpoints).
 * Source of truth: apps/api/routes/billing.py.
 */
import { apiUrl } from "./api";
import { authHeaders } from "./auth";

export interface BillingStatus {
  tier: string;
  billing_configured: boolean;
  has_stripe_customer: boolean;
  subscription: {
    status: string;
    billing_cycle: string;
    current_period_end: string | null;
    cancel_at_period_end: boolean;
  } | null;
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

export async function fetchBillingStatus(): Promise<BillingStatus> {
  const response = await fetch(apiUrl("/api/v1/billing/status"), {
    headers: authHeaders(),
    cache: "no-store",
  });
  return parseOrThrow<BillingStatus>(response, "billing status");
}

/** Returns the Stripe checkout URL to redirect to. */
export async function startCheckout(
  billingCycle: "monthly" | "yearly",
): Promise<string> {
  const response = await fetch(apiUrl("/api/v1/billing/checkout"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ billing_cycle: billingCycle }),
  });
  const body = await parseOrThrow<{ url: string }>(response, "checkout");
  return body.url;
}

/** Returns the Stripe customer-portal URL to redirect to. */
export async function openPortal(): Promise<string> {
  const response = await fetch(apiUrl("/api/v1/billing/portal"), {
    method: "POST",
    headers: authHeaders(),
  });
  const body = await parseOrThrow<{ url: string }>(response, "billing portal");
  return body.url;
}
