# 第二章 反驳与可观测性

## 反驳一个猜想

对正整数 $n$，令 $a(n)$ 为满足 $(1 + 1/n)^k \le 2$ 的最大整数 $k$。Greathouse 为 OEIS A175406 猜想 $a(n) = \lfloor (n + 1/2)\log 2 \rfloor$。

::: {.theorem #thm-greathouse-refuted title="该取整公式不成立" lean="D5/S0/Certificates/GreathouseLogTwoFloorRefutation.result"}
猜想的公式并非对所有 $n \ge 1$ 成立：在 $n = 1121626023352383$ 处，公式给出 $777451915729368$，而实际值小一。
:::

::: {.problem #prob-greathouse-minimal title="最小反例"}
$n = 1121626023352383$ 是否是使公式失效的最小 $n$？使公式失效的输入有怎样的刻画？trureturing 只证明了这个反例，不主张它最小。
:::

## 观测能恢复什么

::: {.theorem #thm-target-recovery title="目标恢复判据" lean="D5/S3/ConceptDynamics/Restoration/TargetRecoveryCriterion.target_recovery_criterion"}
设状态空间 $X$ 非空，过程读数 $p: X \to P$，目标 $t: X \to T$。存在恢复函数 $r$ 使 $t = r \circ p$，当且仅当任意两个读数相同的状态有相同的目标值；这又等价于目标缺陷关系为空。
:::

[@thm-target-recovery] 只断言恢复函数存在，不提供算法，也不给出代价界。

## 有限证书 {#sec-certificates}

::: {.theorem #thm-detlefs-refuted title="一个整数推翻一条刻画" lean="D5/S0/Certificates/DetlefsRoughResidueCharacterizationRefutation.result"}
（待写）
:::

::: proof
（待写）
:::

::: {.conjecture #conj-a008365-corrected title="修正后的刻画"}
（待写）
:::

::: {.theorem #thm-finite-counterexample title="否定即找到反例" lean="D5/S0/Computability/FiniteCounterexampleCertificate.finite_readout_counterexample_certificate"}
（待写）
:::

::: {.theorem #thm-farkas title="Farkas 证书" lean="D5/S0/Certificates/RationalFarkas.infeasible_of_certificate"}
（待写）
:::

::: {.remark #rem-certificates title="证书不只是反例"}
（待写）
:::

## 看不见的部分 {#sec-blind-spots}

::: {.theorem #thm-pigeonhole-fiber title="读数少于对象" lean="D5/S0/Diagonal/PigeonholeFiber.finite_reading_has_fiber"}
（待写）
:::

::: {.theorem #thm-modulus-blind title="余数看不见亏量" lean="D5/S1/Deficit/FixedModulusNoncongruence.deficit_not_determined_by_fixed_modulus"}
（待写）
:::

::: {.example #ex-mod-two title="模 2 的一对反例"}
（待写）
:::

## 演示文稿

::: {.slides src="overview"}
十页概览：两章的定理、开放问题与全部输出。
:::
