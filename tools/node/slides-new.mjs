// Scaffold a slide deck for a book from templates/slides/:
//
//   node tools/node/slides-new.mjs <book> <deck> "<中文标题>" ["<English title>"]
//   (also: ./tbook slides new <book> <deck> "<中文标题>" "<English title>")
//
// Creates books/<book>/slides/<deck>/ with one edition per language of the book: slides.md for the
// book's first language (book.toml editions[0]) and slides.<lang>.md for every other language. Each is
// filled from the template of its language, templates/slides/slides.<lang>.md (zh and en exist), or else
// the English one (with the English title, to be translated). Headmatter is filled from book.toml: theme
// path, book code, book title, version and the language's BCP 47 tag.
//
// Adapted from chrono-company-slides scripts/new.mjs (Apache-2.0).
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { DECK_RE, ROOT, TEMPLATES, bcp47, editionFile, loadBook, pick, themeRef, toPosix } from './slides-lib.mjs';

const USAGE = 'usage: node tools/node/slides-new.mjs <book> <deck> "<中文标题>" ["<English title>"]';
const [slug, deck, zhTitle, enTitle, ...extra] = process.argv.slice(2);
if (!slug || !deck || !zhTitle || extra.length) {
  console.error(USAGE);
  process.exit(2);
}
if (!DECK_RE.test(deck)) {
  console.error(`slides-new: deck name ${JSON.stringify(deck)} must be kebab-case (a-z, 0-9, -), e.g. overview`);
  process.exit(2);
}

for (const t of [zhTitle, enTitle].filter(Boolean)) {
  if (/[<>]|\{\{/.test(t)) {
    console.error(`slides-new: titles must not contain <, > or {{ (Slidev renders the title as a Vue template): ${JSON.stringify(t)}`);
    process.exit(2);
  }
}

let book;
try {
  book = loadBook(slug);
} catch (e) {
  console.error(`slides-new: ${e.message}`);
  process.exit(1);
}
const dir = join(book.slidesDir, deck);
if (existsSync(dir)) {
  console.error(`slides-new: ${toPosix(relative(ROOT, dir))} already exists`);
  process.exit(1);
}

const yaml = (s) => String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
const html = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/\{/g, '&#123;'); // { : no Vue interpolation
const titleFor = (lang) => (lang === 'zh' ? zhTitle : enTitle || zhTitle);

// Templates are named by language (templates/slides/slides.<lang>.md), whichever language a book puts first.
function template(lang) {
  for (const name of [`slides.${lang}.md`, 'slides.en.md']) {
    const file = join(TEMPLATES, name);
    if (existsSync(file)) return readFileSync(file, 'utf8');
  }
  throw new Error(`no template for ${lang} in templates/slides/`);
}

mkdirSync(dir, { recursive: true });
const made = [];
for (const lang of book.languages) {
  const title = titleFor(lang);
  const bookTitle = pick(book.title, lang, book.languages);
  const vars = {
    THEME: themeRef(dir),
    LANG: bcp47(lang),
    VERSION: yaml(book.version),
    TITLE: yaml(title),
    BOOK: yaml(bookTitle),
    CODE: yaml(book.code),
    TITLE_HTML: html(title),
    BOOK_HTML: html(bookTitle),
    CODE_HTML: html(book.code),
  };
  const md = template(lang).replace(/\{\{([A-Z_]+)\}\}/g, (m, k) => (k in vars ? vars[k] : m));
  const file = join(dir, editionFile(book, lang));
  writeFileSync(file, md);
  made.push(toPosix(relative(ROOT, file)));
}
console.log(`created ${made.join(', ')}`);
console.log(`preview: npx slidev ${made[0]}   check: ./tbook check   build: ./tbook build slides --book ${slug}`);
if (!enTitle && book.languages.some((l) => l !== 'zh')) console.log('note: no English title given; the Chinese title was used, translate it in the other editions');
