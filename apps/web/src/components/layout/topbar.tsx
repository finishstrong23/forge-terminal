"use client";

import React from "react";
import { Search, Bell, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface TopbarProps {
  onCommandPalette: () => void;
}

export function Topbar({ onCommandPalette }: TopbarProps) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-surface px-4">
      <button
        onClick={onCommandPalette}
        className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-surface-hover hover:text-foreground"
      >
        <Search className="h-3.5 w-3.5" />
        <span>Search tokens, wallets...</span>
        <kbd className="ml-4 hidden rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:inline-block">
          ⌘K
        </kbd>
      </button>

      <div className="flex items-center gap-3">
        <Badge variant="tier">FREE</Badge>

        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-4 w-4" />
        </Button>

        <Button variant="outline" size="sm" className="gap-2">
          <Wallet className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Connect Wallet</span>
        </Button>
      </div>
    </header>
  );
}
