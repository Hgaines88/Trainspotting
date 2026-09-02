import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";
import path from "node:path";


const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(frontendRoot, "..");


export default defineConfig({
  testDir: "./test/e2e",
  testMatch: "*.spec.js",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["line"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: ".venv/bin/uvicorn tests.e2e_app:app --host 127.0.0.1 --port 8001",
      cwd: projectRoot,
      env: {
        ...process.env,
        TRAINSPOTTING_E2E_TEST: "1",
      },
      port: 8001,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "npm run dev:e2e",
      cwd: frontendRoot,
      env: {
        ...process.env,
        VITE_CLERK_PUBLISHABLE_KEY: "pk_test_synthetic_e2e",
      },
      port: 4173,
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
