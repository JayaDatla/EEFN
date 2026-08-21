import { test, expect } from "@playwright/test";

// UPGRADE_PLAN.md H.4 smoke coverage: triage queue -> open a candidate's evidence
// card -> the record loads with real data (not a silent fabricated fallback).
// Requires a live backend at 127.0.0.1:8000 with at least one ingested candidate.
// H.3.1: the triage queue lives at "/" (the actual home route); "/candidates" is
// kept only as a redirect for old links.

test("triage queue loads and links into an evidence card", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Should I point a telescope at this tonight?" })).toBeVisible();

  const firstCandidateLink = page.locator('a[href^="/candidates/"]').first();
  await expect(firstCandidateLink).toBeVisible({ timeout: 15_000 });
  const toiHref = await firstCandidateLink.getAttribute("href");
  await firstCandidateLink.click();

  await expect(page).toHaveURL(new RegExp(toiHref!.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});

test("/candidates redirects to the triage queue", async ({ page }) => {
  await page.goto("/candidates");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Should I point a telescope at this tonight?" })).toBeVisible();
});

test("triage queue shows an explicit error state when the backend is unreachable", async ({ page }) => {
  await page.route("**/api/v1/candidates**", route => route.abort());
  await page.goto("/");
  await expect(page.getByText(/Backend unavailable/i)).toBeVisible();
  // The core A.14 regression: no fabricated fallback rows may render.
  await expect(page.getByText("No candidates match this query.")).not.toBeVisible();
});

test("export endpoint returns a parseable VOTable", async ({ request }) => {
  const res = await request.get("http://127.0.0.1:8000/api/v1/candidates/export?limit=5");
  expect(res.ok()).toBeTruthy();
  const body = await res.text();
  expect(body).toContain("<VOTABLE");
});
