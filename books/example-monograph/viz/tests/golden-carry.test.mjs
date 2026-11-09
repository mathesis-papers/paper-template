#!/usr/bin/env node
// Browser regression suite for example-monograph/viz/golden-carry (Playwright + Chromium):
//   node books/example-monograph/viz/tests/golden-carry.test.mjs      (or node tools/node/viz-test.mjs example-monograph)
// Reads page state through the read-only window.GC_DEBUG probe and checks it against an independent implementation
// written here: Fibonacci numbers and Zeckendorf digits from a different greedy loop, powers of φ by multiplying pairs
// in ℤ[φ] (no Fibonacci identity), and the carry rules of trureturing's carryPass applied to a sparse map of digits.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { session, cjkLeftovers, overflowX } from '../../../../tools/node/viz-testkit.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..');
const BOOK = 'example-monograph', ID = 'golden-carry';
const lock = JSON.parse(fs.readFileSync(path.join(ROOT, 'trureturing.lock.json'), 'utf8'));

/* ---------- independent implementation (BigInt, ℤ[φ] pairs) ---------- */
const fibs = [1n, 2n]; // F₂, F₃, … — the Zeckendorf weights
while (fibs.length < 40) fibs.push(fibs[fibs.length - 1] + fibs[fibs.length - 2]);
/** Zeckendorf digits, index i ↔ weight F_(i+2), by repeatedly removing the largest weight that fits. */
function zeckendorf(n) {
  let rest = BigInt(n); const set = new Set();
  while (rest > 0n) { let k = 0; while (k + 1 < fibs.length && fibs[k + 1] <= rest) k++; set.add(k); rest -= fibs[k]; }
  const top = set.size ? Math.max(...set) : -1;
  return Array.from({ length: top + 1 }, (_, i) => (set.has(i) ? 1 : 0));
}
/** (a + bφ)(c + dφ) with φ² = φ + 1. */
const mul = ([a, b], [c, d]) => [a * c + b * d, a * d + b * c + b * d];
const PHI = [0n, 1n];
const phiPow = [[1n, 0n]];
for (let k = 1; k < 48; k++) phiPow.push(mul(phiPow[k - 1], PHI));
function betaPair(n) {
  let a = 0n, b = 0n;
  zeckendorf(n).forEach((x, i) => { if (x) { a += phiPow[i + 2][0]; b += phiPow[i + 2][1]; } });
  return [a, b];
}
const betaCache = new Map();
const beta = (n) => { if (!betaCache.has(n)) betaCache.set(n, betaPair(n)); return betaCache.get(n); };
/** c(v₁, v₂) as an exact pair; the second component must be 0. */
function deficit(v1, v2) { const [a1, b1] = beta(v1), [a2, b2] = beta(v2), [a3, b3] = beta(v1 + v2); return [a1 + a2 - a3, b1 + b2 - b3]; }
/** trureturing carryPass on a sparse digit map: returns the rule sequence, signed count and normal form. */
function carryRun(v1, v2) {
  const r = new Map();
  const add = (i, k) => { const x = (r.get(i) || 0) + k; if (x) r.set(i, x); else r.delete(i); };
  zeckendorf(v1).forEach((x, i) => x && add(i, 1));
  zeckendorf(v2).forEach((x, i) => x && add(i, 1));
  const rules = []; let count = 0;
  for (;;) {
    const twos = [...r.keys()].filter((i) => r.get(i) >= 2).sort((x, y) => x - y);
    if (twos.length) {
      const i = twos[0]; add(i, -2);
      if (i === 0) { add(1, 1); rules.push('R0'); count += 1; }
      else if (i === 1) { add(0, 1); add(2, 1); rules.push('R1'); count -= 1; }
      else { add(i - 2, 1); add(i + 1, 1); rules.push('R'); }
      continue;
    }
    const adj = [...r.keys()].filter((i) => r.get(i) === 1 && r.get(i + 1) === 1).sort((x, y) => x - y);
    if (!adj.length) break;
    const i = adj[0]; add(i, -1); add(i + 1, -1); add(i + 2, 1); rules.push('A');
  }
  const top = r.size ? Math.max(...r.keys()) : -1;
  return { rules, count, normal: Array.from({ length: top + 1 }, (_, i) => r.get(i) || 0) };
}
const eq = (x, y) => JSON.stringify(x) === JSON.stringify(y);

