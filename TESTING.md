# Forge Terminal — Launch Verification Checklist

Manual end-to-end verification of production. Companion to
[ROADMAP.md](./ROADMAP.md) — this operationalizes the milestone exit tests.

**URLs**
- App: https://forge-terminal.vercel.app
- API: your Railway domain (Railway → service → Settings → Domains; it must
  equal `NEXT_PUBLIC_API_URL` in Vercel)
- Diagnostics: `<api>/health/pipeline` · API explorer: `<api>/docs`

## Step 0 — go/no-go

Open `<api>/health/pipeline` before anything else.

- [ ] `status: "ok"` — proceed.
- `degraded` → the `problems` list names the broken subsystem. Beat tasks
  all `never`/`unknown` + zero webhook events = the Railway worker/beat
  services aren't running (ROADMAP M0 fix). Migration errors = run
  `alembic upgrade head` (000–002).

## A. Discovery

- [ ] `/discovery` shows tokens; anonymous/free status badge is POLLING and
      the newest token is ≥ 15 minutes old (free-tier delay working).
- [ ] Filters narrow the table; row click opens the detail panel.
- [ ] A row's **Buy** button opens Execute with the mint prefilled.

## B. Accounts

- [ ] Sign up → logged in; topbar shows email + FREE badge.
- [ ] (SMTP configured) Verification email → link → "Email verified" banner;
      Settings shows verified: Yes.
- [ ] Sign out/in; wrong password shows a clean error.
- [ ] Forgot password → email → reset → old password dead, new one works.
- [ ] ~11 rapid failed logins → "Too many attempts — try again later" (429).

## C. Copy Intelligence

Leaderboard needs recorded wallet activity; sparklines need ~30+ min of
15-minute score snapshots.

- [ ] `/copy` ranks wallets; window tabs + "Hide clustered" refetch.
- [ ] Wallet panel: stats, sparkline, **Follow** with risk params.
- [ ] Duplicate follow → "Already subscribed"; 4th follow on free tier →
      blocked with an upgrade hint.

## D. Portfolio

- [ ] Follows list with pause/resume/stop (stop is terminal, frees a slot).
- [ ] Shadow trades appear ≤ ~1 min after a followed wallet trades;
      skipped rows show the filter reason; USD column populated.
- [ ] **Copy** on a simulated buy opens Execute prefilled.

## E. Execute — ⚠️ real funds; test with dust (~0.01 SOL)

- [ ] SOL price shows; pasting a mint yields a quote (estimated tokens,
      price impact, route) with no decimals caveat.
- [ ] Connect Wallet opens the wallet modal; Swap disabled until
      connected + quoted.
- [ ] Tiny buy → wallet signs → Solscan link → recorded `submitted` →
      `confirmed` within ~2–4 min. Rejecting in the wallet shows a clean
      error and records nothing.
- [ ] SELL toggle quotes exact SOL out.

## F. Billing — use Stripe **test mode** first (card 4242 4242 4242 4242)

- [ ] Settings plan section renders ("billing isn't configured" is correct
      when keys are absent).
- [ ] Upgrade → Stripe checkout → success banner → badge flips to PRO
      within seconds (webhook).
- [ ] Paid perks activate: Discovery shows sub-15-min tokens + LIVE badge;
      follow limit rises.
- [ ] Manage billing opens the portal; cancel returns to FREE.

## G. Legal

- [ ] `/terms`, `/privacy`, `/disclaimer` render with cross-links.
- [ ] Signup shows the agreement line; Execute fine print links the Risk
      Disclosure.

## Expected cadences

| Thing | Cadence |
|---|---|
| Token discovery poll | 60s |
| Shadow-trade recording | 60s |
| SOL price refresh | 60s |
| Trade confirmations | 2 min |
| Metric snapshots | 5 min |
| Wallet scores / sparkline points | 15 min |

**When something fails:** check `/health/pipeline` first, then Sentry —
then report the failing step and what you saw.
