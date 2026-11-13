# Upstream 0.8.2 and Mathesis 0.4.0

Upgraded from combined main `22894117c07f3ddd042739e6011254af84afa0f5`
to upstream release `85e533c20bad105dbb6999b2919bda2a6ddcb1d1`, using
`./tbook template update --layer upstream --to v0.8.2 --source
https://github.com/the-omega-institute/trureturing-books-template.git`.
The explicit layer selector is required when multiple layers are installed.

The updater added 7 files and updated 57, with no conflicts or preserved local
managed-file changes. The 241 upstream-managed files and manifest match the
release. `./tbook template manifest` reports the generated manifest unchanged;
`--check` passes. No compatibility patch remains.

Upstream includes the behavior of `690ec33`: written-proof academic citations,
associated nonempty proof validation, a purple badge without a Lean verification
link, and no assigned GID. Its richer ledger supplies DOI/source/request links.
A temporary compatibility probe exercised valid rendering, missing proof,
empty proof and simultaneous Lean citation: all four scenarios passed. The
release also includes the film fixture's `root=self.root` correction; the
relevant test file is byte-identical to the previous combined template.

Mathesis layer 0.4.0 was applied from local source commit
`af3d76085a17199f8d7b088587ba428c50f3e94f` through the same updater: 7 updates,
no conflicts. Its 21 integration tests passed against these upstream tools,
using the existing Chen–Chen projection. Its 21-file layer manifest passes.
`./tbook check` passes with 0 errors and 0 warnings (0 visible books in this
publisher template; the paper clone provides real-book validation).

The first paper requires a content migration: upstream now requires a bare DOI,
original source location and a registered formalization-request URL on every
written-proof result. Its recorded DOI/source locations can be migrated locally.
An anonymous read of the complete public request queue found only the unrelated
golden-deficit issue #1, with no Chen–Chen registrations. The eight missing
registrations remain a paper validation/build gate; no external write or
fabricated request URL is part of this local upgrade.
