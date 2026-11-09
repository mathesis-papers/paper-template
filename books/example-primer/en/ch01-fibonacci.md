# Chapter 1 Fibonacci identities

The Fibonacci numbers start from $0$ and $1$, and every later term is the sum of the two before it. This one simple rule produces a surprising number of tidy identities. This chapter looks in turn at how fast the numbers grow, at Cassini's identity and its generalization, at divisibility, and at the period of the remainders modulo $16$. Every theorem cites a declaration in trureturing; the proof blocks only explain the idea, and the full proofs are checked by the Lean kernel.

## Definition and growth {#sec-fib-growth}

::: {.definition #def-fib title="Fibonacci numbers"}
The Fibonacci numbers $F_0, F_1, F_2, \dots$ are the natural numbers determined by

$$
F_0 = 0, \qquad F_1 = 1, \qquad F_{n+2} = F_{n+1} + F_n \quad (n = 0, 1, 2, \dots).
$$

The $F_n$ of this book is `Nat.fib n` from Mathlib, Lean's mathematics library.
:::

Throughout the book we use the convention $F_0 = 0$, $F_1 = 1$.[^mathlib] Here are the first few terms, with $2^n$ in the third row for comparison:

| $n$ | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| $F_n$ | 0 | 1 | 1 | 2 | 3 | 5 | 8 | 13 | 21 | 34 | 55 | 89 | 144 |
| $2^n$ | 1 | 2 | 4 | 8 | 16 | 32 | 64 | 128 | 256 | 512 | 1024 | 2048 | 4096 |

Each term is the sum of the previous two, and the earlier of those is never larger than the later one, so $F_{n+2} \le 2F_{n+1}$: each step at most doubles the value. The first theorem makes this intuition precise.

::: {.theorem #thm-fib-lt-pow title="Slower than $2^n$" lean="D5/S3/Arith/Robin/FibonacciRankEulerTail.fibonacci_lt_two_pow"}
For every natural number $n$,

$$
F_n < 2^n .
$$
:::

::: proof
Use two-step induction. For $n = 0$ we have $0 < 1$, and for $n = 1$ we have $1 < 2$. If $F_n < 2^n$ and $F_{n+1} < 2^{n+1}$, then

$$
F_{n+2} = F_{n+1} + F_n < 2^{n+1} + 2^n \le 2^{n+1} + 2^{n+1} = 2^{n+2} .
$$

The Lean proof is exactly this two-step induction (Mathlib's `Nat.twoStepInduction`). The full proof is checked by the Lean kernel.
:::

The bound is crude: $F_{20} = 6765$, while $2^{20} = 1048576$. In [Chapter 2](ch02-lucas.md) we will see that the ratio of consecutive terms approaches the golden ratio $\varphi \approx 1.618$, so the Fibonacci numbers grow much more slowly than doubling.

## Cassini's and Vajda's identities {#sec-cassini}

Take a Fibonacci number and compare its square with the product of its two neighbours: the two always differ by exactly $1$.

::: {.theorem #thm-cassini title="Cassini's identity" lean="D5/S1/Scale/Fibonacci.fib_cassini_from_golden_norm"}
For every natural number $n$, in the integers,

$$
F_n F_{n+2} - F_{n+1}^2 = (-1)^{n+1} .
$$
:::

"In the integers" means that the three Fibonacci numbers are read as integers before subtracting, since the difference can be negative. The table checks the first few cases:

| $n$ | $F_n F_{n+2}$ | $F_{n+1}^2$ | difference |
| ---: | ---: | ---: | ---: |
| 0 | $0 \cdot 1 = 0$ | 1 | $-1$ |
| 1 | $1 \cdot 2 = 2$ | 1 | $+1$ |
| 2 | $1 \cdot 3 = 3$ | 4 | $-1$ |
| 3 | $2 \cdot 5 = 10$ | 9 | $+1$ |
| 4 | $3 \cdot 8 = 24$ | 25 | $-1$ |
| 5 | $5 \cdot 13 = 65$ | 64 | $+1$ |
| 6 | $8 \cdot 21 = 168$ | 169 | $-1$ |

::: proof
The Lean proof does not run an induction on Cassini's identity itself. Instead it borrows the golden integers $a + b\varphi$ of [Chapter 2](ch02-lucas.md). A golden integer has a "norm" $N(a + b\varphi) = a^2 + ab - b^2$, which turns products into products, and $N(\varphi) = -1$, so $N(\varphi^{n+1}) = (-1)^{n+1}$. On the other hand, [@thm-phi-pow] gives $\varphi^{n+1} = F_n + F_{n+1}\varphi$, hence

$$
N(\varphi^{n+1}) = F_n^2 + F_n F_{n+1} - F_{n+1}^2 = F_n (F_n + F_{n+1}) - F_{n+1}^2 = F_n F_{n+2} - F_{n+1}^2 .
$$

Comparing the two gives the identity. The full proof is checked by the Lean kernel.
:::

In Lean this declaration is called [`fib_cassini_from_golden_norm`](lean:D5/S1/Scale/Fibonacci.fib_cassini_from_golden_norm): the name says exactly "Cassini from the golden norm".

::: {.example #ex-64-65 title="$64 = 65$?"}
Cut an $8 \times 8$ square (area $64$) into four pieces and rearrange them into what looks like a perfect $5 \times 13$ rectangle (area $65$). The pieces are:

| piece | count | size | area each |
| --- | ---: | --- | ---: |
| right triangle | 2 | legs $3$ and $8$ | $12$ |
| right trapezoid | 2 | parallel sides $3$ and $5$, height $5$ | $20$ |
| total | 4 | | $2 \cdot 12 + 2 \cdot 20 = 64$ |

Where does the extra $1$ come from? The numbers $3, 5, 8, 13$ are $F_4, F_5, F_6, F_7$: the square has side $F_6$, and the rectangle has sides $F_5$ and $F_7$. With $n = 5$, [@thm-cassini] gives

$$
F_5 F_7 - F_6^2 = 5 \cdot 13 - 8^2 = (-1)^6 = 1 .
$$

So the pieces do not really fit. The hypotenuse of a triangle has slope $3/8 = 0.375$ and the slanted side of a trapezoid has slope $2/5 = 0.4$; they differ by only $0.025$, too little for the eye to notice. The "diagonal" of the rectangle is really two slightly different bent lines, and between them lies a long, thin parallelogram-shaped gap of area exactly $65 - 64 = 1$.

With $3, 5, 8$ instead ($n = 4$), rearranging a $5 \times 5$ square into a $3 \times 8$ rectangle gives $F_4 F_6 - F_5^2 = 24 - 25 = -1$: this time the rectangle is $1$ smaller than the square, and the pieces overlap along the diagonal. With larger Fibonacci numbers, for instance a $21 \times 21$ square rearranged into a $13 \times 34$ rectangle, the areas still differ by only $1$, but the gap becomes even harder to see.
:::

Cassini's identity compares immediate neighbours. What happens if we move the two neighbours farther apart?

::: {.theorem #thm-vajda title="Vajda's identity" lean="D5/S1/Recurrence/FibVajda.fib_vajda"}
For all natural numbers $n, i, j$, in the integers,

$$
F_{n+i} F_{n+j} - F_n F_{n+i+j} = (-1)^n F_i F_j .
$$
:::

For example, with $n = 3$, $i = 2$, $j = 4$ the left-hand side is $F_5 F_7 - F_3 F_9 = 5 \cdot 13 - 2 \cdot 34 = -3$, and the right-hand side is $(-1)^3 F_2 F_4 = -1 \cdot 1 \cdot 3 = -3$. All three indices are natural numbers.

::: proof
First, two special cases. With $i = j = 1$ we get $F_{n+1}^2 - F_n F_{n+2} = (-1)^n$; multiplying both sides by $-1$ gives [@thm-cassini]. With $i = j = r$ we get Catalan's identity

$$
F_{n+r}^2 - F_n F_{n+2r} = (-1)^n F_r^2 ,
$$

for example $F_5^2 - F_2 F_8 = 25 - 21 = 4 = F_3^2$ for $n = 2$, $r = 3$. These two special cases are derived here in the book; the cited Lean module does not state them as separate corollaries of Vajda's identity, and [@thm-cassini] cites a different declaration.

The general Lean proof: for $n = 0$ we have $F_0 = 0$ and both sides equal $F_i F_j$. For $n = m + 1$, the addition formula $F_{s+t+1} = F_s F_t + F_{s+1} F_{t+1}$ (Mathlib's `Nat.fib_add`) expands every term; after simplification the left-hand side equals $-(F_{m+1}^2 - F_m F_{m+1} - F_m^2) F_i F_j$, and the Cassini-type expression in parentheses equals $(-1)^m$. The full proof is checked by the Lean kernel.
:::

## Divisibility and periods {#sec-divisibility}

$F_4 = 3$ divides $F_8 = 21$ and $F_{12} = 144$; $F_5 = 5$ divides $F_{10} = 55$ and $F_{15} = 610$. It looks as if divisibility among Fibonacci numbers follows divisibility among their indices.

::: {.theorem #thm-fib-dvd title="Divisibility and indices" lean="D5/S1/Recurrence/GoldenFibDivisibility.fib_dvd_iff"}
Let $a, b$ be natural numbers with $a \ge 3$. Then

$$
F_a \mid F_b \iff a \mid b .
$$
:::

For example, $4 \mid 12$, and accordingly $F_{12} = 144 = 3 \cdot 48$; but $4 \nmid 10$, and accordingly $F_{10} = 55 = 3 \cdot 18 + 1$ is not divisible by $F_4 = 3$.

The hypothesis $a \ge 3$ cannot be weakened to $a \ge 2$. For $a = 2$, $F_2 = 1$ divides every $F_b$, but $2$ does not divide every $b$: $F_2 = 1$ divides $F_3 = 2$, while $2 \nmid 3$.

::: proof
"$\Leftarrow$" is Mathlib's `Nat.fib_dvd`: if $a \mid b$ then $F_a \mid F_b$. "$\Rightarrow$" uses Mathlib's `Nat.fib_gcd`, which says $\gcd(F_a, F_b) = F_{\gcd(a, b)}$. If $F_a \mid F_b$, then $\gcd(F_a, F_b) = F_a$, so $F_{\gcd(a,b)} = F_a$. If $\gcd(a, b) < a$, we would have $F_{\gcd(a,b)} \le F_{a-1} < F_a$, a contradiction; hence $\gcd(a, b) = a$, that is, $a \mid b$. The strict inequality $F_{a-1} < F_a$ needs $a - 1 \ge 2$, and this is exactly where the hypothesis $a \ge 3$ is used: $F_1 = F_2$. The full proof is checked by the Lean kernel.
:::

Finally, remainders. For a natural number $x$ and a positive integer $m$, write $x \bmod m$ for the remainder of $x$ on division by $m$. Computing $F_n \bmod 16$ term by term for $n = 0, 1, \dots, 23$ (every entry of the table is a remainder modulo $16$):

| $n$ | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| $F_n$ | 0 | 1 | 1 | 2 | 3 | 5 | 8 | 13 | 5 | 2 | 7 | 9 |
| $F_{n+12}$ | 0 | 9 | 9 | 2 | 11 | 13 | 8 | 5 | 13 | 2 | 15 | 1 |

The last row holds the remainders for $n = 12$ to $23$. Continuing, $F_{24} = 46368$ and $F_{25} = 75025$ leave remainders $0$ and $1$, the same as $F_0$ and $F_1$. Since each remainder is determined by the two before it, the same $24$ numbers repeat from then on.

::: {.theorem #thm-fib-mod16 title="Remainders modulo $16$ repeat with period $24$" lean="D5/S1/Recurrence/FibonacciPowerSumMod16Obstruction.fib_mod_sixteen_period"}
Both of the following hold:

1. for every natural number $n$, $F_{n+24} \bmod 16 = F_n \bmod 16$;
2. for every natural number $n$, $F_n \bmod 16 = F_{n \bmod 24} \bmod 16$.
:::

The second part means that to find the remainder of any $F_n$ on division by $16$, you only need the remainder of $n$ on division by $24$. For example, $100 = 4 \cdot 24 + 4$, so $F_{100} \bmod 16 = F_4 \bmod 16 = 3$; computing directly, $F_{100} = 354224848179261915075$, and its remainder on division by $16$ is indeed $3$.

::: proof
Lean first checks two initial congruences by kernel computation: $F_{24} \bmod 16 = 0 = F_0$ and $F_{25} \bmod 16 = 1 = F_1$. Then comes a two-step induction: if $F_{n+24}$ is congruent to $F_n$ and $F_{n+25}$ to $F_{n+1}$ modulo $16$, adding the two and using the recurrence shows that $F_{n+26}$ is congruent to $F_{n+2}$ modulo $16$. For the second part, write $n = 24q + r$ with $0 \le r < 24$ and apply the first part $q$ times. The full proof is checked by the Lean kernel.
:::

The theorem only says that $24$ is a period, not that it is the smallest one. The table lets us check that no smaller period exists: a period $p$ must have $F_p \bmod 16 = 0$ and $F_{p+1} \bmod 16 = 1$, and among $0 < p < 24$ only $F_{12} \bmod 16$ is $0$, while the next term leaves $9$, not $1$. This is a finite computation and not part of the Lean statement. About least periods there is a question that is still unsolved; see [@prob-wall-sun-sun] at the end of [Chapter 2](ch02-lucas.md).

[^mathlib]: The Fibonacci numbers are Mathlib's `Nat.fib`, which is not a declaration frozen in trureturing, so [@def-fib] carries no Lean citation; the Lean statements of the theorems in this book use `Nat.fib` directly. Some books start numbering with $F_0 = F_1 = 1$; their $n$-th term is $F_{n+1}$ in this book.
