"use client";

import { Settings } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function SettingsPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24">
      <div className="rounded-full border border-border bg-surface p-4">
        <Settings className="h-8 w-8 text-accent" />
      </div>
      <h1 className="text-lg font-bold text-foreground">Settings</h1>
      <p className="max-w-md text-center text-sm text-muted-foreground">
        Account preferences, subscription management, alert configuration,
        Telegram bot setup, API keys, and risk profile customization.
      </p>
      <Badge variant="warning">Coming in Phase 4</Badge>
    </div>
  );
}
