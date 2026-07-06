"use client";

import React, { useEffect, useState } from "react";
import { X, Copy, TrendingUp, Target, Gauge } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, truncateAddress, scoreColor, scoreBg } from "@/lib/utils";
import {
  fetchScoreHistory,
  fetchWalletDetail,
  formatRelativeTime,
  formatSol,
  type LeaderboardWindow,
} from "@/lib/copy-leaderboard";
import { ScoreSparkline } from "@/components/copy/score-sparkline";
import type { ApiScoreSnapshot, ApiWalletDetailResponse } from "@/lib/types";

interface WalletDetailPanelProps {
  walletAddress: string;
  window: LeaderboardWindow;
  onClose: () => void;
}

function StatBlock({
  label,
  value,
  icon: Icon,
  className,
}: {
  label: string;
  value: string;
  icon: React.ElementType;
  className?: string;
}) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-border p-3">
      <Icon className="mb-1 h-4 w-4 text-muted-foreground" />
      <span className={cn("font-mono-numbers text-lg font-bold", className)}>
        {value}
      </span>
      <span className="text-[10px] text-muted-foreground">{label}</span>
    </div>
  );
}

export function WalletDetailPanel({
  walletAddress,
  window,
  onClose,
}: WalletDetailPanelProps) {
  const [detail, setDetail] = useState<ApiWalletDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<ApiScoreSnapshot[]>([]);

  useEffect(() => {
    let unmounted = false;
    setDetail(null);
    setError(null);
    fetchWalletDetail(walletAddress, window)
      .then((d) => {
        if (!unmounted) setDetail(d);
      })
      .catch((err) => {
        if (!unmounted) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      unmounted = true;
    };
  }, [walletAddress, window]);

  // Score history is supplementary — failures just hide the trend section.
  useEffect(() => {
    let unmounted = false;
    setHistory([]);
    fetchScoreHistory(walletAddress)
      .then((h) => {
        if (!unmounted) setHistory(Array.isArray(h.snapshots) ? h.snapshots : []);
      })
      .catch(() => {
        /* section stays hidden */
      });
    return () => {
      unmounted = true;
    };
  }, [walletAddress]);

  const scoredSnapshots = history.filter((s) => s.total_score !== null);

  const stats = detail?.wallet;

  return (
    <div className="flex w-96 flex-col border-l border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border p-4">
        <div>
          <h3 className="font-mono text-sm font-bold text-foreground">
            {truncateAddress(walletAddress, 6)}
          </h3>
          <p className="text-xs text-muted-foreground">
            Wallet performance · {window}
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <div className="flex items-center gap-2">
          <code className="flex-1 rounded bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
            {truncateAddress(walletAddress, 10)}
          </code>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => navigator.clipboard.writeText(walletAddress)}
          >
            <Copy className="h-3 w-3" />
          </Button>
        </div>

        {error && (
          <div className="rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-400">
            Failed to load wallet: {error}
          </div>
        )}

        {!detail && !error && (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full rounded-md" />
            ))}
          </div>
        )}

        {stats && (
          <>
            <div className="grid grid-cols-3 gap-2">
              <StatBlock
                label="Net SOL"
                value={formatSol(stats.net_sol)}
                icon={TrendingUp}
                className={
                  stats.net_sol > 0
                    ? "text-green-400"
                    : stats.net_sol < 0
                      ? "text-red-400"
                      : undefined
                }
              />
              <StatBlock
                label="Win rate"
                value={
                  stats.win_rate === null
                    ? "—"
                    : `${(stats.win_rate * 100).toFixed(0)}%`
                }
                icon={Target}
              />
              <div
                className={cn(
                  "flex flex-col items-center rounded-lg border p-3",
                  scoreBg(stats.sustainability_score)
                )}
              >
                <Gauge
                  className={cn("mb-1 h-4 w-4", scoreColor(stats.sustainability_score))}
                />
                <span
                  className={cn(
                    "font-mono-numbers text-lg font-bold",
                    scoreColor(stats.sustainability_score)
                  )}
                >
                  {stats.sustainability_grade ?? "—"}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  Sustainability {stats.sustainability_score.toFixed(0)}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <span className="text-muted-foreground">Trades</span>
              <span className="text-right font-mono-numbers">{stats.total_trades}</span>
              <span className="text-muted-foreground">Buys / Sells</span>
              <span className="text-right font-mono-numbers">
                {stats.buy_count} / {stats.sell_count}
              </span>
              <span className="text-muted-foreground">Tokens traded</span>
              <span className="text-right font-mono-numbers">{stats.tokens_traded}</span>
              <span className="text-muted-foreground">Closed / Wins</span>
              <span className="text-right font-mono-numbers">
                {stats.closed_positions} / {stats.wins}
              </span>
              <span className="text-muted-foreground">Active days</span>
              <span className="text-right font-mono-numbers">{stats.active_days}</span>
              <span className="text-muted-foreground">Last active</span>
              <span className="text-right font-mono-numbers">
                {formatRelativeTime(stats.last_active)}
              </span>
            </div>

            {stats.is_clustered && (
              <Badge variant="warning" className="text-[10px]">
                Linked to a funding cluster — possible insider activity
              </Badge>
            )}

            {scoredSnapshots.length >= 2 && (
              <div>
                <div className="mb-1 flex items-baseline justify-between">
                  <h4 className="text-xs font-semibold text-foreground">
                    Score trend
                  </h4>
                  <span className="text-[10px] text-muted-foreground">
                    {scoredSnapshots.length} snapshots · since{" "}
                    {formatRelativeTime(scoredSnapshots[0].scored_at)}
                  </span>
                </div>
                <ScoreSparkline snapshots={scoredSnapshots} />
              </div>
            )}

            <Separator />

            <div>
              <h4 className="mb-2 text-xs font-semibold text-foreground">
                Recent activity
              </h4>
              {detail.recent_activity.length === 0 ? (
                <p className="text-xs text-muted-foreground">No recorded trades.</p>
              ) : (
                <ul className="space-y-1.5">
                  {detail.recent_activity.map((a, i) => (
                    <li
                      key={a.signature ?? `${a.token_address}-${i}`}
                      className="flex items-center justify-between gap-2 rounded border border-border-muted px-2 py-1.5"
                    >
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={a.activity_type === "buy" ? "default" : "outline"}
                          className={cn(
                            "text-[10px] uppercase",
                            a.activity_type === "buy"
                              ? "text-green-400"
                              : "text-red-400"
                          )}
                        >
                          {a.activity_type}
                        </Badge>
                        <span className="font-mono text-xs">
                          {a.symbol ?? truncateAddress(a.token_address)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="font-mono-numbers">
                          {a.sol_amount !== null ? `${a.sol_amount.toFixed(2)} SOL` : "—"}
                        </span>
                        <span className="font-mono-numbers">
                          {formatRelativeTime(a.timestamp)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
