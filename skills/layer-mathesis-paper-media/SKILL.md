---
name: layer-mathesis-paper-media
description: Produce figures, visualizations and an academic Beamer deck when upstream provides it; make Slidev only on request, using upstream skills and build units.
---

# Media from the checked paper book

Read `docs/layer-mathesis/PROJECT.md` and the current book result mapping. Work
from the converted exact-version book. First use `skills/book-figure/SKILL.md`
for static explanatory figures beside their textual references. Then use
`skills/book-viz/SKILL.md` for interactive experiments: choose the stage for the
mathematical object, make each experiment card independently referencable from
the book, and retain the shared runtime, evidence classes and stageFirstChecks.
A numerical example illustrates a result; it does not certify it.

Next inspect the installed upstream skill/CLI for the academic Beamer deck.
When available, produce it through that published interface. If unavailable,
record it as pending upstream capability. Another branch is implementing it;
do not copy that branch, invent flags or build a private deck runtime.
Only on explicit request, then use `skills/book-slides/SKILL.md` for the aligned
Slidev deck and `./tbook build slides`. The default PDF is the academic variant
(`outputs.pdf = ["academic"]`); screen/print require a paper-specific request.

Use the existing upstream CLI, build units and cache for each additional output
as it arrives through template updates. Enable/configure it using upstream docs,
without maintaining a second output registry in this layer. Run the relevant
upstream checks/builds and review both editions, themes and phone widths with
the upstream quality gates. Keep references to result ids and exact frozen GIDs.

Never change mathematics to fit a visual, invent a GID, cite a variant as the
same result, imply that a simulation proves a theorem, or edit catalog receipts,
frozen files or verification status. An image/slide must retain the book's exact
claim scope and distinguish manuscript proof from frozen Lean evidence.
