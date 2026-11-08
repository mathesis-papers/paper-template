# Preface

This book demonstrates the writing conventions of the trureturing books template. Every theorem, lemma, proposition and corollary in it corresponds to a declaration in [trureturing](https://github.com/the-omega-institute/trureturing) that the Lean kernel has verified and that is frozen. The Lean code lives in trureturing; the book cites it by GID. At build time `./tbook check` confirms each citation against the frozen state at the pinned commit, and the verification ledger at the end of the book is generated automatically.

Results without a proof are always written as conjectures or open problems, never as theorems.
