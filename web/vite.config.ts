/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv, type Plugin } from 'vite';

/** Public, indexable routes. App routes are excluded (and disallowed in robots.txt). */
const PUBLIC_ROUTES = ['/', '/about', '/ai-assistant', '/membership', '/legal/risk-disclosure', '/legal/data-storage'];

/**
 * Emits sitemap.xml only when VITE_SITE_URL is set: a sitemap needs absolute
 * URLs, and no production domain is invented here.
 */
function sitemap(siteUrl: string | undefined): Plugin {
  return {
    name: 'ata-sitemap',
    apply: 'build',
    generateBundle() {
      if (!siteUrl || !/^https?:\/\//.test(siteUrl)) return;
      const base = siteUrl.replace(/\/+$/, '');
      const urls = PUBLIC_ROUTES.map((r) => `  <url><loc>${base}${r}</loc></url>`).join('\n');
      const xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', urls, '</urlset>', ''].join('\n');
      this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: xml });
    },
  };
}

/**
 * Local development with the backend: the browser talks to this server on the
 * same origin (/api/v1, /ws/market) and Vite forwards to the backend, so no
 * CORS configuration is needed. BACKEND_URL is read on the dev machine only
 * (no VITE_ prefix): it is never compiled into the bundle.
 */
function backendProxy(target: string) {
  return {
    '/api': { target, changeOrigin: true },
    '/ws': { target: target.replace(/^http/, 'ws'), ws: true, changeOrigin: true },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backend = env.BACKEND_URL || 'http://localhost:8000';
  return {
  plugins: [react(), tailwindcss(), sitemap(env.VITE_SITE_URL)],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: { port: 5173, strictPort: true, proxy: backendProxy(backend) },
  preview: { port: 4173, strictPort: true, proxy: backendProxy(backend) },
  build: {
    target: 'es2022',
    rollupOptions: {
      output: {
        // Long-cached vendor chunks: they change far less often than app code.
        manualChunks: {
          charts: ['lightweight-charts'],
          react: ['react', 'react-dom', 'react-dom/client', 'react-router'],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
};
});
