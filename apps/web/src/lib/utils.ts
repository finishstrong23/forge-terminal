import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toFixed(2);
}

export function formatUsd(n: number): string {
  return `$${formatNumber(n)}`;
}

export function truncateAddress(addr: string, chars = 4): string {
  return `${addr.slice(0, chars)}...${addr.slice(-chars)}`;
}

export function scoreColor(score: number, inverted = false): string {
  const effective = inverted ? 100 - score : score;
  if (effective >= 80) return "text-green-400";
  if (effective >= 60) return "text-cyan-400";
  if (effective >= 40) return "text-amber-400";
  return "text-red-400";
}

export function scoreBg(score: number, inverted = false): string {
  const effective = inverted ? 100 - score : score;
  if (effective >= 80) return "bg-green-400/10 border-green-400/20";
  if (effective >= 60) return "bg-cyan-400/10 border-cyan-400/20";
  if (effective >= 40) return "bg-amber-400/10 border-amber-400/20";
  return "bg-red-400/10 border-red-400/20";
}