/* ---------- open ---------- */
const T = await session({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN' });
const { page, check } = T;
const D = (fn, arg) => page.evaluate(fn, arg);
/** Wait until every scheduled render has run (renders are batched into animation frames). */
const settle = async () => {
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  await page.waitForFunction(() => !GC_DEBUG.pending(), null, { timeout: 30000 });
};
const text = (sel) => D((s) => document.querySelector(s).textContent, sel);
const open = async (query) => {
  await T.goto(BOOK, ID, query);
  await page.waitForFunction(() => window.GC_DEBUG && GC_DEBUG.frames() > 0, null, { timeout: 30000 });
};
await open('?lang=zh');
let st = await D(() => GC_DEBUG.state());
check('opens on (17, 17) with the 0 … 34 map and the finished ledger', st.v1 === 17 && st.v2 === 17 && st.N === 34 && st.pass === st.passes && st.passes === 9, JSON.stringify(st));
check('page carries its id and the runtime language', (await D(() => document.body.dataset.vizId)) === ID && (await D(() => TRV.lang())) === 'zh');

/* ---------- the deficit map: three values, and the same values as the independent implementation ---------- */
for (const N of [34, 89, 233, 987]) {
  await page.click(`#nChips [data-n="${N}"]`); await settle();
  const grid = await D((n) => GC_DEBUG.grid(n), N);
  const okLen = grid.length === (N + 1) * (N + 1);
  const three = okLen && /^[012]+$/.test(grid);
  let agree = okLen, bad = '';
  for (let y = 0; y <= N && agree; y++) for (let x = 0; x <= N; x++) {
    const [c, phi] = deficit(x, y);
    if (phi !== 0n || BigInt(grid.charCodeAt(y * (N + 1) + x) - 48) - 1n !== c) { agree = false; bad = `(${x}, ${y}) page ${grid[y * (N + 1) + x]} mine ${c}+${phi}φ`; break; }
  }
  check(`N = ${N}: c ∈ {−1, 0, 1} for all ${(N + 1) * (N + 1)} pairs of the grid`, three);
  check(`N = ${N}: every cell agrees with the independent ℤ[φ] computation`, agree, bad);
  const counts = await text('#heatCounts');
  check(`N = ${N}: the chip is pressed and the counts cover the grid`, (await D(() => document.querySelector('#nChips [aria-pressed="true"]').dataset.n)) === String(N) && counts.includes(String((N + 1) * (N + 1))) && (await text('#heatRange')) === `0 … ${N}`);
}
check('the map is symmetric (c(v₁, v₂) = c(v₂, v₁)) over 0 … 233', await D(() => { const g = GC_DEBUG.grid(233), n = 234; for (let y = 0; y < n; y++) for (let x = 0; x < y; x++) if (g[y * n + x] !== g[x * n + y]) return false; return true; }));
await page.click('#nChips [data-n="34"]'); await settle();

/* ---------- c(1, 1) = 1 ---------- */
await page.click('#presets [data-preset="1,1"]'); await settle();
let info = await D(() => GC_DEBUG.info());
check('c(1, 1) = 1 on the page and in the independent computation', info.c === 1 && info.cPhi === 0 && deficit(1, 1)[0] === 1n && deficit(1, 1)[1] === 0n);
check('c(1, 1): one R₀ carry 2·W₀ → W₁, signed count +1, readouts say +1', eq(info.passes.map((p) => p.rule), ['R0']) && info.count === 1 && /\+1/.test(await text('#roC')) && /\+1/.test(await text('#pillC')));
await page.click('#presets [data-preset="2,2"]'); await settle();
info = await D(() => GC_DEBUG.info());
check('c(2, 2) = −1 through one R₁ carry', info.c === -1 && info.count === -1 && eq(info.passes.map((p) => p.rule), ['R1']));

/* ---------- pairs: digits, β, the carry run and the signed count ---------- */
const pairs = [[0, 0], [0, 5], [1, 1], [2, 2], [6, 6], [17, 17], [88, 88], [609, 609], [986, 986], [987, 987], [987, 0], [500, 377]];
let seed = 7; const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed; };
for (let k = 0; k < 120; k++) pairs.push([rnd() % 988, rnd() % 988]);
let pairOK = true, pairBad = '';
for (const [v1, v2] of pairs) {
  await D(([a, b]) => GC_DEBUG.set(a, b), [v1, v2]);
  const x = await D(() => GC_DEBUG.info());
  const run = carryRun(v1, v2), [c, phi] = deficit(v1, v2);
  const ok = x.v1 === v1 && x.v2 === v2 && eq(x.z1, zeckendorf(v1)) && eq(x.z2, zeckendorf(v2)) && eq(x.z3, zeckendorf(v1 + v2))
    && eq(x.beta1, beta(v1).map(Number)) && eq(x.beta2, beta(v2).map(Number)) && eq(x.beta3, beta(v1 + v2).map(Number))
    && BigInt(x.c) === c && phi === 0n && x.cPhi === 0 && x.count === run.count && BigInt(run.count) === c
    && eq(x.passes.map((p) => p.rule), run.rules) && eq(x.final, run.normal) && eq(run.normal, zeckendorf(v1 + v2)) && x.canonicalOk;
  if (!ok) { pairOK = false; pairBad = `(${v1}, ${v2}) ${JSON.stringify({ page: [x.c, x.count, x.passes.length], mine: [String(c), run.count, run.rules.length] })}`; break; }
}
check(`${pairs.length} pairs: Zeckendorf digits, β in ℤ[φ], carry rules, normal form and signed count all match; count = c`, pairOK, pairBad);
const real = (n) => { const p = (1 + Math.sqrt(5)) / 2; return zeckendorf(n).reduce((s, x, i) => s + x * p ** (i + 2), 0); };
check('floating-point β agrees with the exact c to 1e−9 (v ≤ 200)', pairs.filter(([a, b]) => a <= 200 && b <= 200).every(([a, b]) => Math.abs(real(a) + real(b) - real(a + b) - Number(deficit(a, b)[0])) < 1e-9));
await D(() => GC_DEBUG.set(986, 986)); await settle();
check('the longest normalization in range: (986, 986) takes 50 carries and c = −1', (await D(() => [GC_DEBUG.state().passes, GC_DEBUG.info().c])).join() === '50,-1' && carryRun(986, 986).rules.length === 50);

/* ---------- controls ---------- */
await page.fill('#v1Num', '34'); await page.press('#v1Num', 'Enter'); await settle();
await page.locator('#v2').fill('21'); await settle();
st = await D(() => GC_DEBUG.state());
check('number box and slider set v₁ = 34, v₂ = 21', st.v1 === 34 && st.v2 === 21 && (await D(() => document.getElementById('v1').value)) === '34' && (await D(() => document.getElementById('v2Num').value)) === '21');
await page.click('#v1Inc'); await page.click('#v2Dec'); await settle();
st = await D(() => GC_DEBUG.state());
check('steppers move v₁ up and v₂ down by one', st.v1 === 35 && st.v2 === 20);
await page.click('#swap'); await settle();
st = await D(() => GC_DEBUG.state());
check('swap exchanges the pair', st.v1 === 20 && st.v2 === 35);
await page.click('#random'); await settle();
st = await D(() => GC_DEBUG.state());
check('random picks a pair in 0 … 987', st.v1 >= 0 && st.v1 <= 987 && st.v2 >= 0 && st.v2 <= 987 && !(st.v1 === 20 && st.v2 === 35));
await page.fill('#v1Num', '5000'); await page.press('#v1Num', 'Enter'); await settle();
check('out-of-range input is clamped to 987', (await D(() => GC_DEBUG.state().v1)) === 987);
for (const p of ['1,1', '2,2', '6,6', '986,986']) {
  await page.click(`#presets [data-preset="${p}"]`); await settle();
  const s = await D(() => GC_DEBUG.state());
  check(`preset ${p} applies and is marked`, `${s.v1},${s.v2}` === p && (await D((q) => document.querySelector(`#presets [data-preset="${q}"]`).getAttribute('aria-pressed'), p)) === 'true');
}
await D(() => GC_DEBUG.set(17, 17)); await settle();
await page.click('#first'); await settle();
check('⏮ returns to the digitwise sum (pass 0), later rows dimmed', (await D(() => GC_DEBUG.state().pass)) === 0 && (await D(() => document.querySelectorAll('#ledger .drow.future').length)) === 9);
await page.click('#next'); await page.click('#next'); await settle();
check('▶▶ steps one carry at a time and marks the current row and tape square', (await D(() => GC_DEBUG.state().pass)) === 2 && (await D(() => document.querySelector('#ledger .drow.now').dataset.pass)) === '2' && (await D(() => document.querySelector('#tape i.now').dataset.pass)) === '2');
await page.click('#prev'); await settle();
check('◀ steps back', (await D(() => GC_DEBUG.state().pass)) === 1);
await page.click('#last'); await settle();
check('⏭ jumps to the normal form', (await D(() => GC_DEBUG.state().pass)) === 9);
await D(() => document.activeElement && document.activeElement.blur());
await page.keyboard.press('ArrowLeft'); await settle();
check('← steps back from the keyboard', (await D(() => GC_DEBUG.state().pass)) === 8);
await page.keyboard.press('Home'); await page.keyboard.press('ArrowRight'); await settle();
check('Home and → work from the keyboard', (await D(() => GC_DEBUG.state().pass)) === 1);
await page.click('#ledger .drow[data-pass="5"]'); await settle();
check('clicking a ledger row selects that pass', (await D(() => GC_DEBUG.state().pass)) === 5);
await D(() => GC_DEBUG.set(6, 6)); await settle();
await page.click('#first'); await page.click('#play'); await settle();
check('▶ plays the carries', (await D(() => GC_DEBUG.state().playing)) === true);
await page.waitForFunction(() => !GC_DEBUG.state().playing, null, { timeout: 15000 }).catch(() => {});
await page.waitForFunction(() => getComputedStyle(document.getElementById('toast')).opacity === '1', null, { timeout: 5000 }).catch(() => {});
check('playback stops at the normal form and reports the signed count', (await D(() => GC_DEBUG.state().pass)) === 3 && /规范化完成：3 次进位，带符号计数 0 = c/.test(await text('#toast')));
const pt = await D(() => GC_DEBUG.cellPoint(5, 8));
await page.mouse.click(pt.x, pt.y); await settle();
st = await D(() => GC_DEBUG.state());
check('clicking the deficit map picks that pair', st.v1 === 5 && st.v2 === 8, JSON.stringify(st));
const lit = await D(() => { const c = document.getElementById('heat'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i] + d[i + 1] + d[i + 2] > 200) n++; return n; });
check('the deficit map is drawn', lit > 2000, String(lit));

