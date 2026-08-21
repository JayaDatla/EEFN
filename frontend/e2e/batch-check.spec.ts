import { test, expect } from "@playwright/test";

test("batch workflow runs a real audit and shows results", async ({ page }) => {
  await page.goto("/batch");
  await expect(page.getByRole("heading", { name: "Upload a target list, get a ranked audit" })).toBeVisible();
  await page.getByRole("button", { name: /Audit \d+ target/ }).click();
  await expect(page.getByText(/of \d+ matched real candidates/)).toBeVisible({ timeout: 15000 });
  await page.screenshot({ path: "screenshots/batch_page.png", fullPage: true });
});

test("batch export produces a real VOTable file", async ({ request }) => {
  const listRes = await request.get("http://127.0.0.1:8000/api/v1/candidates?limit=2");
  const list = await listRes.json();
  const toiIds = list.map((c: any) => c.toi_id);
  const res = await request.post("http://127.0.0.1:8000/api/v1/batch/export", {
    data: { toi_ids: toiIds },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.text();
  expect(body).toContain("<VOTABLE");
});
