import { test, expect } from "@playwright/test";

test("evidence card renders real health breakdown and model tier", async ({ page }) => {
  await page.goto("/candidates/1017.01");
  await expect(page.getByText(/Evidence health breakdown/i)).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/Tier \d/)).toBeVisible();
  await page.screenshot({ path: "screenshots/evidence_card_dark.png", fullPage: false });

  await page.getByRole("button", { name: "Light" }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: "screenshots/evidence_card_light.png", fullPage: false });
});
