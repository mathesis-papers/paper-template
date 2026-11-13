# Mathesis layer changelog

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
