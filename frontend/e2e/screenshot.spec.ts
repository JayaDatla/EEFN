import { test } from "@playwright/test";

const PAGES = ["/", "/candidates/1017.01", "/fusion", "/compare", "/graph", "/batch", "/changes", "/ai-analysis", "/admin", "/predictions", "/about", "/demo", "/showcase"];
const THEMES = ["light", "dark", "red-night"] as const;

test("capture full sweep screenshots", async ({ page }) => {
  test.setTimeout(180_000);
  const pageErrors: string[] = [];
  page.on("pageerror", err => pageErrors.push(`${page.url()}: ${err.message}`));

  await page.goto("/");
  for (const theme of THEMES) {
    await page.evaluate((t) => {
      window.localStorage.setItem("eefn-theme", t);
      document.documentElement.setAttribute("data-theme", t);
    }, theme);
    for (const path of PAGES) {
      await page.goto(path);
      await page.waitForTimeout(1000);
      const safeName = path.replace(/\//g, "_") || "_home";
      await page.screenshot({ path: `screenshots/sweep_${theme}${safeName}.png`, fullPage: false });
    }
  }

  if (pageErrors.length > 0) {
    console.log("PAGE ERRORS FOUND:\n" + pageErrors.join("\n"));
  }
});