/* ---------- Lean links at the pinned commit; drawer ---------- */
const links = await D(() => [...document.querySelectorAll('a[data-lean-gid]')].map((a) => [a.dataset.leanGid, a.href]));
check('every Lean link points at the pinned commit, file and line of trureturing.lock.json', links.length >= 4 && links.every(([gid, href]) => {
  const d = lock.declarations[gid]; return d && href === `https://github.com/${lock.repo}/blob/${lock.commit}/${gid.slice(0, gid.lastIndexOf('.'))}.lean#L${d.line}`;
}), JSON.stringify(links.slice(0, 2)));
const cites = links.map(([g]) => g);
check('the page cites deficit_three_valued and deficit_integer', cites.includes('D5/S1/Deficit/DeficitThreeValued.deficit_three_valued') && cites.includes('D5/S1/Deficit/DeficitInteger.deficit_integer'));
await page.click('#infoBtn');
check('theory drawer opens', (await D(() => document.getElementById('drawer').hidden)) === false);
check('the drawer says the page is a numerical illustration, not a proof', /数值演示，不是证明/.test(await text('#drawer div.zh')) && /numerical illustration, not a proof/.test(await text('#drawer div.en')));
await page.keyboard.press('Escape');
check('Esc closes the drawer and focus returns to its button', (await D(() => document.getElementById('drawer').hidden)) === true && (await D(() => document.activeElement.id)) === 'infoBtn');

