/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { createHash } from 'node:crypto'
import { defineConfig, type Plugin } from 'vite'

/**
 * The built page's Content-Security-Policy, as a meta tag (the server adds frame-ancestors and the
 * other headers, which a meta cannot carry). Scripts and styles come from this site only; the one
 * inline script (theme before first paint) is allowed by its hash. Images may come from https
 * (Google avatars). Development keeps Vite's own inline scripts, so the policy is for builds only.
 */
function contentSecurityPolicy(): Plugin {
  return {
    name: 'lucidnews-csp',
    apply: 'build',
    transformIndexHtml(html) {
      const hashes = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(([, body]) => `'sha256-${createHash('sha256').update(body!).digest('base64')}'`)
      const policy = [
        "default-src 'self'",
        `script-src 'self' ${hashes.join(' ')}`,
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: https:",
        "font-src 'self' data:", // Vite inlines the smallest font subsets
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
      ].join('; ')
      return html.replace('<meta charset="UTF-8" />', `<meta charset="UTF-8" />\n    <meta http-equiv="Content-Security-Policy" content="${policy}" />`)
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), contentSecurityPolicy()],
  server: {
    port: 5173,
    // Read-only Python API: `uv run lucidnews-api` (override with LUCIDNEWS_API)
    // The browser's Host header is kept (changeOrigin off): sign-in checks that the Origin of a POST is the
    // host it was sent to, and Google must come back to the address the browser used (localhost:5173).
    proxy: { '/api': { target: process.env.LUCIDNEWS_API ?? 'http://127.0.0.1:8765', changeOrigin: false } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    include: ['src/**/*.test.{ts,tsx}'], // e2e/ is Playwright's: `npm run e2e`
    // First render of a screen loads its lazy chunk.
    testTimeout: 15_000,
  },
})
