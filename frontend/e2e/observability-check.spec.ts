import { test, expect } from "@playwright/test";

test("observability panel computes real values", async ({ page }) => {
  // Real per-candidate astropy AltAz/moon computation over a full page of
  // candidates takes several seconds -- see app/science/observability.py's
  // own disclosed scaling note. Not a flaky test, a real (bounded) cost.
  test.setTimeout(45_000);
  await page.goto("/");
  await page.getByText("Observability tonight").click();
  await page.getByPlaceholder("31.68").fill("31.68");
  await page.getByPlaceholder("-110.88").fill("-110.88");
  await page.getByRole("button", { name: /Compute observability/ }).click();
  await expect(page.getByText("Active").first()).toBeVisible({ timeout: 30000 });
  await page.screenshot({ path: "screenshots/observability_active.png" });
});
