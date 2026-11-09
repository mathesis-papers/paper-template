# Chapter 1 Introduction

Start writing here. A theorem environment looks like this (the Lean code lives in trureturing; the book only cites its GID):

```markdown
::: {.theorem #thm-example title="Theorem title" lean="D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"}
The statement, possibly with math $a + b$.
:::
```

Refer to it as `[@thm-example]`; the build turns that into "Theorem 1.1". Results without a proof are written as `::: {.conjecture #conj-x}`.
