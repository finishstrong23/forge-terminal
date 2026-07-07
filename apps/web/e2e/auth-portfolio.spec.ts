import { test, expect, type Page, type Route } from "@playwright/test";

const USER = {
  id: "user-1",
  email: "trader@example.com",
  role: "user",
  subscription_tier: "free",
  created_at: new Date().toISOString(),
};

const TOKEN_RESPONSE = {
  access_token: "test-token",
  token_type: "bearer",
  user: USER,
};

const SUB = {
  id: "sub-1",
  wallet_address: "WinnerAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  mode: "shadow",
  status: "active",
  max_position_usd: 100,
  daily_loss_cap_usd: null,
  slippage_tolerance: null,
  min_sustainability_score: 40,
  token_blacklist: null,
  started_at: new Date().toISOString(),
  paused_at: null,
  stopped_at: null,
  created_at: new Date().toISOString(),
};

const TRADES = [
  {
    id: "t-1",
    token_address: "Token1111111111111111111111111111111111111",
    trade_type: "buy",
    source: "copy_shadow",
    sol_amount: 2.5,
    price_at_trade: 0.01,
    status: "simulated",
    error_message: null,
    copy_subscription_id: "sub-1",
    rug_risk_at_trade: 20,
    momentum_at_trade: 80,
    executed_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
  },
  {
    id: "t-2",
    token_address: "Token2222222222222222222222222222222222222",
    trade_type: "buy",
    source: "copy_shadow",
    sol_amount: 1.0,
    price_at_trade: null,
    status: "skipped",
    error_message: "token flagged as honeypot",
    copy_subscription_id: "sub-1",
    rug_risk_at_trade: 95,
    momentum_at_trade: 10,
    executed_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
  },
];

async function fulfillJson(route: Route, body: unknown) {
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

/** Signed-in state: token pre-seeded, /auth/me mocked. */
async function signIn(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("forge_token", "test-token");
  });
  await page.route("**/api/v1/auth/me", (route) => fulfillJson(route, USER));
}

test.describe("Auth", () => {
  test("login page renders and toggles to signup", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();

    await page.getByText("No account? Create one").click();
    await expect(page.getByRole("heading", { name: "Create account" })).toBeVisible();
  });

  test("login flow stores session and updates topbar", async ({ page }) => {
    await page.route("**/api/v1/auth/login", (route) =>
      fulfillJson(route, TOKEN_RESPONSE),
    );
    await page.route("**/api/v1/auth/me", (route) => fulfillJson(route, USER));
    await page.goto("/login");

    await page.getByLabel("Email").fill("trader@example.com");
    await page.getByLabel("Password").fill("password123");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL(/\/discovery/);
    await expect(page.getByText("trader@example.com")).toBeVisible();
    await expect(page.getByTitle("Sign out")).toBeVisible();
  });

  test("failed login shows the backend error", async ({ page }) => {
    await page.route("**/api/v1/auth/login", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid email or password" }),
      }),
    );
    await page.goto("/login");
    await page.getByLabel("Email").fill("trader@example.com");
    await page.getByLabel("Password").fill("wrongpassword");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.getByText("Invalid email or password")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("signed-out topbar shows Sign in link", async ({ page }) => {
    await page.goto("/discovery");
    await expect(page.getByRole("link", { name: /Sign in/ })).toBeVisible();
  });
});

