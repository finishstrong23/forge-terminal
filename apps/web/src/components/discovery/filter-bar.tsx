"use client";

import React from "react";
import { SlidersHorizontal, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface FilterState {
  minLiquidity: string;
  maxAge: string;
  minMomentum: string;
  maxRugRisk: string;
  hideHoneypots: boolean;
  search: string;
}

interface FilterBarProps {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  onRefresh: () => void;
  lastUpdated: Date | null;
  refreshing?: boolean;
}

export function FilterBar({ filters, onChange, onRefresh, lastUpdated, refreshing }: FilterBarProps) {
  const update = (patch: Partial<FilterState>) =>
    onChange({ ...filters, ...patch });

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface p-3">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <SlidersHorizontal className="h-3.5 w-3.5" />
        Filters
      </div>

      <Input
        placeholder="Search token..."
        value={filters.search}
        onChange={(e) => update({ search: e.target.value })}
        className="h-8 w-40 text-xs"
      />

      <div className="flex items-center gap-1.5">
        <label className="text-xs text-muted-foreground">Min Liq</label>
        <Input
          placeholder="$2.5K"
          value={filters.minLiquidity}
          onChange={(e) => update({ minLiquidity: e.target.value })}
          className="h-8 w-20 font-mono-numbers text-xs"
        />
      </div>

      <div className="flex items-center gap-1.5">
        <label className="text-xs text-muted-foreground">Max Age</label>
        <Input
          placeholder="72h"
          value={filters.maxAge}
          onChange={(e) => update({ maxAge: e.target.value })}
          className="h-8 w-16 font-mono-numbers text-xs"
        />
      </div>

      <div className="flex items-center gap-1.5">
        <label className="text-xs text-muted-foreground">Min Mom.</label>
        <Input
          placeholder="0"
          value={filters.minMomentum}
          onChange={(e) => update({ minMomentum: e.target.value })}
          className="h-8 w-16 font-mono-numbers text-xs"
        />
      </div>

      <div className="flex items-center gap-1.5">
        <label className="text-xs text-muted-foreground">Max Risk</label>
        <Input
          placeholder="100"
          value={filters.maxRugRisk}
          onChange={(e) => update({ maxRugRisk: e.target.value })}
          className="h-8 w-16 font-mono-numbers text-xs"
        />
      </div>

      <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <input
          type="checkbox"
          checked={filters.hideHoneypots}
          onChange={(e) => update({ hideHoneypots: e.target.checked })}
          className="rounded border-border"
        />
        Hide honeypots
      </label>

      <div className="ml-auto flex items-center gap-2">
        {lastUpdated && (
          <span className="font-mono-numbers text-[10px] text-muted-foreground" suppressHydrationWarning>
            Updated {lastUpdated.toLocaleTimeString()}
          </span>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={onRefresh}
          disabled={refreshing}
          className="h-8 gap-1 text-xs"
        >
          <RotateCw className={refreshing ? "h-3 w-3 animate-spin" : "h-3 w-3"} />
          Refresh
        </Button>
      </div>
    </div>
  );
}
