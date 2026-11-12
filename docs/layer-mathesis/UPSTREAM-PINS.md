# Temporary upstream integration

The first Mathesis template combines upstream `main` at
`e506a8841cf9deb89e2f70dff69dc5b88b4d8510` with these three pushed PR heads,
using merge commits, and retains template version **0.7.0**:

| PR | Branch | Head |
|---|---|---|
| [#48](https://github.com/the-omega-institute/trureturing-books-template/pull/48) | `feat/template-layers` | `dc4481b85ad3316b9c8556b68cb6da9d8720eed3` |
| [#50](https://github.com/the-omega-institute/trureturing-books-template/pull/50) | `feat/written-proof-status` | `899013b9bad204e0996374082addf6d4a17fd3c2` |
| [#51](https://github.com/the-omega-institute/trureturing-books-template/pull/51) | `feat/academic-slides` | `2738f71a80f04e88cb10c000e5f5bf6dc2c465b8` |

This is a local integration pending those PRs merging upstream. Once merged,
ordinary upstream template updates take over; their already merged content
requires no duplicate paper-side merge. The combined integration also reconciles
the academic citation renderer with the written-proof status introduced by #50:
nonempty associated proofs, an unlinked purple badge, and no GID. This resolves
a semantic overlap between #50 and #51 and has a focused regression test.
Merging those three unmodified heads alone does not include this compatibility
reconciliation: preserve it in the upstream integration before a later ordinary
template update replaces these managed files.
The manifest was regenerated using
`./tbook template manifest`; no runtime interface was forked.

Mathesis layer version: **0.2.1**. This note belongs to the layer, not the
upstream-managed template. It is historical provenance of the initial rollout,
not an instruction to freeze later paper repositories forever.

## Layer 0.3.0 site integration

The optional `site.post_build` argument-array interface is prepared in upstream
commit `7d73e5a76bd347f03cb4d5b68319ec0e06cd28f8` on
`feat/site-post-build-20261113`. The combined template integrates that change
alongside the existing written-proof / academic-slide compatibility work.
This is a local dependency pending dispatcher review and upstream integration;
no release number or remote publication is claimed. Layer-owned policy lives in
`scripts/site.py`, not upstream. Keep this hook when refreshing upstream tools.

## Layer 0.3.1 fixture correction

Upstream commit `7eb37dae97c276c656400e4ddc32dc8feec6e9e3` on the same
`feat/site-post-build-20261113` branch fixes only the film test sandbox and
regenerates its managed-file manifest. `config.load_site()` is cached, so a
later sandbox could inherit a `Site.root` pointing to a removed temporary
directory. The sandbox now sets `root=self.root` when replacing site settings.
The production hook is unchanged. A layer bootstrap cannot handle this error:
the subprocess fails while changing working directory, before Python starts.
Consumer validation needs this fixture correction as well as layer 0.3.1.
