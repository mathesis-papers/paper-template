# Mathesis paper template

One repository for one exact Mathesis paper version. This template has no selected paper and no example books.

The upstream books template supplies the machinery; Mathesis layer 0.5.0 supplies the publisher adapter and the [enforced four-zone layout](docs/layer-mathesis/LAYOUT.md).

Use [the publisher pipeline](docs/layer-mathesis/PIPELINE.md) to import a public projection with `paper.py fill`. It creates the paper record, one bilingual content skeleton and a generated paper README. Upgrade with `tbook template update`; keep preparation run records outside the repository.
