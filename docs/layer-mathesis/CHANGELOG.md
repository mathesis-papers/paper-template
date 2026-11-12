# Mathesis layer changelog

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
