"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Check, Crown, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { startCheckout } from "@/lib/billing";

/** Launch price. The amount actually charged comes from the Stripe Price
 * configured on the backend — keep this display in sync with it. */
const PRO_PRICE_USD = 49;

const FREE_FEATURES = [
  "Token discovery feed (15-minute delay)",
  "Momentum + rug-risk scores on every token",
  "Wallet leaderboard with sustainability grades",
  "Follow up to 3 wallets in shadow mode",
  "Non-custodial swaps via Jupiter",
  "Positions & PnL tracking",
];

const PRO_FEATURES = [
  "Realtime discovery feed — no 15-minute delay",
  "Live WebSocket streaming as tokens are scored",
  "Follow up to 50 wallets in shadow mode",
  "Everything in Free, faster and bigger",
];

export default function PricingPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isPro = user?.subscription_tier === "pro";

  const upgrade = async () => {
    if (!user) {
      router.push("/login");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      window.location.href = await startCheckout("monthly");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 py-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-foreground">Pricing</h1>
        <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">
          In memecoins, fifteen minutes is the whole trade. Free shows you the
          market on a delay — Pro shows it to you live.
        </p>
      </div>

      {error && (
        <div className="rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-center text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <section className="flex flex-col rounded-lg border border-border bg-surface p-6">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold uppercase tracking-wide text-foreground">
              Free
            </h2>
          </div>
          <p className="mt-3">
            <span className="font-mono-numbers text-3xl font-bold text-foreground">$0</span>
            <span className="text-xs text-muted-foreground"> / month</span>
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            The full terminal, on a delay. Try before you trust.
          </p>
          <ul className="mt-4 flex-1 space-y-2">
            {FREE_FEATURES.map((f) => (
              <li key={f} className="flex items-start gap-2 text-xs text-muted-foreground">
                <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green-400" />
                {f}
              </li>
            ))}
          </ul>
          {!user && !loading && (
            <Button variant="outline" className="mt-6 w-full" asChild>
              <Link href="/login">Start free</Link>
            </Button>
          )}
        </section>

        <section className="relative flex flex-col rounded-lg border border-accent/50 bg-surface p-6">
          <Badge className="absolute -top-2.5 right-4 text-[10px] uppercase">
            For traders
          </Badge>
          <div className="flex items-center gap-2">
            <Crown className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold uppercase tracking-wide text-foreground">
              Pro
            </h2>
          </div>
          <p className="mt-3">
            <span className="font-mono-numbers text-3xl font-bold text-foreground">
              ${PRO_PRICE_USD}
            </span>
            <span className="text-xs text-muted-foreground"> / month</span>
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Realtime signals. One avoided rug pays for the year.
          </p>
          <ul className="mt-4 flex-1 space-y-2">
            {PRO_FEATURES.map((f) => (
              <li key={f} className="flex items-start gap-2 text-xs text-muted-foreground">
                <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
                {f}
              </li>
            ))}
          </ul>
          {isPro ? (
            <Button variant="outline" className="mt-6 w-full" asChild>
              <Link href="/settings">You&apos;re Pro — manage billing</Link>
            </Button>
          ) : (
            <Button className="mt-6 w-full" disabled={busy || loading} onClick={upgrade}>
              {busy ? "Redirecting to checkout…" : user ? "Upgrade to Pro" : "Sign in to upgrade"}
            </Button>
          )}
        </section>
      </div>

      <p className="text-center text-[10px] text-muted-foreground">
        Cancel anytime from Settings. Payments via Stripe; Forge never sees
        your card. Trading memecoins is high-risk — read the{" "}
        <Link href="/disclaimer" className="underline hover:text-foreground">
          Risk Disclosure
        </Link>
        .
      </p>
    </div>
  );
}
