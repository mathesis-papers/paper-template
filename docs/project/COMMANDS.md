# Recorded validation and build commands

Working directory: `/Users/lexa/Desktop/lexa/omega/mathesis-paper-template-combined`. Each command was invoked through
`python3 docs/project/run-command.py <log-label> <command...>`; the table shows
the exact child arguments. Commands use the recorded existing Chrome and Tectonic,
repository-local caches and the task temporary directory. No credentials were
passed. Exit codes below are actual, including superseded failures.

| # | Child command | Exit | Log |
|---|---|---:|---|
| 1 | `npm ci --ignore-scripts --no-audit --no-fund` | 0 | [npm-ci.txt](validation/npm-ci.txt) |
| 2 | `./tbook check --offline` | 0 | [template-check.txt](validation/template-check.txt) |
| 3 | `./tbook template install mathesis --source /Users/lexa/Desktop/lexa/omega/mathesis-paper-template --to main --dry-run` | 0 | [install-layer-preview.txt](validation/install-layer-preview.txt) |
| 4 | `./tbook template install mathesis --source /Users/lexa/Desktop/lexa/omega/mathesis-paper-template --to main` | 0 | [install-layer.txt](validation/install-layer.txt) |
| 5 | `./tbook check --offline` | 0 | [empty-template-check.txt](validation/empty-template-check.txt) |
| 6 | `./tbook template manifest --check` | 0 | [template-manifest-check.txt](validation/template-manifest-check.txt) |
| 7 | `./tbook template manifest --layer mathesis --check` | 0 | [layer-manifest-check.txt](validation/layer-manifest-check.txt) |
| 8 | `python3 -m unittest discover -s docs/layer-mathesis/tests` | 0 | [layer-tests.txt](validation/layer-tests.txt) |
| 9 | `python3 -m unittest discover -s tools/tests` | 1 | [template-tests.txt](validation/template-tests.txt) |
| 10 | `python3 -m unittest discover -s tools/tests` | 1 | [template-tests-rerun.txt](validation/template-tests-rerun.txt) |
| 11 | `./tbook check --offline` | 0 | [empty-template-final-check.txt](validation/empty-template-final-check.txt) |
| 12 | `env FILM_CHROMIUM_ARGS=--use-angle=swiftshader python3 -m unittest discover -s tools/tests -p test_film_solid.py` | 1 | [solid-software-check.txt](validation/solid-software-check.txt) |
| 13 | `python3 -m unittest discover -s tools/tests -p test_academic.py` | 0 | [academic-written-proof-tests.txt](validation/academic-written-proof-tests.txt) |
| 14 | `./tbook template update --layer mathesis --source /Users/lexa/Desktop/lexa/omega/mathesis-paper-template --to main` | 0 | [refresh-layer.txt](validation/refresh-layer.txt) |
| 15 | `python3 docs/project/template-suite.py` | 1 | [template-tests-final.txt](validation/template-tests-final.txt) |
| 16 | `./tbook template update --layer mathesis --source /Users/lexa/Desktop/lexa/omega/mathesis-paper-template --to main` | 0 | [refresh-layer-final.txt](validation/refresh-layer-final.txt) |
| 17 | `./tbook template manifest --layer mathesis --check` | 0 | [mathesis-manifest-final.txt](validation/mathesis-manifest-final.txt) |
| 18 | `./tbook check` | 0 | [template-final-check.txt](validation/template-final-check.txt) |
| 19 | `./tbook template manifest --check` | 0 | [upstream-manifest-final.txt](validation/upstream-manifest-final.txt) |

The JSONL also retains UTC start/end timestamps. Direct Git integration, source
reads, scaffold generation, initial manifest regeneration and visual inspection
are described in the handoff; they are not claimed to be part of this command
runner transcript. PDF inspection subcommands appear in `deck-pdf-qa.txt` where
applicable. The final git diff checks and repository-state verification are
retained in the handoff state evidence.
