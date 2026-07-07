"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Flame } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { apiVerifyEmail } from "@/lib/auth";
import { useAuth, type AuthMode } from "@/hooks/useAuth";

export default function LoginPage() {
  // useSearchParams requires a Suspense boundary for static prerendering.
  return (
    <Suspense fallback={<Skeleton className="h-32 w-full rounded-md" />}>
      <LoginContent />
    </Suspense>
  );
}

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { signIn } = useAuth();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [verifyState, setVerifyState] = useState<"idle" | "ok" | "failed">("idle");

  // Emailed verification links land here as /login?verify_token=...
  const verifyToken = searchParams.get("verify_token");
  useEffect(() => {
    if (!verifyToken) return;
    let unmounted = false;
    apiVerifyEmail(verifyToken)
      .then(() => {
        if (!unmounted) setVerifyState("ok");
      })
      .catch(() => {
        if (!unmounted) setVerifyState("failed");
      });
    return () => {
      unmounted = true;
    };
  }, [verifyToken]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn(email, password, mode);
      router.push("/discovery");
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
            <Flame className="h-6 w-6 text-accent" />
          </div>
          <h1 className="text-lg font-bold text-foreground">
            {mode === "login" ? "Sign in" : "Create account"}
          </h1>
          <p className="text-center text-xs text-muted-foreground">
            {mode === "login"
              ? "Welcome back to Forge Terminal."
              : "Follow top wallets and build your shadow ledger."}
          </p>
        </div>

        {verifyState === "ok" && (
          <div className="mb-3 rounded border border-green-400/30 bg-green-400/10 px-3 py-2 text-xs text-green-400">
            Email verified — sign in below.
          </div>
        )}
        {verifyState === "failed" && (
          <div className="mb-3 rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-400">
            That verification link is invalid or expired.
          </div>
        )}

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
          <div>
            <label htmlFor="password" className="mb-1 block text-xs text-muted-foreground">
              Password
            </label>
            <Input
              id="password"
              type="password"
              required
              minLength={8}
              maxLength={72}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "register" ? "At least 8 characters" : "••••••••"}
            />
          </div>

          {error && (
            <div className="rounded border border-red-400/30 bg-red-400/10 px-3 py-2 text-xs text-red-400">
              {error}
            </div>
          )}

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting
              ? "Working..."
              : mode === "login"
                ? "Sign in"
                : "Create account"}
          </Button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode((m) => (m === "login" ? "register" : "login"));
            setError(null);
          }}
          className="mt-4 w-full text-center text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          {mode === "login"
            ? "No account? Create one"
            : "Already have an account? Sign in"}
        </button>

        {mode === "login" && (
          <div className="mt-2 text-center">
            <Link
              href="/forgot-password"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Forgot password?
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
