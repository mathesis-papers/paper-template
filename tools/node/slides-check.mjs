// Static checks of the slide decks (no browser; layout, fonts and PDF page counts are checked by
// slides-build.mjs):
//
//   node tools/node/slides-check.mjs [--book <slug>]… [--deck <name>]…
//
// For every books/<slug>/slides/<deck>/:
//   - an edition file for every language of the book (slides.md for zh, slides.<lang>.md otherwise),
//     and no file for a language the book does not have;
//   - headmatter: theme is the relative path to theme/slides, title, htmlAttrs.lang equal to the
//     language's BCP 47 tag (theme/i18n/<lang>.toml meta.bcp47), deck.code / deck.title / deck.version;
//     deck.code and deck.version identical in every language;
//   - every language page for page: same slide count, and on each slide the same layout, bare, chapter,
//     hide/disabled flags, presence of a section, and the same sequence of cited Lean GIDs;
//   - every <LeanBadge gid> / <TheoremCard gid> is a GID present in trureturing.lock.json (TheoremCard
//     GIDs must be Lean theorems unless kind="definition"); status="open" cites no GID;
//   - no root-relative or file: links (the site is served under /<repo>/), no index.html in the deck;
//   - no class name or attribute on an HTML element that UnoCSS (bundled with Slidev) would turn into
//     a utility that overrides the theme.
// Exit status 1 when any check fails.
//
// Adapted from chrono-company-slides scripts/check.mjs (Apache-2.0).
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import {
  DECK_RE, GID_RE, ROOT, argParser, bcp47, booksWithDecks, deckLangs, deckNames, editionFile, loadLock,
  readEdition, themeRef, toPosix,
} from './slides-lib.mjs';

const cli = argParser(process.argv.slice(2));
const bookSlugs = cli.all('--book');
const deckFilter = cli.all('--deck');
const errors = [];
const fail = (msg) => errors.push(msg);

// Component tags whose `gid` the check verifies.
const TAG_RE = /<(LeanBadge|TheoremCard)\b((?:"[^"]*"|'[^']*'|[^'">])*)>/g;
const ATTR_RE = /([:@]?[\w.-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'))?/g;

function attrsOf(text) {
  const out = {};
  for (const m of text.matchAll(ATTR_RE)) out[m[1]] = m[2] ?? m[3] ?? true;
  return out;
}

const stripCode = (md) => md.replace(/^(\s*)(`{3,}|~{3,})[^\n]*\n[\s\S]*?^\1\2[^\n]*$/gm, '');

// Cited GIDs of one slide, in order: [{ tag, gid, attrs }]; problems go to `bad`.
function citations(content, bad) {
  const out = [];
  for (const m of stripCode(content).matchAll(TAG_RE)) {
    const attrs = attrsOf(m[2]);
    let gid = attrs.gid;
    if (attrs[':gid'] !== undefined) {
      const lit = /^\s*(['"`])(.*)\1\s*$/.exec(String(attrs[':gid']));
      if (lit) gid = lit[2];
      else bad(`<${m[1]} :gid="${attrs[':gid']}">: write gid as a literal string so it can be checked`);
    }
    out.push({ tag: m[1], gid: typeof gid === 'string' ? gid.trim() : '', attrs });
  }
  return out;
}

