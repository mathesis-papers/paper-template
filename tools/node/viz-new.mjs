#!/usr/bin/env node
// Scaffold a new visualization of a book from templates/viz/ and register it as a draft:
//   node tools/node/viz-new.mjs <book> <id> "<CODE//NAME>" "<中文标题>" ["<English title>"]
// (same as: ./tbook viz new <book> <id> "<CODE//NAME>" "<中文标题>" "<English title>")
// Writes books/<book>/viz/<id>/{index.html,style.css,main.js} and books/<book>/viz/tests/<id>.test.mjs.
// Drafts are not published; set status to "live" once the page, summary, theory links, test and thumbnail are done.
// Adapted from trureturing-visualize/scripts/new-viz.mjs (Apache-2.0, the-omega-institute).
import fs from 'node:fs';
import path from 'node:path';
import { ID_RE, RESERVED, TEMPLATES, resolveBook, registryPath, readRegistry, writeRegistry, rel } from './viz-common.mjs';

export const PAGE_FILES = ['index.html', 'style.css', 'main.js'];
export const TEST_TEMPLATE = 'test.mjs';

/** HTML-escape like Python's html.escape(s, quote=True). */
const escHtml = (s) => s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#x27;');

/** Fill the placeholders of a template (same as fill_template in tools/tbook/viz.py). In an HTML template the code and
    titles are HTML-escaped; in a script or stylesheet, where they only appear in comments, a "*\/" is broken up. */
export function fill(text, { slug, id, code, title, titleEn }, { html = true } = {}) {
  const val = (s) => (html ? escHtml(s) : s.replaceAll('*/', '* /'));
  const [head, ...rest] = code.split('//');
  const codeHtml = rest.length ? `${val(head)}<b>//</b>${val(rest.join('//'))}` : val(code);
  return text.replaceAll('__BOOK__', slug).replaceAll('__ID__', id).replaceAll('__CODE_HTML__', codeHtml).replaceAll('__CODE__', val(code))
    .replaceAll('__TITLE_EN__', val(titleEn || title)).replaceAll('__TITLE__', val(title));
}

export function scaffold(book, { id, code, title, titleEn = '', added = new Date().toISOString().slice(0, 10) }) {
  if (!ID_RE.test(id) || RESERVED.includes(id)) throw new Error(`id "${id}" must be kebab-case (a-z, 0-9, -) and not ${RESERVED.join(' or ')}`);
  if (!code || !title) throw new Error('code and Chinese title are required');
  const dest = path.join(book.dir, 'viz', id);
  if (fs.existsSync(dest)) throw new Error(`${rel(dest)}/ already exists`);
  const reg = fs.existsSync(registryPath(book)) ? readRegistry(book) : { version: 1, visualizations: [] };
  if ((reg.visualizations || []).some((v) => v.id === id)) throw new Error(`${id} is already registered in ${rel(registryPath(book))}`);
  const vars = { slug: book.slug, id, code, title, titleEn };
  fs.mkdirSync(dest, { recursive: true });
  for (const name of PAGE_FILES) {
    fs.writeFileSync(path.join(dest, name), fill(fs.readFileSync(path.join(TEMPLATES, name), 'utf8'), vars, { html: name.endsWith('.html') }));
  }
  const testFile = path.join(book.dir, 'viz', 'tests', `${id}.test.mjs`);
  if (!fs.existsSync(testFile)) {
    fs.mkdirSync(path.dirname(testFile), { recursive: true });
    fs.writeFileSync(testFile, fill(fs.readFileSync(path.join(TEMPLATES, TEST_TEMPLATE), 'utf8'), vars, { html: false }));
  }
  reg.version = reg.version || 1;
  reg.visualizations = reg.visualizations || [];
  reg.visualizations.push({
    id, code, title, title_en: titleEn, summary: '', summary_en: '', path: `${id}/`, thumbnail: `${id}/thumb.jpg`,
    status: 'draft', added, tags: [], tags_en: [], theory: [], lean: []
  });
  writeRegistry(book, reg);
  return { dest, testFile };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [bookArg, id, code, title, titleEn = ''] = process.argv.slice(2);
  if (!bookArg || !id || !code || !title) {
    console.error('usage: node tools/node/viz-new.mjs <book> <id> "<CODE//NAME>" "<中文标题>" ["<English title>"]');
    process.exit(2);
  }
  try {
    const book = resolveBook(bookArg);
    const { dest, testFile } = scaffold(book, { id, code, title, titleEn });
    console.log(`created ${rel(dest)}/ and ${rel(testFile)}; registered ${id} as a draft in ${rel(registryPath(book))}.
next: write the page (every text as paired .zh/.en), fill summary/summary_en/tags/theory/lean in the registry,
      node tools/node/viz-server.mjs to look at it, node tools/node/viz-test.mjs ${book.slug},
      node tools/node/viz-thumbs.mjs ${book.slug} ${id}, set "status": "live", then ./tbook check`);
  } catch (e) {
    console.error(`viz-new: ${e.message}`);
    process.exit(2);
  }
}
