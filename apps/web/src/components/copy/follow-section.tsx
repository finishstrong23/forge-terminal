"use client";

import React, { useState } from "react";
import Link from "next/link";
import { UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { createSubscription } from "@/lib/copy-subscriptions";

interface FollowSectionProps {
  walletAddress: string;
}

/**
 * Shadow-follow block for the wallet detail panel.
 *
 * Signed out → prompt with a /login link. Signed in → optional risk
 * params + Follow button. Whether the caller already follows the wallet
 * is discovered on submit: the backend answers 409 with a readable
 * message rather than the panel pre-fetching the subscription list.
 */
export function FollowSection({ walletAddress }: FollowSectionProps) {
  const { user } = useAuth();
  const [maxPosition, setMaxPosition] = useState("");
  const [minScore, setMinScore] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [followed, setFollowed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user) {
    return (
      <div className="rounded-lg border border-border bg-background px-3 py-2 text-xs text-muted-foreground">
        <Link href="/login" className="text-accent hover:underline">
          Sign in
        </Link>{" "}
        to follow this wallet and build a shadow ledger.
      </div>
    );
  }

  if (followed) {
    return (
      <div className="rounded-lg border border-green-400/30 bg-green-400/10 px-3 py-2 text-xs text-green-400">
        Following in shadow mode — trades will appear in your{" "}
        <Link href="/portfolio" className="underline">
          Portfolio
        </Link>
        .
      </div>
    );
  }

  const handleFollow = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const maxPos = parseFloat(maxPosition);
      const min = parseFloat(minScore);
      await createSubscription({
        wallet_address: walletAddress,
        ...(Number.isFinite(maxPos) && maxPos > 0 ? { max_position_usd: maxPos } : {}),
        ...(Number.isFinite(min) ? { min_sustainability_score: min } : {}),
      });
      setFollowed(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-2 rounded-lg border border-border bg-background p-3">
      <h4 className="text-xs font-semibold text-foreground">Follow (shadow mode)</h4>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label
            htmlFor="follow-max-position"
            className="mb-1 block text-[10px] text-muted-foreground"
          >
            Max position USD
          </label>
          <Input
            id="follow-max-position"
            type="number"
            min="0"
            placeholder="optional"
            value={maxPosition}
            onChange={(e) => setMaxPosition(e.target.value)}
            className="h-7 text-xs"
          />
        </div>
        <div>
          <label
            htmlFor="follow-min-score"
            className="mb-1 block text-[10px] text-muted-foreground"
          >
            Min sustainability
          </label>
          <Input
            id="follow-min-score"
            type="number"
            min="0"
            max="100"
            placeholder="optional"
            value={minScore}
            onChange={(e) => setMinScore(e.target.value)}
            className="h-7 text-xs"
          />
        </div>
      </div>
      {error && (
        <div className="rounded border border-red-400/30 bg-red-400/10 px-2 py-1.5 text-xs text-red-400">
          {error}
        </div>
      )}
      <Button
        size="sm"
        className="w-full gap-2"
        onClick={handleFollow}
        disabled={submitting}
      >
        <UserPlus className="h-3.5 w-3.5" />
        {submitting ? "Following..." : "Follow wallet"}
      </Button>
      <p className="text-[10px] text-muted-foreground">
        Shadow mode records what copy execution would do — no funds move.
      </p>
    </div>
  );
}
