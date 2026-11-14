# Publisher and conversion pipeline

The publisher selects one exact public CC-BY-4.0 collected-paper version and
renders it with the existing `sdk/catalog` snapshot/fetch/render process. The
adapter consumes that rendered `papers/<repository-name>/` directory offline.
A new repository is created from `mathesis-papers/paper-template`; an existing
books repository can instead install the layer:

```sh
./tbook template install mathesis --source /path/to/paper-template --to main --dry-run
./tbook template install mathesis --source /path/to/paper-template --to main
```

For the published layer use `--to mathesis-<version>` instead of `main`, or omit `--to` to
select the newest stable layer release. A plain directory source takes its
working tree; a git source reads a committed ref.

Run the publisher adapter with explicit paper slug and titles. These are
parameters supplied by the publisher, not placeholders to edit by hand:

```sh
python3 docs/layer-mathesis/scripts/paper.py fill \
  --input /path/to/catalog-output/papers/PAPER-REPOSITORY \
  --slug PAPER-SLUG --title-zh 'PUBLISHER CHINESE TITLE' \
  --title-en 'EXACT RECORDED TITLE' \
  --repository mathesis-papers/PAPER-REPOSITORY
python3 docs/layer-mathesis/scripts/paper.py check
./tbook check
```

`fill` verifies the existing generated manifest, imports every frozen record path
and the manifest byte-for-byte, fills `site.toml` and `books/<slug>/book.toml`
from `skeleton/*.in`, and creates only title headings and SUMMARYs in `zh` and
`en`. Authors, licence, date and version come from `paper.json`. Upstream example
books move to an external archive and are removed from the repository. The
generated README preserves the hashed catalog prefix and appends the repository
guide. See [the enforced layout](LAYOUT.md). The Chinese title
must come from the publisher's selected metadata; if no translation is supplied,
the publisher can explicitly reuse the recorded title pending translation.
There are no fabricated paper or node files in the layer source template.

The adapter creates `.mathesis/book.json`, separate from catalog data:
`book`, `work`, `version`, `titles`, `stage`, `results`, `pending_claims`.
`results` maps each stable book result id to an object with `claim` (the exact
catalog node identity) and `gids` (the same ordered GID list as the environment), plus the pilot's
`comparison_verdict` (`same`, `special case`, `variant`, `none`),
`compared_public_gid` (the inspected closest public frozen declaration; null for
`none`) and `comparison_commit` (the full inspected commit, even for `none`).
These field names preserve the pilot comparison vocabulary. Do not copy pilot
verdicts across versions without reviewing the statements. The closest GID is
formalization-pool context, never added to `lean`, the lock or a green badge just
because it is nearby. A `same` row requires that exact declaration as a book Lean
citation. Every other formal result requires written-proof and an empty `gids`
list; genuinely open items stay open. The checker validates syntax, consistency
and proof presence, not the truth of the verdict or the declaration's membership
at the recorded comparison commit; review against frozen state is required.
An uncovered result may additionally carry `formalization_request` with exactly
`label` (plain English source/result name) and `url` (canonical shared issue).
This exposes the same registered request in the materials manifest, including
for unbadged remarks from a paper without a DOI. It grants no written-proof
badge, verified coverage, receipt or points. A `same` row cannot request another
proof; use the broader uncovered row for a partial source claim. If the written
proof environment also has a request, the two URLs must agree.
Each mapped environment carries `mathesis="collected:<work>:<version>:<claim>"`.
This file is book integration metadata, never a replacement for nodes or receipts.
Every catalog node must be mapped or explicitly pending; several expository
results may refer to one node only if each states its own exact relationship.

The agent job runner is an external handoff, currently stubbed: give the selected
frozen manuscript, available exact-version public Chinese/English Mathesis
explanations, current pin and imported nodes to `layer-mathesis-paper-book`; synchronize through
`layer-mathesis-paper-sync`; then use `layer-mathesis-paper-media`. Do not supply
private referee/audit findings to the explanation job. Public exposition is
version-bound and is not verification evidence (Mathesis contract §21 and
CLAUDE.md §1). If explanations are absent, the content author writes the same
bilingual story directly from the frozen manuscript in the authored editions;
there is no sidecar prerequisite or duplicate explanation task. Keep absent
outputs pending until authored and checked. The mechanical adapter itself does
not run a book-writing job or generate paper text.

The normal check permits an explicitly unfinished skeleton, reports its pending
claim count, and checks all existing mappings. When conversion and all checks
are complete, the agent removes skeleton comments, maps every claim and sets
`stage = "complete"`. Then run:

```sh
python3 docs/layer-mathesis/scripts/paper.py check --complete
./tbook check
./tbook build all
```

Use upstream skills to render and review the enabled outputs in both languages,
themes and phone widths. The layer does not constrain future upstream output
formats or replace the existing build-unit/cache mechanism. The skeleton uses
`[outputs] pdf = ["academic"]`, making academic its primary and only PDF variant;
screen and print are opt-in per paper. Follow figures → visualizations → academic
Beamer when available. Produce a Slidev deck only on explicit request, through
`book-slides`; use `book-figure` and `book-viz` for the preceding steps. Academic Beamer is
conditional on an upstream implementation being available; use its published
interface when merged, without modifying this layer's upstream runtime now.

