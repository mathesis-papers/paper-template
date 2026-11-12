// The print backdrop of the slide theme: theme/slides/styles/backdrop.jpg.
//
//   node tools/node/slides-backdrop.mjs [--check] [--force]
//
// Every slide's backdrop (void, aurora, scanlines, corner brackets, vignette) is a stack of CSS layers
// defined in theme/slides/styles/backdrop.css. In a PDF those full-page translucent gradients become soft
// masks and shadings that readers composite again on every page (about two seconds a page), so the print
// view (Slidev's PDF export) shows them as one image instead: this script renders that image in Chromium
// from backdrop.css and theme/generated/tokens.css, exactly as the layers look on screen, and records a
// fingerprint of its inputs (backdrop.css and the custom properties it uses, resolved through tokens.css)
// in backdrop.json.
//   (no flag)  render the image when the fingerprint changed (--force: always), write backdrop.json
//   --check    exit 1 when backdrop.json does not match the current inputs (slides-check runs this check)
// Chromium: $PW_CHROMIUM_PATH when set, otherwise Playwright's own download.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ROOT, argParser, toPosix } from './slides-lib.mjs';

const STYLES = join(ROOT, 'theme', 'slides', 'styles');
export const BACKDROP_CSS = join(STYLES, 'backdrop.css');
export const BACKDROP_IMG = join(STYLES, 'backdrop.jpg');
export const BACKDROP_META = join(STYLES, 'backdrop.json');
const TOKENS_CSS = join(ROOT, 'theme', 'generated', 'tokens.css');
// The slide canvas (theme/slides/package.json: canvasWidth 1920, aspect ratio 16/9) and the image format.
const WIDTH = 1920;
const HEIGHT = 1080;
const QUALITY = 90;
const VERSION = 2; // bump when the rendering below or the fingerprint changes
const rel = (p) => toPosix(relative(ROOT, p));

// The custom properties of the first `:root { … }` block of tokens.css (the dark palette slides use).
function rootVars(tokensCss) {
  const block = /:root\s*\{([^}]*)\}/.exec(tokensCss)?.[1] ?? '';
  const vars = new Map();
  for (const m of block.matchAll(/(--[\w-]+)\s*:\s*([^;]*);/g)) if (!vars.has(m[1])) vars.set(m[1], m[2].trim());
  return vars;
}

