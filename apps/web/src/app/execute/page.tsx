"use client";

import { Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function ExecutePage() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24">
      <div className="rounded-full border border-border bg-surface p-4">
        <Zap className="h-8 w-8 text-accent" />
      </div>
      <h1 className="text-lg font-bold text-foreground">Execution Layer</h1>
      <p className="max-w-md text-center text-sm text-muted-foreground">
        Jupiter-routed swaps with MEV protection via Jito bundles. Risk-tier
        slippage profiles, quick-buy presets, and trailing stop-losses — all
        wired to your Discovery signals.
      </p>
      <Badge variant="warning">Coming in Phase 3</Badge>
    </div>
  );
}
