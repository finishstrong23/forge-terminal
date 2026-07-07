"use client";

import React, { useState } from "react";
import Link from "next/link";
import { KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiForgotPassword } from "@/lib/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await apiForgotPassword(email);
      setSent(true);
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
          <h1 className="text-lg font-bold text-foreground">Reset password</h1>
          <p className="text-center text-xs text-muted-foreground">
            Enter your account email and we&apos;ll send a reset link.
          </p>
        </div>

        {sent ? (
          <div className="rounded border border-green-400/30 bg-green-400/10 px-3 py-2 text-xs text-green-400">
            If that email exists, a reset link is on its way. Check your inbox.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label htmlFor="email" className="mb-1 block text-xs text-muted-foreground">
                Email
              </label>
              <Input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>
            {error && (
              <div className="rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-400">
                {error}
              </div>
            )}
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "Sending..." : "Send reset link"}
            </Button>
          </form>
        )}

        <div className="mt-4 text-center">
          <Link
            href="/login"
            className="text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            Back to sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
