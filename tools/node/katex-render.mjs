#!/usr/bin/env node
// Server-side KaTeX for the mdBook pipeline (tools/tbook/mathrender.py).
//
// Protocol: one JSON object per input line, {"id": <string|number>, "tex": <string>,
// "display": <bool>}; one JSON object per output line, in input order:
//   {"id", "html"}                    rendered;
//   {"id", "html", "lenient": true}   rendered, but an undefined macro is shown in red;
//   {"id", "error"}                   KaTeX could not render the formula.
// `--version` prints the installed KaTeX version and exits.
//
// Adapted from trureturing-mdbook (scripts/katex_render.js, Apache-2.0,
// https://github.com/the-omega-institute/trureturing-mdbook): the same package macro set
// and the same retry order (as written → Markdown escaping undone → lenient for a macro
// defined only in a quoted paper). Streaming JSON lines keeps memory flat for large books.

import { createInterface } from "node:readline";

let katex;
try {
  katex = (await import("katex")).default;
} catch (error) {
  if (error && (error.code === "ERR_MODULE_NOT_FOUND" || error.code === "MODULE_NOT_FOUND")) {
    process.stderr.write("katex-render: the pinned katex package is not installed; run `npm ci` in the repository root\n");
    process.exit(2);
  }
  throw error;
}

if (process.argv.includes("--version")) {
  process.stdout.write(katex.version + "\n");
  process.exit(0);
}

// Commands from LaTeX packages that upstream quotes use (amsmath, dsfont, physics,
// mathtools-style delimiters, esvect, nicefrac) and that KaTeX does not define.
const MACROS = {
  "\\Tr": "\\operatorname{Tr}",
  "\\tr": "\\operatorname{tr}",
  "\\trace": "\\operatorname{Tr}",
  "\\diag": "\\operatorname{diag}",
  "\\Tilde": "\\tilde",
  "\\wt": "\\widetilde",
  "\\mathds": "\\mathbb",
  "\\mathpzc": "\\mathcal",
  "\\ketbra": "\\lvert #1\\rangle\\langle #2\\rvert",
  "\\dyad": "\\lvert #1\\rangle\\langle #1\\rvert",
  "\\floor": "\\left\\lfloor #1\\right\\rfloor",
  "\\ceil": "\\left\\lceil #1\\right\\rceil",
  "\\norm": "\\left\\lVert #1\\right\\rVert",
  "\\vv": "\\vec{#1}",
  "\\nicefrac": "{}^{#1}\\!/\\!{}_{#2}",
  "\\mbox": "\\text{#1}",
  "\\emph": "\\textit{#1}",
  "\\normalfont": "",
};

function render(tex, display, lenient) {
  // A fresh copy of the macros: \gdef in one formula must not leak into the next.
  return katex.renderToString(tex, {
    displayMode: display,
    throwOnError: !lenient,
    trust: false,
    // LaTeX-compatibility notices change nothing in the output; thousands flood the log.
    strict: "ignore",
    // HTML only: mdBook indexes every text node for search, and MathML would add a second
    // and third copy of each formula to the index and the result teasers. Screen readers
    // get the TeX source as the accessible name instead (see accessible() below).
    output: "html",
    macros: { ...MACROS },
  });
}

// Returns [html, lenient] or throws the error of the formula as written.
function renderItem(tex, display) {
  const candidates = [tex];
  // Markdown-escaped TeX writes `\\mathcal` and `\\\\` for `\mathcal` and `\\`;
  // try the formula with that escaping undone.
  if (/\\\\[A-Za-z\\]/.test(tex)) candidates.push(tex.replace(/\\\\/g, "\\"));
  let firstError = null;
  for (const candidate of candidates) {
    try {
      return [render(candidate, display, false), false];
    } catch (error) {
      firstError = firstError || error;
    }
  }
  // A macro defined only in the quoted paper (`\qc`, `\scrT`): KaTeX renders the rest of
  // the formula and shows that command's name in red.
  if (/Undefined control sequence/.test(String(firstError && firstError.message))) {
    for (const candidate of candidates) {
      const html = render(candidate, display, true);
      if (!html.startsWith('<span class="katex-error"')) return [html, true];
    }
  }
  throw firstError;
}

function escapeAttribute(text) {
  return text.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/[\r\n\t]+/g, " ");
}

// role="math" with the TeX source as its accessible name (KaTeX already hides its glyphs
// from assistive technology with aria-hidden on .katex-html).
function accessible(html, tex) {
  return html.replace('<span class="katex">', `<span class="katex" role="math" aria-label="${escapeAttribute(tex.trim())}">`);
}

function answer(line) {
  let request;
  try {
    request = JSON.parse(line);
  } catch (error) {
    return { id: null, error: `malformed request: ${error.message}` };
  }
  const id = request && "id" in request ? request.id : null;
  if (!request || typeof request.tex !== "string") return { id, error: "request has no tex string" };
  try {
    const [rendered, lenient] = renderItem(request.tex, Boolean(request.display));
    const html = accessible(rendered, request.tex);
    return lenient ? { id, html, lenient: true } : { id, html };
  } catch (error) {
    return { id, error: error && error.message ? error.message : String(error) };
  }
}

const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of lines) {
  if (!line.trim()) continue;
  // Writes to a pipe are synchronous on Linux, so nothing accumulates here.
  process.stdout.write(JSON.stringify(answer(line)) + "\n");
}
