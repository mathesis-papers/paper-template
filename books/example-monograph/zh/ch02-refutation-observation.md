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