The layer check verifies title/author/version/licence agreement across paper,
CFF, book and site, exact node identity and coverage, per-edition environment ids,
claim attributes and GIDs, and every generated SHA-256. It accepts only the
quoted scalar/name CFF syntax emitted by `sdk/catalog`, not arbitrary hand-edited
YAML. `files.source.sha256` and `bytes` describe `source.archive` before unpacking;
the projection contains the unpacked `manuscript/`, so the check verifies its
individual generated hashes and does not pretend to rehash the missing archive.
`./tbook check` separately validates GIDs against frozen state. Semantic equality
of a manuscript result and a Lean statement still requires the agent's explicit
mathematical review; string/mapping checks cannot prove it.

For a later publisher refresh, import a newly rendered projection in a reviewed
paper-owned change, retaining its generated manifest unchanged. Do not rerun
`fill` over a populated paper: it refuses. Reconcile book integration metadata
with the new exact version, keep old receipts in history, then rerun both checks.
Template update does not refresh paper data or rewrite books.

On a paper release tag (`<slug>-v<catalog version>` or `v<catalog version>`),
`layer-mathesis-zenodo.yml` runs the complete check and `./tbook check`, then
prepares `build/zenodo/metadata.json`, `files.json` and an exact copy of all
catalog-generated files plus `.mathesis/generated.json`. Hashes and byte counts
in `files.json` identify the upload bytes; manuscript paths are preserved under
`files/`. This artifact contains frozen paper files, not substitute rebuilt PDFs.
It is uploaded as a build artifact only. You can prepare it locally:

```sh
python3 docs/layer-mathesis/scripts/paper.py zenodo \
  --tag "$PAPER_RELEASE_TAG" --output build/zenodo
```

No Zenodo request, deposit creation, DOI registration or secret is used. A later
publisher will need `ZENODO_TOKEN` with deposit write access (sandbox and live
credentials kept separate), preserve an existing exact-version DOI, reconcile
concept DOI and deposit identity, and decide whether to update an existing deposit
or create a new version. The Zenodo–GitHub automatic release integration stays
off to avoid a second DOI authority. The payload preparation is not authorization
to publish; validate the current API contract before adding that separate step.

Local integration checks use an existing rendered projection, without network:

```sh
MATHESIS_TEST_UPSTREAM=/path/to/upstream-with-written-proof \
MATHESIS_TEST_PAPER=/path/to/catalog-output/papers/PAPER-REPOSITORY \
  python3 -m unittest discover -s docs/layer-mathesis/tests
```

## Layout and run records (0.5.0)

[LAYOUT.md](LAYOUT.md) defines the four zones for every paper repository.
Run `paper.py tidy --dry-run` then `paper.py tidy --apply` for a legacy tree;
archive destinations must be outside the repository. Paper-sync first condenses
the statement comparison into `.mathesis/REVIEW.md`. Tidy preserves paper-record
bytes and the selected book. Run `paper.py front` when integration metadata or
publication routes change. `paper.py check --layout-only` isolates the layout
check from unresolved upstream evidence gates. Preparation logs, validation
dumps, handoffs, one-off scripts and builds never enter commits.

## Material handoff (0.6.0)

The post-build adapter reads upstream `films/films.json` and the site manifest's
`formalization_requests`. It advertises only built nonempty video files and
requests used by the selected book. These extend `mathesis-materials.json`
without changing its exact paper/version identity. Request links are work
registrations, not proof receipts or live completion claims. Do not infer
coverage from a closed issue. Main-site deployment and materials discovery must
be enabled independently of paper Pages publication.

Before a model run, use the catalog's `scripts/plan_content.py` against the local
paper and built site. Its stable paper/source and story-dependent media keys
identify missing work. It neither executes a model nor marks content as
mathematically verified. The upstream skills remain the content producer's
instructions; the mechanical publisher still does not write a story or render
a film merely because it opened a preparation issue. The complete downstream
ownership and validation plan lives in Mathesis `docs/PAPER_PIPELINE.md`.

The story is the plain-language explanation itself, for a curious high-school
student with school algebra and no university mathematics. Reuse or improve the
same exact-version text; do not schedule separate short-guide and full-story
generations. Missing sidecars do not prevent authoring from the frozen paper.
Mathesis maintains this academic-paper editorial policy in its own layer,
independently of the upstream monograph style, while reusing upstream tools.
[REQUESTS.md](REQUESTS.md) defines source registration and community handoff.
Ordinary contributors develop in their own forks and send focused PRs directly
to upstream trureturing `dev` under its current rules; permitted upstream
branches are also possible. The optional Mathesis fork serves only a named
collaboration, not a required staging merge or permanent sync/CI service. The
single shared request queue, upstream freeze authority and existing independent
Mathesis receipt/points authority remain separate. Paper-sync reviews exact
version/statement correspondence using existing mapping and comparison records;
unreviewed claims remain pending/unknown. No automatic semantic binding or
GitHub-to-platform credit reconciliation is implemented by these links.

Required products are that checked bilingual story, an academic presentation and
an actual narrated video. Interactive illustrations are selected for the
mathematical content. Use `book-film` and the real film build/QA, retaining
subtitles and source claim boundaries; a skipped render is pending, not done.
Editable PowerPoint export is not currently implemented by the template.
These content-completion goals do not add a video gate to publication/display
of an otherwise eligible public paper or its existing checked materials.

The next downstream work is to activate the existing material-discovery
interface and update released consumer pins, then read back exact-version
materials. Follow with one manual exact-claim/frozen-declaration mapping and,
only for an eligible author-confirmed target, the existing independent receipt
route. These are future tasks; no deployment, receipt or points are produced by
this layer documentation. Reuse reviewed content and generate only missing
products. Do not build a second queue, renderer or admission/credit authority.
