// Shared helpers for the slide-deck scripts (slides-check, slides-build, slides-new) and the
// Slidev theme's Vite plugin (theme/slides/setup/vite-plugins.ts).
//
// Layout (docs/ARCHITECTURE.md §2), the same as tools/tbook/slides.py:
//   books/<slug>/slides/<deck>/slides.md         the book's first language (book.toml editions[0], zh by default)
//   books/<slug>/slides/<deck>/slides.<lang>.md  every other edition language of the book (e.g. slides.en.md)
// slides.<first language>.md is not an edition (slides.md would shadow it; the checks report it).
// Directories whose name starts with "_" or "." are ignored.
//
// Adapted from chrono-company-slides scripts/lib.mjs (Apache-2.0, The Omega Institute / Chrono AI).
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

// tools/node/slides-lib.mjs -> repository root (TBOOK_ROOT overrides, as in tools/tbook/paths.py)
export const ROOT = resolve(process.env.TBOOK_ROOT || join(dirname(fileURLToPath(import.meta.url)), '..', '..'));
export const BOOKS = join(ROOT, 'books');
export const THEME_DIR = join(ROOT, 'theme', 'slides');
export const TEMPLATES = join(ROOT, 'templates', 'slides');
export const LOCK_FILE = join(ROOT, 'trureturing.lock.json');
export const PRIMARY_FILE = 'slides.md'; // the edition of the book's first language
export const DECK_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
export const LANG_RE = /^[a-z]{2,3}(?:-[A-Za-z0-9]+)*$/;
const toPosix = (p) => p.split(sep).join('/');

// --------------------------------------------------------------------------- TOML (subset)
// Enough TOML for site.toml, book.toml and theme/i18n/*.toml: tables, dotted keys, basic and
// literal strings (also multi-line), numbers, booleans, dates (kept as strings), arrays
// (also multi-line) and inline tables. Anything else raises with the line number.

