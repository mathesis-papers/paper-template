# Mathesis paper repository layout

This is the single layout contract, enforced by `scripts/paper.py check` in the
layer consistency workflow. A selected paper has exactly four zones:

| Zone | Paths | Writer |
|---|---|---|
| 1 · Paper record | `paper.json`, `CITATION.cff`, `paper.pdf`, `manuscript/`, `formalization/nodes.json`, `LICENSES/`, `.mathesis/` | The Mathesis publisher imports frozen files. `.mathesis/generated.json` is the unchanged catalog manifest; `.mathesis/book.json` is the integration mapping. Paper-sync maintains the sole statement comparison record, either `.mathesis/REVIEW.md` or `.mathesis/review.json`. |
| 2 · Content | Exactly `books/<slug>/`: `book.toml`, `zh/`, `en/`, `figures/`, `viz/`, `slides/`, `assets/` | Author or preparing agent. The slug is `paper.json`'s work id. A shorter slug requires a nonempty `short_slug_reason` in the book mapping. Persist empty media directories with `.gitkeep`, as fill does. |
| 3 · Machinery | Upstream `template.toml` managed paths and installed layer managed paths | Template/layer maintainers, through `tbook template update`. Excluded namespaces are not permission to add local files: `docs/project/` and local skills are outside this layout. Managed files must be listed in the corresponding template manifest. |
| 4 · Repository front | `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`, `PROJECT.md`, `site.toml`, `trureturing.lock.json`, `template.d/` | Publisher generates the README; maintainers configure the remaining front through the existing publisher/template interfaces. `template.d/` contains only installed layer configurations and manifests. |

No other root entry is allowed. Git administrative data and ignored local
build/dependency directories are working files, not a fifth committed zone.
The checker inspects tracked files **and unignored new files**, including files
that are tracked despite an ignore rule. It rejects unknown empty directories
too. A repository without `paper.json` is an unfilled template: no paper record
or book is required, but examples and debris are still forbidden. Its README
links to this contract; `fill` replaces it with the selected paper's front.

## Ownership and generated front

Every frozen record file must be listed in `.mathesis/generated.json` and match
its SHA-256. The manifest cannot claim content, machinery or arbitrary paths.
Only the manifest itself, book mapping and one comparison record are additional
record files. Never rehash frozen files to bless local edits.

The catalog currently hashes its minimal `README.md` too. Preserve those bytes
as the README prefix, then append the deterministic layer repository guide.
`check` verifies the prefix against the unchanged catalog hash and the complete
guide against its generator. The guide supplies site and per-language reading
links, source slides and visualizations, comparison/status links and this zone
map. The catalog prefix retains title, original authors, abstract, DOI, licence,
Mathesis page and public formalization status. `paper.py front` refreshes only
the generated front. Zenodo preparation exports the original catalog prefix,
so the frozen upload bytes continue to match the catalog manifest.

With mapped results, keep exactly one comparison record. Markdown uses one row
per book result under `| Result | Verdict | Compared declaration | Commit | Scope |`;
the first four cells must match `book.json`. JSON uses a `results` object keyed
by book result id, with `comparison_verdict`, `compared_public_gid`,
`comparison_commit` and a nonempty `scope`. Store a concise mathematical scope
comparison here, never transcripts or evidence dumps. This check validates
record consistency, not the mathematical judgment or Lean membership itself.

## Source files and working output

Commit no logs, validation dumps, evidence archives, handoff notes, one-off
scripts or built output anywhere. Preparation run records belong in the
workflow run or an external workspace. The machine-readable rules below name
forbidden directories and filename patterns. Recognized machinery source files
and frozen publisher imports may have historical names such as `evidence.py` or
`manuscript/verify.py`; they are source, not new preparation debris. Size and
built-output limits still apply to machinery. Author figure generators and
their canonical SVGs are content, as required by upstream; rendered PDF/EPUB,
video, archives and presentation binaries are outputs. No file may exceed
2 MiB, except `paper.pdf` and frozen files under `manuscript/`.

## Upgrades and migration to 0.5.0

Paper repositories upgrade with **`tbook template update`**, never by git-merging
the template. Upstream `docs/UPGRADING.md` §1 and `TemplateConfig.protects` /
`plan_update` in `tools/tbook/template.py` exclude repository-owned `books/`
from synchronization. Consequently deleting upstream example books is safe:
future template/layer updates cannot restore them. The hide-examples advice
in upstream §6 addresses git merges, which bring every template file across;
that mechanism is not used for Mathesis papers. Tests exercise a real local
template update to ensure an absent example remains absent.

The 0.5.0 migration previews `paper.py tidy --dry-run` and refreshes the front;
it does not silently remove repository-owned work during a template update.
Run `paper.py tidy --apply` once to move violations into a newly created archive
**outside** the repository (or choose an external `--archive`). Dry-run writes
nothing. Both modes show the same plan. Tidy preserves the selected book and
all paper-record files, even when they violate a rule, and reports the repairs
their owners must make. Upstream `books/example-*` are the explicit migration
exception: they move to the external archive. Other extra books remain protected.
Tidy also preserves machinery listed in template manifests. It never renames a
book, changes hashes, rewrites claims or creates a review. Before archiving
`docs/project/`, paper-sync must condense any statement review into the sole
`.mathesis/REVIEW.md`. Rerun check after the publisher/author repairs. Repeating
tidy on a clean tree changes nothing.

## Executable rules

The checker reads this JSON block; do not duplicate these lists in code.

```json
{
  "record_files": ["paper.json", "CITATION.cff", "paper.pdf", "formalization/nodes.json"],
  "record_directories": ["manuscript", "LICENSES"],
  "record_metadata": [".mathesis/generated.json", ".mathesis/book.json", ".mathesis/REVIEW.md", ".mathesis/review.json"],
  "catalog_front": ["README.md", "CHANGELOG.md", "CONTRIBUTING.md"],
  "front": ["README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE", "PROJECT.md", "site.toml", "trureturing.lock.json", "template.d"],
  "content": ["book.toml", "zh", "en", "figures", "viz", "slides", "assets"],
  "empty_media": ["figures", "viz", "slides", "assets"],
  "forbidden_directories": ["docs/project", "validation", "evidence", "artifacts", "logs", "handoffs", "run-records", "__pycache__"],
  "forbidden_filenames": ["*.log", "*.jsonl", "*.pyc", "*.tmp", "*.bak", "*.template-new", "*handoff*", "validation-*", "validation_*", "validation.*", "evidence-*", "evidence_*", "evidence.*", "run-record*", "run_record*", "one-off*", "one_off*", "prepare-*.py", "audit-*.py"],
  "built_suffixes": [".pdf", ".epub", ".pptx", ".mp4", ".mov", ".zip", ".tar", ".gz", ".tgz", ".aux", ".toc", ".synctex"],
  "local_only": ["build", "_site", ".cache", ".venv", "node_modules", "__pycache__", ".DS_Store"],
  "size_limit": 2097152
}
```
