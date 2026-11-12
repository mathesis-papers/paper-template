# Chapter 2 Lucas numbers and the golden ratio

The golden ratio $\varphi = (1 + \sqrt5)/2 \approx 1.618$ satisfies $\varphi^2 = \varphi + 1$. In the first two sections of this chapter we do not approximate $\sqrt5$ at all. Instead we treat $\varphi$ as a symbol subject to $\varphi^2 = \varphi + 1$ and work with numbers of the form $a + b\varphi$, where $a$ and $b$ are integers. Every computation is then exact integer arithmetic, and this is also how Lean does it. In this number system the Fibonacci numbers appear as the coordinates of powers of $\varphi$, and the Lucas numbers are the "traces" of those powers. The third section returns to the real numbers and shows how the ratios of consecutive Fibonacci numbers approach $\varphi$; the last section presents an unsolved problem.

## Golden integers {#sec-golden-int}

Expanding $(a + b\varphi)(c + d\varphi)$ gives $ac + (ad + bc)\varphi + bd\varphi^2$; replacing $\varphi^2$ by $\varphi + 1$ gives the multiplication rule in the following definition.

::: {.definition #def-golden-int title="Golden integers" lean="D5/S0/Carrier/Ring.GoldenInt D5/S0/Carrier/Ring.phi"}
A golden integer is a pair of integers $(a, b)$, written $a + b\varphi$; the set of all golden integers is written $\mathbb{Z}[\varphi]$. Addition is coordinatewise, and multiplication is defined by

$$
(a + b\varphi)(c + d\varphi) = (ac + bd) + (ad + bc + bd)\varphi .
$$

Here $\varphi$ is the golden integer $0 + 1\varphi$ with coordinates $(0, 1)$; $0$ and $1$ are $(0, 0)$ and $(1, 0)$, and an integer $m$ corresponds to $(m, 0)$.
:::

In Lean, `GoldenInt` is a structure with two integer coordinates `a` and `b`, and multiplication is defined directly by the formula above. The same module also equips it with the structure of a commutative ring (associativity, distributivity and so on all hold), so we may calculate with golden integers as with ordinary numbers.

::: {.theorem #thm-phi-sq title="$\varphi^2 = \varphi + 1$" lean="D5/S0/Carrier/Ring.phi_sq"}
In $\mathbb{Z}[\varphi]$,

$$
\varphi^2 = \varphi + 1 .
$$
:::

::: proof
Take $a = c = 0$ and $b = d = 1$ in the multiplication rule:

$$
(0 + 1\varphi)(0 + 1\varphi) = (0 \cdot 0 + 1 \cdot 1) + (0 \cdot 1 + 1 \cdot 0 + 1 \cdot 1)\varphi = 1 + \varphi .
$$

Lean, too, compares the two sides coordinate by coordinate. The full proof is checked by the Lean kernel.
:::

This is a statement about golden integers, not about the real number $(1 + \sqrt5)/2$. The real number satisfies the same equation (expanding gives $\bigl((1 + \sqrt5)/2\bigr)^2 = (3 + \sqrt5)/2 = (1 + \sqrt5)/2 + 1$), but that is a different fact.

Multiplying by $\varphi$ has a simple effect: by the multiplication rule, $(a + b\varphi)\varphi = b + (a + b)\varphi$, so the coordinates $(a, b)$ become $(b, a + b)$. That is exactly one step of the Fibonacci recurrence. Hence $\varphi = 0 + 1\varphi$, $\varphi^2 = 1 + 1\varphi$, $\varphi^3 = 1 + 2\varphi$, $\varphi^4 = 2 + 3\varphi$, $\varphi^5 = 3 + 5\varphi$: the coordinates are always consecutive Fibonacci numbers.

::: {.theorem #thm-phi-pow title="Powers of $\varphi$ are Fibonacci pairs" lean="D5/S1/Scale/Fibonacci.golden_phi_pow_eq_fib_pair"}
For every natural number $n$, in $\mathbb{Z}[\varphi]$,

$$
\varphi^{n+1} = F_n + F_{n+1}\varphi ,
$$

that is, the two coordinates of $\varphi^{n+1}$ are $(F_n, F_{n+1})$.
:::

::: proof
Induction on $n$. For $n = 0$, $\varphi^1 = 0 + 1\varphi = F_0 + F_1\varphi$. If $\varphi^{n+1} = F_n + F_{n+1}\varphi$, multiplying by $\varphi$ gives

$$
\varphi^{n+2} = F_{n+1} + (F_n + F_{n+1})\varphi = F_{n+1} + F_{n+2}\varphi .
$$

The Lean proof is this induction. The full proof is checked by the Lean kernel.
:::

The theorem covers only exponents of at least $1$. That $\varphi^0 = 1 = 1 + 0\varphi$ is the convention for powers and is not part of the theorem. In Lean the theorem is called [`golden_phi_pow_eq_fib_pair`](lean:D5/S1/Scale/Fibonacci.golden_phi_pow_eq_fib_pair), and the proof of Cassini's identity in [Chapter 1](ch01-fibonacci.md) ([@thm-cassini]) is built on it.

## Lucas numbers {#sec-lucas}

Replacing $\varphi$ by the other root $1 - \varphi$ turns the golden integer $a + b\varphi$ into its conjugate $(a + b) - b\varphi$. Adding the two cancels the $\varphi$ coefficient and leaves the integer $2a + b$.

::: {.definition #def-lucas title="Lucas numbers" lean="D5/S1/Scale/Lucas.goldenLucas D5/S0/Carrier/Conj.trace"}
The trace of a golden integer $x = a + b\varphi$ is the integer

$$
\tr(x) = 2a + b .
$$

For every natural number $n$, the $n$-th Lucas number is

$$
L_n = \tr(\varphi^n) .
$$
:::

Thinking in real numbers, the trace substitutes $\varphi$ and the other root $\psi = (1 - \sqrt5)/2$ and adds the results: $(a + b\varphi) + (a + b\psi) = 2a + b$, because $\varphi + \psi = 1$. By definition, $L_0 = \tr(1) = 2$ and $L_1 = \tr(\varphi) = 1$. The table lists the first few values:

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

From $n = 1$ on, each $L_n$ in the table is the sum $F_{n-1} + F_{n+1}$ of the Fibonacci numbers with the neighbouring indices, for example $L_5 = 11 = 3 + 8 = F_4 + F_6$.

::: {.theorem #thm-lucas-fib title="Lucas and Fibonacci" lean="D5/S1/Scale/Lucas.golden_lucas_succ_eq_fib_add_fib"}
For every natural number $n$,

$$
L_{n+1} = F_n + F_{n+2} .
$$
:::

::: proof
By [@thm-phi-pow], $\varphi^{n+1} = F_n + F_{n+1}\varphi$, so

$$
L_{n+1} = 2F_n + F_{n+1} = F_n + (F_n + F_{n+1}) = F_n + F_{n+2} .
$$

The full proof is checked by the Lean kernel.
:::

It follows that the Lucas numbers obey the same recurrence as the Fibonacci numbers: $L_{n+3} = F_{n+2} + F_{n+4} = (F_n + F_{n+2}) + (F_{n+1} + F_{n+3}) = L_{n+1} + L_{n+2}$, and together with $L_2 = 3 = L_1 + L_0$ this gives $2, 1, 3, 4, 7, 11, 18, \dots$. This recurrence is the book's own consequence of [@thm-lucas-fib]; no further Lean declaration is cited for it.

Lucas numbers also let us double the index of a Fibonacci number.

::: {.theorem #thm-fib-double title="The doubling formula" lean="D5/S1/Scale/FibLucasDouble.golden_fib_two_mul_eq_fib_mul_lucas"}
For every natural number $n$, in the integers,

$$
F_{2n} = F_n L_n .
$$
:::

For example, $F_{10} = 55 = 5 \cdot 11 = F_5 L_5$ and $F_{12} = 144 = 8 \cdot 18 = F_6 L_6$.

::: proof
Write $\varphi^n = a + b\varphi$; then $b = F_n$: for $n \ge 1$ this is [@thm-phi-pow], and for $n = 0$ we have $\varphi^0 = 1 + 0\varphi$. By the multiplication rule, the $\varphi$ coordinate of $(a + b\varphi)^2$ is $ab + ba + b^2 = b(2a + b)$. But $(a + b\varphi)^2 = \varphi^{2n}$, whose $\varphi$ coordinate is $F_{2n}$, so $F_{2n} = b(2a + b) = F_n \tr(\varphi^n) = F_n L_n$. The full proof is checked by the Lean kernel.
:::

In particular, for $n \ge 1$, $F_n$ divides $F_{2n}$, and the quotient is exactly $L_n$. This agrees with [@thm-fib-dvd] in [Chapter 1](ch01-fibonacci.md): for $n \ge 3$, $n \mid 2n$ also gives $F_n \mid F_{2n}$, but that theorem does not tell us the quotient.

The last algebraic identity ties Lucas and Fibonacci numbers together in a single equation.

::: {.theorem #thm-lucas-discriminant title="The discriminant identity" lean="D5/S1/Scale/Lucas.golden_lucas_discriminant"}
For every natural number $n$, in the integers,

$$
L_n^2 - 5F_n^2 = 4(-1)^n .
$$
:::

A check of the first few values:

| $n$ | $L_n$ | $F_n$ | $L_n^2 - 5F_n^2$ |
| ---: | ---: | ---: | ---: |
| 0 | 2 | 0 | $4 - 0 = 4$ |
| 1 | 1 | 1 | $1 - 5 = -4$ |
| 2 | 3 | 1 | $9 - 5 = 4$ |
| 3 | 4 | 2 | $16 - 20 = -4$ |
| 4 | 7 | 3 | $49 - 45 = 4$ |
| 5 | 11 | 5 | $121 - 125 = -4$ |

In other words, every pair $(L_n, F_n)$ is an integer solution of $x^2 - 5y^2 = \pm 4$. The theorem says only that these pairs are solutions; it does not say that they are the only integer solutions of that equation.

::: proof
For $x = a + b\varphi$, the norm is $N(x) = a^2 + ab - b^2$ (the proof of [@thm-cassini] uses it too). Expanding gives

$$
\tr(x)^2 - 5b^2 = (2a + b)^2 - 5b^2 = 4(a^2 + ab - b^2) = 4N(x) .
$$

The norm turns products into products and $N(\varphi) = -1$, so $N(\varphi^n) = (-1)^n$. Apply the formula to $x = \varphi^n$ and substitute $\tr(\varphi^n) = L_n$ and $b = F_n$. The full proof is checked by the Lean kernel.
:::

## Ratios and the golden ratio {#sec-ratio}

From here on, $\varphi$ is again the real golden ratio $(1 + \sqrt5)/2 = 1.6180339\ldots$ (Mathlib's `Real.goldenRatio`). The ratios of consecutive Fibonacci numbers $F_{n+1}/F_n$ are $1, 2, 1.5, 1.667, 1.6, 1.625, 1.615, \dots$: they swing from one side of $\varphi$ to the other, getting closer each time. The next theorem gives an exact formula for the error.

::: {.theorem #thm-ratio-error title="The exact value of $F_n \varphi - F_{n+1}$" lean="D5/S1/Scale/FibonacciErrorRatio.fibonacci_golden_residual"}
Let $\varphi = (1 + \sqrt5)/2$. For every natural number $n$, in the real numbers,

$$
F_n \varphi - F_{n+1} = -\left(-\frac{1}{\varphi}\right)^{n} .
$$
:::

For example, for $n = 3$ the left-hand side is $2\varphi - 3 \approx 0.23607$ and the right-hand side is $1/\varphi^3 \approx 0.23607$.

::: proof
The idea: $\psi = 1 - \varphi = -1/\varphi$ is the other real root of $x^2 = x + 1$. Repeating the induction of [@thm-phi-pow] for $\psi$ gives $\psi^n = F_{n-1} + F_n \psi$ for $n \ge 1$. Therefore

$$
F_n \varphi - F_{n+1} = F_n(\varphi - 1) - F_{n-1} = -(F_{n-1} + F_n \psi) = -\psi^n ,
$$

and for $n = 0$ both sides equal $-1$. The Lean proof first rewrites $-1/\varphi$ as the contracting eigenvalue of the Fibonacci substitution matrix in trureturing's `FibonacciEigen` module (our $\psi$), then cites the last part of a theorem in that module; that part comes down to Mathlib's identity $F_{n+1} - \varphi F_n = \psi^n$ (`Real.fib_succ_sub_goldenRatio_mul_fib`), the same equation as derived above. The full proof is checked by the Lean kernel.
:::

The theorem is an exact equation for each $n$; by itself it is not a statement about limits. But it shows at once how the ratios behave: for $n \ge 1$, dividing both sides by $F_n$ gives

$$
\frac{F_{n+1}}{F_n} - \varphi = \frac{(-1/\varphi)^n}{F_n} .
$$

The absolute value of the right-hand side is $1/(\varphi^n F_n)$, which shrinks quickly as $n$ grows, and its sign alternates: the ratio lies above $\varphi$ for even $n$ and below it for odd $n$. "The ratios tend to $\varphi$" is the book's conclusion from this, not part of the cited Lean declaration. The table is a numerical computation, rounded to six decimal places:

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

## An open problem {#sec-open}

[@thm-fib-mod16] in [Chapter 1](ch01-fibonacci.md#sec-divisibility) says that the remainders of the Fibonacci numbers on division by $16$ repeat with period $24$. For a general positive integer $m$, the least positive period of the Fibonacci remainders on division by $m$ is written $\pi(m)$ and called the Pisano period. By the computation in Chapter 1, $\pi(16) = 24$. Direct computation also gives $\pi(2) = 3$ and $\pi(4) = 6$, $\pi(3) = 8$ and $\pi(9) = 24$, $\pi(5) = 20$ and $\pi(25) = 100$: in these examples, going from a prime $p$ to $p^2$ multiplies the period by $p$. These are only finite computations.

::: {.problem #prob-wall-sun-sun title="The Wall–Sun–Sun question"}
Is there a prime $p$ with

$$
\pi(p) = \pi(p^2) ?
$$

The question is unsolved and has no Lean proof; trureturing records it in `Problems/wall-sun-sun-golden-unit-lift.md`.
:::
