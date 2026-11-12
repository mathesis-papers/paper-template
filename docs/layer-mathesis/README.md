# One repository per Mathesis paper

A paper repository consumes two independently maintained templates. The books
template supplies `tbook`, managed tools, themes, build units, cache, publication
workflows and output skills. The Mathesis layer supplies the catalog-to-book
adapter, checks and paper-specific agent instructions. It does not fork the
books template. The maintainer of upstream remains loning.

`template.toml` and `template-manifest.json` belong to upstream.
`template.d/mathesis.toml` names `mathesis-papers/paper-template` and tracks the
layer version; `template.d/mathesis.manifest.json` hashes only its managed files.
Run `./tbook template status|update` for both. Weekly `template-sync` discovers
the layer and opens its own `template-update/mathesis/<version>` PR. Layer
releases use `mathesis-<version>` tags (`tag_prefix = "mathesis-"`) so they do not
trigger inherited book-release workflows; tag publication is outside this
package. Regenerate the layer manifest only in its source repository:

```sh
./tbook template manifest --layer mathesis
./tbook template manifest --layer mathesis --check
```

The authority split is exact:

| Authority | Owns |
|---|---|
| Mathesis public record and `sdk/catalog` | Exact-version identity, original authors, manuscript/PDF, claims, scope, receipts and projection schemas |
| trureturing frozen state at the book's pinned commit | Which declarations have been kernel-verified and what they state |
| Upstream books template | Tools, runtime, media contracts, output/build units, cache and publication mechanisms |
| Mathesis layer | Adapter, integration checks, paper conversion skills and Zenodo artifact preparation |
| Publisher / paper repository | Imported paper files, site/book metadata, bilingual exposition, result mapping and media |

A paper-level source URL, a variant theorem or a PR does not establish an exact
claim's independent verification. Never promote catalog status from book work.
Original authors and formalization contributors remain separate. A source
proved in prose but lacking a matching frozen GID keeps its formal result kind with
`status="written-proof" proof="<proof-id>"` and a proof block in each edition.
It receives the purple WRITTEN PROOF badge, never a green Lean badge or Lean count.
Use conjecture/problem for genuinely unsettled assertions, and label a missing
formalization as such rather than declaring a proved manuscript result open.

Schema authority is the existing Mathesis repository, not this layer:
[`sdk/catalog/README.md`](https://github.com/the-omega-institute/mathesis/blob/develop/sdk/catalog/README.md),
[`sdk/catalog/src/model.rs`](https://github.com/the-omega-institute/mathesis/blob/develop/sdk/catalog/src/model.rs),
[`sdk/catalog/src/render.rs`](https://github.com/the-omega-institute/mathesis/blob/develop/sdk/catalog/src/render.rs),
[`docs/PAPER_REPOSITORIES.md`](https://github.com/the-omega-institute/mathesis/blob/develop/docs/PAPER_REPOSITORIES.md)
and [contract §31](https://github.com/the-omega-institute/mathesis/blob/develop/docs/contract/31-public-catalog.md).
The implementation was checked against local revision
`6252803b149df73a4c06d268c4059d0e3ba34268`; these public links preserve the source
identity but their remote availability was not checked in this work package.
No alternate paper/node/generated-manifest schema is introduced here.

Mathesis defaults to academic presentation: `outputs.pdf = ["academic"]` makes
academic the primary and only enabled PDF. Enable screen/print only on a paper's
explicit request. Media proceeds figures → visualizations → academic Beamer
when upstream supplies it → Slidev only on request.

Layer **0.2.0 requires upstream written-proof support**, the public
`tbook.model.WRITTEN_PROOF = "written-proof"` capability with per-edition proof
checks and consistent rendering. It also requires the independent template-layer
support from Part A. These changes must arrive through upstream template updates;
this layer does not ship copies of upstream tools or themes. Until written-proof
support is installed, the paper checker fails with an actionable error, including
for an empty skeleton. No unreleased upstream version number is assumed.

[The pipeline](PIPELINE.md) documents the mechanical publisher step and its
agent handoff. [Project rules](PROJECT.md) are imported from root `PROJECT.md`.
