# 第二章 卢卡斯数与黄金比

黄金比 $\varphi = (1 + \sqrt5)/2 \approx 1.618$ 满足 $\varphi^2 = \varphi + 1$。本章前两节先不用 $\sqrt5$ 做近似计算，而是把 $\varphi$ 当作一个满足 $\varphi^2 = \varphi + 1$ 的符号，研究形如 $a + b\varphi$（$a, b$ 为整数）的数。这样所有计算都是精确的整数运算，Lean 也正是这样做的。在这个数系里，斐波那契数会作为 $\varphi$ 的幂的坐标出现，卢卡斯数则是这些幂的“迹”。第三节回到实数，说明相邻斐波那契数之比怎样逼近 $\varphi$；最后一节介绍一个尚未解决的问题。

## 黄金整数 {#sec-golden-int}

把 $(a + b\varphi)(c + d\varphi)$ 展开得 $ac + (ad + bc)\varphi + bd\varphi^2$，再把 $\varphi^2$ 换成 $\varphi + 1$，就得到下面定义中的乘法公式。

::: {.definition #def-golden-int title="黄金整数" lean="D5/S0/Carrier/Ring.GoldenInt D5/S0/Carrier/Ring.phi"}
一个黄金整数是一对整数 $(a, b)$，写作 $a + b\varphi$；全体黄金整数记作 $\mathbb{Z}[\varphi]$。加法逐个坐标相加，乘法规定为

$$
(a + b\varphi)(c + d\varphi) = (ac + bd) + (ad + bc + bd)\varphi .
$$

其中 $\varphi$ 是坐标为 $(0, 1)$ 的黄金整数 $0 + 1\varphi$；$0$ 与 $1$ 分别是 $(0, 0)$ 与 $(1, 0)$，整数 $m$ 对应 $(m, 0)$。
:::

在 Lean 中，`GoldenInt` 是带两个整数坐标 `a`、`b` 的结构，乘法直接按上面的公式定义；同一模块还给出了交换环的结构（结合律、分配律等都成立），所以可以像普通数一样计算。

::: {.theorem #thm-phi-sq title="$\varphi^2 = \varphi + 1$" lean="D5/S0/Carrier/Ring.phi_sq"}
在 $\mathbb{Z}[\varphi]$ 中，

$$
\varphi^2 = \varphi + 1 .
$$
:::

::: proof
按乘法公式取 $a = c = 0$、$b = d = 1$：

$$
(0 + 1\varphi)(0 + 1\varphi) = (0 \cdot 0 + 1 \cdot 1) + (0 \cdot 1 + 1 \cdot 0 + 1 \cdot 1)\varphi = 1 + \varphi .
$$

Lean 也是逐个坐标比较两边。完整证明由 Lean 内核检查。
:::

这是关于黄金整数的陈述，不是关于实数 $(1 + \sqrt5)/2$ 的陈述。后者满足同一个方程（展开即得 $\bigl((1 + \sqrt5)/2\bigr)^2 = (3 + \sqrt5)/2 = (1 + \sqrt5)/2 + 1$），但那是另一件事。

乘以 $\varphi$ 有一个简单的效果：按乘法公式，$(a + b\varphi)\varphi = b + (a + b)\varphi$，也就是把坐标 $(a, b)$ 变成 $(b, a + b)$。这正是斐波那契递推的一步。于是 $\varphi = 0 + 1\varphi$、$\varphi^2 = 1 + 1\varphi$、$\varphi^3 = 1 + 2\varphi$、$\varphi^4 = 2 + 3\varphi$、$\varphi^5 = 3 + 5\varphi$，坐标都是相邻的斐波那契数。

::: {.theorem #thm-phi-pow title="$\varphi$ 的幂由斐波那契数给出" lean="D5/S1/Scale/Fibonacci.golden_phi_pow_eq_fib_pair"}
对每个自然数 $n$，在 $\mathbb{Z}[\varphi]$ 中

$$
\varphi^{n+1} = F_n + F_{n+1}\varphi ,
$$

即 $\varphi^{n+1}$ 的两个坐标是 $(F_n, F_{n+1})$。
:::

::: proof
对 $n$ 归纳。$n = 0$ 时 $\varphi^1 = 0 + 1\varphi = F_0 + F_1\varphi$。若 $\varphi^{n+1} = F_n + F_{n+1}\varphi$，乘以 $\varphi$ 得

$$
\varphi^{n+2} = F_{n+1} + (F_n + F_{n+1})\varphi = F_{n+1} + F_{n+2}\varphi .
$$

Lean 的证明就是这次归纳。完整证明由 Lean 内核检查。
:::

定理只讲指数至少为 $1$ 的幂。$\varphi^0 = 1 = 1 + 0\varphi$ 是乘方的约定，不在定理之内。这条定理在 Lean 中叫 [`golden_phi_pow_eq_fib_pair`](lean:D5/S1/Scale/Fibonacci.golden_phi_pow_eq_fib_pair)，[第一章](ch01-fibonacci.md)中卡西尼恒等式的证明（[@thm-cassini]）就建立在它上面。

## 卢卡斯数 {#sec-lucas}

把 $\varphi$ 换成另一个根 $1 - \varphi$，黄金整数 $a + b\varphi$ 就变成它的共轭 $(a + b) - b\varphi$。两者相加，$\varphi$ 的系数抵消，剩下整数 $2a + b$。

::: {.definition #def-lucas title="卢卡斯数" lean="D5/S1/Scale/Lucas.goldenLucas D5/S0/Carrier/Conj.trace"}
黄金整数 $x = a + b\varphi$ 的迹是整数

$$
\tr(x) = 2a + b .
$$

对每个自然数 $n$，卢卡斯数定义为

$$
L_n = \tr(\varphi^n) .
$$
:::

用实数来想，迹就是把 $\varphi$ 与另一个根 $\psi = (1 - \sqrt5)/2$ 分别代入后相加：$(a + b\varphi) + (a + b\psi) = 2a + b$，因为 $\varphi + \psi = 1$。由定义，$L_0 = \tr(1) = 2$，$L_1 = \tr(\varphi) = 1$。下表列出前几项：

| $n$ | $\varphi^n$ | $F_n$ | $L_n = \tr(\varphi^n)$ |
| ---: | --- | ---: | ---: |
| 0 | $1 + 0\varphi$ | 0 | 2 |
| 1 | $0 + 1\varphi$ | 1 | 1 |
| 2 | $1 + 1\varphi$ | 1 | 3 |
| 3 | $1 + 2\varphi$ | 2 | 4 |
| 4 | $2 + 3\varphi$ | 3 | 7 |
| 5 | $3 + 5\varphi$ | 5 | 11 |
| 6 | $5 + 8\varphi$ | 8 | 18 |
| 7 | $8 + 13\varphi$ | 13 | 29 |
| 8 | $13 + 21\varphi$ | 21 | 47 |

从 $n = 1$ 起，表中每个 $L_n$ 都等于相邻两个下标的斐波那契数之和 $F_{n-1} + F_{n+1}$，例如 $L_5 = 11 = 3 + 8 = F_4 + F_6$。

::: {.theorem #thm-lucas-fib title="卢卡斯数与斐波那契数" lean="D5/S1/Scale/Lucas.golden_lucas_succ_eq_fib_add_fib"}
对每个自然数 $n$，

$$
L_{n+1} = F_n + F_{n+2} .
$$
:::

::: proof
由 [@thm-phi-pow]，$\varphi^{n+1} = F_n + F_{n+1}\varphi$，所以

$$
L_{n+1} = 2F_n + F_{n+1} = F_n + (F_n + F_{n+1}) = F_n + F_{n+2} .
$$

完整证明由 Lean 内核检查。
:::

由此可以推出卢卡斯数满足与斐波那契数相同的递推：$L_{n+3} = F_{n+2} + F_{n+4} = (F_n + F_{n+2}) + (F_{n+1} + F_{n+3}) = L_{n+1} + L_{n+2}$，再加上 $L_2 = 3 = L_1 + L_0$，就得到 $2, 1, 3, 4, 7, 11, 18, \dots$。这条递推是本书由 [@thm-lucas-fib] 推出的说明，没有另外引用 Lean 声明。

卢卡斯数还能把斐波那契数的下标加倍。

::: {.theorem #thm-fib-double title="倍数公式" lean="D5/S1/Scale/FibLucasDouble.golden_fib_two_mul_eq_fib_mul_lucas"}
对每个自然数 $n$，在整数中

$$
F_{2n} = F_n L_n .
$$
:::

例如 $F_{10} = 55 = 5 \cdot 11 = F_5 L_5$，$F_{12} = 144 = 8 \cdot 18 = F_6 L_6$。

::: proof
把 $\varphi^n$ 写成 $a + b\varphi$，则 $b = F_n$：$n \ge 1$ 时这就是 [@thm-phi-pow]，$n = 0$ 时 $\varphi^0 = 1 + 0\varphi$。由乘法公式，$(a + b\varphi)^2$ 的 $\varphi$ 坐标是 $ab + ba + b^2 = b(2a + b)$。而 $(a + b\varphi)^2 = \varphi^{2n}$，它的 $\varphi$ 坐标是 $F_{2n}$，所以 $F_{2n} = b(2a + b) = F_n \tr(\varphi^n) = F_n L_n$。完整证明由 Lean 内核检查。
:::

特别地，$n \ge 1$ 时 $F_n$ 整除 $F_{2n}$，商恰好是 $L_n$。这与[第一章](ch01-fibonacci.md)的 [@thm-fib-dvd] 一致：$n \ge 3$ 时，由 $n \mid 2n$ 也能得到 $F_n \mid F_{2n}$，但那条定理不告诉我们商是多少。

最后一条代数恒等式把卢卡斯数与斐波那契数绑在一个方程里。

::: {.theorem #thm-lucas-discriminant title="判别式恒等式" lean="D5/S1/Scale/Lucas.golden_lucas_discriminant"}
对每个自然数 $n$，在整数中

$$
L_n^2 - 5F_n^2 = 4(-1)^n .
$$
:::

前几项的验算：

| $n$ | $L_n$ | $F_n$ | $L_n^2 - 5F_n^2$ |
| ---: | ---: | ---: | ---: |
| 0 | 2 | 0 | $4 - 0 = 4$ |
| 1 | 1 | 1 | $1 - 5 = -4$ |
| 2 | 3 | 1 | $9 - 5 = 4$ |
| 3 | 4 | 2 | $16 - 20 = -4$ |
| 4 | 7 | 3 | $49 - 45 = 4$ |
| 5 | 11 | 5 | $121 - 125 = -4$ |

换句话说，每一对 $(L_n, F_n)$ 都是方程 $x^2 - 5y^2 = \pm 4$ 的整数解。定理只说这些数对是解，并没有说这个方程的整数解只有这些。

::: proof
设 $x = a + b\varphi$，它的范数是 $N(x) = a^2 + ab - b^2$（[@thm-cassini] 的证明也用到它）。直接展开可得

$$
\tr(x)^2 - 5b^2 = (2a + b)^2 - 5b^2 = 4(a^2 + ab - b^2) = 4N(x) .
$$

范数把乘积变成乘积，且 $N(\varphi) = -1$，所以 $N(\varphi^n) = (-1)^n$。对 $x = \varphi^n$ 用上式，并代入 $\tr(\varphi^n) = L_n$、$b = F_n$，即得结论。完整证明由 Lean 内核检查。
:::

## 比值与黄金比 {#sec-ratio}

从这里起，$\varphi$ 回到实数黄金比 $(1 + \sqrt5)/2 = 1.6180339\ldots$（Mathlib 中的 `Real.goldenRatio`）。相邻斐波那契数之比 $F_{n+1}/F_n$ 依次是 $1, 2, 1.5, 1.667, 1.6, 1.625, 1.615, \dots$，在 $\varphi$ 的两侧来回摆动，越来越近。下面这条定理给出了误差的精确公式。

::: {.theorem #thm-ratio-error title="$F_n \varphi - F_{n+1}$ 的精确值" lean="D5/S1/Scale/FibonacciErrorRatio.fibonacci_golden_residual"}
设 $\varphi = (1 + \sqrt5)/2$。对每个自然数 $n$，在实数中

$$
F_n \varphi - F_{n+1} = -\left(-\frac{1}{\varphi}\right)^{n} .
$$
:::

例如 $n = 3$ 时左边是 $2\varphi - 3 \approx 0.23607$，右边是 $1/\varphi^3 \approx 0.23607$。

::: proof
思路：$\psi = 1 - \varphi = -1/\varphi$ 是 $x^2 = x + 1$ 的另一个实根。对 $\psi$ 重复 [@thm-phi-pow] 的归纳，得到 $\psi^n = F_{n-1} + F_n \psi$（$n \ge 1$）。于是

$$
F_n \varphi - F_{n+1} = F_n(\varphi - 1) - F_{n-1} = -(F_{n-1} + F_n \psi) = -\psi^n ,
$$

$n = 0$ 时两边都是 $-1$。Lean 的证明先把 $-1/\varphi$ 改写为 trureturing 的 `FibonacciEigen` 模块中斐波那契替换矩阵的收缩特征值（就是这里的 $\psi$），再引用该模块一条定理的最后一部分；那一部分归结为 Mathlib 的恒等式 $F_{n+1} - \varphi F_n = \psi^n$（`Real.fib_succ_sub_goldenRatio_mul_fib`），与上面推出的是同一个等式。完整证明由 Lean 内核检查。
:::

定理对每个 $n$ 给出一个精确的等式，本身并不是关于极限的陈述。但由它马上可以看出比值的行为：$n \ge 1$ 时两边除以 $F_n$，得

$$
\frac{F_{n+1}}{F_n} - \varphi = \frac{(-1/\varphi)^n}{F_n} .
$$

右边的绝对值是 $1/(\varphi^n F_n)$，随 $n$ 增大迅速变小；符号交替，$n$ 为偶数时比值在 $\varphi$ 上方，为奇数时在下方。“比值趋于 $\varphi$”是本书由此得出的结论，不是所引 Lean 声明本身的内容。下表是数值计算（保留六位小数）：

| $n$ | $F_{n+1}/F_n$ | $F_{n+1}/F_n - \varphi$ | $1/(\varphi^n F_n)$ |
| ---: | ---: | ---: | ---: |
| 1 | 1.000000 | −0.618034 | 0.618034 |
| 2 | 2.000000 | +0.381966 | 0.381966 |
| 3 | 1.500000 | −0.118034 | 0.118034 |
| 4 | 1.666667 | +0.048633 | 0.048633 |
| 5 | 1.600000 | −0.018034 | 0.018034 |
| 6 | 1.625000 | +0.006966 | 0.006966 |
| 7 | 1.615385 | −0.002649 | 0.002649 |
| 8 | 1.619048 | +0.001014 | 0.001014 |
| 9 | 1.617647 | −0.000387 | 0.000387 |
| 10 | 1.618182 | +0.000148 | 0.000148 |

## 一个开放问题 {#sec-open}

[第一章](ch01-fibonacci.md#sec-divisibility)的 [@thm-fib-mod16] 说，斐波那契数除以 $16$ 的余数以 $24$ 为周期重复。对一般的正整数 $m$，把斐波那契数列除以 $m$ 的余数的最小正周期记作 $\pi(m)$，称为皮萨诺周期。按第一章的计算，$\pi(16) = 24$。直接计算还可得到 $\pi(2) = 3$、$\pi(4) = 6$，$\pi(3) = 8$、$\pi(9) = 24$，$\pi(5) = 20$、$\pi(25) = 100$：在这些例子里，从素数 $p$ 换到 $p^2$，周期都变成原来的 $p$ 倍。这些只是有限的计算。

::: {.problem #prob-wall-sun-sun title="Wall–Sun–Sun 问题"}
是否存在素数 $p$，使

$$
\pi(p) = \pi(p^2) ?
$$

这个问题尚未解决，没有 Lean 证明；trureturing 在 `Problems/wall-sun-sun-golden-unit-lift.md` 中记录了它。
:::
