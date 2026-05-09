"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Radar } from "lucide-react";
import { SignalTable, type TokenSignal } from "@/components/discovery/signal-table";
import { FilterBar, type FilterState } from "@/components/discovery/filter-bar";
import { SignalDetailPanel } from "@/components/discovery/signal-detail-panel";
import { Badge } from "@/components/ui/badge";

const DEMO_SIGNALS: TokenSignal[] = [
  {
    id: "1",
    symbol: "FORGE",
    name: "Forge Protocol",
    token_address: "FoRGe1111111111111111111111111111111111111",
    price_usd: 0.00042,
    market_cap: 42000,
    volume_1h: 15200,
    liquidity_usd: 8500,
    rug_risk_score: 22,
    momentum_score: 78,
    confidence_score: 85,
    age_minutes: 45,
    holder_count: 127,
    buy_ratio_1h: 72,
    is_honeypot: false,
    flags: [],
  },
  {
    id: "2",
    symbol: "BLAZE",
    name: "Blaze Token",
    token_address: "BLAZe2222222222222222222222222222222222222",
    price_usd: 0.0013,
    market_cap: 130000,
    volume_1h: 45000,
    liquidity_usd: 22000,
    rug_risk_score: 15,
    momentum_score: 92,
    confidence_score: 91,
    age_minutes: 120,
    holder_count: 342,
    buy_ratio_1h: 81,
    is_honeypot: false,
    flags: [],
  },
  {
    id: "3",
    symbol: "RUGGED",
    name: "Rug Example",
    token_address: "RUGGd3333333333333333333333333333333333333",
    price_usd: 0.000001,
    market_cap: 500,
    volume_1h: 200,
    liquidity_usd: 150,
    rug_risk_score: 89,
    momentum_score: 12,
    confidence_score: 45,
    age_minutes: 5,
    holder_count: 3,
    buy_ratio_1h: 15,
    is_honeypot: true,
    flags: ["LOW_LIQ", "TOO_NEW", "SELL_PRESSURE"],
  },
  {
    id: "4",
    symbol: "EMBER",
    name: "Emberwake",
    token_address: "EMBRw4444444444444444444444444444444444444",
    price_usd: 0.0089,
    market_cap: 890000,
    volume_1h: 120000,
    liquidity_usd: 95000,
    rug_risk_score: 8,
    momentum_score: 85,
    confidence_score: 94,
    age_minutes: 360,
    holder_count: 1240,
    buy_ratio_1h: 68,
    is_honeypot: false,
    flags: [],
  },
  {
    id: "5",
    symbol: "NOVA",
    name: "Nova Finance",
    token_address: "NOVAf5555555555555555555555555555555555555",
    price_usd: 0.025,
    market_cap: 2500000,
    volume_1h: 380000,
    liquidity_usd: 420000,
    rug_risk_score: 5,
    momentum_score: 71,
    confidence_score: 97,
    age_minutes: 1440,
    holder_count: 5600,
    buy_ratio_1h: 55,
    is_honeypot: false,
    flags: [],
  },
  {
    id: "6",
    symbol: "PUMP",
    name: "PumpCoin",
    token_address: "PUMPc6666666666666666666666666666666666666",
    price_usd: 0.00078,
    market_cap: 78000,
    volume_1h: 32000,
    liquidity_usd: 12000,
    rug_risk_score: 35,
    momentum_score: 65,
    confidence_score: 72,
    age_minutes: 90,
    holder_count: 89,
    buy_ratio_1h: 62,
    is_honeypot: false,
    flags: ["SPIKE_1H"],
  },
  {
    id: "7",
    symbol: "VOID",
    name: "Void Protocol",
    token_address: "VOIDp7777777777777777777777777777777777777",
    price_usd: 0.0032,
    market_cap: 320000,
    volume_1h: 85000,
    liquidity_usd: 55000,
    rug_risk_score: 18,
    momentum_score: 88,
    confidence_score: 89,
    age_minutes: 210,
    holder_count: 670,
    buy_ratio_1h: 74,
    is_honeypot: false,
    flags: [],
  },
  {
    id: "8",
    symbol: "SHARD",
    name: "Shard Network",
    token_address: "SHRDn8888888888888888888888888888888888888",
    price_usd: 0.00015,
    market_cap: 15000,
    volume_1h: 4500,
    liquidity_usd: 3200,
    rug_risk_score: 52,
    momentum_score: 45,
    confidence_score: 60,
    age_minutes: 25,
    holder_count: 28,
    buy_ratio_1h: 48,
    is_honeypot: false,
    flags: ["TOO_NEW"],
  },
];

const defaultFilters: FilterState = {
  minLiquidity: "",
  maxAge: "",
  minMomentum: "",
  maxRugRisk: "",
  hideHoneypots: true,
  search: "",
};

export default function DiscoveryPage() {
  const [signals, setSignals] = useState<TokenSignal[]>(DEMO_SIGNALS);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<FilterState>(defaultFilters);
  const [selectedSignal, setSelectedSignal] = useState<TokenSignal | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(new Date());

  const filteredSignals = React.useMemo(() => {
    return signals.filter((s) => {
      if (filters.hideHoneypots && s.is_honeypot) return false;
      if (filters.search) {
        const q = filters.search.toLowerCase();
        if (
          !s.symbol.toLowerCase().includes(q) &&
          !s.name.toLowerCase().includes(q)
        )
          return false;
      }
      if (filters.minLiquidity) {
        const v = parseFloat(filters.minLiquidity);
        if (!isNaN(v) && s.liquidity_usd < v) return false;
      }
      if (filters.maxAge) {
        const v = parseFloat(filters.maxAge) * 60;
        if (!isNaN(v) && s.age_minutes > v) return false;
      }
      if (filters.minMomentum) {
        const v = parseFloat(filters.minMomentum);
        if (!isNaN(v) && s.momentum_score < v) return false;
      }
      if (filters.maxRugRisk) {
        const v = parseFloat(filters.maxRugRisk);
        if (!isNaN(v) && s.rug_risk_score > v) return false;
      }
      return true;
    });
  }, [signals, filters]);

  const handleRefresh = useCallback(() => {
    setLoading(true);
    setTimeout(() => {
      setLastUpdated(new Date());
      setLoading(false);
    }, 600);
  }, []);

  return (
    <div className="flex h-full gap-0">
      <div className="flex flex-1 flex-col gap-4 overflow-hidden">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Radar className="h-5 w-5 text-accent" />
            <h1 className="text-lg font-bold text-foreground">Discovery</h1>
            <Badge variant="outline" className="font-mono-numbers">
              {filteredSignals.length} tokens
            </Badge>
          </div>
          <Badge variant="default" className="animate-pulse-glow">
            LIVE
          </Badge>
        </div>

        <FilterBar
          filters={filters}
          onChange={setFilters}
          onRefresh={handleRefresh}
          lastUpdated={lastUpdated}
        />

        <div className="flex-1 overflow-y-auto">
          <SignalTable
            data={filteredSignals}
            loading={loading}
            onRowClick={setSelectedSignal}
          />
        </div>
      </div>

      {selectedSignal && (
        <SignalDetailPanel
          signal={selectedSignal}
          onClose={() => setSelectedSignal(null)}
        />
      )}
    </div>
  );
}
