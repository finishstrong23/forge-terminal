"use client";

/**
 * Topbar wallet button. Wraps WalletMultiButton so that:
 * - disconnected state keeps the "Connect Wallet" label (product copy +
 *   existing e2e assertions), while connected state shows the truncated
 *   address that the adapter renders by default;
 * - it's loaded client-side only (the adapter reads `window`), with a
 *   lookalike placeholder during SSR/hydration.
 */
import React from "react";
import dynamic from "next/dynamic";
import { Wallet } from "lucide-react";
import { useWallet } from "@solana/wallet-adapter-react";

const WalletMultiButton = dynamic(
  async () =>
    (await import("@solana/wallet-adapter-react-ui")).WalletMultiButton,
  {
    ssr: false,
    loading: () => (
      <button className="inline-flex h-8 items-center gap-2 rounded-md border border-border px-3 text-xs font-medium text-foreground">
        <Wallet className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Connect Wallet</span>
      </button>
    ),
  },
);

export function WalletButton() {
  const { connected } = useWallet();
  return (
    <WalletMultiButton
      style={{
        height: "2rem",
        fontSize: "0.75rem",
        borderRadius: "0.375rem",
        padding: "0 0.75rem",
        background: "transparent",
        border: "1px solid var(--border, #333)",
        lineHeight: "2rem",
      }}
    >
      {!connected && (
        <>
          <Wallet className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Connect Wallet</span>
        </>
      )}
    </WalletMultiButton>
  );
}