test.describe("Portfolio", () => {
  test("signed out shows the sign-in prompt", async ({ page }) => {
    await page.goto("/portfolio");
    await expect(page.getByRole("heading", { name: "Portfolio" })).toBeVisible();
    await expect(
      page.getByRole("paragraph").getByRole("link", { name: "Sign in" }),
    ).toBeVisible();
  });

  test("signed in renders follows and shadow ledger", async ({ page }) => {
    await signIn(page);
    await page.route("**/api/v1/copy/subscriptions*", (route) =>
      fulfillJson(route, { subscriptions: [SUB], count: 1 }),
    );
    await page.route("**/api/v1/copy/trades*", (route) =>
      fulfillJson(route, { trades: TRADES, count: 2 }),
    );
    await page.goto("/portfolio");

    await expect(page.getByText("Followed wallets")).toBeVisible();
    await expect(page.getByText("Winne...AAAAA")).toBeVisible();
    await expect(page.getByRole("button", { name: "Pause" })).toBeVisible();

    await expect(page.getByText("Shadow ledger")).toBeVisible();
    await expect(page.getByText("SIMULATED")).toBeVisible();
    await expect(page.getByText("SKIPPED")).toBeVisible();
    await expect(page.getByText("token flagged as honeypot")).toBeVisible();
  });

  test("Copy button on a simulated buy prefills the Execute ticket", async ({ page }) => {
    await signIn(page);
    await page.route("**/api/v1/copy/subscriptions*", (route) =>
      fulfillJson(route, { subscriptions: [SUB], count: 1 }),
    );
    await page.route("**/api/v1/copy/trades*", (route) =>
      fulfillJson(route, { trades: TRADES, count: 2 }),
    );
    await page.route("**/api/v1/execute/price", (route) =>
      fulfillJson(route, { sol_usd: 150 }),
    );
    await page.goto("/portfolio");

    // Only the simulated buy row gets a Copy button (skipped rows don't).
    const copyLinks = page.getByRole("link", { name: "Copy", exact: true });
    await expect(copyLinks).toHaveCount(1);
    await copyLinks.click();

    await expect(page).toHaveURL(/\/execute\?mint=.*side=buy.*amount=2\.5/);
    await expect(page.getByLabel("Token mint address")).toHaveValue(
      TRADES[0].token_address,
    );
    await expect(page.getByLabel("Amount (SOL)")).toHaveValue("2.5");
  });

  test("pause action patches the subscription", async ({ page }) => {
    await signIn(page);
    const patched: string[] = [];
    await page.route("**/api/v1/copy/subscriptions*", (route) =>
      fulfillJson(route, { subscriptions: [SUB], count: 1 }),
    );
    // PATCH goes to /subscriptions/{id} — needs its own (deeper) pattern.
    await page.route("**/api/v1/copy/subscriptions/**", (route) => {
      patched.push(route.request().postData() ?? "");
      return fulfillJson(route, { ...SUB, status: "paused" });
    });
    await page.route("**/api/v1/copy/trades*", (route) =>
      fulfillJson(route, { trades: [], count: 0 }),
    );
    await page.goto("/portfolio");

    await page.getByRole("button", { name: "Pause" }).click();
    await expect.poll(() => patched.some((b) => b.includes("pause"))).toBe(true);
  });
});

test.describe("Follow flow", () => {
  const entry = {
    rank: 1,
    wallet_address: SUB.wallet_address,
    total_trades: 12,
    buy_count: 7,
    sell_count: 5,
    tokens_traded: 4,
    closed_positions: 4,
    wins: 3,
    win_rate: 0.75,
    sol_in: 10,
    sol_out: 14.5,
    net_sol: 4.5,
    active_days: 1,
    sustainability_score: 78.2,
    sustainability_grade: "A",
    is_clustered: false,
    last_active: new Date().toISOString(),
  };

  async function openWalletPanel(page: Page) {
    await page.route("**/api/v1/copy/leaderboard*", (route) =>
      fulfillJson(route, { entries: [entry], count: 1, has_more: false, window: "24h" }),
    );
    await page.route("**/api/v1/copy/wallets/**", (route) =>
      fulfillJson(route, { wallet: entry, window: "24h", recent_activity: [] }),
    );
    await page.route("**/api/v1/copy/wallets/**/score-history*", (route) =>
      fulfillJson(route, { wallet_address: entry.wallet_address, count: 0, snapshots: [] }),
    );
    await page.goto("/copy");
    await page.getByRole("table").getByText("Winne...AAAAA", { exact: true }).click();
  }

  test("signed out shows sign-in prompt in the panel", async ({ page }) => {
    await openWalletPanel(page);
    await expect(
      page.getByText("to follow this wallet and build a shadow ledger."),
    ).toBeVisible();
  });

  test("signed in can follow a wallet", async ({ page }) => {
    await signIn(page);
    await page.route("**/api/v1/copy/subscriptions", (route) =>
      fulfillJson(route, SUB),
    );
    await openWalletPanel(page);

    await expect(page.getByText("Follow (shadow mode)")).toBeVisible();
    await page.getByRole("button", { name: "Follow wallet" }).click();
    await expect(page.getByText(/Following in shadow mode/)).toBeVisible();
  });

  test("duplicate follow surfaces the 409 message", async ({ page }) => {
    await signIn(page);
    await page.route("**/api/v1/copy/subscriptions", (route) =>
      route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Already subscribed to this wallet" }),
      }),
    );
    await openWalletPanel(page);

    await page.getByRole("button", { name: "Follow wallet" }).click();
    await expect(page.getByText("Already subscribed to this wallet")).toBeVisible();
  });
});
