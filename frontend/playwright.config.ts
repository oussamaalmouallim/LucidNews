import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end journeys (lot 31) on the built interface, as it ships (CSP included), in front of a
 * throwaway API: accounts on, sign-up open, one edition (scripts/e2e_server.py). Ports 8766 and
 * 5174, so a development server on 8765 / 5173 keeps running. Build first: `npm run e2e`.
 */
const API_PORT = 8766
const WEB_PORT = 5174

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1, // one server, one state: the journeys run one after the other
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `uv run python scripts/e2e_server.py --data-dir ${join(tmpdir(), 'lucidnews-e2e')} --port ${API_PORT}`,
      cwd: '..',
      url: `http://127.0.0.1:${API_PORT}/api/auth/session`,
      reuseExistingServer: false, // a fresh database at every run
      timeout: 120_000,
    },
    {
      command: `npx vite preview --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      env: { LUCIDNEWS_API: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
    },
  ],
})
