# Forge Terminal — Launch Roadmap

Last updated: 2026-07-12. Launch verification lives in [TESTING.md](./TESTING.md). This is the working plan from "code
exists" to "people pay for it." Milestones are ordered by dependency, not
calendar. Each has an explicit exit test — a milestone isn't done until its
exit test passes in **production**, not localhost.

## Business phases (post-M0, 2026-07-12)

M0 closed 2026-07-12: full pipeline live in prod (webhooks, scoring,
beat tasks, prices; `/health/pipeline` green). The path to revenue:

| Phase | Goal | Exit test | Status |
|---|---|---|---|
| **P1 Credibility** | Feed shows real names/images/prices (DAS metadata + execution-price from swaps) + uptime monitor | A stranger can't tell the feed from paid competitors' | code shipped, verifying in prod |
| **P2 Prove it** | A week of accumulated wallet scores; TESTING.md A–G pass; M3 exit test (dust swap → position) | Owner uses it daily and trusts it | waiting on data |
| **P3 Intelligence Beta** | Stripe live (≈$49/mo Pro), Helius paid tier, lawyer-reviewed legal, soft launch to memecoin communities | 10 paying strangers | blocked on P2 + legal review |
| **P4 Auto-copy** | Automated copy execution w/ kill switches + shadow-vs-live accuracy report (per-trade fees) | See M4 exit test | deferred until P3 revenue |

Running cost: ~$5/mo now; ~$55–75/mo at P3 (Helius Developer ~$49 +
domain + Railway overage). Break-even ≈ 2 Pro subscribers.

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

1. **Railway process topology.** ✅ resolved 2026-07-10 — web/worker/beat
   run as three Railway services sharing `DATABASE_URL`/`REDIS_URL`. The
   original outage was the Redis service itself: "Active" in the dashboard
   but not accepting TCP connections on either address family (diagnosed
   via `/health/redis-debug`); a **Redeploy** (not Restart) of the Redis
   service fixed it. The Redis cache client now self-heals (30s reconnect
   cooldown) and Celery sets `broker_connection_retry_on_startup`, so a
   future Redis outage no longer needs process restarts.
2. **Helius webhook registration.** ✅ self-healing — the API
   create-or-updates its Helius webhook on every boot (needs
   `HELIUS_API_KEY`; targets the Railway public domain automatically,
   override with `PUBLIC_API_URL`). `GET /api/v1/webhooks/helius/registration`
   reports the last attempt; owner-only `POST /api/v1/webhooks/helius/register`
   forces one. DAS discovery now derives its RPC URL from `HELIUS_API_KEY`
   when `HELIUS_RPC_URL` is unset.
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
Temporary M0 triage endpoints (remove once stable): `/health/redis-debug`
(DNS/TCP/PING from inside the container) and `/health/celery-debug`
(live workers, queue depth, process heartbeats, last task exception).

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
  ✅ Access tokens now 24h with 30-day rotating refresh tokens
  (`POST /auth/refresh`); frontend refreshes transparently. Known
  follow-up: refresh-token revocation storage.
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
  reason). ✅ Token-level prices (Jupiter batch lookup, request-driven,
  60s cache) mark open positions to market. ✅ Daily loss cap enforced in
  shadow mode (buys skip once today's net simulated USD outflow would
  exceed `daily_loss_cap_usd`; sells never blocked).
- ✅ **Manual swaps (buy-side v1):** Execute page swap ticket — live
  Jupiter quote (price impact, route), slippage presets, swap tx built
  server-side (`POST /execute/swap-transaction`, keys never leave the
  wallet), signed + sent client-side, recorded to `ExecutedTrade`
  (source=manual) via `POST /execute/trades`. ✅ Sell side (token->SOL
  quoting with decimals param), ✅ Buy buttons on Discovery rows
  prefilling the Execute ticket, ✅ confirmation-checker beat task
  (submitted -> confirmed/failed via batched getSignatureStatuses;
  expires never-landed txs after 15 min; `SOLANA_RPC_URL` config).
  ✅ Real token-decimals lookup (RPC getTokenSupply, day-cached; ticket
  falls back to the 6-dp assumption with its caveat only when the
  lookup fails). Still pending: priority-fee UI, Jito MEV protection.
