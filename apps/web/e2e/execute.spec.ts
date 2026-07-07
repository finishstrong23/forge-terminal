import { test, expect, type Route } from "@playwright/test";

async function fulfillJson(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

const MINT = "TokenMint111111111111111111111111111111111";

const QUOTE = {
  input_mint: "So11111111111111111111111111111111111111112",
  output_mint: MINT,
  in_amount: "500000000",
  out_amount: "123456789000",
  other_amount_threshold: "122000000000",
  price_impact_pct: "0.0042",
  slippage_bps: 100,
  route_labels: ["Raydium", "Orca"],
  quote_response: { outAmount: "123456789000" },
};

test.describe("Execute", () => {
  test("renders the swap ticket with SOL price", async ({ page }) => {
    await page.route("**/api/v1/execute/price", (route) =>
      fulfillJson(route, { sol_usd: 150.25 }),
    );
    await page.goto("/execute");

    await expect(page.getByRole("heading", { name: "Execute" })).toBeVisible();
    await expect(page.getByText("NON-CUSTODIAL")).toBeVisible();
    await expect(page.getByText("SOL $150.25")).toBeVisible();
    await expect(page.getByLabel("Token mint address")).toBeVisible();
  });

  test("fetches and displays a quote", async ({ page }) => {
    await page.route("**/api/v1/execute/price", (route) =>
      fulfillJson(route, { sol_usd: 150 }),
    );
    await page.route("**/api/v1/execute/quote*", (route) =>
      fulfillJson(route, QUOTE),
    );
    await page.goto("/execute");

    await page.getByLabel("Token mint address").fill(MINT);
    await page.getByLabel("Amount (SOL)").fill("0.5");

    await expect(page.getByText(/123,456\.79 tokens/)).toBeVisible();
    await expect(page.getByText("0.420%")).toBeVisible();
    await expect(page.getByText("Raydium → Orca")).toBeVisible();
    // ≈ $75 USD estimate under the amount input.
    await expect(page.getByText("≈ $75.00")).toBeVisible();
  });

  test("quote failure is surfaced", async ({ page }) => {
    await page.route("**/api/v1/execute/price", (route) =>
      fulfillJson(route, { sol_usd: 150 }),
    );
    await page.route("**/api/v1/execute/quote*", (route) =>
      fulfillJson(route, { detail: "Jupiter quote unavailable: timeout" }, 503),
    );
    await page.goto("/execute");

    await page.getByLabel("Token mint address").fill(MINT);
    await page.getByLabel("Amount (SOL)").fill("1");

    await expect(page.getByText(/Jupiter quote unavailable/)).toBeVisible();
  });

  test("swap stays disabled without a connected wallet", async ({ page }) => {
    await page.route("**/api/v1/execute/price", (route) =>
      fulfillJson(route, { sol_usd: 150 }),
    );
    await page.route("**/api/v1/execute/quote*", (route) =>
      fulfillJson(route, QUOTE),
    );
    await page.goto("/execute");

    await page.getByLabel("Token mint address").fill(MINT);
    await page.getByLabel("Amount (SOL)").fill("0.5");
    await expect(page.getByText(/123,456\.79 tokens/)).toBeVisible();

    const swapButton = page.getByRole("button", { name: "Connect a wallet to swap" });
    await expect(swapButton).toBeVisible();
    await expect(swapButton).toBeDisabled();
  });
});
