"use client";

/**
 * useDiscoveryFeed — React hook that orchestrates the discovery feed.
 *
 * State machine:
 *   loading  → initial mount, REST not yet returned, WS not yet connected
 *   live     → WS connected AND first message received (green badge)
 *   polling  → WS down, REST polling every POLL_INTERVAL_MS (amber badge)
 *   offline  → REST_FAILURES_BEFORE_OFFLINE consecutive REST failures (red badge)
 *
 * Transitions:
 *   loading → polling   after initial REST succeeds (waiting for WS first msg)
 *   polling → live      on WS first message
 *   live    → polling   on WS close (immediate)
 *   polling → offline   after REST_FAILURES_BEFORE_OFFLINE consecutive REST failures
 *   offline → polling   when a REST poll subsequently succeeds
 *   offline → live      when WS recovers and emits its first message
 *
 * The entire lifecycle lives in a single useEffect with mutable closure state.
 * No useCallback acrobatics — keeps the effect's deps array empty and avoids
 * stale-closure bugs that crop up when the WS/REST handlers each carry their
 * own status dependency.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import type { TokenSignal } from "@/components/discovery/signal-table";
import {
  POLL_BACKOFF_CAP_MS,
  POLL_INTERVAL_MS,
  REST_FAILURES_BEFORE_OFFLINE,
  WS_RECONNECT_BASE_MS,
  WS_RECONNECT_CAP_MS,
  discoveryWsUrl,
  fetchInitialFeed,
  mergeIncomingToken,
  normalizeToken,
  type FeedStatus,
} from "@/lib/discovery-feed";
import type { WsTokenEnvelope } from "@/lib/types";

export interface UseDiscoveryFeed {
  tokens: TokenSignal[];
  status: FeedStatus;
  error: string | null;
  refresh: () => Promise<void>;
  refreshing: boolean;
  lastUpdated: Date | null;
}

export function useDiscoveryFeed(): UseDiscoveryFeed {
  const [tokens, setTokens] = useState<TokenSignal[]>([]);
  const [status, setStatus] = useState<FeedStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const refreshingRef = useRef(false);

  // Manual refresh button — fetches the REST feed once. Does NOT touch WS state.
  const refresh = useCallback(async () => {
    if (refreshingRef.current) return;
    refreshingRef.current = true;
    setRefreshing(true);
    try {
      const next = await fetchInitialFeed(50);
      setTokens(next);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      refreshingRef.current = false;
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let unmounted = false;
    let ws: WebSocket | null = null;
    let wsAttempts = 0;
    let wsReconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;
    let pollInterval = POLL_INTERVAL_MS;
    let restFailures = 0;
    let wsConfirmed = false;

    const clearPoll = () => {
      if (pollTimer) {
        clearTimeout(pollTimer);
        pollTimer = null;
      }
    };

    const clearReconnect = () => {
      if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
      }
    };

    const onRestSuccess = (next: TokenSignal[]) => {
      if (unmounted) return;
      setTokens(next);
      setLastUpdated(new Date());
      setError(null);
      restFailures = 0;
      pollInterval = POLL_INTERVAL_MS;
      // If we were OFFLINE, recover to POLLING (WS will promote us to LIVE on next msg).
      setStatus((s) => (s === "offline" ? "polling" : s));
    };

    const onRestFailure = (err: unknown) => {
      if (unmounted) return;
      restFailures += 1;
      setError(err instanceof Error ? err.message : String(err));
      pollInterval = Math.min(pollInterval * 2, POLL_BACKOFF_CAP_MS);
      if (restFailures >= REST_FAILURES_BEFORE_OFFLINE) {
        setStatus("offline");
      }
    };

    const pollTick = async () => {
      if (unmounted || wsConfirmed) return;
      try {
        const next = await fetchInitialFeed(50);
        onRestSuccess(next);
      } catch (err) {
        onRestFailure(err);
      }
      if (!unmounted && !wsConfirmed) {
        pollTimer = setTimeout(pollTick, pollInterval);
      }
    };

    const startPolling = () => {
      clearPoll();
      if (wsConfirmed) return;
      pollTimer = setTimeout(pollTick, pollInterval);
    };

    const scheduleReconnect = () => {
      clearReconnect();
      const delay = Math.min(
        WS_RECONNECT_BASE_MS * Math.pow(2, wsAttempts),
        WS_RECONNECT_CAP_MS,
      );
      wsAttempts += 1;
      wsReconnectTimer = setTimeout(connectWs, delay);
    };

    const connectWs = () => {
      if (unmounted) return;
      try {
        ws = new WebSocket(discoveryWsUrl());
      } catch (err) {
        console.warn("[useDiscoveryFeed] WS construct failed:", err);
        scheduleReconnect();
        return;
      }

      ws.onopen = () => {
        // Reset attempts on a successful handshake; status flip waits for first msg.
        wsAttempts = 0;
      };

      ws.onmessage = (ev: MessageEvent) => {
        if (unmounted) return;
        try {
          const parsed = JSON.parse(ev.data as string) as WsTokenEnvelope;
          if (!parsed || parsed.type !== "token") return;
          const norm = normalizeToken(parsed.data);
          if (!norm) return;
          setTokens((prev) => mergeIncomingToken(prev, norm));
          setLastUpdated(new Date());
        } catch (err) {
          console.warn("[useDiscoveryFeed] WS message parse failed:", err);
          return;
        }
        if (!wsConfirmed) {
          wsConfirmed = true;
          clearPoll();
          restFailures = 0;
          pollInterval = POLL_INTERVAL_MS;
          setStatus("live");
          setError(null);
        }
      };

      ws.onerror = () => {
        // onclose will follow; do the work there.
      };

      ws.onclose = () => {
        ws = null;
        if (unmounted) return;
        wsConfirmed = false;
        // LIVE → POLLING (unless we're already OFFLINE from REST failures).
        setStatus((s) => (s === "offline" ? "offline" : "polling"));
        startPolling();
        scheduleReconnect();
      };
    };

    // Boot: initial REST fetch, then open the WS.
    (async () => {
      try {
        const initial = await fetchInitialFeed(50);
        if (unmounted) return;
        onRestSuccess(initial);
        // Transition out of LOADING into POLLING while WS handshake races.
        setStatus("polling");
      } catch (err) {
        if (unmounted) return;
        onRestFailure(err);
      }
      if (!unmounted) connectWs();
    })();

    return () => {
      unmounted = true;
      clearReconnect();
      clearPoll();
      if (ws) {
        try {
          ws.close();
        } catch {
          /* noop */
        }
        ws = null;
      }
    };
  }, []);

  return { tokens, status, error, refresh, refreshing, lastUpdated };
}
