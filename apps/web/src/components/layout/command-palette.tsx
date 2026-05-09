"use client";

import React, { useEffect, useState } from "react";
import { Command } from "cmdk";
import {
  Radar,
  Users,
  Zap,
  LayoutDashboard,
  Settings,
  Search,
} from "lucide-react";
import { useRouter } from "next/navigation";

const pages = [
  { label: "Discovery", href: "/discovery", icon: Radar },
  { label: "Copy Intelligence", href: "/copy", icon: Users },
  { label: "Execute Trade", href: "/execute", icon: Zap },
  { label: "Portfolio", href: "/portfolio", icon: LayoutDashboard },
  { label: "Settings", href: "/settings", icon: Settings },
];

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!open) setSearch("");
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="fixed inset-0 bg-black/60"
        onClick={() => onOpenChange(false)}
      />
      <div className="fixed left-1/2 top-[20%] w-full max-w-lg -translate-x-1/2">
        <Command
          className="rounded-lg border border-border bg-surface shadow-2xl"
          shouldFilter={true}
        >
          <div className="flex items-center gap-2 border-b border-border px-3">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <Command.Input
              value={search}
              onValueChange={setSearch}
              placeholder="Search tokens, wallets, or navigate..."
              className="flex h-12 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            />
          </div>
          <Command.List className="max-h-72 overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
              No results found.
            </Command.Empty>

            <Command.Group
              heading="Navigation"
              className="text-xs font-medium text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5"
            >
              {pages.map((page) => (
                <Command.Item
                  key={page.href}
                  value={page.label}
                  onSelect={() => {
                    router.push(page.href);
                    onOpenChange(false);
                  }}
                  className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 text-sm text-foreground aria-selected:bg-accent/10 aria-selected:text-accent"
                >
                  <page.icon className="h-4 w-4 text-muted-foreground" />
                  {page.label}
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
