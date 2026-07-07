# Forge Terminal — Launch Roadmap

Last updated: 2026-07-07 (PR #1 era). This is the working plan from "code
exists" to "people pay for it." Milestones are ordered by dependency, not
calendar. Each has an explicit exit test — a milestone isn't done until its
exit test passes in **production**, not localhost.

## Where things stand

| Layer | State |
|---|---|
| Discovery backend (webhook ingest, scoring, clustering, Celery pipeline) | Built, tested, deployed — **but pipeline liveness in prod is unverified** (see M0) |
| Discovery frontend (live feed, WS + polling) | Built, deployed |
| Copy Intelligence backend (leaderboard, score persistence/history, shadow recorder) | Built + tested on PR #1, **not yet in prod** |
| Copy Intelligence frontend (leaderboard UI, detail panel, sparkline) | Built + tested on PR #1, **not yet in prod** |
| Auth backend (JWT register/login/me) | Built + tested on PR #1, **not yet in prod** |
| Auth frontend (login UI, session state) | **Absent** |
| Copy subscriptions API (shadow follow, ledger) | Built + tested on PR #1, **not yet in prod** |
| Follow/ledger frontend | **Absent** |
| Execution layer (Jupiter swaps, wallet connect) | **Absent** (placeholder pages) |
| Billing (Stripe, tier enforcement) | **Absent** (config + models scaffolded) |
| CI (pytest + Playwright on every PR) | Live as of PR #1 |

---

## M0 — Production resurrection  *(do first; everything else is invisible without it)*

The deploy has been idle since May 12 and "nothing works" in the preview.
Known-suspect list, most likely first:

1. **Railway process topology.** The `Procfile` declares `web`, `worker`,
   and `beat`, but Railway does not fan one service out into three
   processes. If only `web` is running, **no token discovery, webhook
   processing, scoring, or aggregation has ever executed in prod** — the
   feed would be permanently empty. Fix: three Railway services from the
   same repo (or one service per start command), sharing `DATABASE_URL` /
   `REDIS_URL`. Verify worker + beat logs show task activity.
2. **Helius webhook registration.** Registered webhooks and API keys can
   lapse. `GET /api/v1/webhooks/helius/stats` shows event counts —
   zero/stale counts mean re-registering via `token_discovery` or checking
   the Helius dashboard.
3. **Migrations.** `alembic upgrade head` must have run against prod
   Postgres (base schema 000 + 001). The release command isn't in
   `railway.toml` — confirm how it runs, or add a release phase.
4. **Env vars.** Prod needs real `SECRET_KEY` (not the default!),
   `HELIUS_API_KEY`, `DATABASE_URL`, `REDIS_URL`; Vercel needs
   `NEXT_PUBLIC_API_URL` pointing at the Railway domain.
5. **CORS.** `core/config.py` must allow the real Vercel domain(s),
   including preview URLs if we want previews to hit prod.

**Build item (small, this repo):** ✅ built — `GET /health/pipeline`
reports last webhook event time, unprocessed backlog, last-scored-token
freshness, Redis state, and per-beat-task heartbeat staleness. Turns
"nothing works" into a diagnosable dashboard; point uptime monitors at it.

**Exit test:** the production Discovery page shows tokens < 5 minutes old
with a LIVE badge; `/health/pipeline` is green on every subsystem.

---

## M1 — Merge PR #1 + Phase 2 frontend completion

Backend for all of this is merged and live after M0; this milestone makes
it usable by humans.

- ✅ Merge PR #1 (CI green; adds copy module + auth + shadow subscriptions).
- ✅ **Auth UI:** /login page with signup toggle, localStorage token, auth
  context, logged-in topbar state (email + tier badge from the session;
  "Connect Wallet" stays a stub until M3).
- ✅ **Follow flow:** Follow button + risk params (position cap, min
  sustainability) in the wallet detail panel; follows management with
  pause/resume/stop lives on Portfolio.
- ✅ **Shadow ledger UI:** simulated-vs-skipped trades with reasons on the
  Portfolio page — the "try before you trust" product moment.
- ✅ e2e coverage: login/signup, failed login, signed-out prompts, follow
  (success + 409), portfolio tables, pause action (35 Playwright tests).

**Exit test:** a fresh user can sign up, follow a leaderboard wallet, and
see shadow trades appear in their ledger within minutes — in prod.

---

## M2 — Monetization-lite: Stripe + tier enforcement  *(launchable: "Intelligence Beta")*

Recommended launch point. Discovery + Copy Intelligence (shadow) is a
sellable product without touching custody/execution risk.

- ✅ Stripe integration: checkout session, customer portal, billing status,
  signature-verified `/api/v1/webhooks/stripe` syncing tier + Subscription
  rows through the full lifecycle (checkout → update → downgrade → delete).
  Gracefully 503s until `STRIPE_SECRET_KEY` / price IDs / webhook secret
  are configured (create the Product/Prices in the Stripe dashboard).
- ✅ Tier enforcement: free/anonymous signals delayed
  `FREE_TIER_DELAY_MINUTES` on both REST endpoints; realtime WS tokens
  gated to paid tiers (JWT via `?token=`, free sockets fall back to
  delayed polling); follow limits (3 free / 50 pro). Daily signal cap
  still pending.
- ✅ Auth hardening: per-IP throttling on register/login/forgot (Redis
  fixed-window, fail-open), password reset via purpose-scoped JWT links,
  email verification (migration 002 + emailed link + login-page banner).
  Still open: refresh tokens or a shorter access-token TTL than 7 days.
- ✅ Settings page: account, plan with upgrade (checkout) or manage
  billing (portal), sign out, checkout success/cancel banners.

**Exit test:** a user can upgrade with a real card, immediately sees
undelayed signals, and their tier survives webhook-driven renewal/cancel.

---

## M3 — Execution layer, manual first

Sequenced to defer the hardest risk (automated custody) while shipping
visible value early.

- ✅ **Wallet connect** (Solana wallet-adapter, Phantom + wallet-standard
  autodetect) — non-custodial; set `NEXT_PUBLIC_SOLANA_RPC_URL` in prod
  (public mainnet RPC is rate-limited).
- ✅ **SOL/USD price feed**: Jupiter price API + CoinGecko fallback,
  Redis-cached, refreshed by a 60s beat task (heartbeat-monitored),
  `GET /api/v1/execute/price`. `max_position_usd` is now ENFORCED in
  shadow mode (usd_value stamped on ledger rows; cap skips carry a
  reason). Token-level price feed + daily loss cap still pending.
- ✅ **Manual swaps (buy-side v1):** Execute page swap ticket — live
  Jupiter quote (price impact, route), slippage presets, swap tx built
  server-side (`POST /execute/swap-transaction`, keys never leave the
  wallet), signed + sent client-side, recorded to `ExecutedTrade`
  (source=manual) via `POST /execute/trades`. Still pending: sell side,
  Buy buttons on Discovery/Copy rows, priority-fee UI, Jito MEV
  protection, a confirmation-checker beat task (recorded trades stay
  "submitted"), and real token decimals on the ticket.
- Execute page: swap ticket + open positions; Portfolio: real holdings +
  PnL from `ExecutedTrade`.
- Record executed trades with the risk-context columns already in the
  model (`rug_risk_at_trade`, `momentum_at_trade`).

**Exit test:** a user swaps SOL→token from the terminal with their own
wallet and sees the position + PnL in Portfolio.

---

## M4 — Automated copy execution  *(the big one — do not rush)*

**Decision required before any code: custody model.**
`CopySubscription.execution_wallet_pubkey` implies delegated execution.
Options, in ascending risk: (a) notify-and-one-click (user taps to approve
each copy — non-custodial, slower), (b) session-key / delegation programs,
(c) custodial hot wallets (fast, but regulatory + security weight:
key management, withdrawal limits, insurance story). Recommendation:
ship (a) first, evaluate (b); treat (c) as a company decision, not a
sprint task.

- Copy engine: leader trade → risk-filter check (now USD-enforceable via
  M3 price feed) → execution path per custody model → `ExecutedTrade`
  (source="copy") with slippage/fee accounting.
- Kill switches: per-subscription daily loss cap enforcement, global
  pause, anomaly detection (leader rug-pulls, wash-trade patterns —
  clustering data helps here).
- Shadow-vs-live accuracy report: how closely live fills track the shadow
  ledger (slippage drag) — this is the trust metric for the product.

**Exit test:** a live copy subscription mirrors a leader trade end-to-end
within its caps, and stops itself when the daily loss cap is hit.

---

## M5 — Launch hardening  *(runs alongside M2–M4, gates public launch)*

- **Security:** rotate/verify all secrets (`SECRET_KEY` default is
  "change-me-in-production" — confirm prod overrides it), dependency
  audit, tighten CORS, penetration pass on auth + subscription endpoints,
  Helius webhook secret enforcement verification (code exists).
- **Observability:** Sentry release tagging, uptime checks on `/health` +
  `/health/pipeline`, Celery task failure alerting, structured logging.
- **Performance debt:** the `TODO(scaling)` per-request COUNTs in
  signals/discovery routes → sampled or periodic; leaderboard cache
  warming; DB index review against real query plans.
- **Known small debt:** repo-wide ESLint config is missing (`npm run
  lint` is broken); pydantic class-based-config deprecation warning from a
  dependency; multi-DEX `source_dex` still hardcoded (`TODO(task-2)`).
- **Legal/product:** trading-risk disclaimers, ToS + privacy policy,
  jurisdiction gating decision, pricing page, onboarding flow, docs.

---

## Sequencing at a glance

```
M0 prod resurrection ──► M1 Phase-2 UI ──► M2 billing ══► LAUNCH "Intelligence Beta"
                                                │
                                                ▼
                                   M3 manual execution ──► M4 auto-copy ══► LAUNCH "Full Terminal"
                                   (M5 hardening runs alongside, gates both launches)
```

Two launches on purpose: the Intelligence Beta (M0–M2) monetizes the parts
that are already built and de-risked, while execution (M3–M4) — the
hardest, riskiest surface — follows without blocking revenue.
