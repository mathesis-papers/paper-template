---
name: layer-mathesis-paper-sync
description: Reconcile Mathesis exact-version claim identities with a paper book's result ids and Lean references without editing catalog schemas, source mathematics or verification receipts.
---

# Claim and result synchronization

Read `docs/layer-mathesis/LAYOUT.md` for the fixed repository layout.
Zone 1 integration only: update `.mathesis/book.json` and own the sole
`.mathesis/REVIEW.md` statement comparison. Record every mapped result, verdict,
compared declaration (or none), full inspected commit and concise scope using
the LAYOUT.md table. Delete superseded review copies only after their relevant
comparisons are retained here. Never edit frozen publisher records or their
hashes. Zone 2 identity/evidence attributes may be synchronized with the mapping;
refresh the generated zone 4 README using `paper.py front`. Zone 3 is template-owned.

Never commit preparation logs, validation dumps, evidence archives, handoff
notes, one-off scripts or built outputs anywhere. Keep run records in the
workflow run or an external workspace, including during migration.


Read `docs/layer-mathesis/PIPELINE.md`. Treat `paper.json` and
`formalization/nodes.json` as publisher-owned `sdk/catalog` output. Do not add
book ids or custom fields to nodes. Use publisher-owned `.mathesis/book.json`
for the book mapping: each `results` row has `claim`, `gids`,
`comparison_verdict` (exactly `same` / `special case` / `variant` / `none`),
`compared_public_gid` (closest inspected public frozen declaration, null for
`none`) and `comparison_commit` (full inspected commit). These are the pilot's
comparison fields, not additions to the catalog schema. `pending_claims`
explicitly covers every not-yet-mapped catalog node.

Use the exact node `identity` already present in nodes:
`collected:<work>:<version>:<claim>`. Never derive a new id from a title or use
lineage (which omits version) as the current-version identity. Attach that exact
identity as the `mathesis` attribute on the corresponding book environment in
both editions. Copy the same ordered GID list into the mapping's `gids`.
Use `same` only when the frozen declaration states this complete written result;
it must be one of the book's actual GIDs. For special case / variant / none,
`gids` is empty. If the source supplies a written proof, use the original formal
kind with `status="written-proof" proof="<proof-id>"` and a proof block in each
edition, together with the bare DOI, original source location and registered
formalization-request URL required by upstream ≥ 0.8.2; reserve conjecture/problem
for actually open claims. Never invent a request or use an unrelated issue. The comparison
GID belongs to the formalization pool, not the result's verification citations.
Preserve the comparison scope and gaps in prose; never manufacture a GID or
commit for an unperformed search. Keep a claim pending until this review exists.

Every formal/open result environment is mapped; an attributed remark carrying a
manuscript result is also mapped. The checker compares both language editions.

For each mapping compare the complete written claim and frozen Lean statement.
Never change mathematics, invent a GID, or cite a variant as the same result.
Several expository statements may refer to one catalog node only when their
precise relationship is recorded in the exposition; do not claim equivalence
for a specialization, stronger hypothesis or counterexample. A public receipt
and an exact frozen declaration are distinct authorities. Do not upgrade
Mathesis status because a book has a Lean link.

When the publisher selects another version, require a new rendered projection;
never hand-edit paper identity, nodes, generated hashes or frozen files. Check
work/version/claim identity, target digest, statement, receipt and attribution
against that projection before carrying a mapping forward. Similar text is not
identity. Keep absent or changed claims pending until reconciled.

Run `python3 docs/layer-mathesis/scripts/paper.py front`, then
`python3 docs/layer-mathesis/scripts/paper.py check` and `./tbook check`.
For release use `check --complete`; pending claims or a skeleton must stop release
preparation. Report semantic mismatches explicitly: the mechanical check validates
identity, hashes and mapping consistency, not mathematical equivalence.

For a registered uncovered result, retain its canonical shared request in the
existing mapping row as `formalization_request` with plain `label` and `url`.
This also exposes requests for unbadged remarks when the paper has no DOI; it
does not waive written-proof evidence rules or change verification/credit.
An exactly covered row cannot request a duplicate proof. See `REQUESTS.md`.
