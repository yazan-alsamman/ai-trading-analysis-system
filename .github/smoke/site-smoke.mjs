// One-off smoke check of the live site (backend mode). Registers one throwaway user, signs in
// through the form, opens every page and records API errors, console errors and blank pages.
import { chromium } from 'playwright';
import fs from 'node:fs';

const BASE = process.env.SITE ?? 'http://187.127.76.76:8080';
const email = `smoke-${Date.now()}@example.com`;
const password = 'SmokeTest2026x';
const out = { base: BASE, api: {}, pages: [] };

async function api(path, init) {
  const r = await fetch(BASE + '/api/v1' + path, init);
  return { status: r.status, body: (await r.text()).slice(0, 200) };
}
out.api.ready = await api('/health/ready');
out.api.instruments = await api('/instruments');
out.api.register = await api('/auth/register', {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ email, password, full_name: 'Smoke Test' }),
});

const PUBLIC = ['/', '/about', '/login', '/register', '/legal/risk-disclosure', '/membership'];
const PRIVATE = ['/overview', '/workspace', '/signals', '/strategies', '/backtests', '/ai-setups',
  '/calendar', '/risk', '/alerts', '/assistant', '/insights', '/community/news',
  '/community/posts', '/community/experts', '/settings', '/admin'];

const browser = await chromium.launch();
const page = await browser.newPage();
let cur = null;
page.on('response', (r) => {
  if (cur && r.url().includes('/api/') && r.status() >= 400)
    cur.apiErrors.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, '')}`);
});
page.on('console', (m) => { if (cur && m.type() === 'error') cur.console.push(m.text().slice(0, 200)); });
page.on('pageerror', (e) => { if (cur) cur.console.push('PAGEERROR ' + String(e).slice(0, 200)); });

async function visit(path) {
  cur = { path, apiErrors: [], console: [] };
  try {
    await page.goto(BASE + path, { waitUntil: 'networkidle', timeout: 30000 });
  } catch (e) { cur.console.push('NAV ' + String(e).slice(0, 120)); }
  await page.waitForTimeout(1500);
  cur.finalUrl = page.url().replace(BASE, '');
  cur.title = await page.title();
  const text = (await page.locator('body').innerText().catch(() => '')).replace(/\s+/g, ' ');
  cur.textLen = text.length;
  cur.configScreen = /configuration/i.test(text) && /VITE_/.test(text);
  cur.snippet = text.slice(0, 160);
  await page.screenshot({ path: `shots${path.replace(/\//g, '_') || '_root'}.png` });
  out.pages.push(cur);
}

for (const p of PUBLIC) await visit(p);
cur = { path: 'LOGIN', apiErrors: [], console: [] };
await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
await page.getByLabel('Email').fill(email);
await page.getByLabel('Password', { exact: true }).fill(password);
await page.getByRole('button', { name: 'Sign in' }).last().click();
await page.waitForTimeout(4000);
cur.finalUrl = page.url().replace(BASE, '');
out.pages.push(cur);
for (const p of PRIVATE) await visit(p);
await browser.close();

fs.writeFileSync('smoke.json', JSON.stringify(out, null, 1));
console.log(JSON.stringify(out, null, 1));
