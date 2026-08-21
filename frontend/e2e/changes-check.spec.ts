import { test, expect } from "@playwright/test";

test("changes/diff view loads and shows honest empty or real state", async ({ page }) => {
  await page.goto("/changes");
  await expect(page.getByRole("heading", { name: "What changed since your last visit" })).toBeVisible();
  // Either a real empty-state message or a real table -- never a crash, never
  // fabricated rows (there is no fallback dataset in this component at all).
  await expect(
    page.getByText(/No real disposition or health-grade changes have been recorded/).or(page.locator("table"))
  ).toBeVisible({ timeout: 10000 });
  await page.screenshot({ path: "screenshots/changes_page.png", fullPage: true });
});
