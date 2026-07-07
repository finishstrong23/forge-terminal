"use client";

/**
 * Solana wallet plumbing (M3 — non-custodial).
 *
 * ConnectionProvider points at NEXT_PUBLIC_SOLANA_RPC_URL (falls back to
 * the public mainnet endpoint, which is fine for sending the occasional
 * user-signed transaction but rate-limited — set a real RPC in prod).
 * Wallet-standard wallets (Phantom, Solflare, Backpack…) are auto-detected;
 * the explicit Phantom adapter covers older extension versions.
 */
import React, { useMemo } from "react";
import { clusterApiUrl } from "@solana/web3.js";
import {
  ConnectionProvider,
  WalletProvider,
} from "@solana/wallet-adapter-react";
import { WalletModalProvider } from "@solana/wallet-adapter-react-ui";
import { PhantomWalletAdapter } from "@solana/wallet-adapter-phantom";

import "@solana/wallet-adapter-react-ui/styles.css";

export function SolanaProvider({ children }: { children: React.ReactNode }) {
  const endpoint =
    process.env.NEXT_PUBLIC_SOLANA_RPC_URL || clusterApiUrl("mainnet-beta");
  const wallets = useMemo(() => [new PhantomWalletAdapter()], []);

  return (
    <ConnectionProvider endpoint={endpoint}>
      <WalletProvider wallets={wallets} autoConnect>
        <WalletModalProvider>{children}</WalletModalProvider>
      </WalletProvider>
    </ConnectionProvider>
  );
}