/* ---------- language ---------- */
await page.click('[data-lang-set="en"]'); await settle();
let left = await cjkLeftovers(page);
check('no visible Chinese in English mode', left.length === 0, left.slice(0, 6).join(' | '));
for (const p of ['986,986', '1,1']) {
  await page.click(`#presets [data-preset="${p}"]`); await settle();
  await page.click('#first'); await settle();
  left = await cjkLeftovers(page);
  check(`no visible Chinese in English mode after preset ${p}`, left.length === 0, left.slice(0, 6).join(' | '));
}
await page.click('#infoBtn');
left = await cjkLeftovers(page);
check('no visible Chinese in the English drawer', left.length === 0, left.slice(0, 6).join(' | '));
await page.keyboard.press('Escape');
check('English title', (await D(() => document.title)).startsWith('GOLDEN//CARRY · Golden carry'));
await D(() => document.activeElement && document.activeElement.blur());
await page.keyboard.press('Home'); await settle(); await page.click('#play');
await page.waitForFunction(() => getComputedStyle(document.getElementById('toast')).opacity === '1', null, { timeout: 10000 }).catch(() => {});
check('the end-of-playback toast is in English', /^Normalized after 1 carry: signed count \+1 = c$/.test(await text('#toast')));

/* ---------- hub round trip (the crumb leads to ../ = the book's visualization index) ---------- */
await page.click('.crumb'); await page.waitForLoadState('load');
// the hub lists every live visualization of the book; check this one's card, not the total
check('the crumb opens the hub, which keeps the language and lists this visualization', (await D(() => document.documentElement.dataset.lang)) === 'en'
  && (await D(() => document.querySelectorAll('.card[data-viz="golden-carry"]').length)) === 1 && (await D(() => !!document.querySelector('.card[data-viz="golden-carry"] img[src="golden-carry/thumb.jpg"]'))));
