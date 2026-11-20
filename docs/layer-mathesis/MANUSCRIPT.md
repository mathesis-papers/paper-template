# Mathesis LaTeX manuscript template

[`manuscript/note.tex`](manuscript/note.tex) is the shared LaTeX starting point
for research papers and short notes. Mathesis's own short notes use this
template as their default reference. It standardizes typography while the
mathematical argument determines the manuscript's structure and length.

Copy the file into the manuscript's authoring workspace as `note.tex` or
`main.tex`, replace the placeholders, and add the required bibliography and
figures. The copy under this template's managed documentation stays unchanged
in a selected paper repository. Submitted PDF/source bytes are imported by the
publisher into `paper.pdf`, `source.archive` and `manuscript/`; subsequent
editing belongs to a new reviewed manuscript version.

## Layout

- `\documentclass[11pt,a4paper]{article}`, one column, 1 inch margins, Latin Modern
  with T1 encoding.
- Packages: `amsmath`, `amssymb`, `amsthm`, `booktabs`, `array`, `hyperref`
  (coloured links, one colour), `xurl`. PDF metadata carries the title, the
  authors and the licence.
- `theorem`, `lemma`, `proposition`, `corollary`, `definition`, `conjecture`,
  `example` and `remark` share one counter, with the appropriate theorem style.
- Set the actual author names, affiliations, date, PDF metadata and licence.
  Our short notes use CC BY 4.0; another manuscript uses its approved licence.

## Organizing the mathematics

The example starts with an abstract, introduction and main theorem with proof.
Rename, combine or extend the sections to fit the question. State the result
early, introduce notation where needed, explain the proof mechanism, and give
complete arguments with their boundary and equality cases. Precisely referenced
appendices may hold longer supporting derivations. There is no fixed page
count, section count or mandatory closing section.

When a note answers a sourced question, identify its exact statement and
locator and explain the relationship to earlier work. Describe Lean verification
and finite computations when they support the result, with their exact scope.
A comparison or coverage table is useful for some notes; include it when it
clarifies several relevant statements. It is not required in every manuscript.

## References

Check authors, titles, dates and the statements being cited. Include a DOI or
arXiv identifier when one exists. Books may use ISBNs and chapter/theorem/page
locators; OEIS entries, MathOverflow questions and other online sources may use
a stable URL, entry/question number and the relevant version or revision.
No source needs an invented identifier. Put an exact locator at the point of
use when the argument depends on a particular result.

Use the example `thebibliography` environment or replace it with BibTeX and an
included `.bib` file. Both produce an ordinary scholarly bibliography.

## Compilation and reuse

Compile a copied template with `pdflatex note.tex` twice, or `tectonic note.tex`.
For BibTeX, run `pdflatex`, `bibtex`, and `pdflatex` twice, using the manuscript's
actual filename. Inspect the final PDF and resolve missing references.

Preparing agents use a fixed template commit and record its source revision
in their preparation evidence. Keep the manuscript's text and bibliography
specific to its mathematics; future revisions may adopt updated typography
through the normal manuscript workflow. An existing published version retains
its exact source and PDF.

Build output (`.pdf`, `.aux` and similar) is never committed next to the
skeleton.
