"use client";

import React from "react";
import Link from "next/link";
import { Search, Bell, LogIn, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { WalletButton } from "@/components/layout/wallet-button";
import { useAuth } from "@/hooks/useAuth";

interface TopbarProps {
  onCommandPalette: () => void;
}

export function Topbar({ onCommandPalette }: TopbarProps) {
  const { user, signOut } = useAuth();
  const tier = (user?.subscription_tier ?? "free").toUpperCase();

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
        <Badge variant="tier">{tier}</Badge>

        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-4 w-4" />
        </Button>

        <WalletButton />

        {user ? (
          <div className="flex items-center gap-2">
            <span className="hidden max-w-[160px] truncate text-xs text-muted-foreground md:inline">
              {user.email}
            </span>
            <Button variant="ghost" size="icon" title="Sign out" onClick={signOut}>
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <Button variant="default" size="sm" className="gap-2" asChild>
            <Link href="/login">
              <LogIn className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Sign in</span>
            </Link>
          </Button>
        )}
      </div>
    </header>
  );
}