const ABS_LINK = [
  /\b(?:href|src|poster|data)\s*=\s*["'](\/(?!\/)[^"']*|file:[^"']*)["']/gi,
  /\]\((\/(?!\/)[^)\s]*|file:[^)\s]*)\)/g,
  /url\(\s*["']?(\/(?!\/)[^"')]*)/gi,
];

const lock = loadLock();
if (!lock) fail('trureturing.lock.json not found: run ./tbook pin');
const decls = lock?.declarations ?? {};

// UnoCSS collisions (see theme/slides/uno.config.ts, whose blocklist is honoured here).
const unoConfig = readFileSync(join(ROOT, 'theme', 'slides', 'uno.config.ts'), 'utf8');
const UNO_BLOCKLIST = [...(/blocklist:\s*\[([^\]]*)\]/.exec(unoConfig)?.[1] ?? '').matchAll(/['"]([^'"]+)['"]/g)].map((m) => m[1]);
const UNO_HARMLESS = new Set(['grow']); // same effect as the theme rule of that name
let uno = null;
async function unoConflicts(md) {
  if (!uno) {
    const { createGenerator, presetWind3, presetAttributify } = await import('unocss');
    uno = await createGenerator({ presets: [presetWind3(), presetAttributify()], blocklist: UNO_BLOCKLIST });
  }
  const classes = new Set();
  const attrs = [];
  for (const [, , rest] of md.matchAll(/<([a-z][\w-]*)\b([^>]*)>/g)) {
    for (const [, name, val] of rest.matchAll(/([\w:.-]+)="([^"]*)"/g)) {
      if (name === 'class') val.split(/\s+/).filter(Boolean).forEach((c) => classes.add(c));
      else if (!/^(style|href|src|id|role|lang|title|alt|xmlns|target|rel|data-|aria-)/.test(name)) attrs.push(`${name}="${val}"`);
    }
  }
  const out = [];
  for (const u of (await uno.generate([...classes].join(' '), { preflights: false })).matched) {
    if (!UNO_HARMLESS.has(u)) out.push(`class ${u} is also a UnoCSS utility and its generated style overrides the theme; rename it or add it to the blocklist in theme/slides/uno.config.ts`);
  }
  for (const u of (await uno.generate(`<div ${attrs.join(' ')}>`, { preflights: false })).matched) {
    out.push(`attribute ${u} is read by UnoCSS (attributify) as a style; use style="…" instead`);
  }
  return out;
}

