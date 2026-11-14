# Mathesis formalization requests and contributions

Use the existing [shared-request contract](../FORMALIZATION-REQUESTS.md),
including its English title, complete statement, library comparison and `tbook`
registration. Search open and closed issues by mathematical content before
creating a request. The same theorem can serve multiple papers; neither a
translation nor another consumer creates a new issue.

## Register the source

When preparing a new request or registering another paper's use, add this
provenance beside the existing `tbook` registration. Fill it from the frozen
paper record and inspected source, not a guessed URL or author affiliation:

```markdown
### Source registered through Mathesis

- Paper: <full original title>, by <original authors>.
- Exact source: https://doi.org/<version DOI>, <original theorem/section>.
- Mathesis record: <exact paper page including version>.
- Paper repository: <current canonical GitHub repository>.
- Use: <which result needs the formalization and why>.
```

For a paper without a DOI, link the immutable public source version and explain
that no DOI is assigned. This does not waive the upstream written-proof DOI
requirement. For an unbadged, attributed remark, add the registered request to
its `.mathesis/book.json` result row as
`"formalization_request": {"label": "Theorem 1 — readable result name", "url": "https://github.com/the-omega-institute/trureturing-requests/issues/24"}`
using the real result name and issue URL. This is a work link, not proof evidence;
it is exported beside requests from written-proof environments without needing
a DOI or a second queue. Never invent an issue to populate the field. Retain original question/literature credit and distinguish the
paper's authors from the person registering or formalizing it. "Through
Mathesis" identifies the submission channel, not ownership of the mathematics.

Do not rewrite or duplicate historical `tbook` markers after a DOI-based repo
rename. Add a current repository/record link to the existing registration body
or, when another person owns it, a single registration comment; inspect existing
comments first. Preserve other papers' registrations and the issue's original
canonical source. No new shared label or workflow is required.

## Claim work and contribute

The public task list is
[trureturing-requests](https://github.com/the-omega-institute/trureturing-requests/issues).
Comment on the request with the exact scope you will tackle and the working
branch/PR link; coordinate overlapping work there. A comment records intent,
not a proof, automatic assignment or exclusive ownership.

For every contributor, the default is a focused branch in their own contributor
fork and a PR directly to `the-omega-institute/trureturing:dev`, following
[upstream contribution rules](https://github.com/the-omega-institute/trureturing/blob/dev/docs/CONTRIBUTING.md),
proof admission, independent review and current required CI. Use an upstream
branch only when permitted. There is no preliminary Mathesis-fork merge gate.
Retain contributor authorship when preparing the upstream PR. Fork CI does not
replace upstream acceptance, frozen declaration membership or exact paper
statement review. Keep shared request links as full URLs; bare `Closes #N` can
close an unrelated repository's issue.

The existing [Mathesis fork](https://github.com/mathesis-papers/trureturing) is
optional for a concrete collaboration with a named owner, scope and end
condition. It is not a permanent mirror or an extra funded sync/CI service.
Before use, inspect its actual repository/network protections, workflow events,
permissions, secrets and cache access rather than assuming blanket inheritance
behavior. Enabled workflows alone do not establish successful proof CI. The
shared request remains the sole queue under either development route.

After upstream merge/freeze, record the full revision, declaration and exactly
which clauses were proved. Leave a broader request open when only part is done.
Recheck statement correspondence, update the book pin using `tbook pin`, and
synchronize both editions. An environment failure is not an open conjecture.
An unreviewed correspondence stays pending/unknown, not a demonstrated missing
proof. Record partial coverage at clause level; neither a paper-level Lean URL
nor an issue closure establishes the whole paper theorem.

Original mathematical authors, prior-work authors and proof contributors keep
separate attribution. The `mathesis-papers/formalization` repository is generated
platform evidence, not this development fork. GitHub authorship is recorded by
PRs; platform leaderboard points still require the independent Mathesis receipt
and its existing submission path. Do not invent points from issue closure or CI.
