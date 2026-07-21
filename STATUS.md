# STATUS — forge-terminal

> Updated: 2026-07-21

## Current phase
P1 "Credibility" shipped and verifying in production; P2 "Prove it" is
accumulating a week of wallet-score data before the paid P3 beta (Stripe,
~$49/mo Pro tier).

## Last shipped
2026-07-21 — tightened raw-event retention to 2 hours to keep the Postgres
volume small. Capped a week of production hardening: retry-storm root-cause
fix, bounded webhook queue, full-app security audit fixes, P3 prep (pricing
page, daily loss cap, refresh tokens).

## Next action
Verify the P1 exit test in production (feed shows real names/images/prices,
uptime monitor green), then run TESTING.md sections A–G as P2 data accumulates.

## Blockers
- None technical.

## Waiting on
- A week of accumulated wallet scores (P2 exit condition).
- Lawyer legal review before Stripe goes live (P3 gate).

## Notes
Revenue math: break-even ≈ 2 Pro subscribers. Running cost ~$5/mo now,
~$55–75/mo at P3 (Helius paid tier + Railway overage). Roadmap and exit
tests live in ROADMAP.md; launch verification in TESTING.md.
