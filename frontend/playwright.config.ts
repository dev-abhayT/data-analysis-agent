import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  retries: 0,
  reporter: 'line',
  use: {
    baseURL: 'http://localhost:8001',
    headless: true,
    // Wait up to 10 s for navigation
    navigationTimeout: 10_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // Do NOT spin up a dev server — the backend serves the built frontend
  // Run `pnpm build` and `uv run python -m src` before running these tests
})
