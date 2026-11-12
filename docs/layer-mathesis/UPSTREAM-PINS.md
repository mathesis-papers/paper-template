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
requires no duplicate paper-side merge. The manifest was regenerated using
`./tbook template manifest`; no runtime interface was forked.

Mathesis layer version: **0.2.1**. This note belongs to the layer, not the
upstream-managed template. It is historical provenance of the initial rollout,
not an instruction to freeze later paper repositories forever.
