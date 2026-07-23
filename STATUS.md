# STATUS — forge-terminal

> Updated: 2026-07-23

## Current phase
Pre-launch, **path-to-first-revenue**. Running lean on Helius free tier in
poll-only mode. Plan: finish the launch-gating chores (legal review, Stripe
config, domain/email), then flip on the paid Helius tier + firehose at
launch to relight Copy Intelligence and open the paid "Intelligence Beta".

## Last shipped
2026-07-23 — Helius credit control: `WEBHOOK_ENABLED` flag (poll-only mode
deletes the firehose webhook to cut ~97% of credit spend) + env-tunable
poll cadences. Removed four unenforced tier-cap settings. Prior: retry-storm
+ queue-starvation + Postgres disk-full root-cause fixes, full security
audit, Postgres rebuilt.

## Important: Copy Intelligence is dormant
Poll-only mode means `WalletActivity` stops updating (it's fed only by the
webhook firehose), so the leaderboard, wallet scoring, and shadow trades go
stale. This is a deliberate cost decision — Discovery still works. Copy
Intelligence relights automatically when `WEBHOOK_ENABLED=true` on a paid
Helius tier at launch.

## Next action
Verify the M3 exit test in prod (dust swap on /execute → position on
/portfolio) in poll-only mode. In parallel, start the launch-gating chores
(legal review first — longest lead).

## Blockers
- None technical.

## Waiting on (launch gates)
- Qualified-counsel review of the template legal pages (hard gate before
  charging).
- Stripe live config (dashboard Products/Prices + env vars).
- Domain + SMTP; paid Helius tier (flip at launch).

## Notes
Revenue math: break-even ≈ 2 Pro subscribers (~$49/mo). Cost ~$5/mo now,
~$55–75/mo at launch (paid Helius + Railway). Full plan in
`~/.claude/plans/agile-plotting-melody.md`; roadmap/exit tests in
ROADMAP.md; launch verification in TESTING.md.
