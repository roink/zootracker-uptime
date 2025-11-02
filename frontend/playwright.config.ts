import { defineConfig, devices } from '@playwright/test';

const isCI = Boolean(process.env['CI']);

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: isCI ? 1 : 0,
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
    command: isCI
      ? 'npm run build && npm run preview -- --host 0.0.0.0 --port 4173'
      : 'npm run dev -- --host 0.0.0.0 --port 4173',
    port: 4173,
    reuseExistingServer: !isCI,
    env: {
      VITE_MAP_STYLE_URL: 'http://127.0.0.1:4173/__map-style',
    },
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
