import Link from "next/link";
import { ArrowRight, Radar, ShieldCheck, Users, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";

export const metadata = { title: "How it works — Forge Terminal" };

const STEPS = [
  {
    icon: Radar,
    step: "1",
    title: "Discover",
    href: "/discovery",
    linkLabel: "Open the Discovery feed",
    body:
      "Thousands of tokens launch on pump.fun every day; most are rugs. " +
      "The Discovery feed scores every launch in real time — momentum, " +
      "rug risk, holder quality — so you look at ten tokens instead of " +
      "three thousand.",
  },
  {
    icon: Users,
    step: "2",
    title: "Shadow-follow the winners",
    href: "/copy",
    linkLabel: "Open the wallet leaderboard",
    body:
      "The leaderboard ranks wallets by sustained, un-gamed performance " +
      "(coordinated wallet clusters are detected and flagged). Follow a " +
      "wallet in shadow mode and a simulated ledger shows exactly what " +
      "copying them would have earned — every trade, every skip, every " +
      "reason — before you risk a cent.",
  },
  {
    icon: Zap,
    step: "3",
    title: "Execute on your terms",
    href: "/execute",
    linkLabel: "Open the swap ticket",
    body:
      "When you're ready, trade with your own wallet via Jupiter routing. " +
      "You sign every transaction; Forge never holds your keys or funds. " +
      "Positions and PnL land in your Portfolio automatically, stamped " +
      "with the risk scores at the moment you traded.",
  },
];

export default function HowItWorksPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 py-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-foreground">How Forge works</h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
          A terminal for trading memecoins without donating to rug-pullers:
          find real momentum, verify who actually wins, then trade from your
          own wallet.
        </p>
      </div>

      <ol className="space-y-4">
        {STEPS.map((s) => (
          <li key={s.step} className="rounded-lg border border-border bg-surface p-5">
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/10 font-mono-numbers text-sm font-bold text-accent">
                {s.step}
              </span>
              <s.icon className="h-4 w-4 text-accent" />
              <h2 className="text-sm font-semibold text-foreground">{s.title}</h2>
            </div>
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{s.body}</p>
            <Link
              href={s.href}
              className="mt-3 inline-flex items-center gap-1 text-xs text-accent hover:underline"
            >
              {s.linkLabel}
              <ArrowRight className="h-3 w-3" />
            </Link>
          </li>
        ))}
      </ol>

      <div className="rounded-lg border border-border bg-surface p-5">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-green-400" />
          <h2 className="text-sm font-semibold text-foreground">Non-custodial, always</h2>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          Forge never asks for your seed phrase and never holds your funds.
          Every swap is signed in your own wallet. Memecoin trading remains
          high-risk — read the{" "}
          <Link href="/disclaimer" className="underline hover:text-foreground">
            Risk Disclosure
          </Link>{" "}
          before trading.
        </p>
      </div>

      <div className="flex justify-center gap-3">
        <Button asChild>
          <Link href="/login">Create a free account</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/pricing">See pricing</Link>
        </Button>
      </div>
    </div>
  );
}
