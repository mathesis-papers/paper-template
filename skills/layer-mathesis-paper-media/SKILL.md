---
name: layer-mathesis-paper-media
description: Produce figures, visualizations, narrated video and an academic Beamer deck; make Slidev only on request, using upstream skills and build units.
---

# Media from the checked paper book

Read `docs/layer-mathesis/LAYOUT.md` for the fixed repository layout.
Zone 2 only: `books/<slug>/figures/`, `viz/`, `films/`, `slides/` and `assets/`, plus
corresponding content references/configuration. Built outputs are local working
files only. Do not edit zone 1 records or zone 3 machinery. Refresh the generated
zone 4 README with `paper.py front`.

Never commit preparation logs, validation dumps, evidence archives, handoff
notes, one-off scripts or built outputs anywhere. Keep run records in the
workflow run or an external workspace, including during migration.


Read `docs/layer-mathesis/PROJECT.md` and the current book result mapping. Work
from the converted exact-version book. The story is the same bilingual
plain-language explanation, understandable with school mathematics. Derive
slides and narration from it, introducing specialist ideas before their names;
do not commission a separate story or summarize away essential qualifications.
First use `skills/book-figure/SKILL.md`
for static explanatory figures beside their textual references. Then use
`skills/book-viz/SKILL.md` for interactive experiments: choose the stage for the
mathematical object, make each experiment card independently referencable from
the book, and retain the shared runtime, evidence classes and stageFirstChecks.
A numerical example illustrates a result; it does not certify it.

Use the installed `book-slides` interface for academic Beamer slides. Then use
`skills/book-film/SKILL.md` for a narrated video from the same checked story,
with aligned Chinese/English subtitles. Build through upstream commands and
require the actual playable MP4. The post-build manifest lists only actual
built outputs; a skipped render or empty film registry is not completion.
Video remains a required planned content product. While it is unavailable,
record it as pending and retain publication/display of the eligible public
paper and its existing checked materials; do not invent a video link or
reschedule already reviewed story/slides work.
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
