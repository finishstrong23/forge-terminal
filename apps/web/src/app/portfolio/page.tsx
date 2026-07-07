"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/useAuth";
import { formatRelativeTime } from "@/lib/copy-leaderboard";
import {
  listShadowTrades,
  listSubscriptions,
  patchSubscription,
  type SubscriptionAction,
} from "@/lib/copy-subscriptions";
import { cn, truncateAddress } from "@/lib/utils";
import type { ApiCopySubscription, ApiShadowTrade } from "@/lib/types";

const STATUS_BADGE: Record<string, string> = {
  active: "text-green-400 border-green-400/40",
  paused: "text-amber-400 border-amber-400/40",
  stopped: "text-muted-foreground border-border",
};

function SignedOut() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24">
      <div className="rounded-full border border-border bg-surface p-4">
        <Briefcase className="h-8 w-8 text-accent" />
      </div>
      <h1 className="text-lg font-bold text-foreground">Portfolio</h1>
      <p className="max-w-md text-center text-sm text-muted-foreground">
        Your followed wallets and shadow-trade ledger live here.{" "}
        <Link href="/login" className="text-accent hover:underline">
          Sign in
        </Link>{" "}
        to get started.
      </p>
    </div>
  );
}

export default function PortfolioPage() {
  const { user, loading: authLoading } = useAuth();
  const [subs, setSubs] = useState<ApiCopySubscription[]>([]);
  const [trades, setTrades] = useState<ApiShadowTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [subsResult, tradesResult] = await Promise.all([
        listSubscriptions(),
        listShadowTrades(),
      ]);
      setSubs(subsResult.subscriptions);
      setTrades(tradesResult.trades);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && user) void refresh();
  }, [authLoading, user, refresh]);

  if (authLoading) {
    return (
      <div className="space-y-2 py-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-md" />
        ))}
      </div>
    );
  }
  if (!user) return <SignedOut />;

  const act = async (id: string, action: SubscriptionAction) => {
    setBusyId(id);
    try {
      await patchSubscription(id, action);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  };

  const subWallet = new Map(subs.map((s) => [s.id, s.wallet_address]));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Briefcase className="h-5 w-5 text-accent" />
          <h1 className="text-lg font-bold text-foreground">Portfolio</h1>
          <Badge variant="outline" className="font-mono-numbers">
            {subs.filter((s) => s.status !== "stopped").length} follows
          </Badge>
        </div>
        <Button variant="outline" size="sm" className="h-7 text-xs" onClick={refresh}>
          <RefreshCw className="mr-1 h-3 w-3" />
          Refresh
        </Button>
      </div>

      {error && (
        <div className="rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <section>
        <h2 className="mb-2 text-sm font-semibold text-foreground">Followed wallets</h2>
        {loading ? (
          <Skeleton className="h-24 w-full rounded-md" />
        ) : subs.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface px-4 py-6 text-center text-xs text-muted-foreground">
            No follows yet — pick a wallet on the{" "}
            <Link href="/copy" className="text-accent hover:underline">
              Copy Intelligence
            </Link>{" "}
            leaderboard.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-surface text-left text-xs text-muted-foreground">
                  <th className="px-3 py-2">Wallet</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Mode</th>
                  <th className="px-3 py-2">Started</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {subs.map((s) => (
                  <tr key={s.id} className="border-b border-border-muted">
                    <td className="px-3 py-2 font-mono text-xs">
                      {truncateAddress(s.wallet_address, 5)}
                    </td>
                    <td className="px-3 py-2">
                      <Badge
                        variant="outline"
                        className={cn("text-[10px] uppercase", STATUS_BADGE[s.status])}
                      >
                        {s.status}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{s.mode}</td>
                    <td className="px-3 py-2 font-mono-numbers text-xs text-muted-foreground">
                      {formatRelativeTime(s.started_at)}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex justify-end gap-1">
                        {s.status === "active" && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-6 text-xs"
                            disabled={busyId === s.id}
                            onClick={() => act(s.id, "pause")}
                          >
                            Pause
                          </Button>
                        )}
                        {s.status === "paused" && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-6 text-xs"
                            disabled={busyId === s.id}
                            onClick={() => act(s.id, "resume")}
                          >
                            Resume
                          </Button>
                        )}
                        {s.status !== "stopped" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 text-xs text-red-400"
                            disabled={busyId === s.id}
                            onClick={() => act(s.id, "stop")}
                          >
                            Stop
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-foreground">Shadow ledger</h2>
        {loading ? (
          <Skeleton className="h-24 w-full rounded-md" />
        ) : trades.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface px-4 py-6 text-center text-xs text-muted-foreground">
            No shadow trades yet — they appear within a minute of a followed
            wallet trading.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-surface text-left text-xs text-muted-foreground">
                  <th className="px-3 py-2">Time</th>
                  <th className="px-3 py-2">Leader</th>
                  <th className="px-3 py-2">Token</th>
                  <th className="px-3 py-2">Side</th>
                  <th className="px-3 py-2">SOL</th>
                  <th className="px-3 py-2">USD</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Reason</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.id} className="border-b border-border-muted">
                    <td className="px-3 py-2 font-mono-numbers text-xs text-muted-foreground">
                      {formatRelativeTime(t.executed_at ?? t.created_at)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {t.copy_subscription_id && subWallet.get(t.copy_subscription_id)
                        ? truncateAddress(subWallet.get(t.copy_subscription_id)!, 4)
                        : "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {truncateAddress(t.token_address, 4)}
                    </td>
                    <td
                      className={cn(
                        "px-3 py-2 text-xs uppercase",
                        t.trade_type === "buy" ? "text-green-400" : "text-red-400",
                      )}
                    >
                      {t.trade_type}
                    </td>
                    <td className="px-3 py-2 font-mono-numbers text-xs">
                      {t.sol_amount !== null ? t.sol_amount.toFixed(2) : "—"}
                    </td>
                    <td className="px-3 py-2 font-mono-numbers text-xs text-muted-foreground">
                      {t.usd_value != null ? `$${t.usd_value.toFixed(2)}` : "—"}
                    </td>
                    <td className="px-3 py-2">
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px] uppercase",
                          t.status === "simulated"
                            ? "text-green-400 border-green-400/40"
                            : "text-amber-400 border-amber-400/40",
                        )}
                      >
                        {t.status}
                      </Badge>
                    </td>
                    <td className="max-w-[240px] truncate px-3 py-2 text-xs text-muted-foreground">
                      {t.error_message ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
