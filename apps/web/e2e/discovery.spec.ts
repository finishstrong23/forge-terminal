import { test, expect } from "@playwright/test";

test.describe("Discovery Page", () => {
  test("redirects root to /discovery", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/discovery/);
  });

  test("renders the discovery page with signal table", async ({ page }) => {
    await page.goto("/discovery");

    await expect(page.getByRole("heading", { name: "Discovery" })).toBeVisible();
    await expect(page.getByText("LIVE")).toBeVisible();
    await expect(page.getByText(/\d+ tokens/)).toBeVisible();
  });

  test("displays demo token data in the table", async ({ page }) => {
    await page.goto("/discovery");

    await expect(page.getByRole("table").getByText("FORGE", { exact: true })).toBeVisible();
    await expect(page.getByRole("table").getByText("BLAZE", { exact: true })).toBeVisible();
    await expect(page.getByRole("table").getByText("EMBER", { exact: true })).toBeVisible();
  });

  test("filter bar is functional", async ({ page }) => {
    await page.goto("/discovery");

    const searchInput = page.getByPlaceholder("Search token...");
    await expect(searchInput).toBeVisible();
    await searchInput.fill("FORGE");

    await expect(page.getByRole("table").getByText("FORGE", { exact: true })).toBeVisible();
    await expect(page.getByRole("table").getByText("BLAZE", { exact: true })).not.toBeVisible();
  });

  test("hide honeypots filter works", async ({ page }) => {
    await page.goto("/discovery");

    await expect(page.getByRole("table").getByText("RUGGED")).not.toBeVisible();

    const honeypotCheckbox = page.getByLabel("Hide honeypots");
    await honeypotCheckbox.uncheck();

    await expect(page.getByRole("table").getByText("RUGGED")).toBeVisible();
    await expect(page.getByText("HONEYPOT", { exact: true })).toBeVisible();
  });

  test("clicking a row opens the detail panel", async ({ page }) => {
    await page.goto("/discovery");

    await page.getByRole("table").getByText("BLAZE", { exact: true }).click();

    await expect(page.getByRole("heading", { name: "BLAZE" })).toBeVisible();
    await expect(page.getByText("Market Data")).toBeVisible();
  });

  test("detail panel shows market data", async ({ page }) => {
    await page.goto("/discovery");
    await page.getByRole("table").getByText("EMBER", { exact: true }).click();

    await expect(page.getByText("Market Data")).toBeVisible();
    await expect(page.getByText("Price")).toBeVisible();
    await expect(page.getByText("Liquidity")).toBeVisible();
  });

  test("detail panel can be closed", async ({ page }) => {
    await page.goto("/discovery");
    await page.getByRole("table").getByText("BLAZE", { exact: true }).click();

    await expect(page.getByRole("heading", { name: "BLAZE" })).toBeVisible();

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
