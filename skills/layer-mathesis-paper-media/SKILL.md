---
name: layer-mathesis-paper-media
description: Produce a Mathesis paper book's figures, interactive visualizations and slides through upstream book skills and build units, including an academic deck only when upstream provides it.
---

# Media from the checked paper book

Read `docs/layer-mathesis/PROJECT.md` and the current book result mapping. Work
from the converted exact-version book. First use `skills/book-figure/SKILL.md`
for static explanatory figures beside their textual references. Then use
`skills/book-viz/SKILL.md` for interactive experiments: choose the stage for the
mathematical object, make each experiment card independently referencable from
the book, and retain the shared runtime, evidence classes and stageFirstChecks.
A numerical example illustrates a result; it does not certify it.

Next use `skills/book-slides/SKILL.md` to produce the template's aligned Slidev
deck. Build through `./tbook build slides` and the upstream build cache. Inspect
the installed upstream skill/CLI for an academic Beamer deck; when it provides
one, follow that published interface and produce it after Slidev. If unavailable,
record that output as pending upstream capability; never copy the concurrent
slides branch, invent a build flag, implement a private deck runtime, or block
the supported outputs on the future deck.

Use the existing upstream CLI, build units and cache for each additional output
as it arrives through template updates. Enable/configure it using upstream docs,
without maintaining a second output registry in this layer. Run the relevant
upstream checks/builds and review both editions, themes and phone widths with
the upstream quality gates. Keep references to result ids and exact frozen GIDs.

Never change mathematics to fit a visual, invent a GID, cite a variant as the
same result, imply that a simulation proves a theorem, or edit catalog receipts,
frozen files or verification status. An image/slide must retain the book's exact
claim scope and distinguish manuscript proof from frozen Lean evidence.
