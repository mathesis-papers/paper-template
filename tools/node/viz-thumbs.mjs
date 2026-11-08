#!/usr/bin/env node
// Capture hub/landing-page thumbnails (1280×720 JPEG) with Playwright + Chromium (software WebGL):
//   node tools/node/viz-thumbs.mjs                          every registered entry of every book
//   node tools/node/viz-thumbs.mjs example-monograph        every entry of one book (slug or directory)
//   node tools/node/viz-thumbs.mjs example-monograph golden-carry [more ids]
// The page is opened as <id>/?thumb=1&lang=zh, served with the runtime mounted at ../assets like the published site.
// shell.js then sets <html data-thumb-mode>, theme.css makes the page's [data-thumb] region (else its .stage) fill the
// viewport and hides toasts and HUD text, so one cover serves both languages. A page may define window.TRV_THUMB()
// (sync or async) to put itself into a representative cover state first. Chromium honours PW_CHROMIUM_PATH.
// Adapted from trureturing-visualize/scripts/thumbs.mjs (Apache-2.0, the-omega-institute).
import path from 'node:path';
import fs from 'node:fs';
import { listBooks, resolveBook, readRegistry, registryPath, chromiumOptions, loadChromium, rel } from './viz-common.mjs';
import { startServer, vizUrl } from './viz-server.mjs';
import { routeLocalFonts } from './viz-testkit.mjs';

export const WIDTH = 1280, HEIGHT = 720;
const args = process.argv.slice(2);
let books = listBooks(), ids = [];
if (args.length) {
  try { books = [resolveBook(args[0])]; ids = args.slice(1); } catch (e) {
    // not a book: treat every argument as an id across all books
    ids = args;
  }
}
const jobs = [];
for (const book of books) {
  if (!fs.existsSync(registryPath(book))) continue;
  for (const v of readRegistry(book).visualizations || []) if (!ids.length || ids.includes(v.id)) jobs.push({ book, v });
}
if (!jobs.length) { console.error(`no matching registry entries${ids.length ? ` for ${ids.join(', ')}` : ''}`); process.exit(2); }

const chromium = await loadChromium();
const { server, origin } = await startServer(0);
const browser = await chromium.launch(chromiumOptions());
let failures = 0;
try {
  for (const { book, v } of jobs) {
    const context = await browser.newContext({ viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 1, locale: 'zh-CN', reducedMotion: 'reduce' });
    await routeLocalFonts(context, origin);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto(vizUrl(origin, book.slug, v.id, '?thumb=1&lang=zh'), { waitUntil: 'load' });
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await page.waitForTimeout(600);
    // a [data-thumb] region, else the page's stage, fills the viewport (theme.css); give layout and canvases a resize
    await page.evaluate(() => {
      if (!document.querySelector('[data-thumb]')) { const s = document.querySelector('.stage'); if (s) s.setAttribute('data-thumb', ''); }
      window.dispatchEvent(new Event('resize'));
    });
    const hooked = await page.evaluate(async () => { if (typeof window.TRV_THUMB === 'function') { await window.TRV_THUMB(); return true; } return false; });
    await page.waitForTimeout(hooked ? 1500 : 1000);
    if (!(await page.$('[data-thumb]'))) { console.error(`${book.slug}/${v.id}: no [data-thumb] or .stage element to capture`); failures++; await context.close(); continue; }
    const out = path.join(book.dir, 'viz', v.thumbnail || `${v.id}/thumb.jpg`);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    await page.screenshot({ path: out, type: 'jpeg', quality: 84, clip: { x: 0, y: 0, width: WIDTH, height: HEIGHT } });
    console.log(`${book.slug}/${v.id} → ${rel(out)}${errors.length ? `  (page errors: ${errors.join('; ')})` : ''}`);
    if (errors.length) failures++;
    await context.close();
  }
} finally {
  await browser.close();
  server.close();
}
process.exit(failures ? 1 : 0);
