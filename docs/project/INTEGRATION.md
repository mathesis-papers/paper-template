# Local combined-template handoff

Prepared on 2026-11-13 for dispatcher review. No GitHub write was performed.
This repository is on `main`; its sole remote is anonymous upstream
`https://github.com/the-omega-institute/trureturing-books-template.git`, named
`upstream`. The input branch clones and Lean checkout were read-only.

## Integration

Base upstream main: `e506a8841cf9deb89e2f70dff69dc5b88b4d8510`.
All three PR heads were fetched from that remote, then merged with merge commits.

| PR | Pushed head | Local merge |
|---|---|---|
| #48, template layers | `dc4481b85ad3316b9c8556b68cb6da9d8720eed3` | `fd85a93` |
| #50, written-proof status | `899013b9bad204e0996374082addf6d4a17fd3c2` | `e7e8c70` |
| #51, academic Beamer | `2738f71a80f04e88cb10c000e5f5bf6dc2c465b8` | `a6f7b52` |

`docs/CHANGELOG.md` and generated `template-manifest.json` conflicted in the
merges. Release notes were consolidated under one 0.7.0 release dated
2026-11-13, retaining the upstream notes. The manifest was regenerated through
`./tbook template manifest`, never hand-merged. `template.toml` merged
automatically and remains 0.7.0. The #51 conflict in `tools/tbook/doctor.py`
retains both upstream's WebGL probe and the PR's Tectonic check.

A semantic conflict remained: the new academic renderer rejected no-GID
written-proof results. Commit `690ec33` reconciles the two PR contracts using
the existing proof-policy checker, an unlinked purple WRITTEN PROOF badge,
and a ledger row without a GID. Its regression covers rendering, a missing
proof, an empty proof and an impermissible Lean citation. Twelve academic
tests pass. No shared workflow, runner or publication contract was altered.

**Dispatcher integration requirement:** merging the three unmodified PR heads
alone does not include `690ec33`. Preserve/incorporate that reconciliation
before a later ordinary upstream template update replaces its managed files.
The PR-head merge content itself will already be present after those PRs merge.

## Mathesis layer

Installed with the actual layer CLI from #48, dry run followed by install:

```sh
./tbook template install mathesis --source /Users/lexa/Desktop/lexa/omega/mathesis-paper-template --to main --dry-run
./tbook template install mathesis --source /Users/lexa/Desktop/lexa/omega/mathesis-paper-template --to main
```

The layer is 0.2.1 (15 managed files); upstream is 0.7.0 (233 managed files).
The layer source has only layer-owned changes, committed on its local main:
`885a58d`, `8220560`, `a6e42ab76931` (final). It includes a changelog and
`docs/layer-mathesis/UPSTREAM-PINS.md` with the full PR heads and preservation
requirement. Later note refreshes used supported `template update --layer
mathesis`, with zero conflicts.

The root publisher skeleton is configured for `mathesis-papers/paper-template`.
`site.toml` has `order = []` and `hide = ["example-*"]`. Upstream examples
remain hidden; there is no selected paper, `.mathesis` mapping, manuscript,
paper PDF or generated catalog input in this combined template.

## Validation

Exact command arguments, exit codes, timestamps and logs are retained in
[COMMANDS.md](COMMANDS.md) and [validation/commands.jsonl](validation/commands.jsonl).
Readable task logs have trailing whitespace and blank EOF normalized for Git;
`evidence/log-normalization.json` lists the affected logs. Results are unchanged.

| Check | Actual final result |
|---|---|
| Pre-layer `./tbook check --offline` | 2 examples, 0 errors, 0 warnings |
| Final empty-template `./tbook check` | 0 visible books, 0 errors, 0 warnings |
| Upstream manifest check | pass, 233 files, 0.7.0 |
| Mathesis manifest check | pass, 15 files, 0.2.1 |
| Layer integration suite using actual projection and combined upstream | 10 tests pass |
| Focused academic written-proof suite | 12 tests pass |
| Full upstream suite on final runtime | 1,032 run; 934 passed, 95 skipped, 3 failed |

The full suite requires examples to be visible. `template-suite.py` temporarily
selects them and restores the empty template in `finally`. Final failure log:
[validation/template-tests-final.txt](validation/template-tests-final.txt).

Remaining failures:

1. `test_film_solid.SolidShotInTheBrowser.test_checks`: the same time drawn
   twice does not give identical pixels in installed Chrome 157. A separate
   task-only SwiftShader-angle rerun also failed this assertion. The paper has
   no films. No browser download or shared rendering infrastructure change was made.
2. `test_verification.BuildCacheWorkflowTests.test_release_attaches_the_build_cache_and_publishes_a_complete_draft`:
   macOS `/bin/bash` lacks `mapfile` (exit 127).
3. `test_verification.BuildCacheWorkflowTests.test_template_release_attaches_the_example_site_cache`:
   the same `mapfile` limitation (exit 127).

The first suite attempt had 11 failures and one error from the initial browser
configuration, checkout-local temporary directories and a concurrent change to
example selection. It was superseded by two corrected full runs; the final run
above includes the compatibility regression. Initial and retry logs are kept.
The release tests use mock executables; no real `gh` command was run.

CI must confirm the three unresolved platform/browser tests and run the skipped
tool-dependent checks. This local handoff does not claim a green full suite.

## Local cleanup

After all jobs exited, an open-file check found no handles in the task dependency
and temporary-cache paths. The shared task-only node_modules, its paper symlink,
npm cache and obsolete checkout-local test temporary files were removed,
reclaiming 886,688 KiB (865.9 MiB). Source, logs, unique evidence, paper PDFs,
visualization screenshots and the requested temporary deck renders remain.
The paper-local Tectonic resource cache is retained. Reinstall local Node
dependencies with the recorded `npm ci` before rerunning browser tests; no
global installation or shared cache was changed. See `evidence/cleanup.json`.
