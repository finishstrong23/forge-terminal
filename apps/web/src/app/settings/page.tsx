"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CreditCard, Settings, User as UserIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/useAuth";
import {
  fetchBillingStatus,
  openPortal,
  startCheckout,
  type BillingStatus,
} from "@/lib/billing";
import { formatRelativeTime } from "@/lib/copy-leaderboard";

function SignedOut() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24">
      <div className="rounded-full border border-border bg-surface p-4">
        <Settings className="h-8 w-8 text-accent" />
      </div>
      <h1 className="text-lg font-bold text-foreground">Settings</h1>
      <p className="max-w-md text-center text-sm text-muted-foreground">
        Manage your account and plan here.{" "}
        <Link href="/login" className="text-accent hover:underline">
          Sign in
        </Link>{" "}
        to continue.
      </p>
    </div>
  );
}

export default function SettingsPage() {
  // useSearchParams requires a Suspense boundary for static prerendering.
  return (
    <Suspense fallback={<Skeleton className="h-32 w-full rounded-md" />}>
      <SettingsContent />
    </Suspense>
  );
}

function SettingsContent() {
  const { user, loading: authLoading, signOut } = useAuth();
  const searchParams = useSearchParams();
  const billingResult = searchParams.get("billing"); // success | cancelled | null
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (authLoading || !user) return;
    let unmounted = false;
    fetchBillingStatus()
      .then((b) => {
        if (!unmounted) setBilling(b);
      })
      .catch((err) => {
        if (!unmounted) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      unmounted = true;
    };
  }, [authLoading, user]);

  if (authLoading) {
    return (
      <div className="space-y-2 py-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-md" />
        ))}
      </div>
    );
  }
  if (!user) return <SignedOut />;

  const redirectTo = async (getUrl: () => Promise<string>) => {
    setBusy(true);
    setError(null);
    try {
      window.location.assign(await getUrl());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  const tier = (billing?.tier ?? user.subscription_tier).toUpperCase();
  const isFree = (billing?.tier ?? user.subscription_tier) === "free";

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div className="flex items-center gap-3">
        <Settings className="h-5 w-5 text-accent" />
        <h1 className="text-lg font-bold text-foreground">Settings</h1>
      </div>

      {billingResult === "success" && (
        <div className="rounded border border-green-400/30 bg-green-400/10 px-3 py-2 text-xs text-green-400">
          Payment complete — your plan updates within a few seconds of
          Stripe&apos;s confirmation. Refresh if the badge still shows FREE.
        </div>
      )}
      {billingResult === "cancelled" && (
        <div className="rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-400">
          Checkout cancelled — no changes made.
        </div>
      )}
      {error && (
        <div className="rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <section className="rounded-lg border border-border bg-surface p-4">
        <div className="mb-3 flex items-center gap-2">
          <UserIcon className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold text-foreground">Account</h2>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <span className="text-muted-foreground">Email</span>
          <span className="text-right">{user.email}</span>
          <span className="text-muted-foreground">Member since</span>
          <span className="text-right font-mono-numbers">
            {formatRelativeTime(user.created_at)}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="mt-4 h-7 text-xs"
          onClick={signOut}
        >
          Sign out
        </Button>
      </section>

      <section className="rounded-lg border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CreditCard className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold text-foreground">Plan</h2>
          </div>
          <Badge variant="tier">{tier}</Badge>
        </div>

        {billing && !billing.billing_configured ? (
          <p className="text-xs text-muted-foreground">
            Billing isn&apos;t configured on this deployment yet — all accounts
            run on the free tier.
          </p>
        ) : isFree ? (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Free tier: signals delayed 15 minutes, up to 3 followed wallets.
              Pro unlocks the realtime feed and 50 follows.
            </p>
            <div className="flex gap-2">
              <Button
                size="sm"
                className="h-7 text-xs"
                disabled={busy}
                onClick={() => redirectTo(() => startCheckout("monthly"))}
              >
                Upgrade — monthly
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                disabled={busy}
                onClick={() => redirectTo(() => startCheckout("yearly"))}
              >
                Upgrade — yearly
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <span className="text-muted-foreground">Status</span>
              <span className="text-right">{billing?.subscription?.status ?? "active"}</span>
              {billing?.subscription?.current_period_end && (
                <>
                  <span className="text-muted-foreground">
                    {billing.subscription.cancel_at_period_end ? "Ends" : "Renews"}
                  </span>
                  <span className="text-right font-mono-numbers">
                    {new Date(billing.subscription.current_period_end).toLocaleDateString()}
                  </span>
                </>
              )}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              disabled={busy}
              onClick={() => redirectTo(openPortal)}
            >
              Manage billing
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
