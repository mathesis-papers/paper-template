# Mathesis project rules

This page is imported through publisher-owned `PROJECT.md`, which upstream
`CLAUDE.md` already imports. Apply upstream book rules and the authority split in
[the layer guide](README.md) together.

Mathesis owns paper identity, version selection, authors, frozen bytes, claims,
receipts and verification status. `sdk/catalog` owns the paper projection format.
Only the publisher imports or refreshes `paper.json`, `CITATION.cff`,
`formalization/nodes.json`, `.mathesis/generated.json`, `LICENSES/`, `manuscript/`,
`paper.pdf`, generated README/changelog/contribution instructions and receipts.
Never hand-edit those files or regenerate their manifest to bless an edit.

The book explains that exact version. Its original English title, authors,
licence and version must match the projection. A publisher-supplied Chinese
title may translate the title; do not change the mathematical claim. Preserve
author metadata, including affiliations, without inferring an institution from
a GitHub namespace. The book is not a new paper or a verification receipt.

`skills/layer-mathesis-paper-book`, `skills/layer-mathesis-paper-sync` and
`skills/layer-mathesis-paper-media` define the conversion. Book integration state
is publisher-owned `.mathesis/book.json`; it is separate from catalog nodes.
An agent updates its result mapping with the book, never catalog verification.
Run the layer check and `./tbook check` after each conversion or sync.

Keep the template's runtime, visual contracts, output discovery and build cache.
Use upstream commands for each output. Future upstream outputs arrive through
`./tbook template update`, then the upstream authoring/build instructions;
do not maintain a second build/export framework in this layer.
