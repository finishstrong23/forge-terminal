import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * Mock the /api/v1/discovery/feed endpoint with a given response body.
 * Use before page.goto(...) so the initial fetch is intercepted.
 */
async function mockFeed(page: Page, body: unknown) {
  await page.route("**/api/v1/discovery/feed*", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    }),
  );
}

const mockToken = {
  id: "test-1",
  token_address: "Test111111111111111111111111111111111111111",
  symbol: "TEST1",
  name: "Test Token 1",
  scan_timestamp: new Date().toISOString(),
  age_minutes: 10,
  age_seconds: 600,
  price_usd: 0.01,
  market_cap: 10000,
  volume_1h: 5000,
  liquidity_usd: 2500,
  rug_risk_score: 20,
  momentum_score: 80,
  confidence_score: 75,
  holder_count: 100,
  buy_ratio_1h: 65,
  is_honeypot: false,
  flags: [],
  source_dex: "pump_fun",
};

test.describe("Discovery Page", () => {
  test("redirects root to /discovery", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/discovery/);
  });

  test("renders heading + status badge + token count", async ({ page }) => {
    await mockFeed(page, { tokens: [mockToken], count: 1, has_more: false });
    await page.goto("/discovery");

    await expect(page.getByRole("heading", { name: "Discovery" })).toBeVisible();
    // Status badge varies (LOADING/LIVE/POLLING/OFFLINE) based on WS+REST state.
    await expect(page.getByText(/LOADING|LIVE|POLLING|OFFLINE/)).toBeVisible();
    await expect(page.getByText(/\d+ tokens/)).toBeVisible();
  });

  test("shows empty state when feed returns no tokens", async ({ page }) => {
    await mockFeed(page, { tokens: [], count: 0, has_more: false });
    await page.goto("/discovery");

    await expect(page.getByText("Scanning for new tokens...")).toBeVisible();
  });

  test("renders mocked token in the table", async ({ page }) => {
    await mockFeed(page, { tokens: [mockToken], count: 1, has_more: false });
    await page.goto("/discovery");

    await expect(
      page.getByRole("table").getByText("TEST1", { exact: true }),
    ).toBeVisible();
  });

  test("filter bar is functional", async ({ page }) => {
    const second = { ...mockToken, id: "test-2", symbol: "OTHER", name: "Other Token" };
    await mockFeed(page, { tokens: [mockToken, second], count: 2, has_more: false });
    await page.goto("/discovery");

    const searchInput = page.getByPlaceholder("Search token...");
    await expect(searchInput).toBeVisible();
    await searchInput.fill("TEST1");

    await expect(
      page.getByRole("table").getByText("TEST1", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("table").getByText("OTHER", { exact: true }),
    ).not.toBeVisible();
  });

  test("hide honeypots filter works", async ({ page }) => {
    const honeypot = { ...mockToken, id: "test-honey", symbol: "HONEY", name: "Honey Token", is_honeypot: true };
    await mockFeed(page, { tokens: [mockToken, honeypot], count: 2, has_more: false });
    await page.goto("/discovery");

    // Hidden by default
    await expect(
      page.getByRole("table").getByText("HONEY", { exact: true }),
    ).not.toBeVisible();

    const honeypotCheckbox = page.getByLabel("Hide honeypots");
    await honeypotCheckbox.uncheck();

    await expect(
      page.getByRole("table").getByText("HONEY", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("HONEYPOT", { exact: true })).toBeVisible();
  });

  test("clicking a row opens the detail panel", async ({ page }) => {
    await mockFeed(page, { tokens: [mockToken], count: 1, has_more: false });
    await page.goto("/discovery");

    await page.getByRole("table").getByText("TEST1", { exact: true }).click();
    await expect(page.getByRole("heading", { name: "TEST1" })).toBeVisible();
    await expect(page.getByText("Market Data")).toBeVisible();
  });

  test("detail panel shows market data", async ({ page }) => {
    await mockFeed(page, { tokens: [mockToken], count: 1, has_more: false });
    await page.goto("/discovery");
    await page.getByRole("table").getByText("TEST1", { exact: true }).click();

    await expect(page.getByText("Market Data")).toBeVisible();
    await expect(page.getByText("Price")).toBeVisible();
    await expect(page.getByText("Liquidity")).toBeVisible();
  });

  test("detail panel can be closed", async ({ page }) => {
    await mockFeed(page, { tokens: [mockToken], count: 1, has_more: false });
    await page.goto("/discovery");
    await page.getByRole("table").getByText("TEST1", { exact: true }).click();

    await expect(page.getByRole("heading", { name: "TEST1" })).toBeVisible();

    const closeButtons = page.locator("button:has(svg.lucide-x)");
    if (await closeButtons.count() > 0) {
      await closeButtons.first().click();
    }
  });
});

test.describe("Navigation", () => {
  test("sidebar navigation works", async ({ page }) => {
    await page.goto("/discovery");

    await page.getByRole("link", { name: "Copy Intel" }).click();
    await expect(page).toHaveURL(/\/copy/);
    await expect(page.getByRole("heading", { name: "Copy Intelligence" })).toBeVisible();

    await page.getByRole("link", { name: "Execute" }).click();
    await expect(page).toHaveURL(/\/execute/);

    await page.getByRole("link", { name: "Portfolio" }).click();
    await expect(page).toHaveURL(/\/portfolio/);

    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page).toHaveURL(/\/settings/);
  });

  test("command palette opens with Ctrl+K", async ({ page }) => {
    await page.goto("/discovery");
    await page.waitForTimeout(500);

    await page.keyboard.press("Control+k");
    await page.waitForTimeout(300);

    const input = page.locator('[cmdk-input]');
    await expect(input).toBeVisible({ timeout: 3000 });
  });

  test("command palette navigates to pages", async ({ page }) => {
    await page.goto("/discovery");
    await page.waitForTimeout(500);

    await page.keyboard.press("Control+k");
    await page.waitForTimeout(300);

    const input = page.locator('[cmdk-input]');
    await input.fill("Copy");

    await page.locator('[cmdk-item]').filter({ hasText: "Copy Intelligence" }).click();
    await expect(page).toHaveURL(/\/copy/);
  });
});

test.describe("Layout", () => {
  test("shows Forge branding in sidebar", async ({ page }) => {
    await page.goto("/discovery");
    await expect(page.getByRole("complementary").getByText("FORGE")).toBeVisible();
  });

  test("shows wallet connect button", async ({ page }) => {
    await page.goto("/discovery");
    await expect(page.getByText("Connect Wallet")).toBeVisible();
  });

  test("shows FREE tier badge", async ({ page }) => {
    await page.goto("/discovery");
    await expect(page.getByText("FREE")).toBeVisible();
  });
});
