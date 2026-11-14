# Prepare the reading, visualizations, slides and video

- [ ] Follow the four zones in `docs/layer-mathesis/LAYOUT.md`; keep run records outside commits.
- [ ] Read `docs/layer-mathesis/PIPELINE.md` and the frozen manuscript; preserve every imported catalog byte and hash.
- [ ] Follow `layer-mathesis-paper-book`: prepare one aligned Chinese and English plain-language story for a high-school reader. Reuse/improve the exact-version public explanation, or author from the frozen manuscript when absent; do not schedule a second story. Keep claims pending until reviewed.
- [ ] Compare every result with frozen trureturing state at the inspected full commit. Record same / special case / variant / none only for an inspected comparison; leave unreviewed correspondence pending/unknown. A nearby declaration is context, never verification of the complete result.
- [ ] Register missing formalizations using `docs/layer-mathesis/REQUESTS.md`: identify submission through Mathesis, exact paper DOI/version, authors, theorem location and paper repository; reuse existing requests.
- [ ] Map every catalog node in `.mathesis/book.json`. Keep unmatched manuscript proofs as written-proof, with complete per-edition proof blocks; do not promote catalog verification status.
- [ ] Follow `layer-mathesis-paper-sync` for bilingual identity and evidence alignment; keep the sole comparison in `.mathesis/REVIEW.md`, then refresh `paper.py front`.
- [ ] Follow `layer-mathesis-paper-media`: figures → interactive visualizations → academic Beamer with audience and notes PDFs. Produce narrated video from the same checked story, with subtitles and a playable MP4. Generate Slidev only on request.
- [ ] Review both languages, themes and phone layouts. Verify original authors and affiliations against recorded metadata.
- [ ] Remove skeleton markers, clear pending claims and set stage complete only after the conversion is reviewed.
- [ ] Run `python3 docs/layer-mathesis/scripts/paper.py check --complete`, `./tbook check`, and `./tbook build all`; review the root redirect and `mathesis-materials.json` alongside the reading and media.

This issue assigns content preparation. Missing video remains pending without blocking publication/display of an otherwise eligible public paper and its existing materials. Community proof contributions normally go from contributor forks directly to upstream `dev`; no Mathesis staging merge is required. The mechanical publisher creates only a skeleton and never changes proof receipts, formalization credit or DOI authority.