- ✅ **Positions + PnL:** `GET /api/v1/execute/positions` aggregates real
  trades (submitted/confirmed; shadow + failed rows excluded) per token —
  average-cost basis, realized PnL, and mark-to-market unrealized PnL in
  SOL, rendered on Portfolio. Quantities degrade to "—" rather than
  guessing when a legacy row lacks `token_amount` or prices are down.
- ✅ Executed trades now record risk context at trade time
  (`rug_risk_at_trade`, `momentum_at_trade` from the latest scored
  signal) plus `token_amount` and `price_at_trade`.

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

✅ Option (a) v1 shipped: simulated BUY rows in the shadow ledger carry a
Copy button that prefills the Execute ticket (mint + side + SOL amount);
the user's wallet signs. Sells are deliberately excluded (sell size
depends on the copier's own holdings). Fully-automated paths (b)/(c)
remain open decisions.

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

- **Security:** ✅ full-app audit (2026-07-12, five-surface pass) with
  fixes landed:
  - **Fail-closed prod config** (`ENVIRONMENT=production`): boot refuses a
    default/weak `SECRET_KEY` and a missing `HELIUS_WEBHOOK_SECRET`; API
    docs/openapi hidden in prod.
  - **Webhook ingest hardened:** unauthenticated writes rejected in prod,
    event array length-capped, NaN/Infinity rejected at parse; execution
    price now taken from the bonding-curve leg (self-transfer/`max()`
    inflation blocked). All mutating ops endpoints (`reprocess`,
    `recalculate-scores`, `refresh-metadata`, `stats`, `registration`)
    owner-gated with capped limits; 500s no longer echo internals.
  - **Auth:** rate-limit key uses the trusted (rightmost) XFF hop
    (spoof-proof); owner emails can't be self-registered; login timing
    equalized (no account-enumeration oracle); purposeless JWTs rejected.
  - **Trades:** signature uniqueness scoped per-user (no cross-user
    suppression) + IntegrityError→409; base58 mint validation; amount
    bounds.
  - **Diagnostics:** `/health/redis-debug` + `/health/celery-debug`
    owner-gated; stored task-failure text redacts api-key/credential URLs.
  - **Shadow caps:** `max_position_usd` enforced on the accumulated
    position (not per-trade); daily cap on gross buys (sells can't create
    headroom).
  - **Web:** CSP + `X-Frame-Options: DENY` + HSTS + `nosniff` +
    `Referrer-Policy`; token images restricted to https.
  - **Deps/secrets:** no secrets in repo or git history; the two npm
    advisories (shell-quote/ws) are transitive dev tooling under the
    unused Solana mobile adapter, not in the prod bundle.
  - **Still open (documented follow-ups):** refresh-token revocation /
    move refresh token to an httpOnly cookie; WS auth via one-time ticket
    instead of `?token=`; enforce or delete the unused free-tier
    signal/token caps; DB-level follow-limit constraint before live copy.
    **Manual:** rotate the Helius key + Railway token exposed in chat.
- **Observability:** ✅ Sentry release tagging (deploy SHA + environment);
  ✅ Celery task-failure alerting (Sentry CeleryIntegration in the
  worker/beat processes, release + environment tagged); still open:
  uptime checks on `/health` + `/health/pipeline`, structured logging.
- **Performance debt:** ✅ per-request observability COUNTs now sampled
  1-in-20; still open: leaderboard cache warming, DB index review against
  real query plans.
- **Known small debt:** ✅ ESLint fixed (flat config, `npm run lint` works
  and gates CI); ✅ pydantic deprecation warning resolved; multi-DEX
  `source_dex` still hardcoded (`TODO(task-2)`).
- **Legal/product:** ✅ drafted — /terms, /privacy, /disclaimer pages with
  signup agreement + Execute-page risk link. These are TEMPLATES and
  **must be reviewed by qualified counsel before public launch**. Still
  open: jurisdiction gating decision, pricing page, onboarding flow, docs.

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
