"use client";

import { Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function CopyPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24">
      <div className="rounded-full border border-border bg-surface p-4">
        <Users className="h-8 w-8 text-accent" />
      </div>
      <h1 className="text-lg font-bold text-foreground">Copy Intelligence</h1>
      <p className="max-w-md text-center text-sm text-muted-foreground">
        Curated wallet leaderboards with sustainability scoring, shadow trading,
        and one-click copy execution. Track top Solana traders and mirror their
        moves with risk controls.
      </p>
      <Badge variant="warning">Coming in Phase 2</Badge>
    </div>
  );
}
