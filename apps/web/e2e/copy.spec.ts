import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * Mock the /api/v1/copy/leaderboard endpoint with a given response body.
 * Use before page.goto(...) so the initial fetch is intercepted.
 * Returns the list of intercepted request URLs for param assertions.
 */
async function mockLeaderboard(page: Page, body: unknown): Promise<string[]> {
  const requests: string[] = [];
  await page.route("**/api/v1/copy/leaderboard*", (route: Route) => {
    requests.push(route.request().url());
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
  return requests;
}

async function mockWalletDetail(page: Page, body: unknown) {
  await page.route("**/api/v1/copy/wallets/**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    }),
  );
}

/** Register AFTER mockWalletDetail — later routes take precedence in Playwright. */
async function mockScoreHistory(page: Page, body: unknown) {
  await page.route("**/api/v1/copy/wallets/**/score-history*", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    }),
  );
}

const truncate = (addr: string, chars: number) =>
  `${addr.slice(0, chars)}...${addr.slice(-chars)}`;

const WALLET_A = "WinnerAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
const WALLET_B = "InsiderBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB";

const entryA = {
  rank: 1,
  wallet_address: WALLET_A,
  total_trades: 12,
  buy_count: 7,
  sell_count: 5,
  tokens_traded: 4,
  closed_positions: 4,
  wins: 3,
  win_rate: 0.75,
  sol_in: 10.0,
  sol_out: 14.5,
  net_sol: 4.5,
  active_days: 1,
  sustainability_score: 78.2,
  sustainability_grade: "A",
  is_clustered: false,
  last_active: new Date().toISOString(),
};

const entryB = {
  ...entryA,
  rank: 2,
  wallet_address: WALLET_B,
  win_rate: 0.2,
  net_sol: -2.25,
  sustainability_score: 31.4,
  sustainability_grade: "D",
  is_clustered: true,
};

const twoWalletBody = { entries: [entryA, entryB], count: 2, has_more: false, window: "24h" };
const emptyBody = { entries: [], count: 0, has_more: false, window: "24h" };

const historyBody = {
  wallet_address: WALLET_A,
  count: 3,
  snapshots: [72.1, 74.8, 78.2].map((score, i) => ({
    scored_at: new Date(Date.now() - (3 - i) * 15 * 60_000).toISOString(),
    total_score: score,
    grade: "A",
    persistence_score: 40 + i,
    win_rate_score: 75,
    hold_pattern_score: 90,
    insider_penalty: 0,
  })),
};

const emptyHistoryBody = { wallet_address: WALLET_A, count: 0, snapshots: [] };

const detailBody = {
  wallet: entryA,
  window: "24h",
  recent_activity: [
    {
      token_address: "Token1111111111111111111111111111111111111",
      symbol: "TOK1",
      activity_type: "buy",
      sol_amount: 2.5,
      signature: "sig-1",
      timestamp: new Date().toISOString(),
    },
    {
      token_address: "Token2222222222222222222222222222222222222",
      symbol: null,
      activity_type: "sell",
      sol_amount: 5.0,
      signature: "sig-2",
      timestamp: new Date().toISOString(),
    },
  ],
};

