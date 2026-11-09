// Helpers for the browser regression suites books/<slug>/viz/tests/<id>.test.mjs (Playwright + Chromium).
//
//   import { session } from '../../../../tools/node/viz-testkit.mjs';
//   const T = await session();                       // server + browser + page (zh-CN, 1440×900)
//   await T.goto('example-monograph', 'golden-carry', '?lang=zh');
//   T.check('c(1, 1) = 1', value === 1, `got ${value}`);
//   await T.finish();                                // prints the tally and exits non-zero on any failure
//
// The suite reuses the server started by tools/node/viz-test.mjs (env VIZ_ORIGIN) or starts its own, so a suite also
// runs alone:  node books/<slug>/viz/tests/<id>.test.mjs.  Chromium honours PW_CHROMIUM_PATH. Google Fonts requests are
// answered with the local @fontsource files, so pages render with their real fonts offline.
import { chromiumOptions, loadChromium, localFontsCss } from './viz-common.mjs';
import { startServer, vizUrl } from './viz-server.mjs';

/** Route Google Fonts to the local @fontsource copies served by the viz server at `origin`. */
export async function routeLocalFonts(context, origin) {
  const css = localFontsCss(`${origin}/__fonts/`);
  await context.route(/^https:\/\/fonts\.googleapis\.com\//, (route) => route.fulfill({ status: 200, contentType: 'text/css; charset=utf-8', body: css }));
  await context.route(/^https:\/\/fonts\.gstatic\.com\//, (route) => route.fulfill({ status: 204, body: '' }));
}

/** Visible text nodes containing CJK characters (language-switch leftovers). */
export async function cjkLeftovers(page) {
  return page.evaluate(() => {
    const bad = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) {
      const t = n.textContent.trim(); if (!/[　-〿㐀-鿿＀-￯]/.test(t)) continue;
      const el = n.parentElement; if (!el || el.closest('[hidden]') || el.closest('.langs')) continue;
      let hidden = false; for (let a = el; a; a = a.parentElement) { const s = getComputedStyle(a); if (s.opacity === '0' || s.visibility === 'hidden') { hidden = true; break; } }
      if (hidden || getComputedStyle(el).display === 'none' || (el.offsetParent === null && getComputedStyle(el).position !== 'fixed')) continue;
      bad.push(t.slice(0, 40));
    }
    for (const el of document.querySelectorAll('[aria-label]')) if (/[㐀-鿿]/.test(el.getAttribute('aria-label')) && !el.closest('.langs') && el.offsetParent !== null) bad.push('aria-label: ' + el.getAttribute('aria-label').slice(0, 40));
    if (/[㐀-鿿]/.test(document.title)) bad.push('title: ' + document.title);
    return bad;
  });
}

/** Horizontal overflow of the document in CSS pixels (0 = no sideways scrolling). */
export const overflowX = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

/**
 * Open a browser session. Options: viewport, locale, reducedMotion ('reduce' | 'no-preference').
 * Returns { page, context, browser, origin, errors, check, goto, url, newPage, finish }.
 */
export async function session(opts = {}) {
  let origin = process.env.VIZ_ORIGIN, server = null;
  if (!origin) ({ server, origin } = await startServer(0));
  const chromium = await loadChromium();
  const browser = await chromium.launch(chromiumOptions());
  const context = await browser.newContext({
    viewport: opts.viewport || { width: 1440, height: 900 }, locale: opts.locale || 'zh-CN',
    reducedMotion: opts.reducedMotion || 'no-preference', deviceScaleFactor: opts.deviceScaleFactor || 1
  });
  await routeLocalFonts(context, origin);
  const results = [], errors = [];
  const watch = (page) => {
    page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
    // net::ERR_ABORTED = cancelled by a navigation (e.g. late font requests); missing files surface as HTTP 404 below
    page.on('requestfailed', (r) => {
      const why = r.failure() ? r.failure().errorText : '';
      if (!/^https:\/\/fonts\./.test(r.url()) && !/ERR_ABORTED/.test(why)) errors.push(`requestfailed: ${r.url()} ${why}`);
    });
    page.on('response', (r) => { if (r.status() >= 400 && r.url().startsWith(origin)) errors.push(`HTTP ${r.status()}: ${r.url()}`); });
    return page;
  };
  const page = watch(await context.newPage());
  const check = (name, ok, detail = '') => {
    results.push({ name, ok: !!ok, detail });
    console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail && !ok ? '  — ' + detail : ''}`);
    return !!ok;
  };
  const url = (slug, id, query = '') => vizUrl(origin, slug, id, query);
  const goto = async (slug, id, query = '', p = page) => { await p.goto(url(slug, id, query), { waitUntil: 'load' }); return p; };
  const newPage = async () => watch(await context.newPage());
  async function finish() {
    await browser.close();
    if (server) server.close();
    const failed = results.filter((r) => !r.ok).length;
    console.log(`\n${results.length - failed}/${results.length} passed`);
    process.exit(failed || !results.length ? 1 : 0);
  }
  return { page, context, browser, origin, errors, results, check, goto, url, newPage, finish };
}
