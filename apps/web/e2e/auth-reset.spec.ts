import { test, expect, type Route } from "@playwright/test";

async function fulfillJson(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test.describe("Password reset", () => {
  test("login page links to forgot-password", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("link", { name: "Forgot password?" }).click();
    await expect(page).toHaveURL(/\/forgot-password/);
    await expect(page.getByRole("heading", { name: "Reset password" })).toBeVisible();
  });

  test("forgot-password submits and shows the non-leaking confirmation", async ({ page }) => {
    await page.route("**/api/v1/auth/forgot-password", (route) =>
      fulfillJson(route, { status: "ok" }),
    );
    await page.goto("/forgot-password");
    await page.getByLabel("Email").fill("trader@example.com");
    await page.getByRole("button", { name: "Send reset link" }).click();
    await expect(page.getByText(/If that email exists/)).toBeVisible();
  });

  test("reset-password sets a new password with the emailed token", async ({ page }) => {
    await page.route("**/api/v1/auth/reset-password", (route) =>
      fulfillJson(route, { status: "ok" }),
    );
    await page.goto("/reset-password?token=tok-123");
    await page.getByLabel("New password").fill("brandnewpass1");
    await page.getByRole("button", { name: "Set new password" }).click();
    await expect(page.getByText("Password updated.")).toBeVisible();
    await expect(
      page.getByRole("main").getByRole("link", { name: "Sign in" }),
    ).toBeVisible();
  });

  test("reset-password surfaces backend rejection", async ({ page }) => {
    await page.route("**/api/v1/auth/reset-password", (route) =>
      fulfillJson(route, { detail: "Invalid or expired reset link" }, 400),
    );
    await page.goto("/reset-password?token=expired");
    await page.getByLabel("New password").fill("brandnewpass1");
    await page.getByRole("button", { name: "Set new password" }).click();
    await expect(page.getByText("Invalid or expired reset link")).toBeVisible();
  });

  test("reset-password without a token explains itself", async ({ page }) => {
    await page.goto("/reset-password");
    await expect(page.getByText(/needs the link from your reset email/)).toBeVisible();
  });
});

test.describe("Email verification", () => {
  test("login page verifies an emailed token and shows the banner", async ({ page }) => {
    await page.route("**/api/v1/auth/verify-email*", (route) =>
      fulfillJson(route, { status: "ok" }),
    );
    await page.goto("/login?verify_token=tok-123");
    await expect(page.getByText("Email verified — sign in below.")).toBeVisible();
  });

  test("invalid verification token shows the failure note", async ({ page }) => {
    await page.route("**/api/v1/auth/verify-email*", (route) =>
      fulfillJson(route, { detail: "Invalid or expired verification link" }, 400),
    );
    await page.goto("/login?verify_token=bad");
    await expect(page.getByText(/verification link is invalid or expired/)).toBeVisible();
  });
});