const books = booksWithDecks(bookSlugs);
let editionCount = 0;
let deckCount = 0;
for (const book of books) {
  for (const deck of deckNames(book).filter((d) => !deckFilter.length || deckFilter.includes(d))) {
    deckCount++;
    const dir = join(book.slidesDir, deck);
    const at = toPosix(join('books', book.slug, 'slides', deck));
    if (!DECK_RE.test(deck)) fail(`${at}: deck names are kebab-case (a-z, 0-9, -)`);
    if (existsSync(join(dir, 'index.html'))) fail(`${at}/index.html: Slidev merges it into every page; delete it`);
    const langs = deckLangs(book, deck);
    for (const name of readdirSync(dir)) {
      if (/^slides\..+\.md$/.test(name) && !langs.some((l) => editionFile(l) === name)) fail(`${at}/${name}: not an edition file (slides.md or slides.<lang>.md)`);
    }
    for (const lang of langs) if (!book.languages.includes(lang)) fail(`${at}/${editionFile(lang)}: ${lang} is not an edition of this book (book.toml editions: ${book.languages.join(', ')})`);
    for (const lang of book.languages) if (!langs.includes(lang)) fail(`${at}: missing ${editionFile(lang)} (every deck has an edition for each language of the book: ${book.languages.join(', ')})`);
    const eds = [];
    for (const lang of book.languages.filter((l) => langs.includes(l))) eds.push(await readEdition(book, deck, lang));
    if (!eds.length) continue;
    const theme = themeRef(dir);
    for (const ed of eds) {
      editionCount++;
      const where = ed.rel;
      if (ed.head.theme !== theme) fail(`${where}: headmatter must say theme: ${theme} (the shared theme)`);
      if (!ed.title) fail(`${where}: headmatter title is missing`);
      else if (/[<>]|\{\{/.test(ed.title)) fail(`${where}: title must not contain <, > or {{ (Slidev renders it as a Vue template)`);
      const want = bcp47(ed.lang);
      if (ed.head.htmlAttrs?.lang !== want) fail(`${where}: headmatter must set htmlAttrs.lang: "${want}" (the language of the file)`);
      for (const k of ['code', 'title', 'version']) if (!ed.meta[k]) fail(`${where}: deck.${k} is missing (header and footer need it)`);
      if (!ed.count) fail(`${where}: no slides`);
      ed.cites = ed.slides.map((s, i) => citations(s.content ?? '', (msg) => fail(`${where} slide ${i + 1}: ${msg}`)));
      ed.slides.forEach((s, i) => {
        const here = `${where} slide ${i + 1}`;
        for (const c of ed.cites[i]) {
          if (c.attrs.status === 'open' && c.gid) fail(`${here}: <${c.tag} status="open"> must not cite Lean (open problems have no proof); drop gid`);
          if (!c.gid) {
            if (!c.attrs.status) fail(`${here}: <${c.tag}> needs gid="<GID>" or status="open|argued"`);
            continue;
          }
          if (!GID_RE.test(c.gid)) { fail(`${here}: ${c.gid} is not a GID (<module path>.<name>, e.g. D5/S1/Deficit/DeficitThreeValued.deficit_three_valued)`); continue; }
          const d = decls[c.gid];
          if (!d) fail(`${here}: ${c.gid} is not in trureturing.lock.json; slides may only cite declarations the lock resolves (cite it in the book and run ./tbook pin --refresh)`);
          else if (c.tag === 'TheoremCard' && c.attrs.kind !== 'definition' && d.kind !== 'theorem') fail(`${here}: ${c.gid} is a Lean ${d.kind}; a TheoremCard must cite a theorem (or say kind="definition")`);
        }
        const body = stripCode(s.content ?? '');
        for (const re of ABS_LINK) for (const m of body.matchAll(re)) fail(`${here}: link ${m[1]} is absolute; the site lives under /<repo>/, use a relative or https:// link`);
      });
      for (const msg of await unoConflicts(ed.md)) fail(`${where}: ${msg}`);
    }
    // page-for-page parity with the primary language
    const [main, ...rest] = eds;
    for (const ed of rest) {
      if (ed.count !== main.count) fail(`${ed.rel}: ${ed.count} slides, ${main.rel} has ${main.count}; editions correspond page for page`);
      for (const k of ['code', 'version']) if (String(ed.meta[k] ?? '') !== String(main.meta[k] ?? '')) fail(`${ed.rel}: deck.${k} differs from ${main.rel} (${main.meta[k] ?? '—'})`);
      for (let i = 0; i < Math.min(ed.count, main.count); i++) {
        const a = main.slides[i].frontmatter ?? {};
        const b = ed.slides[i].frontmatter ?? {};
        for (const key of ['layout', 'bare', 'chapter', 'class']) {
          if (String(a[key] ?? '') !== String(b[key] ?? '')) fail(`${ed.rel} slide ${i + 1}: ${key} is ${JSON.stringify(b[key] ?? null)}, ${main.rel} has ${JSON.stringify(a[key] ?? null)}`);
        }
        if (!!a.section !== !!b.section) fail(`${ed.rel} slide ${i + 1}: section ${b.section ? 'present' : 'missing'}, unlike ${main.rel}`);
        const ga = main.cites[i].map((c) => c.gid || `(${c.attrs.status})`).join(' ');
        const gb = ed.cites[i].map((c) => c.gid || `(${c.attrs.status})`).join(' ');
        if (ga !== gb) fail(`${ed.rel} slide ${i + 1}: cites [${gb}], ${main.rel} cites [${ga}]`);
      }
    }
    for (const ed of eds) console.log(`${ed.rel}: ${ed.lang}, ${ed.count} slides`);
  }
}

if (errors.length) {
  console.error(`\nslides-check failed (${errors.length}):\n- ${errors.join('\n- ')}`);
  process.exit(1);
}
console.log(`slides-check: ${deckCount} deck(s), ${editionCount} edition(s), ok`);
