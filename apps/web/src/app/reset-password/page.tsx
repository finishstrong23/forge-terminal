"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { apiResetPassword } from "@/lib/auth";

export default function ResetPasswordPage() {
  // useSearchParams requires a Suspense boundary for static prerendering.
  return (
    <Suspense fallback={<Skeleton className="h-32 w-full rounded-md" />}>
      <ResetPasswordContent />
    </Suspense>
  );
}

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await apiResetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex h-full items-center justify-center py-16">
      <div className="w-full max-w-sm rounded-lg border border-border bg-surface p-6">
        <div className="mb-6 flex flex-col items-center gap-2">
          <div className="rounded-full bg-accent/10 p-3">
            <KeyRound className="h-6 w-6 text-accent" />
          </div>
          <h1 className="text-lg font-bold text-foreground">Choose a new password</h1>
        </div>

        {!token ? (
          <div className="rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-400">
            This page needs the link from your reset email.
          </div>
        ) : done ? (
          <div className="space-y-4">
            <div className="rounded border border-green-400/30 bg-green-400/10 px-3 py-2 text-xs text-green-400">
              Password updated.
            </div>
            <Button className="w-full" asChild>
              <Link href="/login">Sign in</Link>
            </Button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label htmlFor="password" className="mb-1 block text-xs text-muted-foreground">
                New password
              </label>
              <Input
                id="password"
                type="password"
                required
                minLength={8}
                maxLength={72}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
              />
            </div>
            {error && (
              <div className="rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-400">
                {error}
              </div>
            )}
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "Saving..." : "Set new password"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
