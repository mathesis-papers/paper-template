# Mathesis paper template

This repository consumes `the-omega-institute/trureturing-books-template` and adds
one independently managed Mathesis layer. Create each paper repository from this
GitHub template after the publisher has selected an exact public paper version.

See [the layer guide](docs/layer-mathesis/README.md) and
[the publisher pipeline](docs/layer-mathesis/PIPELINE.md). `template.toml`, tools,
theme and output contracts stay upstream-owned. `template.d/mathesis.toml` and its
manifest track only the Mathesis layer. `./tbook template update` receives both;
weekly template sync opens a separate PR for each source.

The template contains no fabricated paper identity, nodes or manuscript. The
publisher imports an existing `sdk/catalog` rendered paper tree byte-for-byte,
then fills the bilingual book skeleton. The example books remain hidden.
