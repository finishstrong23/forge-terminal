"use client";

import { Radar } from "lucide-react";

/**
 * Empty state shown when the discovery feed has zero tokens and we're past
 * the initial loading phase. Distinct from the table-internal "no tokens
 * match your filters" message (which renders when filteredSignals is empty
 * but the underlying tokens list is not).
 */
export function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-surface py-16 text-center">
      <div className="mb-4 rounded-full bg-accent/10 p-4 animate-pulse">
        <Radar className="h-8 w-8 text-accent" />
      </div>
      <h3 className="mb-1 text-sm font-semibold text-foreground">
        Scanning for new tokens...
      </h3>
      <p className="text-xs text-muted-foreground">
        The feed will populate as the scanner detects activity.
      </p>
    </div>
  );
}
