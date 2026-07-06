"use client";

import React, { useCallback, useState } from "react";
import { RefreshCw, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LeaderboardTable } from "@/components/copy/leaderboard-table";
import { WalletDetailPanel } from "@/components/copy/wallet-detail-panel";
import { useLeaderboard, type LeaderboardStatus } from "@/hooks/useLeaderboard";
import {
  LEADERBOARD_WINDOWS,
  type LeaderboardWindow,
  type WalletRow,
} from "@/lib/copy-leaderboard";
import { cn } from "@/lib/utils";

const STATUS_BADGE: Record<LeaderboardStatus, { label: string; className: string }> = {
  loading: {
    label: "LOADING",
    className: "text-muted-foreground border-border",
  },
  ready: {
    label: "AUTO-REFRESH",
    className: "text-green-400 border-green-400/40",
  },
  offline: {
    label: "OFFLINE",
    className: "text-red-400 border-red-400/40 bg-red-400/10",
  },
};

function CopyEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-surface py-16 text-center">
      <div className="mb-4 animate-pulse rounded-full bg-accent/10 p-4">
        <Users className="h-8 w-8 text-accent" />
      </div>
      <h3 className="mb-1 text-sm font-semibold text-foreground">
        Building the leaderboard...
      </h3>
      <p className="text-xs text-muted-foreground">
        Wallets appear as the discovery pipeline records their trades. Try a
        wider window if this one is empty.
      </p>
    </div>
  );
}

export default function CopyPage() {
  const [window, setWindow] = useState<LeaderboardWindow>("24h");
  const [excludeClustered, setExcludeClustered] = useState(false);
  const [selectedWallet, setSelectedWallet] = useState<WalletRow | null>(null);
  const { wallets, status, error, refresh, refreshing, lastUpdated } =
    useLeaderboard(window, excludeClustered);

  const handleRefresh = useCallback(() => {
    void refresh();
  }, [refresh]);

  const badge = STATUS_BADGE[status];
  const showSkeleton = status === "loading" && wallets.length === 0;
  const showEmptyState = !showSkeleton && wallets.length === 0;

  return (
    <div className="flex h-full gap-0">
      <div className="flex flex-1 flex-col gap-4 overflow-hidden">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Users className="h-5 w-5 text-accent" />
            <h1 className="text-lg font-bold text-foreground">Copy Intelligence</h1>
            <Badge variant="outline" className="font-mono-numbers">
              {wallets.length} wallets
            </Badge>
          </div>
          <Badge variant="outline" className={badge.className}>
            {badge.label}
          </Badge>
        </div>

        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="flex rounded-md border border-border p-0.5">
              {LEADERBOARD_WINDOWS.map((w) => (
                <button
                  key={w}
                  onClick={() => setWindow(w)}
                  className={cn(
                    "rounded px-3 py-1 font-mono-numbers text-xs transition-colors",
                    w === window
                      ? "bg-accent/15 text-accent"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {w}
                </button>
              ))}
            </div>
            <Button
              variant={excludeClustered ? "default" : "outline"}
              size="sm"
              className="h-7 text-xs"
              onClick={() => setExcludeClustered((v) => !v)}
            >
              Hide clustered
            </Button>
          </div>
          <div className="flex items-center gap-2">
            {lastUpdated && (
              <span className="text-xs text-muted-foreground">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              <RefreshCw className={cn("mr-1 h-3 w-3", refreshing && "animate-spin")} />
              Refresh
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {showEmptyState ? (
            <CopyEmptyState />
          ) : (
            <LeaderboardTable
              data={wallets}
              loading={showSkeleton}
              onRowClick={setSelectedWallet}
            />
          )}
        </div>

        {error && status === "offline" && (
          <div className="rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-400">
            Connection error: {error}
          </div>
        )}
      </div>

      {selectedWallet && (
        <WalletDetailPanel
          walletAddress={selectedWallet.wallet_address}
          window={window}
          onClose={() => setSelectedWallet(null)}
        />
      )}
    </div>
  );
}
