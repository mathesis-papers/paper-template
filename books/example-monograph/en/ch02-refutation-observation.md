# Chapter 2 Refutation and observability

## Refuting a conjecture

For a positive integer $n$, let $a(n)$ be the greatest integer $k$ with $(1 + 1/n)^k \le 2$. Greathouse conjectured for OEIS A175406 that $a(n) = \lfloor (n + 1/2)\log 2 \rfloor$.

::: {.theorem #thm-greathouse-refuted title="The floor formula is false" lean="D5/S0/Certificates/GreathouseLogTwoFloorRefutation.result"}
The conjectured formula does not hold for all $n \ge 1$: at $n = 1121626023352383$ it gives $777451915729368$, while the actual value is one less.
:::

::: {.problem #prob-greathouse-minimal title="The least counterexample"}
Is $n = 1121626023352383$ the least $n$ at which the formula fails? What characterizes the inputs where it fails? trureturing proves this counterexample only; it does not claim minimality.
:::

## What observations can recover

::: {.theorem #thm-target-recovery title="Target recovery criterion" lean="D5/S3/ConceptDynamics/Restoration/TargetRecoveryCriterion.target_recovery_criterion"}
Let the state space $X$ be nonempty, with a process readout $p: X \to P$ and a target $t: X \to T$. A recovery function $r$ with $t = r \circ p$ exists if and only if any two states with the same readout have the same target value; this in turn is equivalent to the target defect relation being empty.
:::

[@thm-target-recovery] asserts only that a recovery function exists; it gives no algorithm and no cost bound.
