"use client";

import React from "react";
import { X, Copy, Shield, TrendingUp, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn, formatUsd, truncateAddress, scoreColor, scoreBg } from "@/lib/utils";
import type { TokenSignal } from "./signal-table";

interface SignalDetailPanelProps {
  signal: TokenSignal | null;
  onClose: () => void;
}

function ScoreBlock({
  label,
  score,
  icon: Icon,
  inverted = false,
}: {
  label: string;
  score: number;
  icon: React.ElementType;
  inverted?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center rounded-lg border p-3",
        scoreBg(score, inverted)
      )}
    >
      <Icon className={cn("h-4 w-4 mb-1", scoreColor(score, inverted))} />
      <span
        className={cn(
          "font-mono-numbers text-2xl font-bold",
          scoreColor(score, inverted)
        )}
      >
        {score}
      </span>
      <span className="text-[10px] text-muted-foreground">{label}</span>
    </div>
  );
}

export function SignalDetailPanel({ signal, onClose }: SignalDetailPanelProps) {
  if (!signal) return null;

  return (
    <div className="flex w-96 flex-col border-l border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border p-4">
        <div>
          <h3 className="font-bold text-foreground">{signal.symbol}</h3>
          <p className="text-xs text-muted-foreground">{signal.name}</p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="flex items-center gap-2">
          <code className="flex-1 rounded bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
            {truncateAddress(signal.token_address, 8)}
          </code>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => navigator.clipboard.writeText(signal.token_address)}
          >
            <Copy className="h-3 w-3" />
          </Button>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <ScoreBlock label="Rug Risk" score={signal.rug_risk_score} icon={Shield} inverted />
          <ScoreBlock label="Momentum" score={signal.momentum_score} icon={TrendingUp} />
          <ScoreBlock label="Confidence" score={signal.confidence_score} icon={Target} />
        </div>

        <Separator />

        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">Market Data</h4>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex justify-between rounded bg-muted p-2">
              <span className="text-muted-foreground">Price</span>
              <span className="font-mono-numbers">${signal.price_usd.toFixed(8)}</span>
            </div>
            <div className="flex justify-between rounded bg-muted p-2">
              <span className="text-muted-foreground">MCap</span>
              <span className="font-mono-numbers">{formatUsd(signal.market_cap)}</span>
            </div>
            <div className="flex justify-between rounded bg-muted p-2">
              <span className="text-muted-foreground">Liquidity</span>
              <span className="font-mono-numbers">{formatUsd(signal.liquidity_usd)}</span>
            </div>
            <div className="flex justify-between rounded bg-muted p-2">
              <span className="text-muted-foreground">Vol 1h</span>
              <span className="font-mono-numbers">{formatUsd(signal.volume_1h)}</span>
            </div>
            <div className="flex justify-between rounded bg-muted p-2">
              <span className="text-muted-foreground">Holders</span>
              <span className="font-mono-numbers">{signal.holder_count}</span>
            </div>
            <div className="flex justify-between rounded bg-muted p-2">
              <span className="text-muted-foreground">Buy Ratio</span>
              <span className="font-mono-numbers">{signal.buy_ratio_1h.toFixed(0)}%</span>
            </div>
          </div>
        </div>

        {signal.flags.length > 0 && (
          <>
            <Separator />
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-muted-foreground">Flags</h4>
              <div className="flex flex-wrap gap-1">
                {signal.flags.map((flag) => (
                  <Badge key={flag} variant="warning" className="text-[10px]">
                    {flag}
                  </Badge>
                ))}
              </div>
            </div>
          </>
        )}

        <Separator />

        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">Chart</h4>
          <div className="flex h-48 items-center justify-center rounded-lg border border-border-muted bg-muted">
            <span className="text-xs text-muted-foreground">
              Chart loads with live data
            </span>
          </div>
        </div>
      </div>

      <div className="border-t border-border p-4">
        <div className="grid grid-cols-4 gap-2">
          {[0.1, 0.25, 0.5, 1].map((amount) => (
            <Button key={amount} variant="outline" size="sm" className="font-mono-numbers text-xs">
              {amount} SOL
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
}
