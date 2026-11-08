# 第一章 导引

在这里开始写作。定理环境的写法（Lean 代码写在 trureturing 中，这里只引用其 GID）：

```markdown
::: {.theorem #thm-example title="定理标题" lean="D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"}
定理陈述，可含数学 $a + b$。
:::
```

引用写作 `[@thm-example]`，构建时变成“定理 1.1”。尚未证明的结论写成 `::: {.conjecture #conj-x}`。
