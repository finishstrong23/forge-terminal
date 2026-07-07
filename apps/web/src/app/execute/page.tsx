"use client";

import React, { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ExternalLink, Zap } from "lucide-react";
import { VersionedTransaction } from "@solana/web3.js";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/useAuth";
import {
  base64ToBytes,
  buildSwapTransaction,
  fetchQuote,
  fetchSolPrice,
  recordManualTrade,
  type SwapQuote,
  type SwapSide,
} from "@/lib/execute";
import { cn } from "@/lib/utils";

const SLIPPAGE_OPTIONS = [50, 100, 300];
const QUOTE_DEBOUNCE_MS = 600;

/** Pump.fun mints use 6 decimals; the ticket says so rather than guessing silently. */
const ASSUMED_DECIMALS = 6;

export default function ExecutePage() {
  // useSearchParams requires a Suspense boundary for static prerendering.
  return (
    <Suspense fallback={<Skeleton className="h-32 w-full rounded-md" />}>
      <ExecuteContent />
    </Suspense>
  );
}

function ExecuteContent() {
  const { connection } = useConnection();
  const { publicKey, connected, sendTransaction } = useWallet();
  const { user } = useAuth();
  const searchParams = useSearchParams();

  // Buy buttons on Discovery rows land here as /execute?mint=<address>.
  const [outputMint, setOutputMint] = useState(searchParams.get("mint") ?? "");
  const [side, setSide] = useState<SwapSide>("buy");
  const [amountSol, setAmountSol] = useState("");
  const [slippageBps, setSlippageBps] = useState(100);
  const [solPrice, setSolPrice] = useState<number | null>(null);
  const [quote, setQuote] = useState<SwapQuote | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [quoting, setQuoting] = useState(false);
  const [swapping, setSwapping] = useState(false);
  const [result, setResult] = useState<{ signature: string } | null>(null);
  const [swapError, setSwapError] = useState<string | null>(null);

  useEffect(() => {
    fetchSolPrice().then(setSolPrice).catch(() => setSolPrice(null));
  }, []);

  // Debounced quoting whenever the ticket inputs change.
  useEffect(() => {
    setQuote(null);
    setQuoteError(null);
    setResult(null);
    const amount = parseFloat(amountSol);
    if (!outputMint || outputMint.length < 32 || !Number.isFinite(amount) || amount <= 0) {
      return;
    }
    let cancelled = false;
    setQuoting(true);
    const timer = setTimeout(() => {
      fetchQuote({ tokenMint: outputMint, side, amount, slippageBps })
        .then((q) => {
          if (!cancelled) setQuote(q);
        })
        .catch((err) => {
          if (!cancelled) setQuoteError(err instanceof Error ? err.message : String(err));
        })
        .finally(() => {
          if (!cancelled) setQuoting(false);
        });
    }, QUOTE_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [outputMint, amountSol, slippageBps, side]);

  const handleSwap = useCallback(async () => {
    if (!quote?.quote_response || !publicKey) return;
    setSwapping(true);
    setSwapError(null);
    try {
      const built = await buildSwapTransaction(quote.quote_response, publicKey.toBase58());
      const tx = VersionedTransaction.deserialize(base64ToBytes(built.swap_transaction));
      const signature = await sendTransaction(tx, connection);
      setResult({ signature });
      if (user) {
        // Best-effort ledger entry; the swap succeeded regardless.
        // For sells, SOL amount = the quoted SOL received (exact 9 dp).
        const solAmount =
          side === "buy"
            ? parseFloat(amountSol)
            : Number(quote.out_amount ?? 0) / 1e9;
        void recordManualTrade({
          token_address: side === "buy" ? quote.output_mint : quote.input_mint,
          trade_type: side,
          sol_amount: solAmount,
          signature,
          slippage_bps: slippageBps,
        }).catch(() => undefined);
      }
    } catch (err) {
      setSwapError(err instanceof Error ? err.message : String(err));
    } finally {
      setSwapping(false);
    }
  }, [quote, publicKey, sendTransaction, connection, user, amountSol, slippageBps, side]);

  const amount = parseFloat(amountSol);
  const usdEstimate =
    side === "buy" && solPrice !== null && Number.isFinite(amount) && amount > 0
      ? amount * solPrice
      : null;
  // Buys receive tokens (assumed decimals); sells receive SOL (exact 9 dp).
  const estimatedTokens =
    side === "buy" && quote?.out_amount != null
      ? Number(quote.out_amount) / 10 ** ASSUMED_DECIMALS
      : null;
  const estimatedSol =
    side === "sell" && quote?.out_amount != null
      ? Number(quote.out_amount) / 1e9
      : null;

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Zap className="h-5 w-5 text-accent" />
          <h1 className="text-lg font-bold text-foreground">Execute</h1>
          <Badge variant="warning" className="text-[10px]">NON-CUSTODIAL</Badge>
        </div>
        <span className="font-mono-numbers text-xs text-muted-foreground">
          SOL {solPrice !== null ? `$${solPrice.toFixed(2)}` : "—"}
        </span>
      </div>

      <div className="space-y-3 rounded-lg border border-border bg-surface p-4">
        <div className="flex rounded-md border border-border p-0.5">
          {(["buy", "sell"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSide(s)}
              className={cn(
                "flex-1 rounded px-2 py-1.5 text-xs font-medium uppercase transition-colors",
                s === side
                  ? s === "buy"
                    ? "bg-green-400/15 text-green-400"
                    : "bg-red-400/15 text-red-400"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {s}
            </button>
          ))}
        </div>

        <div>
          <label htmlFor="mint" className="mb-1 block text-xs text-muted-foreground">
            Token mint address
          </label>
          <Input
            id="mint"
            value={outputMint}
            onChange={(e) => setOutputMint(e.target.value.trim())}
            placeholder="Paste a token address from Discovery"
            className="font-mono text-xs"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="amount" className="mb-1 block text-xs text-muted-foreground">
              {side === "buy" ? "Amount (SOL)" : "Amount (tokens)"}
            </label>
            <Input
              id="amount"
              type="number"
              min="0"
              step="0.1"
              value={amountSol}
              onChange={(e) => setAmountSol(e.target.value)}
              placeholder={side === "buy" ? "0.5" : "1000"}
            />
            {usdEstimate !== null && (
              <span className="mt-1 block font-mono-numbers text-[10px] text-muted-foreground">
                ≈ ${usdEstimate.toFixed(2)}
              </span>
            )}
          </div>
          <div>
            <span className="mb-1 block text-xs text-muted-foreground">Slippage</span>
            <div className="flex rounded-md border border-border p-0.5">
              {SLIPPAGE_OPTIONS.map((bps) => (
                <button
                  key={bps}
                  onClick={() => setSlippageBps(bps)}
                  className={cn(
                    "flex-1 rounded px-2 py-1.5 font-mono-numbers text-xs transition-colors",
                    bps === slippageBps
                      ? "bg-accent/15 text-accent"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {(bps / 100).toFixed(1)}%
                </button>
              ))}
            </div>
          </div>
        </div>

        {quoting && (
          <p className="text-xs text-muted-foreground">Fetching quote…</p>
        )}
        {quoteError && (
          <div className="rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-400">
            {quoteError}
          </div>
        )}
        {quote && (
          <div className="space-y-1 rounded-lg border border-border bg-background p-3 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Estimated received</span>
              <span className="font-mono-numbers">
                {side === "buy"
                  ? estimatedTokens !== null
                    ? `≈ ${estimatedTokens.toLocaleString(undefined, { maximumFractionDigits: 2 })} tokens`
                    : "—"
                  : estimatedSol !== null
                    ? `${estimatedSol.toFixed(4)} SOL${
                        solPrice !== null ? ` (≈ $${(estimatedSol * solPrice).toFixed(2)})` : ""
                      }`
                    : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Price impact</span>
              <span className="font-mono-numbers">
                {quote.price_impact_pct != null
                  ? `${(Number(quote.price_impact_pct) * 100).toFixed(3)}%`
                  : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Route</span>
              <span>{quote.route_labels.filter(Boolean).join(" → ") || "—"}</span>
            </div>
            {side === "buy" && (
              <p className="pt-1 text-[10px] text-muted-foreground">
                Token amount assumes {ASSUMED_DECIMALS} decimals — verify the
                exact amount in your wallet before signing.
              </p>
            )}
          </div>
        )}

        {swapError && (
          <div className="rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-400">
            {swapError}
          </div>
        )}
        {result && (
          <div className="rounded border border-green-400/30 bg-green-400/10 px-3 py-2 text-xs text-green-400">
            Transaction sent —{" "}
            <a
              href={`https://solscan.io/tx/${result.signature}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 underline"
            >
              view on Solscan <ExternalLink className="h-3 w-3" />
            </a>
            {user ? " · recorded in your trades" : ""}
          </div>
        )}

        <Button
          className="w-full"
          disabled={!connected || !quote || swapping}
          onClick={handleSwap}
        >
          {swapping
            ? "Waiting for wallet…"
            : !connected
              ? "Connect a wallet to swap"
              : !quote
                ? "Enter a token and amount"
                : "Swap"}
        </Button>
        <p className="text-[10px] text-muted-foreground">
          You sign in your own wallet; Forge never holds keys or funds. Quotes
          via Jupiter.
        </p>
      </div>
    </div>
  );
}
