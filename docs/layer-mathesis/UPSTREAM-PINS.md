# Upstream release requirement

Mathesis layer **0.4.0 requires trureturing-books-template ≥ 0.8.2**.
Use ordinary upstream template releases; no pull-request heads are pinned.
The combined template and first paper were upgraded with:

```sh
./tbook template update --layer upstream --to v0.8.2 \
  --source https://github.com/the-omega-institute/trureturing-books-template.git
```

The verified release is `v0.8.2` at
`85e533c20bad105dbb6999b2919bda2a6ddcb1d1`. Its managed code includes the
independent layers, written-proof results, academic Beamer decks and optional
`site.post_build` argument-array interface previously integrated from PRs
#48, #50, #51 and #55.

## Compatibility review

The release already supplies the behavior of local compatibility commit
`690ec33`: academic citations accept written-proof results, check their
associated nonempty proof, render a purple badge without a Lean verification
link, and do not assign a GID. Upstream now also renders DOI, source location
and formalization-request links in the result and ledger. The badge name and
ledger wording differ from the earlier local implementation. Coverage lives in
`tools/tests/test_written_proof.py` and `tools/tests/test_academic.py`; the
earlier local regression test is superseded by these upstream tests.

The film test sandbox also contains the local fixture correction: the cached
site configuration is replaced with `root=self.root`, so inherited post-build
hooks run in the active sandbox. No local upstream-managed patch is needed.

## Written-proof migration

Upstream 0.8.2 requires each written-proof environment, in both editions, to
include a bare `doi`, an original theorem/section/page `source`, and a canonical
`request` issue URL in `the-omega-institute/trureturing-requests`, in addition
to the associated nonempty proof. The issue must have the upstream title format
and register the consuming repository, book and result. Existing papers must
provide real provenance and registration before their checks and deck build
can pass. Never invent a request URL or alter a catalog-owned projection to
satisfy this gate. See upstream `docs/FORMALIZATION-REQUESTS.md`.
