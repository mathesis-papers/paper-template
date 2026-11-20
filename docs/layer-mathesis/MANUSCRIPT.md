# Manuscript skeleton for short notes

[`manuscript/note.tex`](manuscript/note.tex) is the LaTeX skeleton for a short
research note submitted to Mathesis. It fixes the layout so that notes from
different authors and preparation runs look the same. The submitted PDF and
source archive are imported unchanged into the paper record (`paper.pdf`,
`source.archive`, `manuscript/`); this skeleton governs how that manuscript is
written, not the bilingual reading edition under `books/<slug>/`.

## Layout

- `\documentclass[11pt]{article}`, one column, 1 inch margins, Latin Modern
  with T1 encoding.
- Packages: `amsmath`, `amssymb`, `amsthm`, `booktabs`, `array`, `hyperref`
  (coloured links, one colour), `xurl`. PDF metadata carries the title, the
  authors and the licence.
- `theorem`, `lemma`, `proposition` and `corollary` share one counter.
- Date as day, month name, year. Typical length is five to eight pages in three
  to five sections.

## Order of parts

1. Title that states the result and the question it answers.
2. Authors with affiliations in small type under each name.
3. Abstract in one paragraph: source and conclusion, exact scope, what is
   Lean-verified.
4. The question: the posed statement as its source states it, with a locator.
5. One to three sections with the result and its complete proof; exact
   computed examples in `booktabs` tables.
6. Scope and coverage: a two-column table with one row per source statement and
   its status in the note, then a paragraph headed "Verification coverage" that
   separates Lean-covered conclusions (declaration name and pinned `.lean`
   link), written proofs and exact finite computations.
7. Hand-written bibliography; every entry has a DOI or arXiv identifier and the
   cited locator.
8. The copyright and CC BY 4.0 line.

Build output (`.pdf`, `.aux` and similar) is never committed next to the
skeleton.
