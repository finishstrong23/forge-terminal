"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Radar,
  Users,
  Zap,
  LayoutDashboard,
  Settings,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Crown,
  Flame,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navItems = [
  {
    label: "Discovery",
    href: "/discovery",
    icon: Radar,
    description: "Multi-DEX token scanner",
  },
  {
    label: "Copy Intel",
    href: "/copy",
    icon: Users,
    description: "Wallet leaderboards & copy trading",
  },
  {
    label: "Execute",
    href: "/execute",
    icon: Zap,
    description: "Jupiter-routed swaps",
  },
  {
    label: "Portfolio",
    href: "/portfolio",
    icon: LayoutDashboard,
    description: "Positions & PnL",
  },
  {
    label: "Pricing",
    href: "/pricing",
    icon: Crown,
    description: "Free vs Pro",
  },
  {
    label: "How it works",
    href: "/how-it-works",
    icon: CircleHelp,
    description: "Discover → Shadow-follow → Execute",
  },
  {
    label: "Settings",
    href: "/settings",
    icon: Settings,
    description: "Account & preferences",
  },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-border bg-surface transition-all duration-200",
        collapsed ? "w-16" : "w-56"
      )}
    >
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        <Flame className="h-6 w-6 shrink-0 text-accent" />
        {!collapsed && (
          <span className="text-sm font-bold tracking-wider text-foreground">
            FORGE
          </span>
        )}
      </div>

      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          const linkContent = (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-accent/10 text-accent"
                  : "text-muted-foreground hover:bg-surface-hover hover:text-foreground"
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );

          if (collapsed) {
            return (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                <TooltipContent side="right">
                  <p className="font-medium">{item.label}</p>
                  <p className="text-muted-foreground">{item.description}</p>
                </TooltipContent>
              </Tooltip>
            );
          }

          return linkContent;
        })}
      </nav>

      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center border-t border-border p-3 text-muted-foreground transition-colors hover:text-foreground"
      >
        {collapsed ? (
          <ChevronRight className="h-4 w-4" />
        ) : (
          <ChevronLeft className="h-4 w-4" />
        )}
      </button>
    </aside>
  );
}
