# Mathesis project rules

This page is imported through publisher-owned `PROJECT.md`, which upstream
`CLAUDE.md` already imports. Apply upstream book rules and the authority split in
[the layer guide](README.md) and [the enforced layout](LAYOUT.md) together.

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
Paper-sync owns the sole `.mathesis/REVIEW.md` statement comparison, with verdict,
compared declaration, full inspected commit and scope per result. Run records
belong in workflow artifacts or outside the repository; never commit them.
Run `paper.py front`, the layer check and `./tbook check` after each conversion or sync.

The Mathesis layer maintains the academic-paper editorial policy independently
of the upstream monograph style. Story and plain-language explanation are one
bilingual product for a curious high-school student, assuming school algebra
and no university mathematics. Reuse the exact-version public explanation when
sufficient; improve it in the authored reading editions where needed. Do not
create a second story job or wait for a short teaser before writing the story.
Explain the question, useful definitions, result, mechanism, significance and
limits with concrete examples; preserve technical statements and evidence in
clearly introduced sections. Slides and video derive from that same checked
story. Keep original authors and prior literature credited.

Use [REQUESTS.md](REQUESTS.md) when registering a formalization. Mark the Mathesis
submission channel and exact paper version without taking credit for its
original mathematics. Every contributor normally develops a focused branch in
their own fork and submits it directly to upstream trureturing `dev` under its
current admission/review/CI rules. Use an upstream branch only when permitted.
The shared request is the public coordination point; a Mathesis-fork merge is
not a prerequisite. `mathesis-papers/trureturing` is optional for a named actual
collaboration, with no permanent mirror/sync service implied. Upstream remains
the frozen mathematics authority. The generated `mathesis-papers/formalization`
repo continues to project platform receipts and statistics; GitHub CI/merge
does not grant platform points or establish exact paper coverage. Unreviewed
statement correspondence stays pending/unknown.

Video remains a required planned content product. A missing video stays pending
and does not prevent publication/display of the eligible public paper or its
existing checked materials.

The default PDF is academic (`[outputs] pdf = ["academic"]`); enable screen/print
only if the paper asks. Make figures or interaction only when they clarify the
mathematics; a story with no useful interaction needs none. Produce academic
Beamer when upstream provides it; Slidev is on request. Source-proved unmatched results
use written-proof, not conjecture. Read the required upstream capability and
comparison-record contract in the layer guide and pipeline before conversion.

Keep the template's runtime, visual contracts, output discovery and build cache.
Use upstream commands for each output. Future upstream outputs arrive through
`./tbook template update`, then the upstream authoring/build instructions;
do not maintain a second build/export framework in this layer.