export function parseToml(text, where = 'toml') {
  const root = {};
  let table = root;
  let i = 0;
  const n = text.length;
  let line = 1;
  const fail = (msg) => { throw new Error(`${where}:${line}: ${msg}`); };
  const peek = () => text[i];
  const skipWs = () => { while (i < n && (text[i] === ' ' || text[i] === '\t')) i++; };
  const skipWsNl = () => {
    for (;;) {
      skipWs();
      if (text[i] === '#') { while (i < n && text[i] !== '\n') i++; }
      if (text[i] === '\r') { i++; continue; }
      if (text[i] === '\n') { i++; line++; continue; }
      break;
    }
  };
  const ESC = { b: '\b', t: '\t', n: '\n', f: '\f', r: '\r', '"': '"', '\\': '\\', e: '\x1b' };
  function basicString() {
    const multi = text.startsWith('"""', i);
    i += multi ? 3 : 1;
    if (multi && text[i] === '\n') { i++; line++; }
    let out = '';
    for (;;) {
      if (i >= n) fail('unterminated string');
      const c = text[i];
      if (multi ? text.startsWith('"""', i) && text[i + 3] !== '"' : c === '"') { i += multi ? 3 : 1; return out; }
      if (c === '\n') { if (!multi) fail('newline in string'); line++; }
      if (c === '\\') {
        const d = text[i + 1];
        if (d === 'u' || d === 'U') {
          const len = d === 'u' ? 4 : 8;
          out += String.fromCodePoint(parseInt(text.slice(i + 2, i + 2 + len), 16));
          i += 2 + len;
          continue;
        }
        if (multi && (d === '\n' || d === ' ' || d === '\r')) { // line-ending backslash
          i++;
          while (i < n && /[\s]/.test(text[i])) { if (text[i] === '\n') line++; i++; }
          continue;
        }
        if (!(d in ESC)) fail(`bad escape \\${d}`);
        out += ESC[d];
        i += 2;
        continue;
      }
      out += c;
      i++;
    }
  }
  function literalString() {
    const multi = text.startsWith("'''", i);
    i += multi ? 3 : 1;
    if (multi && text[i] === '\n') { i++; line++; }
    const end = text.indexOf(multi ? "'''" : "'", i);
    if (end < 0) fail('unterminated string');
    const s = text.slice(i, end);
    if (!multi && s.includes('\n')) fail('newline in string');
    line += (s.match(/\n/g) || []).length;
    i = end + (multi ? 3 : 1);
    return s;
  }
  function key() {
    skipWs();
    if (peek() === '"') return basicString();
    if (peek() === "'") return literalString();
    const m = /^[A-Za-z0-9_-]+/.exec(text.slice(i, i + 256));
    if (!m) fail('expected a key');
    i += m[0].length;
    return m[0];
  }
  function dottedKey() {
    const parts = [key()];
    for (;;) {
      skipWs();
      if (peek() !== '.') return parts;
      i++;
      parts.push(key());
    }
  }
  function value() {
    skipWs();
    const c = peek();
    if (c === '"') return basicString();
    if (c === "'") return literalString();
    if (c === '[') {
      i++;
      const arr = [];
      for (;;) {
        skipWsNl();
        if (peek() === ']') { i++; return arr; }
        arr.push(value());
        skipWsNl();
        if (peek() === ',') { i++; continue; }
        if (peek() === ']') { i++; return arr; }
        fail('expected , or ] in array');
      }
    }
    if (c === '{') {
      i++;
      const obj = {};
      skipWs();
      if (peek() === '}') { i++; return obj; }
      for (;;) {
        const k = dottedKey();
        skipWs();
        if (peek() !== '=') fail('expected = in inline table');
        i++;
        setPath(obj, k, value());
        skipWs();
        if (peek() === ',') { i++; continue; }
        if (peek() === '}') { i++; return obj; }
        fail('expected , or } in inline table');
      }
    }
    const m = /^[^\s,\]}#]+(?: [0-9:.+\-Z]+)?/.exec(text.slice(i, i + 128));
    if (!m) fail('expected a value');
    i += m[0].length;
    const raw = m[0];
    if (raw === 'true') return true;
    if (raw === 'false') return false;
    if (/^[+-]?(?:0|[1-9][0-9_]*)$/.test(raw)) return Number(raw.replace(/_/g, ''));
    if (/^[+-]?[0-9_]+(?:\.[0-9_]+)?(?:[eE][+-]?[0-9]+)?$/.test(raw)) return Number(raw.replace(/_/g, ''));
    if (/^\d{4}-\d{2}-\d{2}/.test(raw) || /^\d{2}:\d{2}/.test(raw)) return raw; // dates stay strings
    fail(`unsupported value ${JSON.stringify(raw)}`);
  }
  function setPath(obj, parts, v) {
    let o = obj;
    for (const p of parts.slice(0, -1)) {
      if (o[p] === undefined) o[p] = {};
      if (typeof o[p] !== 'object' || Array.isArray(o[p])) fail(`key ${parts.join('.')} redefined`);
      o = o[p];
    }
    o[parts.at(-1)] = v;
  }
  function tableAt(parts, arrayOfTables) {
    let o = root;
    parts.forEach((p, idx) => {
      const last = idx === parts.length - 1;
      if (last && arrayOfTables) {
        if (o[p] === undefined) o[p] = [];
        if (!Array.isArray(o[p])) fail(`${parts.join('.')} is not an array of tables`);
        o[p].push({});
        o = o[p].at(-1);
        return;
      }
      if (o[p] === undefined) o[p] = {};
      o = Array.isArray(o[p]) ? o[p].at(-1) : o[p];
      if (typeof o !== 'object') fail(`${parts.join('.')} is not a table`);
    });
    return o;
  }
  for (;;) {
    skipWsNl();
    if (i >= n) break;
    if (peek() === '[') {
      const aot = text[i + 1] === '[';
      i += aot ? 2 : 1;
      const parts = dottedKey();
      skipWs();
      if (!text.startsWith(aot ? ']]' : ']', i)) fail('expected ] after table name');
      i += aot ? 2 : 1;
      table = tableAt(parts, aot);
    } else {
      const parts = dottedKey();
      skipWs();
      if (peek() !== '=') fail('expected =');
      i++;
      setPath(table, parts, value());
    }
    skipWs();
    if (peek() === '#') { while (i < n && text[i] !== '\n') i++; }
    if (i < n && text[i] !== '\n' && text[i] !== '\r') fail(`unexpected ${JSON.stringify(text[i])}`);
  }
  return root;
}

export const readToml = (path) => parseToml(readFileSync(path, 'utf8'), toPosix(relative(ROOT, path)) || path);

function deepMerge(base, extra) {
  const out = { ...base };
  for (const [k, v] of Object.entries(extra)) {
    out[k] = v && typeof v === 'object' && !Array.isArray(v) && out[k] && typeof out[k] === 'object' ? deepMerge(out[k], v) : v;
  }
  return out;
}

// --------------------------------------------------------------------------- site, books, i18n, lock

