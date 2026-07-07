"use client";

/**
 * useLeaderboard — React hook that polls the copy-intelligence leaderboard.
 *
 * State machine (simpler than useDiscoveryFeed — REST only, no WS):
 *   loading → initial mount or window/filter change, first fetch in flight
 *   ready   → last fetch succeeded, polling every LEADERBOARD_POLL_MS
 *   offline → a fetch failed; stale rows (if any) stay visible, polling continues
 *
 * The effect re-runs when window or excludeClustered changes, resetting to
 * loading so the UI shows a skeleton instead of rows from the old window.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import {
  LEADERBOARD_POLL_MS,
  fetchLeaderboard,
  type LeaderboardWindow,
  type WalletRow,
} from "@/lib/copy-leaderboard";

export type LeaderboardStatus = "loading" | "ready" | "offline";

export interface UseLeaderboard {
  wallets: WalletRow[];
  status: LeaderboardStatus;
  error: string | null;
  refresh: () => Promise<void>;
  refreshing: boolean;
  lastUpdated: Date | null;
}

export function useLeaderboard(
  window: LeaderboardWindow,
  excludeClustered: boolean,
): UseLeaderboard {
  const [wallets, setWallets] = useState<WalletRow[]>([]);
  const [status, setStatus] = useState<LeaderboardStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const refreshingRef = useRef(false);

  // Manual refresh button — one immediate fetch, doesn't reset the poll timer.
  const refresh = useCallback(async () => {
    if (refreshingRef.current) return;
    refreshingRef.current = true;
    setRefreshing(true);
    try {
      const rows = await fetchLeaderboard({ window, excludeClustered });
      setWallets(rows);
      setLastUpdated(new Date());
      setError(null);
      setStatus("ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus("offline");
    } finally {
      refreshingRef.current = false;
      setRefreshing(false);
    }
  }, [window, excludeClustered]);

  useEffect(() => {
    let unmounted = false;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;

    setStatus("loading");
    setWallets([]);

    const tick = async () => {
      try {
        const rows = await fetchLeaderboard({ window, excludeClustered });
        if (unmounted) return;
        setWallets(rows);
        setLastUpdated(new Date());
        setError(null);
        setStatus("ready");
      } catch (err) {
        if (unmounted) return;
        setError(err instanceof Error ? err.message : String(err));
        setStatus("offline");
      }
      if (!unmounted) {
        pollTimer = setTimeout(tick, LEADERBOARD_POLL_MS);
      }
    };

    void tick();

    return () => {
      unmounted = true;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [window, excludeClustered]);

  return { wallets, status, error, refresh, refreshing, lastUpdated };
}