test.describe("Copy Intelligence Page", () => {
  test("renders heading + status badge + wallet count", async ({ page }) => {
    await mockLeaderboard(page, twoWalletBody);
    await page.goto("/copy");

    await expect(page.getByRole("heading", { name: "Copy Intelligence" })).toBeVisible();
    await expect(page.getByText(/LOADING|AUTO-REFRESH|OFFLINE/)).toBeVisible();
    await expect(page.getByText(/\d+ wallets/)).toBeVisible();
  });

  test("renders mocked wallets in the table", async ({ page }) => {
    await mockLeaderboard(page, twoWalletBody);
    await page.goto("/copy");

    const table = page.getByRole("table");
    await expect(table.getByText(truncate(WALLET_A, 5), { exact: true })).toBeVisible();
    await expect(table.getByText("+4.50 SOL", { exact: true })).toBeVisible();
    await expect(table.getByText("-2.25 SOL", { exact: true })).toBeVisible();
    await expect(table.getByText("75%", { exact: true })).toBeVisible();
  });

  test("flags clustered wallets", async ({ page }) => {
    await mockLeaderboard(page, twoWalletBody);
    await page.goto("/copy");

    await expect(
      page.getByRole("table").getByText("CLUSTER", { exact: true }),
    ).toBeVisible();
  });

  test("shows empty state when no wallets qualify", async ({ page }) => {
    await mockLeaderboard(page, emptyBody);
    await page.goto("/copy");

    await expect(page.getByText("Building the leaderboard...")).toBeVisible();
  });

  test("window tabs refetch with the selected window", async ({ page }) => {
    const requests = await mockLeaderboard(page, twoWalletBody);
    await page.goto("/copy");
    await expect(page.getByRole("table")).toBeVisible();

    await page.getByRole("button", { name: "7d", exact: true }).click();
    await expect
      .poll(() => requests.some((u) => u.includes("window=7d")))
      .toBe(true);
  });

  test("hide clustered toggle refetches with exclude_clustered", async ({ page }) => {
    const requests = await mockLeaderboard(page, twoWalletBody);
    await page.goto("/copy");
    await expect(page.getByRole("table")).toBeVisible();

    await page.getByRole("button", { name: "Hide clustered" }).click();
    await expect
      .poll(() => requests.some((u) => u.includes("exclude_clustered=true")))
      .toBe(true);
  });

  test("clicking a row opens the wallet detail panel", async ({ page }) => {
    await mockLeaderboard(page, twoWalletBody);
    await mockWalletDetail(page, detailBody);
    await mockScoreHistory(page, historyBody);
    await page.goto("/copy");

    await page
      .getByRole("table")
      .getByText(truncate(WALLET_A, 5), { exact: true })
      .click();

    await expect(
      page.getByRole("heading", { name: truncate(WALLET_A, 6) }),
    ).toBeVisible();
    await expect(page.getByText("Recent activity")).toBeVisible();
    await expect(page.getByText("TOK1", { exact: true })).toBeVisible();
  });

  test("detail panel shows the score trend sparkline", async ({ page }) => {
    await mockLeaderboard(page, twoWalletBody);
    await mockWalletDetail(page, detailBody);
    await mockScoreHistory(page, historyBody);
    await page.goto("/copy");

    await page
      .getByRole("table")
      .getByText(truncate(WALLET_A, 5), { exact: true })
      .click();

    await expect(page.getByText("Score trend")).toBeVisible();
    await expect(page.getByText("3 snapshots", { exact: false })).toBeVisible();
    await expect(
      page.getByRole("img", { name: /Sustainability score trend/ }),
    ).toBeVisible();
  });

  test("score trend section is hidden without snapshots", async ({ page }) => {
    await mockLeaderboard(page, twoWalletBody);
    await mockWalletDetail(page, detailBody);
    await mockScoreHistory(page, emptyHistoryBody);
    await page.goto("/copy");

    await page
      .getByRole("table")
      .getByText(truncate(WALLET_A, 5), { exact: true })
      .click();

    await expect(page.getByText("Recent activity")).toBeVisible();
    await expect(page.getByText("Score trend")).not.toBeVisible();
  });

  test("detail panel can be closed", async ({ page }) => {
    await mockLeaderboard(page, twoWalletBody);
    await mockWalletDetail(page, detailBody);
    await mockScoreHistory(page, emptyHistoryBody);
    await page.goto("/copy");

    await page
      .getByRole("table")
      .getByText(truncate(WALLET_A, 5), { exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: truncate(WALLET_A, 6) }),
    ).toBeVisible();

    const closeButtons = page.locator("button:has(svg.lucide-x)");
    await closeButtons.first().click();
    await expect(
      page.getByRole("heading", { name: truncate(WALLET_A, 6) }),
    ).not.toBeVisible();
  });
});
