/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import fs from 'node:fs';
import path from 'node:path';
import { defineConfig, type Plugin } from 'vite';
import { hostingHeaders } from './scripts/gates/test-hosting.ts';
import { escapeHtml, resolveFirestoreDocs, resolveSiteOrigin } from './scripts/head.ts';
import { BRAND_CONFIG } from './src/ui/theme/brand.ts';

// Justification (typed boundary): package.json, whose `version` is a string by npm's own rule.
const APP_VERSION = JSON.parse(fs.readFileSync(path.resolve(import.meta.dirname, 'package.json'), 'utf8'))
  .version as string;

function brandHtmlPlugin(): Plugin {
  const tokens = fs.readFileSync(path.resolve(import.meta.dirname, 'src/ui/theme/tokens.css'), 'utf8');
  const [pageLight, pageDark] = [...tokens.matchAll(/--color-page:\s*([^;]+);/g)].map((m) => m[1].trim());
  const values: Record<string, string> = { BRAND_WORDMARK: BRAND_CONFIG.wordmark, BRAND_TAGLINE: BRAND_CONFIG.tagline,
    PAGE_LIGHT: pageLight, PAGE_DARK: pageDark };
  return {
    name: 'brand-html',
    transformIndexHtml: {
      order: 'pre',
      handler: (html) => html.replace(/%(BRAND_WORDMARK|BRAND_TAGLINE|PAGE_LIGHT|PAGE_DARK)%/g,
        (_, name: string) => escapeHtml(values[name])),
    },
  };
}

function hostingHeadersPlugin(): Plugin {
  return {
    name: 'hosting-headers',
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        for (const [key, value] of Object.entries(hostingHeaders(new URL(req.url ?? '/', 'http://preview').pathname,
          true))) res.setHeader(key, value);
        next();
      });
    },
  };
}

export default defineConfig(({ isSsrBuild }) => ({
  plugins: [react(), tailwindcss(), brandHtmlPlugin(), hostingHeadersPlugin()],
  build: { copyPublicDir: !isSsrBuild },
  define: {
    __APP_VERSION__: JSON.stringify(APP_VERSION),
    __SITE_ORIGIN__: JSON.stringify(resolveSiteOrigin()),
    __FIRESTORE_DOCS__: JSON.stringify(resolveFirestoreDocs()),
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
  },
  preview: {
    ...(process.env.MVR_ASK_LOCAL ? { proxy: { '/api': { target: process.env.MVR_ASK_LOCAL, xfwd: true } } } : {}),
  },
  test: { globalSetup: ['tests/fixture.ts'] },
}));
