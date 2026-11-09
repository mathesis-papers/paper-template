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

## Finite certificates {#sec-certificates}

::: {.theorem #thm-detlefs-refuted title="One integer refutes a characterization" lean="D5/S0/Certificates/DetlefsRoughResidueCharacterizationRefutation.result"}
(To be written.)
:::

::: proof
(To be written.)
:::

::: {.conjecture #conj-a008365-corrected title="The corrected characterization"}
(To be written.)
:::

::: {.theorem #thm-finite-counterexample title="Refuting is finding a counterexample" lean="D5/S0/Computability/FiniteCounterexampleCertificate.finite_readout_counterexample_certificate"}
(To be written.)
:::

::: {.theorem #thm-farkas title="Farkas certificates" lean="D5/S0/Certificates/RationalFarkas.infeasible_of_certificate"}
(To be written.)
:::

::: {.remark #rem-certificates title="Certificates are more than counterexamples"}
(To be written.)
:::

## What stays invisible {#sec-blind-spots}

::: {.theorem #thm-pigeonhole-fiber title="Fewer readings than objects" lean="D5/S0/Diagonal/PigeonholeFiber.finite_reading_has_fiber"}
(To be written.)
:::

::: {.theorem #thm-modulus-blind title="Residues cannot see the deficit" lean="D5/S1/Deficit/FixedModulusNoncongruence.deficit_not_determined_by_fixed_modulus"}
(To be written.)
:::

::: {.example #ex-mod-two title="A pair of witnesses modulo 2"}
(To be written.)
:::

## Slides

::: {.slides src="overview"}
A ten-slide overview: the theorems of both chapters, the open problem and every output.
:::
