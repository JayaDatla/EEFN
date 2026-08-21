import { test, expect } from "@playwright/test";

// Regression test: this page used to crash with "Cannot read properties of null
// (reading 'toFixed')" for any real candidate with a null pl_rade -- the fabricated
// mock data it used to fall back on always had a non-null radius, so the missing
// null-guard was never exercised until this was rebuilt against real data.
test("compare page renders real candidates without crashing", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", err => pageErrors.push(err.message));

  await page.goto("/compare");
  await expect(page.getByRole("heading", { name: "Side-by-Side Comparison Workspace" })).toBeVisible();
  await expect(page.getByText(/CANDIDATE A:/)).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(/CANDIDATE B:/)).toBeVisible();
  await page.screenshot({ path: "screenshots/compare_page.png", fullPage: true });

  expect(pageErrors).toEqual([]);
});
