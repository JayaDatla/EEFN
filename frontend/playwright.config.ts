import { defineConfig } from "@playwright/test";

// UPGRADE_PLAN.md H.4: Playwright smoke coverage for the core triage -> evidence
// card -> export flow. Assumes the backend (127.0.0.1:8000) and frontend dev
// server are already running -- this suite does not manage the backend process.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 0,
  // The dev backend runs as a single uvicorn process (no worker pool), and the
  // observability endpoint's per-candidate astropy computation is CPU-bound --
  // running specs in parallel serializes those requests behind each other and
  // can push a single spec past its own timeout even though nothing is broken.
  // One worker keeps this suite's timing honest against a real single-process
  // dev backend rather than papering over it with longer timeouts.
  workers: 1,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3001",
    headless: true,
  },
  webServer: process.env.PLAYWRIGHT_SKIP_WEBSERVER
    ? undefined
    : {
        command: "npm run dev -- -p 3001",
        url: "http://127.0.0.1:3001",
        reuseExistingServer: true,
        timeout: 60_000,
      },
});
