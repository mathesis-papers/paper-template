---
name: layer-mathesis-paper-book
description: Explain one frozen Mathesis paper as a bilingual story understandable with school mathematics, preserving source claims and formalization evidence; do not use for manuscript changes or new theorem proving.
---

# Paper to bilingual explanation

Read `docs/layer-mathesis/LAYOUT.md` for the fixed repository layout.
Zone 2 only: `books/<slug>/` text and book metadata. Ask paper-sync to update
the integration mapping and review; do not edit zone 1 frozen records or zone 3
machinery. Refresh the generated zone 4 README with `paper.py front`.

Never commit preparation logs, validation dumps, evidence archives, handoff
notes, one-off scripts or built outputs anywhere. Keep run records in the
workflow run or an external workspace, including during migration.


Read `docs/layer-mathesis/PROJECT.md`, `PIPELINE.md`, `skills/book-write/SKILL.md`
and the imported paper identity before writing. Use the frozen manuscript/PDF
and the public Mathesis explanations for that exact version. Mathesis exposition
explains the question, result, mechanism, significance and limitations; it is
neither a referee report nor verification. Never feed private audit or review
material into this conversion. Story and plain-language explanation are the same
product. Reuse the public exact-version text when it already explains the paper;
otherwise improve it from the frozen manuscript in the authored editions. If
there is no public sidecar, write the explanation directly from that manuscript,
without waiting for or scheduling a duplicate explanation task.

Start from the publisher-created skeleton. Explain definitions, motivating
examples and the argument for a curious high-school student, assuming school
algebra but no university mathematics. Explain specialist objects through
concrete examples before naming them. An analogy motivates the mathematics;
it cannot replace the hypotheses or proof. Keep precise result/evidence sections
available after the accessible explanation rather than leading with a theorem
inventory. Follow the Mathesis academic-paper editorial policy when the upstream
monograph style differs. Write Chinese
first, then natural English; align filenames, chapter order, environment kind,
id, Lean references and media sequence under the upstream language rules.
Preserve the paper's authors, title provenance, version and licence.

For each written result compare the complete manuscript statement (quantifiers,
hypotheses, domains, conclusion and boundary cases) with the proposed frozen
Lean statement at the book pin. A formal theorem/lemma/proposition/corollary
requires a frozen declaration of kind theorem that states that result. A source
link or a nearby variant is insufficient. Never change mathematics to fit an
available GID, invent a GID, or cite a variant as the same result. Do not change
pins/claims/receipts merely to make a check pass. If new formalization is needed,
record the exact gap; this conversion does not authorize changes to trureturing.
An uninspected statement correspondence remains pending/unknown; it is not
evidence that no proof exists. Ordinary formalization contributors follow
`REQUESTS.md`: focused contributor-fork PRs directly to upstream `dev`, with no
mandatory Mathesis-fork integration step. GitHub checks/merge do not establish
exact paper verification or independent platform receipts/points.

For a manuscript-proved result without a matching frozen declaration, retain
its theorem/lemma/proposition/corollary kind and use
`status="written-proof" proof="<proof-id>"`, no `lean`. Upstream ≥ 0.8.2 also
requires a bare source `doi`, original theorem/section/page `source`, and a
canonical `request` issue URL registered for this repository, book and result.
Follow `docs/FORMALIZATION-REQUESTS.md` and the Mathesis provenance supplement
`docs/layer-mathesis/REQUESTS.md`; reuse a matching registered request and
never invent issue URLs. Missing registration remains an unmet publication gate.
Add a nonempty proof
block with that id in every edition, even when the source separates statement
and argument across chapters. Attribute and review the written proof; the tool
cannot prove it correct. The purple WRITTEN PROOF badge has no verification
link and contributes nothing to Lean counts. Run the layer check first: it
refuses an upstream that lacks this capability. Record the comparison verdict
and closest public declaration through paper-sync, without citing a variant as
verification.
Use `conjecture`/`problem` for genuinely unproved conclusions as upstream requires;
do not turn a proved manuscript claim into a mathematical open problem solely
because its formalization is missing. Never emit a green verification claim from
catalog status or an illustration.

Invoke `layer-mathesis-paper-sync` as results are added. Keep unmapped nodes in
`.mathesis/book.json` pending; do not edit catalog-owned files. Run the layer check
and `./tbook check`. Complete conversion requires no pending claims, aligned
editions, faithful statements and reviewed outputs. Remove skeleton markers and
set the book integration stage to complete only after that work. Use
`layer-mathesis-paper-media` for the output sequence.
Missing video stays a pending content product; it does not block publication or
display of the eligible public paper and its existing checked materials.
