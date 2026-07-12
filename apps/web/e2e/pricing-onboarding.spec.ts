import { test, expect } from "@playwright/test";

test.describe("Pricing", () => {
  test("signed out shows tiers and routes upgrade to login", async ({ page }) => {
    await page.goto("/pricing");

    await expect(page.getByRole("heading", { name: "Pricing" })).toBeVisible();
    await expect(page.getByText("$0")).toBeVisible();
    await expect(page.getByText("$49")).toBeVisible();
    await expect(page.getByText(/no 15-minute delay/i)).toBeVisible();

    await page.getByRole("button", { name: "Sign in to upgrade" }).click();
    await expect(page).toHaveURL(/\/login/);
  });

  test("signed-in free user goes to checkout", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("forge_token", "test-token");
    });
    await page.route("**/api/v1/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "u1",
          email: "trader@example.com",
          role: "user",
          subscription_tier: "free",
          created_at: new Date().toISOString(),
        }),
      }),
    );
    let checkoutCalled = false;
    await page.route("**/api/v1/billing/checkout", (route) => {
      checkoutCalled = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ url: "https://checkout.stripe.example/session" }),
      });
    });
    await page.goto("/pricing");

    await page.getByRole("button", { name: "Upgrade to Pro" }).click();
    await expect.poll(() => checkoutCalled).toBe(true);
  });
});

test.describe("How it works", () => {
  test("renders the three steps with links", async ({ page }) => {
    await page.goto("/how-it-works");

    await expect(
      page.getByRole("heading", { name: "How Forge works" }),
    ).toBeVisible();
    await expect(page.getByText("Discover", { exact: true })).toBeVisible();
    await expect(page.getByText("Shadow-follow the winners")).toBeVisible();
    await expect(page.getByText("Execute on your terms")).toBeVisible();
    await expect(page.getByText("Non-custodial, always")).toBeVisible();

    await expect(
      page.getByRole("link", { name: /Open the Discovery feed/ }),
    ).toHaveAttribute("href", "/discovery");
    await expect(
      page.getByRole("link", { name: /Open the wallet leaderboard/ }),
    ).toHaveAttribute("href", "/copy");
    await expect(
      page.getByRole("link", { name: /Open the swap ticket/ }),
    ).toHaveAttribute("href", "/execute");
  });
});