// What the image shows: backdrop.css without its print rules (which only use the image), and every custom
// property it uses, directly or through another one, with its tokens.css value. `problems` are what the
// rendering cannot see: a property tokens.css does not define (deck.css, say), a url() it would not load.
function backdropInputs(css, tokensCss) {
  const shown = css.replace(/\/\*[\s\S]*?\*\//g, '').replace(/:where\(html\.print\)[^{]*\{[^}]*\}/g, '')
    .replace(/[ \t]+$/gm, '').replace(/\n{2,}/g, '\n').trim(); // comments and blank lines draw nothing
  const vars = rootVars(tokensCss);
  const used = {};
  const todo = [...shown.matchAll(/var\(\s*(--[\w-]+)/g)].map((m) => m[1]);
  while (todo.length) {
    const name = todo.pop();
    if (name in used) continue;
    used[name] = vars.get(name) ?? null;
    for (const m of (used[name] ?? '').matchAll(/var\(\s*(--[\w-]+)/g)) todo.push(m[1]);
  }
  const problems = Object.keys(used).filter((k) => used[k] === null).sort()
    .map((k) => `${rel(BACKDROP_CSS)} uses ${k}, which the first :root block of ${rel(TOKENS_CSS)} does not define; `
      + 'the backdrop is rendered from those two files alone, so use a token');
  if (/url\(/i.test(shown)) {
    problems.push(`${rel(BACKDROP_CSS)} loads a url() outside its print rules; the backdrop is rendered from CSS alone`);
  }
  const sorted = Object.fromEntries(Object.keys(used).sort().map((k) => [k, used[k]]));
  return { shown, vars: sorted, problems };
}

// The fingerprint of backdropInputs: it changes exactly when the rendered image would.
export function backdropFingerprint(css, tokensCss) {
  const { shown, vars } = backdropInputs(css, tokensCss);
  const inputs = JSON.stringify({ version: VERSION, width: WIDTH, height: HEIGHT, quality: QUALITY, css: shown, vars });
  return createHash('sha256').update(inputs).digest('hex');
}

// { fresh, fingerprint, problems, message }: whether backdrop.jpg and backdrop.json match backdrop.css and
// tokens.css; `problems` (backdropInputs) make the image wrong whatever is rendered: they are reported first.
export function backdropState() {
  if (!existsSync(BACKDROP_CSS)) return { fresh: true, fingerprint: '', problems: [], message: '' }; // no slide theme
  const css = readFileSync(BACKDROP_CSS, 'utf8');
  const tokens = readFileSync(TOKENS_CSS, 'utf8');
  const { problems } = backdropInputs(css, tokens);
  const fingerprint = backdropFingerprint(css, tokens);
  let recorded = '';
  try { recorded = JSON.parse(readFileSync(BACKDROP_META, 'utf8')).fingerprint ?? ''; } catch {}
  const fresh = !problems.length && recorded === fingerprint && existsSync(BACKDROP_IMG);
  const message = problems.length ? problems.join('; ') : fresh ? ''
    : `${rel(BACKDROP_IMG)} does not match ${rel(BACKDROP_CSS)} and ${rel(TOKENS_CSS)} (the PDF export shows it instead`
      + ` of the slide backdrop); run node tools/node/slides-backdrop.mjs and commit ${rel(BACKDROP_IMG)} and ${rel(BACKDROP_META)}`;
  return { fresh, fingerprint, problems, message };
}

async function launch() {
  const { chromium } = await import('playwright-chromium');
  try {
    return await chromium.launch({ executablePath: process.env.PW_CHROMIUM_PATH || undefined });
  } catch (e) {
    throw new Error(`cannot start Chromium (${e.message.split('\n')[0]}); set PW_CHROMIUM_PATH to a Chromium binary or run \`npx playwright install chromium\``);
  }
}

// Render backdrop.jpg and write backdrop.json (with `browser`, or a Chromium of its own). Returns the paths.
export async function renderBackdrop(browser = null) {
  const { fingerprint, problems } = backdropState();
  if (problems.length) throw new Error(problems.join('; '));
  const own = !browser;
  browser ??= await launch();
  try {
    const page = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 1 });
    // the slide as the layouts build it (layouts/default.vue, layouts/cover.vue), with the canvas geometry
    // of deck.css; nothing else is on it
    // (inline: a page set with setContent is about:blank, which may not load file: stylesheets)
    const css = readFileSync(TOKENS_CSS, 'utf8') + '\n' + readFileSync(BACKDROP_CSS, 'utf8');
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8">
<style>${css.replace(/<\/style/gi, '<\\/style')}</style>
<style>html, body { margin: 0; } .slide { position: relative; width: ${WIDTH}px; height: ${HEIGHT}px; overflow: hidden; isolation: isolate; }</style>
</head><body><div class="slide"><div class="tr-fx"><i class="bracket tl"></i><i class="bracket tr"></i><i class="bracket bl"></i><i class="bracket br"></i></div></div></body></html>`,
    { waitUntil: 'load' });
    await page.locator('.slide').screenshot({ path: BACKDROP_IMG, type: 'jpeg', quality: QUALITY });
    await page.close();
  } finally {
    if (own) await browser.close();
  }
  writeFileSync(BACKDROP_META, JSON.stringify({
    image: 'backdrop.jpg', width: WIDTH, height: HEIGHT, quality: QUALITY, fingerprint,
    source: 'tools/node/slides-backdrop.mjs from backdrop.css and theme/generated/tokens.css',
  }, null, 2) + '\n');
  return [BACKDROP_IMG, BACKDROP_META];
}

// run as a script (also through a symbolic link, which Node resolves for import.meta.url), not imported
const invoked = (() => { try { return realpathSync(process.argv[1] ?? ''); } catch { return ''; } })();
if (invoked === realpathSync(fileURLToPath(import.meta.url))) {
  const cli = argParser(process.argv.slice(2));
  const check = cli.flag('--check');
  const force = cli.flag('--force');
  if (cli.rest().length) {
    console.error(`slides-backdrop: unexpected arguments ${cli.rest().join(' ')}`);
    process.exit(2);
  }
  const state = backdropState();
  if (check) {
    if (!state.fresh) {
      console.error(`slides-backdrop: ${state.message}`);
      process.exit(1);
    }
    console.log(`slides-backdrop: ${rel(BACKDROP_IMG)} is up to date`);
  } else if (state.problems.length) {
    console.error(`slides-backdrop: ${state.message}`);
    process.exit(1);
  } else if (state.fresh && !force) {
    console.log(`slides-backdrop: ${rel(BACKDROP_IMG)} is up to date`);
  } else {
    for (const p of await renderBackdrop()) console.log(`wrote ${rel(p)}`);
  }
}
