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

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), sitemap(loadEnv(mode, process.cwd(), '').VITE_SITE_URL)],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: { port: 5173, strictPort: true },
  preview: { port: 4173, strictPort: true },
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
}));
