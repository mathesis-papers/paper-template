# Mathesis layer changelog

## [0.7.6] - 2026-11-20

- Make the LaTeX manuscript template general for papers and short notes. Standardize A4 typography and common mathematical environments while leaving sections, length and coverage tables to the argument. Support DOI, arXiv, ISBN and stable web-source references, with either an inline bibliography or BibTeX. Our own short notes use the template as their default reference.

## [0.7.5] - 2026-11-20

- Add the LaTeX manuscript skeleton for short notes (`manuscript/note.tex`) and its description (`MANUSCRIPT.md`): fixed layout, order of parts, the scope table and the verification-coverage paragraph.

## [0.7.4] - 2026-11-19

- Keep the real paper work ID separate from the repository name in integration fixtures. DOI-named repositories now exercise the same content-slug and request-registration checks as other papers.

## [0.7.3] - 2026-11-15

- Present paper films with a readable bilingual heading, narration information and author credit. Keep proof sources expandable and preserve playback, downloads and language controls, while removing build instructions and internal book codes from the reader page. Adapt only Mathesis output; the upstream renderer and media contract remain unchanged.

## [0.7.2] - 2026-11-15

- Read written-proof request attributes through the upstream parsed-attribute interface. Accept matching mapped request links and keep rejecting links that disagree with the written proof.

## [0.7.1] - 2026-11-15

- Treat the published film pipeline's ignored, untracked `books/<slug>/films/<id>/out/` as local build output. Keep rejecting tracked media, unignored output and unrelated content directories.
- Consume the published film registry's standard output keys, including `narrated_720p`, and exclude its cover image when emitting actual built video links.

## [0.7.0] - 2026-11-15

- Preserve publisher-owned collection version snapshots during an authored-book migration, with a separate immutable source inventory and unchanged public download paths.
- Retain original root PDF/source downloads and old language reading addresses; historical snapshots grant no current coverage, receipts or credit.

## [0.6.2] - 2026-11-15

- Export registered shared requests from reviewed result mappings, including unbadged remarks without a DOI, while preserving proof-evidence and credit boundaries.
- Require canonical URLs, readable labels and agreement with written-proof request attributes; deduplicate repeated uses of one request.
- Make interactive visualization conditional on a concrete explanatory benefit; stories and static figures can be complete without interaction.

## [0.6.1] - 2026-11-14

- Define one bilingual story/plain-language explanation for a high-school reader, reused by slides and video, with Mathesis academic-paper editorial ownership.
- Document shared-request claiming and ordinary contributor-fork PRs directly to upstream dev; retain the Mathesis fork only for a named collaboration, without an extra integration gate or permanent sync service.
- Preserve original-source/Mathesis provenance, historical registration identities, exact/partial/unknown coverage and existing platform credit rules.
- Align the preparation checklist with the single-story and actual-video requirements.
- Permit direct story authoring from the frozen manuscript when sidecars are absent; missing video remains pending without blocking eligible paper display. Record future discovery/pin activation and a manual mapping/eligible-receipt pilot without claiming automation.

## [0.6.0] - 2026-11-14

- Discover actual built videos and selected-book shared formalization requests through the existing upstream manifests.
- Permit film sources and frozen source.archive; preserve four-zone ownership and migrate existing film directories/fronts.
- Specify story → presentation/video production and local missing-work inspection without model calls or invented proof status.

## [0.5.0] - 2026-11-13

- Define and enforce the four-zone layout in LAYOUT.md, including one work-id book, generated record ownership, manifest-listed machinery, the sole statement review, debris/output bans and the 2 MiB limit.
- Fill removes upstream examples, persists empty media directories and generates a paper repository guide while preserving the catalog README prefix and manifest.
- Add dry-run/apply tidy with external archives and protected paper/content zones; the migration previews cleanup and refreshes the generated front. Paper repositories upgrade by template update, never git merge.
- Scope each conversion skill to its write zone and keep preparation run records outside commits. Run layout regression tests in the layer consistency workflow.

## [0.4.0] - 2026-11-13

- Require upstream trureturing-books-template ≥ 0.8.2 and retire all temporary PR-head pins.
- Confirm that the release includes written-proof academic citations and the active-root film fixture correction; use upstream managed files without compatibility patches.
- Document the released DOI, source-location and registered formalization-request contract for written proofs, and adapt the offline layer fixture to it.

## [0.3.1] - 2026-11-13

- Run the postprocessor against the hook's working directory, rather than the script's source repository.
- Skip inherited hooks when the build has no layer script, no Mathesis book mapping, or no mapped book in its site manifest; leave output untouched and print one reason.
- Keep all real-paper `emit` checks strict and migrate legacy hook declarations to a guarded Python bootstrap. The upstream hook's production behavior is unchanged; its film sandbox must bind the site root to the active fixture rather than a cached, removed directory.

## [0.3.0] - 2026-11-13

- Configure a layer-owned post-build command: redirect a single paper's root to its existing book landing and publish `mathesis-materials.json` from built output only.
- Migrate existing single-paper site settings and use the organization custom domain.
- Provide the publisher's preparation issue checklist. Requires the upstream optional `site.post_build` command interface; no upstream version number is assumed.

## [0.2.1] - 2026-11-13

- Record the temporary upstream 0.7.0 integration of PRs #48, #50 and #51, with exact heads, for the first real paper repository.

## [0.2.0] - 2026-11-12

- Default to the academic PDF alone; figures → visualizations → academic Beamer when available → Slidev only on request.
- Require upstream written-proof support, preserve proved manuscript results as written-proof environments, and validate per-edition proof presence and status parity.
- Record same / special case / variant / none plus the closest public declaration and inspected commit in book integration metadata, without changing catalog schemas or verification receipts.

## [0.1.1] - 2026-11-12

- Confirm independent propagation: a layer update leaves upstream and paper-owned files unchanged; an upstream update leaves layer and paper-owned files unchanged.

## [0.1.0] - 2026-11-12

- Consume the books template through an independent Mathesis layer; import frozen
  catalog files, create an empty bilingual book, check identity and mappings, and
  prepare a Zenodo artifact without network writes.
