#!/usr/bin/env node
// Browser regression suite for __BOOK__/viz/__ID__ (Playwright + Chromium):
//   node books/__BOOK__/viz/tests/__ID__.test.mjs        (or node tools/node/viz-test.mjs __BOOK__)
// Starter checks every page must pass. Add checks for every control and for each property the page claims, against an
// independent implementation written here (not by calling the page's own functions).
import { session, cjkLeftovers, overflowX } from '../../../../tools/node/viz-testkit.mjs';

const T = await session();
const { page, check } = T;
await T.goto('__BOOK__', '__ID__', '?lang=zh');
await page.waitForTimeout(300);
check('page carries its id', (await page.evaluate(() => document.body.dataset.vizId)) === '__ID__');
check('runtime loaded', await page.evaluate(() => typeof window.TRV === 'object' && TRV.lang() === 'zh'));

await page.click('[data-lang-set="en"]');
await page.waitForTimeout(200);
const left = await cjkLeftovers(page);
check('no visible Chinese in English mode', left.length === 0, left.slice(0, 5).join(' | '));
await page.click('#infoBtn');
check('theory drawer opens', (await page.evaluate(() => document.getElementById('drawer').hidden)) === false);
await page.keyboard.press('Escape');
check('Esc closes the drawer', (await page.evaluate(() => document.getElementById('drawer').hidden)) === true);

for (const lang of ['zh', 'en']) {
  await page.setViewportSize({ width: 390, height: 844 });
  await T.goto('__BOOK__', '__ID__', `?lang=${lang}`);
  await page.waitForTimeout(200);
  check(`no horizontal scroll at 390px (${lang})`, (await overflowX(page)) === 0);
}
await page.setViewportSize({ width: 760, height: 560 });
await T.goto('__BOOK__', '__ID__', '?embed=1&lang=zh');
check('?embed=1 hides the header chrome', await page.evaluate(() => getComputedStyle(document.querySelector('header.top')).display === 'none'));
check('no script errors', T.errors.length === 0, T.errors.slice(0, 3).join(' | '));
await T.finish();
