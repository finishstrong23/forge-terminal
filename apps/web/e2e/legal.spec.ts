import { test, expect } from "@playwright/test";

test.describe("Legal pages", () => {
  test("terms, privacy, and disclaimer render with cross-links", async ({ page }) => {
    await page.goto("/terms");
    await expect(page.getByRole("heading", { name: "Terms of Service" })).toBeVisible();

    await page.getByRole("link", { name: "Privacy Policy" }).click();
    await expect(page.getByRole("heading", { name: "Privacy Policy" })).toBeVisible();

    await page.getByRole("link", { name: "Risk Disclosure" }).click();
    await expect(page.getByRole("heading", { name: "Risk Disclosure" })).toBeVisible();
    await expect(page.getByText(/extremely risky/)).toBeVisible();
  });

  test("signup shows the agreement line with working links", async ({ page }) => {
    await page.goto("/login");
    await page.getByText("No account? Create one").click();

    await expect(page.getByText(/By creating an account you agree/)).toBeVisible();
    await page.getByRole("link", { name: "Terms of Service" }).click();
    await expect(page).toHaveURL(/\/terms/);
  });

  test("execute fine print links the risk disclosure", async ({ page }) => {
    await page.route("**/api/v1/execute/price", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ sol_usd: 150 }),
      }),
    );
    await page.goto("/execute");
    await page.getByRole("link", { name: "Risk Disclosure" }).click();
    await expect(page).toHaveURL(/\/disclaimer/);
  });
});