// Strings for `lang`: theme/i18n/<lang>.toml (English when missing) overridden by i18n/<lang>.toml,
// exactly as tbook.config.i18n() does.
export function i18n(lang, root = ROOT) {
  let base = join(root, 'theme', 'i18n', `${lang}.toml`);
  if (!existsSync(base)) base = join(root, 'theme', 'i18n', 'en.toml');
  let table = existsSync(base) ? parseToml(readFileSync(base, 'utf8'), base) : {};
  const local = join(root, 'i18n', `${lang}.toml`);
  if (existsSync(local)) table = deepMerge(table, parseToml(readFileSync(local, 'utf8'), local));
  return table;
}

export const bcp47 = (lang, root = ROOT) => String(i18n(lang, root)?.meta?.bcp47 || lang);

export function loadSite(root = ROOT) {
  const file = join(root, 'site.toml');
  const raw = existsSync(file) ? parseToml(readFileSync(file, 'utf8'), 'site.toml') : {};
  const site = raw.site ?? {};
  let baseUrl = process.env.TBOOK_BASE_URL || site.base_url || '';
  if (baseUrl && !baseUrl.endsWith('/')) baseUrl += '/';
  return { raw, languages: site.languages ?? ['zh', 'en'], baseUrl };
}

const localized = (v) => (v == null ? {} : typeof v === 'string' ? { '*': v } : { ...v });
export const pick = (text, lang, fallback = []) => {
  if (lang in text) return text[lang];
  if ('*' in text) return text['*'];
  for (const l of fallback) if (l in text) return text[l];
  return Object.values(text)[0] ?? '';
};

export function loadBook(slug, root = ROOT) {
  const dir = join(root, 'books', slug);
  const file = join(dir, 'book.toml');
  if (!existsSync(file)) throw new Error(`books/${slug}/book.toml not found`);
  const raw = parseToml(readFileSync(file, 'utf8'), `books/${slug}/book.toml`);
  const meta = raw.book ?? {};
  const languages = meta.editions?.length ? meta.editions : loadSite(root).languages;
  return {
    slug,
    dir,
    slidesDir: join(dir, 'slides'),
    version: String(meta.version ?? '0.1.0'),
    code: String(meta.code ?? slug.toUpperCase().replace('-', '//')),
    title: localized(meta.title),
    languages,
  };
}

export function listBooks(root = ROOT) {
  const dir = join(root, 'books');
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((n) => existsSync(join(dir, n, 'book.toml'))).sort().map((n) => loadBook(n, root));
}

export function loadLock(root = ROOT) {
  const file = join(root, 'trureturing.lock.json');
  if (!existsSync(file)) return null;
  return JSON.parse(readFileSync(file, 'utf8'));
}

// Source permalink of a locked declaration at the pinned commit (same as tbook.lean.Lock.source_url).
export function leanSourceUrl(lock, gid) {
  if (!lock) return '';
  const module = gid.slice(0, gid.indexOf('.')) || gid;
  const line = lock.declarations?.[gid]?.line;
  return `https://github.com/${lock.repo}/blob/${lock.commit}/${module}.lean${line ? `#L${line}` : ''}`;
}

