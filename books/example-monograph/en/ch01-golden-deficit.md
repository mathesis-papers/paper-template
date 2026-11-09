# Chapter 1 The carry deficit of golden integers

Every natural number $n$ is, in a unique way, a sum of nonadjacent Fibonacci numbers (its Zeckendorf representation), with weights $F_2 = 1, F_3 = 2, F_4 = 3, \dots$. Replacing each weight $F_i$ by $\varphi^i$, where $\varphi = (1+\sqrt5)/2$ is the golden ratio, gives a real number $\beta(n)$.

::: {.definition #def-deficit title="Normalized deficit" lean="D5/S1/Deficit/DeficitInteger.deficit"}
For natural numbers $v_1, v_2$, define
$$
c(v_1, v_2) = \beta(v_1) + \beta(v_2) - \beta(v_1 + v_2).
$$
:::

$\beta$ does not preserve addition: for example $\beta(1) = \varphi^2$ and $\beta(2) = \varphi^3$, so $c(1, 1) = 2\varphi^2 - \varphi^3 = 1$.

::: {.theorem #thm-deficit-integer title="The deficit is an integer, the signed carry count" lean="D5/S1/Deficit/DeficitInteger.deficit_integer"}
For all natural numbers $v_1, v_2$, the deficit $c(v_1, v_2)$ equals its reading on the contraction face (the Galois conjugate), is an integer, and equals the signed count of the two lowest repeated-carry rules applied while normalizing the digitwise sum of the two Zeckendorf representations.
:::

::: {.theorem #thm-deficit-three-valued title="The deficit takes three values" lean="D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"}
For all natural numbers $v_1, v_2$,
$$
c(v_1, v_2) \in \{-1, 0, 1\}.
$$
:::

::: proof
The contraction face evaluates Zeckendorf digits at powers of the conjugate $\psi = (1-\sqrt5)/2$. Each $\beta'(v)$ lies in the window $[-\psi^2, -\psi]$, whose length is exactly $1$, so the contraction-face reading of $c$ lies strictly between $-2$ and $2$; by [@thm-deficit-integer] it is an integer. The full proof is checked by the Lean kernel.
:::

::: remark
[@thm-deficit-three-valued] holds however large the inputs are: it ties an arithmetic algorithm (digitwise carrying) to an exact bound, and can be reused as a premise in later arguments. In Lean its name is [`deficit_three_valued`](lean:D5/S1/Deficit/DeficitThreeValued.deficit_three_valued).
:::

## Two faces {#sec-two-faces}

::: {.definition #def-beta-contraction title="The conjugate reading $\beta'$" lean="D5/S1/Deficit/DeficitInteger.betaContraction"}
(To be written.)
:::

::: {.lemma #lem-two-faces title="The gap between the faces" lean="D5/S1/Deficit/DoubleFaceLength.betaReal_sub_betaContraction"}
(To be written.)
:::

::: {.lemma #lem-window title="The window of the conjugate face" lean="D5/S1/Words/Expansions/BasePhiNegativeBridge.betaContraction_mem_window"}
(To be written.)
:::

::: proof
(To be written.)
:::

## When the deficit takes which value {#sec-phases}

::: {.theorem #thm-beatty-deficit title="The Beatty form of the deficit" lean="D5/S1/Deficit/ChargedCarryPath.deficit_eq_beattyDeficit"}
(To be written.)
:::

::: {.theorem #thm-golden-phase title="The phase criterion" lean="D5/S1/Deficit/GoldenPhaseDeficit.golden_phase_deficit"}
(To be written.)
:::

::: {.example #ex-small-deficits title="A table of small values"}
(To be written.)
:::

::: {.proposition #prop-phase-areas title="The areas of the three values" lean="D5/S1/Deficit/GoldenPhaseDistribution.limiting_deficit_distribution"}
(To be written.)
:::

::: {.remark #rem-areas-not-frequencies title="Areas are not yet frequencies"}
(To be written.)
:::

## See it for yourself

The interactive visualization and the film below are built from this book's repository. The numbers on screen are computations on the page that help you see; whether a result holds is decided by Lean.

::: {.viz src="golden-carry" height="560"}
Drag the sliders or click the deficit map to pick $v_1, v_2$ and step through the carries; the deficit $c(v_1, v_2)$ is always $-1$, $0$ or $1$ ([@thm-deficit-three-valued]).
:::

::: {.film src="001-golden-deficit"}
Animation: adding two Zeckendorf representations, the carries, and why the deficit takes only $-1, 0, 1$ ([@thm-deficit-three-valued]).
:::
