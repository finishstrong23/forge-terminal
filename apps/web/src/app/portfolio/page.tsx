"use client";

import { LayoutDashboard } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function PortfolioPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24">
      <div className="rounded-full border border-border bg-surface p-4">
        <LayoutDashboard className="h-8 w-8 text-accent" />
      </div>
      <h1 className="text-lg font-bold text-foreground">Portfolio</h1>
      <p className="max-w-md text-center text-sm text-muted-foreground">
        Live view of all your positions, PnL tracking, trade history with CSV
        export, and performance analytics across Discovery finds, copy trades,
        and manual executions.
      </p>
      <Badge variant="warning">Coming in Phase 3</Badge>
    </div>
  );
}
