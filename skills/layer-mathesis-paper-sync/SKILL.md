---
name: layer-mathesis-paper-sync
description: Reconcile Mathesis exact-version claim identities with a paper book's result ids and Lean references without editing catalog schemas, source mathematics or verification receipts.
---

# Claim and result synchronization

Read `docs/layer-mathesis/PIPELINE.md`. Treat `paper.json` and
`formalization/nodes.json` as publisher-owned `sdk/catalog` output. Do not add
book ids or custom fields to nodes. Use publisher-owned `.mathesis/book.json`
for the book mapping: its `results` maps a book environment id to `claim` and
`gids`, and `pending_claims` explicitly covers every not-yet-mapped catalog node.

Use the exact node `identity` already present in nodes:
`collected:<work>:<version>:<claim>`. Never derive a new id from a title or use
lineage (which omits version) as the current-version identity. Attach that exact
identity as the `mathesis` attribute on the corresponding book environment in
both editions. Copy the same ordered GID list into the mapping's `gids`.
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

Run `python3 docs/layer-mathesis/scripts/paper.py check` and `./tbook check`.
For release use `check --complete`; pending claims or a skeleton must stop release
preparation. Report semantic mismatches explicitly: the mechanical check validates
identity, hashes and mapping consistency, not mathematical equivalence.