export const GID_RE = /^D[0-9]+\/S[0-9]+\/(?:[A-Za-z_][A-Za-z0-9_]*\/)*[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*$/;

// --------------------------------------------------------------------------- decks

// `book` is anything with `languages` (the book's edition languages, the first one owning slides.md).
export const primaryLang = (book) => book.languages[0];
export const editionFile = (book, lang) => (lang === primaryLang(book) ? PRIMARY_FILE : `slides.${lang}.md`);
// The edition language of a deck file, or null when it is not an edition (slides.<first language>.md is not).
export function langOfFile(book, name) {
  if (name === PRIMARY_FILE) return primaryLang(book) ?? null;
  const m = /^slides\.([a-z]{2,3}(?:-[A-Za-z0-9]+)*)\.md$/.exec(name);
  return m && m[1] !== primaryLang(book) ? m[1] : null;
}

// The `theme:` value every deck must use: the relative path from the deck to theme/slides.
export const themeRef = (deckDir, root = ROOT) => toPosix(relative(deckDir, join(root, 'theme', 'slides')));

export function deckNames(book) {
  if (!existsSync(book.slidesDir)) return [];
  return readdirSync(book.slidesDir)
    .filter((n) => !/^[_.]/.test(n) && statSync(join(book.slidesDir, n)).isDirectory())
    .sort();
}

// Languages present in a deck directory, the book's own order first.
export function deckLangs(book, deck) {
  const dir = join(book.slidesDir, deck);
  const found = [...new Set(readdirSync(dir).map((n) => langOfFile(book, n)).filter(Boolean))];
  const rank = (l) => (book.languages.includes(l) ? book.languages.indexOf(l) : book.languages.length);
  return found.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}

// One language edition of a deck, parsed with Slidev's own parser.
export async function readEdition(book, deck, lang) {
  const { parseSync } = await import('@slidev/parser');
  const dir = join(book.slidesDir, deck);
  const file = join(dir, editionFile(book, lang));
  const md = readFileSync(file, 'utf8');
  const all = parseSync(md, file).slides;
  // Slidev drops slides marked hide/disabled from the presentation and the PDF.
  const slides = all.filter((s) => !(s.frontmatter?.hide || s.frontmatter?.disabled));
  const head = all[0]?.frontmatter ?? {};
  return {
    book: book.slug,
    deck,
    lang,
    dir,
    file,
    rel: toPosix(relative(ROOT, file)),
    md,
    head,
    meta: head.deck ?? {},
    title: String(head.title ?? ''),
    info: String(head.info ?? ''),
    all,
    slides,
    count: slides.length,
  };
}

// Publication paths, shared with tools/tbook/slides.py (keep in sync):
//   site:  _site/<slug>/slides/<deck>/        the book's first language
//          _site/<slug>/slides/<deck>/<lang>/ every other language
//          _site/<slug>/slides/<deck>/<slug>-<deck>-<lang>.pdf
//   build: build/slides/<slug>/<deck>/<lang>/ and build/slides/<slug>/<deck>-<lang>.pdf
export const sitePathOf = (book, deck, lang) => (lang === primaryLang(book) ? `${deck}/` : `${deck}/${lang}/`);
export const pdfName = (slug, deck, lang) => `${slug}-${deck}-${lang}.pdf`;
export const buildPdfName = (deck, lang) => `${deck}-${lang}.pdf`;

// URL path of the site root (from site.toml base_url) such as "/books/"; "/" when unknown.
export function basePath(baseUrl) {
  if (!baseUrl) return '/';
  let p = baseUrl;
  try { p = new URL(baseUrl).pathname; } catch {}
  if (!p.startsWith('/')) p = '/' + p;
  return p.endsWith('/') ? p : p + '/';
}

export const deckBase = (base, book, deck, lang) => `${basePath(base)}${book.slug}/slides/${sitePathOf(book, deck, lang)}`;

// --------------------------------------------------------------------------- slidev

export function slidevBin(root = ROOT) {
  const bin = join(root, 'node_modules', '.bin', process.platform === 'win32' ? 'slidev.cmd' : 'slidev');
  if (!existsSync(bin)) throw new Error('Slidev is not installed: run `npm ci` at the repository root');
  return bin;
}

// Run a slidev sub-command; throw with its output on failure. The last argument may be { env }.
export function slidev(cmd, ...rest) {
  const opts = rest.length && typeof rest.at(-1) === 'object' ? rest.pop() : {};
  const env = { ...process.env, ...(opts.env ?? {}) };
  const r = spawnSync(slidevBin(), [cmd, ...rest], { cwd: ROOT, env, encoding: 'utf8', maxBuffer: 1 << 28 });
  if (r.status !== 0) {
    process.stderr.write((r.stdout ?? '') + (r.stderr ?? ''));
    throw new Error(`slidev ${cmd} ${rest[0] ?? ''} failed (exit ${r.status ?? r.signal})`);
  }
  return r.stdout ?? '';
}

// Command-line helpers: --name value (repeatable) and --flag.
export function argParser(argv) {
  const args = [...argv];
  return {
    all(name) {
      const out = [];
      for (let i = args.indexOf(name); i >= 0; i = args.indexOf(name)) {
        if (i + 1 >= args.length) throw new Error(`${name} needs a value`);
        out.push(args[i + 1]);
        args.splice(i, 2);
      }
      return out;
    },
    one(name, dflt) { const v = this.all(name); return v.length ? v.at(-1) : dflt; },
    flag(name) { const i = args.indexOf(name); if (i < 0) return false; args.splice(i, 1); return true; },
    rest: () => args,
  };
}

// Books (optionally restricted to slugs) that have at least one deck.
export function booksWithDecks(slugs = []) {
  const books = listBooks();
  const unknown = slugs.filter((s) => !books.some((b) => b.slug === s));
  if (unknown.length) throw new Error(`unknown book(s): ${unknown.join(', ')}; known: ${books.map((b) => b.slug).join(', ') || 'none'}`);
  return books.filter((b) => (!slugs.length || slugs.includes(b.slug)) && deckNames(b).length);
}

export { toPosix };
