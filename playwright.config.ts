import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], headless: true },
    },
  ],
  webServer: {
    command: 'npm --prefix frontend run dev -- --host 0.0.0.0 --port 4173',
    port: 4173,
    reuseExistingServer: !process.env.CI,
    env: {
      VITE_MAP_STYLE_URL: 'http://127.0.0.1:4173/__map-style',
    },
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
