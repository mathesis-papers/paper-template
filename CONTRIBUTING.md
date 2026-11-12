# Contributing

Mathesis records formalization attempts through the public attempt path. Read [Contribute](https://mathesis-omega-research.apps.chrono-ai.fun/contribute) and the [public contribution guide](https://github.com/the-omega-institute/mathesis/blob/develop/docs/CONTRIBUTE.md), then use `sdk/contribute`. A repository pull request may explain a proof, point to an erratum, or add reproducibility material; it does not register an attempt, confer verification status, or create credit. Only an independent verifier receipt for the exact target counts. Original paper authors and formalization contributors remain separate.

The shared Lean library is the first binding. This repository does not copy library sources and does not emit a Lean environment for a paper that has no new Lean. If a paper-specific development is later needed, its pinned environment is generated from the verifier's pinned environment and is never hand-edited.
