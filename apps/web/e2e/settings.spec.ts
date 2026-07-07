import { test, expect, type Page, type Route } from "@playwright/test";

const USER = {
  id: "user-1",
  email: "trader@example.com",
  role: "user",
  subscription_tier: "free",
  created_at: new Date(Date.now() - 86400e3).toISOString(),
};

const FREE_STATUS = {
  tier: "free",
  billing_configured: true,
  has_stripe_customer: false,
  subscription: null,
};

const PRO_STATUS = {
  tier: "pro",
  billing_configured: true,
  has_stripe_customer: true,
  subscription: {
    status: "active",
    billing_cycle: "monthly",
    current_period_end: new Date(Date.now() + 20 * 86400e3).toISOString(),
    cancel_at_period_end: false,
  },
};

async function fulfillJson(route: Route, body: unknown) {
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function signIn(page: Page, user = USER) {
  await page.addInitScript(() => {
    window.localStorage.setItem("forge_token", "test-token");
  });
  await page.route("**/api/v1/auth/me", (route) => fulfillJson(route, user));
}

test.describe("Settings", () => {
  test("signed out shows the sign-in prompt", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
    await expect(
      page.getByRole("paragraph").getByRole("link", { name: "Sign in" }),
    ).toBeVisible();
  });

  test("free tier shows account info and upgrade buttons", async ({ page }) => {
    await signIn(page);
    await page.route("**/api/v1/billing/status", (route) =>
      fulfillJson(route, FREE_STATUS),
    );
    await page.goto("/settings");

    const main = page.getByRole("main");
    await expect(main.getByText("trader@example.com")).toBeVisible();
    await expect(main.getByText("FREE", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Upgrade — monthly" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Upgrade — yearly" })).toBeVisible();
  });

  test("upgrade redirects to the checkout URL", async ({ page }) => {
    await signIn(page);
    await page.route("**/api/v1/billing/status", (route) =>
      fulfillJson(route, FREE_STATUS),
    );
    // Same-origin URL so the test can observe the navigation.
    await page.route("**/api/v1/billing/checkout", (route) =>
      fulfillJson(route, { url: "/settings?billing=success" }),
    );
    await page.goto("/settings");

    await page.getByRole("button", { name: "Upgrade — monthly" }).click();
    await expect(page).toHaveURL(/billing=success/);
    await expect(page.getByText("Payment complete")).toBeVisible();
  });

  test("pro tier shows renewal info and manage billing", async ({ page }) => {
    await signIn(page, { ...USER, subscription_tier: "pro" });
    await page.route("**/api/v1/billing/status", (route) =>
      fulfillJson(route, PRO_STATUS),
    );
    await page.goto("/settings");

    await expect(page.getByRole("main").getByText("PRO", { exact: true })).toBeVisible();
    await expect(page.getByText("Renews")).toBeVisible();
    await expect(page.getByRole("button", { name: "Manage billing" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Upgrade/ })).not.toBeVisible();
  });

  test("unconfigured billing explains free-only mode", async ({ page }) => {
    await signIn(page);
    await page.route("**/api/v1/billing/status", (route) =>
      fulfillJson(route, { ...FREE_STATUS, billing_configured: false }),
    );
    await page.goto("/settings");

    await expect(page.getByText(/Billing isn't configured/)).toBeVisible();
  });
});
