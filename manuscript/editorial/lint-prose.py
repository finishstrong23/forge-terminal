#!/usr/bin/env python3
"""Prose-tic linter for The Hollow Hunt revision.

Usage: python3 lint-prose.py [chapter-file ...]
With no args, lints every chapter in ../chapters and prints totals vs. budget.
"""
import re
import sys
from pathlib import Path

BUDGETS = {
    "specific": 60,
    "quality": 60,
    "register": 25,
    "the way": 90,
    "he looked at me": 30,
    "for a long moment": 6,
    "something": 250,
    "i filed": 0,
    "not a .*, not a .*, but": 15,  # "not X, not Y, but" machinery
}

def count(text, pattern):
    return len(re.findall(pattern, text, re.IGNORECASE))

def main():
    root = Path(__file__).resolve().parent.parent / "chapters"
    files = [Path(a) for a in sys.argv[1:]] or sorted(root.glob("[0-9][0-9]-*.md"))
    totals = {k: 0 for k in BUDGETS}
    words = 0
    for f in files:
        text = f.read_text()
        words += len(text.split())
        per = {k: count(text, k if ".*" in k else re.escape(k)) for k in BUDGETS}
        for k, v in per.items():
            totals[k] += v
        worst = sorted((v, k) for k, v in per.items() if v)[-3:]
        print(f"{f.name:60s} {sum(per.values()):4d} tics  " +
              "  ".join(f"{k}:{v}" for v, k in reversed(worst)))
    print(f"\nTotal words: {words:,}")
    print(f"{'phrase':22s} {'count':>6s} {'budget':>7s}")
    over = False
    for k, budget in BUDGETS.items():
        flag = " OVER" if totals[k] > budget else ""
        if flag:
            over = True
        print(f"{k:22s} {totals[k]:6d} {budget:7d}{flag}")
    sys.exit(1 if over else 0)

if __name__ == "__main__":
    main()
