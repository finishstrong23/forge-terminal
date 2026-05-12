"use client";

import React, { useCallback, useState } from "react";
import { Radar } from "lucide-react";
import { SignalTable, type TokenSignal } from "@/components/discovery/signal-table";
import { FilterBar, type FilterState } from "@/components/discovery/filter-bar";
import { SignalDetailPanel } from "@/components/discovery/signal-detail-panel";
import { EmptyState } from "@/components/discovery/empty-state";
import { Badge } from "@/components/ui/badge";
import { useDiscoveryFeed } from "@/hooks/useDiscoveryFeed";
import type { FeedStatus } from "@/lib/discovery-feed";

const defaultFilters: FilterState = {
  minLiquidity: "",
  maxAge: "",
  minMomentum: "",
  maxRugRisk: "",
  hideHoneypots: true,
  search: "",
};

const STATUS_BADGE: Record<
  FeedStatus,
  { label: string; className: string }
> = {
  loading: {
    label: "LOADING",
    className: "text-muted-foreground border-border",
  },
  live: {
    label: "LIVE",
    className: "animate-pulse-glow",
  },
  polling: {
    label: "POLLING",
    className: "text-amber-400 border-amber-400/40",
  },
  offline: {
    label: "OFFLINE",
    className: "text-red-400 border-red-400/40 bg-red-400/10",
  },
};

export default function DiscoveryPage() {
  const { tokens, status, error, refresh, refreshing, lastUpdated } = useDiscoveryFeed();
  const [filters, setFilters] = useState<FilterState>(defaultFilters);
  const [selectedSignal, setSelectedSignal] = useState<TokenSignal | null>(null);

  const filteredSignals = React.useMemo(() => {
    return tokens.filter((s) => {
      if (filters.hideHoneypots && s.is_honeypot) return false;
      if (filters.search) {
        const q = filters.search.toLowerCase();
        if (
          !s.symbol.toLowerCase().includes(q) &&
          !s.name.toLowerCase().includes(q)
        )
          return false;
      }
      if (filters.minLiquidity) {
        const v = parseFloat(filters.minLiquidity);
        if (!isNaN(v) && s.liquidity_usd < v) return false;
      }
      if (filters.maxAge) {
        const v = parseFloat(filters.maxAge) * 60;
        if (!isNaN(v) && s.age_minutes > v) return false;
      }
      if (filters.minMomentum) {
        const v = parseFloat(filters.minMomentum);
        if (!isNaN(v) && s.momentum_score < v) return false;
      }
      if (filters.maxRugRisk) {
        const v = parseFloat(filters.maxRugRisk);
        if (!isNaN(v) && s.rug_risk_score > v) return false;
      }
      return true;
    });
  }, [tokens, filters]);

  const handleRefresh = useCallback(() => {
    void refresh();
  }, [refresh]);

  const badge = STATUS_BADGE[status];
  const showSkeleton = status === "loading" && tokens.length === 0;
  const showEmptyState = !showSkeleton && tokens.length === 0;

  return (
    <div className="flex h-full gap-0">
      <div className="flex flex-1 flex-col gap-4 overflow-hidden">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Radar className="h-5 w-5 text-accent" />
            <h1 className="text-lg font-bold text-foreground">Discovery</h1>
            <Badge variant="outline" className="font-mono-numbers">
              {filteredSignals.length} tokens
            </Badge>
          </div>
          <Badge variant="outline" className={badge.className}>
            {badge.label}
          </Badge>
        </div>

        <FilterBar
          filters={filters}
          onChange={setFilters}
          onRefresh={handleRefresh}
          lastUpdated={lastUpdated}
          refreshing={refreshing}
        />

        <div className="flex-1 overflow-y-auto">
          {showEmptyState ? (
            <EmptyState />
          ) : (
            <SignalTable
              data={filteredSignals}
              loading={showSkeleton}
              onRowClick={setSelectedSignal}
            />
          )}
        </div>

        {error && status === "offline" && (
          <div className="rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-400">
            Connection error: {error}
          </div>
        )}
      </div>

      {selectedSignal && (
        <SignalDetailPanel
          signal={selectedSignal}
          onClose={() => setSelectedSignal(null)}
        />
      )}
    </div>
  );
}