check('the choice is remembered under the site-wide key tr-lang', (await D(() => localStorage.getItem('tr-lang'))) === 'en');
left = await cjkLeftovers(page);
check('no visible Chinese on the English hub', left.length === 0, left.slice(0, 6).join(' | '));
await page.click('.card[data-viz="golden-carry"] .enter'); await page.waitForLoadState('load');
await page.waitForFunction(() => window.GC_DEBUG && GC_DEBUG.frames() > 0, null, { timeout: 30000 });
check('the hub card opens this page', (await D(() => document.body.dataset.vizId)) === ID);

/* ---------- layouts ---------- */
for (const lang of ['zh', 'en']) {
  for (const [w, h] of [[390, 844], [820, 1000], [1440, 900]]) {
    await page.setViewportSize({ width: w, height: h });
    await open(`?lang=${lang}`); await settle();
    check(`no horizontal scroll at ${w}px (${lang})`, (await overflowX(page)) === 0);
  }
}
await page.setViewportSize({ width: 740, height: 560 });
await open('?embed=1&lang=en'); await settle();
check('?embed=1 hides the header, crumb and key help', await D(() => ['header.top', '.crumb', '.keys'].every((s) => getComputedStyle(document.querySelector(s)).display === 'none') && document.documentElement.dataset.embed === '1'));
check('?embed=1&lang=en starts in English', (await D(() => TRV.lang())) === 'en' && (await cjkLeftovers(page)).length === 0);
check('embedded at 740px: two columns, no horizontal scroll', (await overflowX(page)) === 0 && (await D(() => { const a = document.getElementById('inputs').getBoundingClientRect(), b = document.getElementById('ledgerPanel').getBoundingClientRect(); return b.left > a.right - 1 && Math.abs(a.top - b.top) < 40; })));
await page.setViewportSize({ width: 360, height: 560 });
await open('?embed=1&lang=zh'); await settle();
check('embedded at 360px: no horizontal scroll', (await overflowX(page)) === 0);
await page.setViewportSize({ width: 1280, height: 720 });
await open('?thumb=1&lang=zh'); await settle();
check('?thumb=1: the deficit-map panel fills the frame', await D(() => { const r = document.getElementById('heat').getBoundingClientRect(); return document.documentElement.dataset.thumbMode === '1' && r.width === 1280 && r.height === 720; }));
await page.emulateMedia({ reducedMotion: 'reduce' });
await page.setViewportSize({ width: 1440, height: 900 });
await open('?lang=zh'); await settle();
check('reduced motion is honoured (no logo glitch)', (await D(() => TRV.reduceMotion)) === true && (await D(() => !document.getElementById('app').classList.contains('glitching'))));

check('no script errors, failed requests or console errors during the session', T.errors.length === 0, T.errors.slice(0, 4).join(' | '));
await T.finish();
