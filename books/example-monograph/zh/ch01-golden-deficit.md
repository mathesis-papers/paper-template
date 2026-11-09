# 第一章 黄金整数的进位亏量

每个自然数 $n$ 都可以唯一地写成互不相邻的 Fibonacci 数之和（Zeckendorf 表示），权重取 $F_2 = 1, F_3 = 2, F_4 = 3, \dots$。把每个权重 $F_i$ 换成 $\varphi^i$，其中 $\varphi = (1+\sqrt5)/2$ 是黄金比，就得到实数 $\beta(n)$。

::: {.definition #def-deficit title="归一化亏量" lean="D5/S1/Deficit/DeficitInteger.deficit"}
对自然数 $v_1, v_2$，定义
$$
c(v_1, v_2) = \beta(v_1) + \beta(v_2) - \beta(v_1 + v_2).
$$
:::

$\beta$ 并不保持加法：例如 $\beta(1) = \varphi^2$、$\beta(2) = \varphi^3$，于是 $c(1, 1) = 2\varphi^2 - \varphi^3 = 1$。

::: {.theorem #thm-deficit-integer title="亏量是整数，且等于带符号的进位计数" lean="D5/S1/Deficit/DeficitInteger.deficit_integer"}
对所有自然数 $v_1, v_2$，亏量 $c(v_1, v_2)$ 等于它在收缩面（Galois 共轭）上的读数，是一个整数，并且等于把两个 Zeckendorf 表示逐位相加后、规范化过程中两条最低重复进位规则的带符号计数。
:::

::: {.theorem #thm-deficit-three-valued title="亏量只取三个值" lean="D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"}
对所有自然数 $v_1, v_2$，
$$
c(v_1, v_2) \in \{-1, 0, 1\}.
$$
:::

::: proof
收缩面把 Zeckendorf 数字放在共轭 $\psi = (1-\sqrt5)/2$ 的幂上求值。每个 $\beta'(v)$ 落在长度恰为 $1$ 的窗口 $[-\psi^2, -\psi]$ 中，所以 $c$ 在收缩面上的读数严格介于 $-2$ 与 $2$ 之间；再由 [@thm-deficit-integer]，它是整数。完整证明已在 Lean 中由内核检查。
:::

::: remark
[@thm-deficit-three-valued] 对任意大的输入都成立：它把一个算术算法（逐位进位）和一个精确界联系起来，可以作为后续推理的前提反复使用。在 Lean 中，它的名字是 [`deficit_three_valued`](lean:D5/S1/Deficit/DeficitThreeValued.deficit_three_valued)。
:::

## 两张面孔 {#sec-two-faces}

::: {.definition #def-beta-contraction title="共轭面读数 $\beta'$" lean="D5/S1/Deficit/DeficitInteger.betaContraction"}
（待写）
:::

::: {.lemma #lem-two-faces title="两面之差" lean="D5/S1/Deficit/DoubleFaceLength.betaReal_sub_betaContraction"}
（待写）
:::

::: {.lemma #lem-window title="共轭面的窗口" lean="D5/S1/Words/Expansions/BasePhiNegativeBridge.betaContraction_mem_window"}
（待写）
:::

::: proof
（待写）
:::

## 亏量何时取哪个值 {#sec-phases}

::: {.theorem #thm-beatty-deficit title="亏量的 Beatty 形式" lean="D5/S1/Deficit/ChargedCarryPath.deficit_eq_beattyDeficit"}
（待写）
:::

::: {.theorem #thm-golden-phase title="相位判据" lean="D5/S1/Deficit/GoldenPhaseDeficit.golden_phase_deficit"}
（待写）
:::

::: {.example #ex-small-deficits title="小数值表"}
（待写）
:::

::: {.proposition #prop-phase-areas title="三种取值的面积" lean="D5/S1/Deficit/GoldenPhaseDistribution.limiting_deficit_distribution"}
（待写）
:::

::: {.remark #rem-areas-not-frequencies title="面积还不是频率"}
（待写）
:::

## 动手看一看

下面的交互可视化与视频都由本书仓库构建：画面上的数值只是页面上的计算，帮助理解；结论成立与否以 Lean 为准。

::: {.viz src="golden-carry" height="560"}
拖动滑块或点击亏量图选择 $v_1, v_2$，逐步观察进位；亏量 $c(v_1, v_2)$ 总是 $-1$、$0$、$1$ 之一（[@thm-deficit-three-valued]）。
:::

::: {.film src="001-golden-deficit"}
动画：两个 Zeckendorf 表示相加、进位，以及亏量为什么只取 $-1, 0, 1$（[@thm-deficit-three-valued]）。
:::
