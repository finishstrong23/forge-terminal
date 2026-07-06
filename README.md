# Forge Terminal

Solana trader intelligence platform — Discovery, Copy Intelligence, and Execution in one unified interface.

## Architecture

```
forge-terminal/
├── apps/
│   ├── web/          # Next.js 16 (App Router, Tailwind v4, shadcn/ui)
│   └── api/          # FastAPI (PostgreSQL, Redis, Alembic)
├── packages/
│   └── shared/       # Shared TypeScript types
└── vercel.json       # Vercel deployment config
```

## Local Development

### Prerequisites

- Node.js 18+
- Python 3.12+
- PostgreSQL 15+
- Redis (optional, for caching)

### Frontend

```bash
cd apps/web
npm install
npm run dev        # http://localhost:3000
```

### Backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # Edit with your credentials
alembic upgrade head        # Run migrations
uvicorn main:app --reload   # http://localhost:8000
```

### E2E Tests

```bash
cd apps/web
npx playwright install chromium
npx playwright test
```

## Environment Variables

### Backend (`apps/api/.env`)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT signing key |
| `HELIUS_API_KEY` | Yes | Helius API key for Solana RPC |
| `HELIUS_RPC_URL` | No | Helius RPC endpoint |
| `REDIS_URL` | No | Redis connection string |
| `STRIPE_SECRET_KEY` | No | Stripe API key |
| `SENTRY_DSN` | No | Sentry error tracking |

### Frontend (`apps/web/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | No | Backend API URL (default: localhost:8000) |

## Deployment

- **Frontend**: Vercel (auto-deploys from `main`)
- **Backend**: Railway (auto-deploys from `main`)

## Modules

| Module | Status | Description |
|---|---|---|
| Discovery | Phase 1 (live) | Multi-DEX token scanner with dual scoring |
| Copy Intelligence | Phase 2 (leaderboards live) | Wallet leaderboards + copy trading |
| Execution Layer | Phase 3 | Jupiter-routed swaps with MEV protection |
| Subscriptions | Phase 4 | Tiered billing via Stripe |
