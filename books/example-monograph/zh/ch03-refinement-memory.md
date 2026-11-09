# 第三章 细化、记忆与信息

[第二章](ch02-refutation-observation.md) 的 [@thm-target-recovery] 回答了一个是非问题：目标 $t$ 能否从读数 $p$ 恢复。判据是缺陷关系，即读数相同而目标不同的状态对 $(x, y)$ 构成的集合：状态空间非空时，它为空，恢复函数就存在；它非空，任何函数都恢复不了。

这个问题本身是两个映射之间的比较。“存在 $r$ 使 $t = r \circ p$”说的是 $t$ 可以由 $p$ 算出，也就是 $p$ 至少和 $t$ 一样细。本章把这种比较看作读数之间的一个序（[@def-refines]），从三个方向考察它。

细化与代价
: 读数越细，有缺陷的目标越少，读数取到的值越多（[@thm-refinement-tradeoff]）；恢复失败时，能保留的最大状态子集有精确的大小（[@thm-max-compatible]）。

记忆
: 读数随时间改变。知道一个事件，就是当时读数相同的世界中，它的取值也相同；遗忘，就是事件仍在账上，这种性质却失去了（见[记忆](#sec-memory)一节）。

信息
: 给状态加上概率分布，细化的序就变成熵的不等式（见[信息](#sec-information)一节）；但一个熵值代替不了缺陷关系（[@ex-equal-entropy]）。

本章的读数都是映射 $q: X \to C$，其中 $X$ 是状态空间，$C$ 是读数空间；trureturing 把这样的映射称为概念（`Concept X C`，就是函数类型 $X \to C$）。目标也是这样的映射，所以目标与读数可以放进同一个序中比较。

## 细化 {#sec-refinement}

::: {.definition #def-refines title="细化" lean="D5/S3/ConceptDynamics/ConceptJoinUniversal.Refines"}
设 $q_C: X \to C$ 与 $q_D: X \to D$ 是同一状态空间 $X$ 上的两个读数。若存在映射 $f: D \to C$ 使 $q_C = f \circ q_D$，就称 $q_D$ 细化 $q_C$，记作 $\mathrm{Refines}(q_C, q_D)$。
:::

注意参数的顺序：较粗的读数在前。$\mathrm{Refines}(q_C, q_D)$ 说的是 $q_C$ 可以由 $q_D$ 算出，$q_C = f \circ q_D$ 是函数的相等。[@thm-target-recovery] 的第一个条件正是 $\mathrm{Refines}(t, p)$：目标能恢复，就是读数细化了目标。取 $f$ 为恒等映射，可知每个读数细化它自己；把两个分解映射复合，可知细化可以传递。这两点直接来自定义，Lean 名为 [`Refines`](lean:D5/S3/ConceptDynamics/ConceptJoinUniversal.Refines)。

细化也可以用纤维来说。若 $q_C = f \circ q_D$，则 $q_D(x) = q_D(y)$ 蕴含 $q_C(x) = f(q_D(x)) = f(q_D(y)) = q_C(y)$：$q_D$ 的每个纤维都落在 $q_C$ 的某个纤维中。$X$ 非空时反过来也成立，这是 [@thm-target-recovery] 取 $p = q_D$、$t = q_C$ 时的第一个等价。

两个读数总有一个公共细化：把两个读数值并排记下。

::: {.theorem #thm-join-universal title="联合读数的泛性质" lean="D5/S3/ConceptDynamics/ConceptJoinUniversal.concept_join_universal"}
对读数 $q_C: X \to C$ 与 $q_D: X \to D$，令联合读数 $\langle q_C, q_D \rangle: X \to C \times D$ 为 $x \mapsto (q_C(x), q_D(x))$。则

1. $\mathrm{Refines}(q_C, \langle q_C, q_D \rangle)$；
2. $\mathrm{Refines}(q_D, \langle q_C, q_D \rangle)$；
3. 对任意读数 $q_E: X \to E$，若 $\mathrm{Refines}(q_C, q_E)$ 且 $\mathrm{Refines}(q_D, q_E)$，则 $\mathrm{Refines}(\langle q_C, q_D \rangle, q_E)$。
:::

::: proof
前两条由两个坐标投影给出：$q_C = \pi_1 \circ \langle q_C, q_D \rangle$，$q_D = \pi_2 \circ \langle q_C, q_D \rangle$。第三条：若 $q_C = f \circ q_E$、$q_D = g \circ q_E$，令 $h(e) = (f(e), g(e))$，则 $\langle q_C, q_D \rangle = h \circ q_E$。完整证明由 Lean 内核检查。
:::

前两条说联合读数是 $q_C$ 与 $q_D$ 的公共细化，第三条说每个公共细化都细化它：在细化的序中，它是最粗的公共细化，这就是 Lean 名字里 join 的含义（联合读数在 Lean 中是 `conceptJoin`）。按 [@thm-target-recovery] 来读：两个目标都能从 $q_E$ 恢复时，由它们组成的对也能从 $q_E$ 恢复，恢复映射就是两个恢复映射配成的对。定理只谈两个读数，不谈任意多个；它也不断言恢复映射唯一。

读数越细，能恢复的目标越多；但细的读数要区分更多的状态。下面的定义给这两方面各一个量。

::: {.definition #def-target-risk title="目标风险与细化代价" lean="D5/S3/ConceptDynamics/TargetRisk/RefinementRiskCostTradeoff.targetRisk D5/S3/ConceptDynamics/TargetRisk/RefinementRiskCostTradeoff.refinementCost"}
设 $q: X \to C$ 是读数。对目标 $t: X \to T$，称
$$
\mathrm{Def}(q, t) = \{(x, y) \in X \times X : q(x) = q(y),\ t(x) \ne t(y)\}
$$
为 $q$ 对 $t$ 的缺陷关系。对一族目标 $\mathcal{T}$（其中都是 $X \to T$ 的映射），$q$ 的目标风险是缺陷关系非空的那些目标：
$$
\mathrm{Risk}(q, \mathcal{T}) = \{t \in \mathcal{T} : \mathrm{Def}(q, t) \ne \varnothing\}.
$$
$q$ 的细化代价是它实际取到的值的个数：
$$
\mathrm{Cost}(q) = |q(X)| \in \mathbb{N} \cup \{\infty\},
$$
$q(X)$ 是无限集时取 $\infty$。
:::

两者在 Lean 中分别是 [`targetRisk`](lean:D5/S3/ConceptDynamics/TargetRisk/RefinementRiskCostTradeoff.targetRisk) 与 [`refinementCost`](lean:D5/S3/ConceptDynamics/TargetRisk/RefinementRiskCostTradeoff.refinementCost)；缺陷关系是同一模块中的 `defectRelation`，与 [@thm-target-recovery] 中的缺陷关系相同。代价数的是取到的值 $q(X)$，不是读数空间 $C$：$C$ 可以很大，代价只看 $q$ 实际用到多少个值[^encard]。$X$ 非空时，由 [@thm-target-recovery]，目标属于 $\mathrm{Risk}(q, \mathcal{T})$ 恰好意味着它不能从 $q$ 恢复；定义本身只看缺陷关系是否非空，不需要这个假设。

[^encard]: Lean 中 $\mathrm{Cost}(q)$ 是 `(Set.range q).encard`，取值于扩充自然数 $\mathbb{N}_\infty = \mathbb{N} \cup \{\infty\}$：有限集取元素个数，无限集一律取 $\infty$，不区分无穷基数的大小；$\infty$ 大于每个自然数。

::: {.theorem #thm-refinement-tradeoff title="细化不增风险、不减代价" lean="D5/S3/ConceptDynamics/TargetRisk/RefinementRiskCostTradeoff.refinement_reduces_target_risk_and_raises_cost"}
设读数 $q_C: X \to C$、$q_D: X \to D$ 满足 $\mathrm{Refines}(q_C, q_D)$，$\mathcal{T}$ 是任一目标族（其中都是 $X \to T$ 的映射）。则
$$
\mathrm{Risk}(q_D, \mathcal{T}) \subseteq \mathrm{Risk}(q_C, \mathcal{T}), \qquad \mathrm{Cost}(q_C) \le \mathrm{Cost}(q_D),
$$
后一个不等式在 $\mathbb{N} \cup \{\infty\}$ 中。
:::

::: proof
设 $q_C = f \circ q_D$。若 $(x, y)$ 是 $q_D$ 对目标 $t$ 的缺陷对，即 $q_D(x) = q_D(y)$ 而 $t(x) \ne t(y)$，则 $q_C(x) = f(q_D(x)) = f(q_D(y)) = q_C(y)$，同一对也是 $q_C$ 对 $t$ 的缺陷对；所以在 $q_D$ 下有风险的目标，在 $q_C$ 下也有风险。代价：$q_C(X) = f(q_D(X))$，而集合在映射下的像不会比它本身大。完整证明由 Lean 内核检查。
:::

两个方向相反：细的读数风险少、代价高，粗的读数省代价、却让更多目标有风险。定理只给出这两个单调性：包含与不等式都可能取等号，它也不给出风险与代价之间的任何最优折中。方向反过来，两者一般都不成立。记 $\mathbb{B} = \{0, 1\}$（Lean 的 `Bool`，$0$ 即 false，$1$ 即 true）。trureturing 在同一模块中用三个 Lean `example` 检查过：在 $X = \mathbb{B}$ 上，常值读数被恒等读数细化；对恒等目标，常值读数有风险（缺陷对 $(0, 1)$），恒等读数没有；两者的代价分别是 $1$ 与 $2$。

目标不能恢复时，还可以问：在多大的状态子集上它能恢复？称子集 $A \subseteq X$ 对读数 $q$ 与目标 $t$ 相容，如果 $A$ 中任意两个读数相同的状态目标值也相同。$A$ 非空时，对状态空间 $A$ 用 [@thm-target-recovery]，相容就是 $t$ 在 $A$ 上能由 $q$ 恢复。

::: {.theorem #thm-max-compatible title="能挽救多少" lean="D5/S3/ConceptDynamics/TargetRisk/MaximumFactorCompatibleSubdomain.maximum_factor_compatible_subdomain"}
设 $X$ 是有限集，$q: X \to B$ 是读数，$t: X \to Y$ 是目标（$B$、$Y$ 不必有限）。令
$$
N = \sum_{b \in q(X)} \ \max_{r \in X,\ q(r) = b} \ \bigl|\{x \in X : q(x) = b,\ t(x) = t(r)\}\bigr|.
$$
则

1. 每个相容的子集 $A \subseteq X$（即对任意 $x, y \in A$，$q(x) = q(y)$ 蕴含 $t(x) = t(y)$）都满足 $|A| \le N$；
2. 存在相容的子集 $A \subseteq X$，使 $|A| = N$。
:::

对读数取到的每个值 $b$，纤维 $q^{-1}(b)$ 按目标值分成若干块；集合 $\{x \in X : q(x) = b,\ t(x) = t(r)\}$ 是代表元 $r$ 所在的那一块，对 $r$ 取最大，就是纤维中最大块的大小。所以 $N$ 是各纤维最大块的大小之和。

::: proof
上界：相容的 $A$ 在每个纤维 $q^{-1}(b)$ 上只取一个目标值，所以 $A \cap q^{-1}(b)$ 落在纤维的某一块中，大小不超过最大块；按纤维求和即得 $|A| \le N$。可达：在每个纤维中选一个最大块，它们的并是相容的，大小恰为 $N$。Lean 证明用选择为每个纤维挑出一个最大块的代表元，所以只给出这样的子集存在，不说它唯一，也不说多个最大块之间怎样选。完整证明由 Lean 内核检查。
:::

由第 2 条，$N \le |X|$。$X$ 非空时，$t$ 能从 $q$ 恢复，当且仅当 $X$ 本身相容，当且仅当 $N = |X|$：前者由第 1 条推出 $|X| \le N$；后者由第 2 条给出一个有 $|X|$ 个元素的相容子集，它只能是 $X$。一般地，要让剩下的状态相容，至少要去掉 $|X| - N$ 个状态（第 1 条），而去掉这么多也就够了（第 2 条）。定理只涉及计数：没有概率权重，也不谈子集之外的状态上会错多少。

::: {.example #ex-partial-recovery title="部分恢复"}
[@ex-mod-two] 中，$(1, 2)$ 与 $(1, 4)$ 模 $2$ 同余而亏量不同，所以模 $2$ 的余数不能恢复亏量。能挽救多少？固定 $v_1 = 1$，取状态空间 $X = \{0, 1, \dots, 7\}$，读数 $q(v) = v \bmod 2$，目标 $t(v) = c(1, v)$，目标值取自 [@ex-small-deficits] 中 $v_1 = 1$ 的一行。

| 状态 $v$ | 读数 $q(v) = v \bmod 2$ | 目标 $t(v) = c(1, v)$ |
| :---: | :---: | :---: |
| 0 | 0 | 0 |
| 1 | 1 | 1 |
| 2 | 0 | 0 |
| 3 | 1 | 0 |
| 4 | 0 | 1 |
| 5 | 1 | 0 |
| 6 | 0 | 1 |
| 7 | 1 | 0 |

偶数纤维 $q^{-1}(0) = \{0, 2, 4, 6\}$ 上的目标值是 $0, 0, 1, 1$，分成两块 $\{0, 2\}$ 与 $\{4, 6\}$，最大块的大小是 $2$；奇数纤维 $q^{-1}(1) = \{1, 3, 5, 7\}$ 上的目标值是 $1, 0, 0, 0$，分成 $\{1\}$ 与 $\{3, 5, 7\}$，最大块的大小是 $3$。由 [@thm-max-compatible]，$N = 2 + 3 = 5$：至少要去掉 $8 - 5 = 3$ 个状态。

在每个纤维中选一个最大块，就得到大小为 $5$ 的相容子集。偶数纤维有两个一样大的块，所以有两种选法：$\{0, 2, 3, 5, 7\}$，在其上 $t$ 恒为 $0$；$\{3, 4, 5, 6, 7\}$，在其上 $t(v) = 1 - q(v)$。[@ex-mod-two] 的缺陷对是状态 $2$ 与 $4$，两个子集各保留其中一个。我们用 Python 穷举了 $X$ 的全部 $2^8 = 256$ 个子集：相容子集最大有 $5$ 个元素，达到 $5$ 的恰是这两个。这是对这个例子的计算，不是定理；定理不断言最优子集唯一，这里就有两个。
:::

## 记忆 {#sec-memory}

到这里读数都是固定的。观察者的读数会随时间改变：记录被压缩，细节被丢弃。trureturing 用同样的纤维语言描述知道与遗忘。本节中 $t$ 表示时刻。

::: {.definition #def-knows title="知道与遗忘" lean="D5/S3/ObserverMemory/TwoTimeKnowledge.Knows D5/S3/ObserverMemory/TwoTimeKnowledge.Forgot"}
设时刻构成预序集 $\mathrm{Time}$，$W$ 是世界的集合。观察者在时刻 $t$ 的读数是 $r_t: W \to V$，事件 $e$ 的取值是 $v_e: W \to \mathrm{Val}$，账本 $L(t)$ 是时刻 $t$ 记录在案的事件的集合。

- 在时刻 $t$ 知道事件 $e$，记作 $\mathrm{Knows}(e, t)$，指 $v_e$ 在 $r_t$ 的每个纤维上取常值：对任意 $x, y \in W$，$r_t(x) = r_t(y)$ 蕴含 $v_e(x) = v_e(y)$。
- 在时刻 $t_0$ 与 $t_1$ 之间遗忘事件 $e$，记作 $\mathrm{Forgot}(e, t_0, t_1)$，指以下四条同时成立：$t_0 < t_1$；对每个满足 $t_0 \le t \le t_1$ 的时刻 $t$，$e \in L(t)$；$\mathrm{Knows}(e, t_0)$；$\mathrm{Knows}(e, t_1)$ 不成立。
:::

两者在 Lean 中是 [`Knows`](lean:D5/S3/ObserverMemory/TwoTimeKnowledge.Knows) 与 [`Forgot`](lean:D5/S3/ObserverMemory/TwoTimeKnowledge.Forgot)；第二条“始终在账”是 `Persists`。知道就是 [@thm-target-recovery] 中的纤维条件，读数是 $r_t$，目标是 $v_e$；$W$ 非空时，它等价于存在 $g$ 使 $v_e = g \circ r_t$[^factors]。遗忘是语义上的：事件仍在账本上，失去的不是记录，而是读数区分它的取值的能力。它不是删除账目，也不是物理擦除或某种认知状态的标签。

[^factors]: Lean 用 Mathlib 的 `Function.FactorsThrough` 表达这个纤维条件。名字说“经由……分解”，定义却只要求纤维上取常值，不要求分解映射存在。[@thm-max-compatible] 中的相容条件，在 Lean 中也是这样写的。

::: {.theorem #thm-forgot-iff title="遗忘的见证" lean="D5/S3/ObserverMemory/TwoTimeKnowledge.forgot_iff_later_fiber_counterexample"}
在 [@def-knows] 的设定下，对任意事件 $e$ 与时刻 $t_0, t_1$，$\mathrm{Forgot}(e, t_0, t_1)$ 成立，当且仅当以下四条同时成立：

1. $t_0 < t_1$；
2. 对每个满足 $t_0 \le t \le t_1$ 的时刻 $t$，$e \in L(t)$；
3. 对任意 $x, y \in W$，$r_{t_0}(x) = r_{t_0}(y)$ 蕴含 $v_e(x) = v_e(y)$；
4. 存在 $x, y \in W$，使 $r_{t_1}(x) = r_{t_1}(y)$ 而 $v_e(x) \ne v_e(y)$。
:::

前三条只是把定义展开，第四条把“$\mathrm{Knows}(e, t_1)$ 不成立”改写成一个见证：后来的某个纤维中有两个世界，读数相同而事件取值不同。用 [@def-target-risk] 的记号，第 3 条说 $\mathrm{Def}(r_{t_0}, v_e) = \varnothing$，第 4 条说 $\mathrm{Def}(r_{t_1}, v_e) \ne \varnothing$：遗忘的见证就是后来的一个缺陷对。trureturing 的 Blueprint 说明，这条定理只是量词的规范化，不是遗忘的独立刻画；它也不给出遗忘的速度或程度。

同一模块中还有一个具体实例（`finite_certificate_instantiates_forgot`）：$W = \mathbb{B}$，时刻也取自 $\mathbb{B}$，$0 < 1$；时刻 $0$ 的读数是恒等映射，时刻 $1$ 的读数是常值；唯一的事件以世界本身为取值，账本始终记录它。于是这个事件在时刻 $0$ 被知道，在时刻 $0$ 与 $1$ 之间被遗忘，见证是 $(x, y) = (0, 1)$。

::: {.corollary #cor-knows-monotone title="更粗的读数不会知道更多" lean="D5/S3/ObserverMemory/TwoTimeKnowledge.knows_of_later_readout_factors_through_earlier"}
在 [@def-knows] 的设定下，设 $t_0, t_1$ 是任意两个时刻（不要求 $t_0 \le t_1$），并且对任意 $x, y \in W$，$r_{t_0}(x) = r_{t_0}(y)$ 蕴含 $r_{t_1}(x) = r_{t_1}(y)$。若 $\mathrm{Knows}(e, t_1)$，则 $\mathrm{Knows}(e, t_0)$。
:::

::: proof
若 $r_{t_0}(x) = r_{t_0}(y)$，由假设 $r_{t_1}(x) = r_{t_1}(y)$，再由 $\mathrm{Knows}(e, t_1)$ 得 $v_e(x) = v_e(y)$。完整证明由 Lean 内核检查。
:::

假设说 $r_{t_1}$ 的每个纤维都是 $r_{t_0}$ 的纤维的并，也就是 $r_{t_1}$ 比 $r_{t_0}$ 粗；$\mathrm{Refines}(r_{t_1}, r_{t_0})$ 时它成立（见 [@def-refines] 后的说明）。这是 [@thm-refinement-tradeoff] 中风险包含关系在记忆中的对应：在粗读数下没有缺陷的事件，在细读数下也没有。读数只变粗时，不会知道新的事件，知识只能保持或丢失。推论不说变粗一定导致遗忘：被知道的事件可以一直被知道。

例如取 $W = \mathbb{B}^2$，$r_{t_0}$ 为恒等映射，$r_{t_1}$ 为第一个坐标 $\mathrm{fst}$。取值为第一个坐标的事件在两个时刻都被知道；取值为第二个坐标的事件只在 $t_0$ 被知道。若 $t_0 < t_1$ 且后一个事件始终在账，它就在 $t_0$ 与 $t_1$ 之间被遗忘，见证是 $((0, 0), (0, 1))$。

## 信息 {#sec-information}

前两节只问缺陷对是否存在。给状态加上概率分布之后，还可以问读数保留了多少信息。有限集 $X$ 上的概率分布是满足 $p \ge 0$ 与 $\sum_{x} p(x) = 1$ 的函数 $p: X \to \mathbb{R}$，它的熵是
$$
H(p) = -\sum_{x \in X} p(x) \log p(x),
$$
约定 $0 \log 0 = 0$。本节的 $\log$ 都是自然对数，熵的单位是纳特（nat）。映射 $f: X \to Y$ 把 $p$ 推前为 $Y$ 上的分布 $(f_* p)(y) = \sum_{x:\, f(x) = y} p(x)$，即 $f(x)$ 的分布。

::: {.theorem #thm-entropy-injective title="熵不变当且仅当不合并正概率状态" lean="D5/S3/Entropy/Forgetting/DeterministicEntropyEquality.pushforward_entropy_eq_iff_injective_on_support"}
设 $X$、$Y$ 是有限集，$p$ 是 $X$ 上的概率分布，$f: X \to Y$。则 $H(f_* p) = H(p)$，当且仅当 $f$ 在支撑集 $\{x \in X : p(x) \ne 0\}$ 上是单射。
:::

::: proof
Lean 证明考虑 $(f(x), x)$ 的联合分布：它的熵等于 $H(p)$，第一个坐标的边缘分布是 $f_* p$。由熵的链式法则，$H(p) = H(f_* p) + H(X \mid f(X))$，所以等式成立当且仅当这个条件熵为零，即每个概率为正的纤维上，条件分布集中在一点；这恰好是 $f$ 不把两个正概率的状态并在一起。完整证明由 Lean 内核检查。
:::

单射的要求只针对支撑集：零概率的状态可以与别的状态落在同一个纤维中，不影响这个判据。同一模块的另一条定理 `pushforward_entropy_lt_iff_not_injective_on_support`（本书不单独引用）说，一旦合并了两个正概率的状态，熵就严格下降；两条合起来才有 $H(f_* p) \le H(p)$，[@thm-entropy-injective] 本身不陈述这个不等式。用前两节的话说：$f$ 在支撑集上单射，就是在支撑集上状态本身（恒等目标）能由 $f$ 恢复；合并两个正概率的状态，就是恒等目标的一个缺陷对。

作为计算：四个状态上的均匀分布，熵是 $\log 4 \approx 1.3863$；把其中两个状态并为一个，得到分布 $(1/2, 1/4, 1/4)$，熵是 $\tfrac32 \log 2 \approx 1.0397$，严格下降。若 $p = (1/2, 1/2, 0)$，把零概率的第三个状态并入第二个，熵仍是 $\log 2 \approx 0.6931$。

再看读数。设 $\mu$ 是有限集 $X$ 上的概率分布，$q: X \to C$ 是读数，$C$ 有限。读数的信息是读数值的分布的熵 $I_\mu(q) = H(q_* \mu)$；剩余熵 $R_\mu(q)$ 是读出 $q$ 之后状态还剩的不确定性，即 $(q(x), x)$ 的联合分布对第一个坐标取条件的条件熵：
$$
R_\mu(q) = \sum_{c \in C} (q_* \mu)(c) \, H\bigl(\mu(\,\cdot \mid q = c)\bigr),
$$
其中 $\mu(\,\cdot \mid q = c)$ 是 $\mu$ 限制在纤维 $q^{-1}(c)$ 上再归一化得到的分布，$(q_* \mu)(c) = 0$ 的项记为 $0$。两者在 Lean 中是 `conceptInformation` 与 `conceptResidual`。

::: {.theorem #thm-entropy-monotone title="细化与信息" lean="D5/S3/ConceptDynamics/Information/RefinementEntropyMonotonicity.refinement_information_residual_monotone"}
设 $X$、$C$、$D$ 是有限集，$\mu$ 是 $X$ 上的概率分布，读数 $q_C: X \to C$、$q_D: X \to D$ 满足 $\mathrm{Refines}(q_C, q_D)$。则
$$
I_\mu(q_C) \le I_\mu(q_D), \qquad R_\mu(q_D) \le R_\mu(q_C).
$$
:::

::: proof
设 $q_C = f \circ q_D$，则 $(q_C)_* \mu = f_* \bigl((q_D)_* \mu\bigr)$：粗读数的分布是细读数分布的推前。按 $f$ 在 $(q_D)_* \mu$ 的支撑集上是否单射分两种情形，分别用 [@thm-entropy-injective] 与上面提到的严格下降定理，得到 $I_\mu(q_C) \le I_\mu(q_D)$。再由链式法则，每个读数都满足 $H(\mu) = I_\mu(q) + R_\mu(q)$（Lean 中是模块内的私有引理），信息多出多少，剩余熵就少多少。完整证明由 Lean 内核检查。
:::

方向与 [@thm-refinement-tradeoff] 相同：信息像代价一样随细化不减，剩余熵像风险一样随细化不增。定理不给出不等式何时严格。剩余熵量的是关于整个状态的不确定性，不是关于某个目标的；下面的例子说明，后者不能从前者读出。

::: {.example #ex-equal-entropy title="熵相等，可恢复性不同" lean="D5/S3/ConceptDynamics/Information/EqualEntropyTargetValueContrast.equal_entropy_target_value_contrast"}
取 $X = \mathbb{B}^2$，$\mu$ 为均匀分布（每点 $1/4$），读数 $\mathrm{fst}(x_1, x_2) = x_1$ 与 $\mathrm{snd}(x_1, x_2) = x_2$，目标 $t = \mathrm{fst}$。记 $H(t \mid q)$ 为 $(q(x), t(x))$ 的联合分布对第一个坐标取条件的条件熵，即读出 $q$ 之后目标还剩的不确定性。则

- $H(\mathrm{fst}_* \mu) = H(\mathrm{snd}_* \mu) = \log 2$；
- 两个读数都恰好取到 $2$ 个值，取值个数与状态个数之比都是 $2/4 = 1/2$；
- $H(t \mid \mathrm{fst}) = 0$，$H(t \mid \mathrm{snd}) = \log 2$；
- $\mathrm{Refines}(t, \mathrm{fst})$ 成立，$\mathrm{Refines}(t, \mathrm{snd})$ 不成立。
:::

两个读数的熵、取值个数与压缩比都一样，对目标 $\mathrm{fst}$ 却一个完全够用、一个完全无用：$\mathrm{snd}$ 把 $(0, 0)$ 与 $(1, 0)$ 读成同一个值，而目标区分它们，这是一个缺陷对。可恢复性取决于目标，要看的是缺陷关系，而不只是一个数。这只是一个具体例子，不是一般定理；它也不说熵从来不提供信息。数值上 $\log 2 \approx 0.6931$。

::: {.remark #rem-one-order title="[@thm-refinement-tradeoff] 与 [@thm-entropy-monotone] 并读"}
两条定理沿同一个细化的序给出单调性：代价与信息随细化不减，风险与剩余熵随细化不增。下面的例子把这四个量放进一张表，也说明 [@ex-equal-entropy] 中的两个读数为什么无法比较。

::: {.example #ex-two-bit-readouts title="$\mathbb{B}^2$ 上的四个读数"}
在 $X = \mathbb{B}^2$ 上取均匀分布 $\mu$ 与目标族 $\mathcal{T} = \{\mathrm{fst}, \mathrm{snd}\}$，比较常值读数 $\kappa$、$\mathrm{fst}$、$\mathrm{snd}$ 与恒等读数 $\mathrm{id}$。

| 读数 $q$ | $\mathrm{Cost}(q)$ | $I_\mu(q)$ | $R_\mu(q)$ | $\mathrm{Risk}(q, \mathcal{T})$ |
| :---: | :---: | :---: | :---: | :---: |
| $\kappa$ | $1$ | $0$ | $\log 4$ | $\{\mathrm{fst}, \mathrm{snd}\}$ |
| $\mathrm{fst}$ | $2$ | $\log 2$ | $\log 2$ | $\{\mathrm{snd}\}$ |
| $\mathrm{snd}$ | $2$ | $\log 2$ | $\log 2$ | $\{\mathrm{fst}\}$ |
| $\mathrm{id}$ | $4$ | $\log 4$ | $0$ | $\varnothing$ |

每个读数都细化 $\kappa$，也都被 $\mathrm{id}$ 细化，所以沿 $\kappa, \mathrm{fst}, \mathrm{id}$ 与 $\kappa, \mathrm{snd}, \mathrm{id}$ 这两条链，各列都按两条定理单调变化。$\mathrm{fst}$ 与 $\mathrm{snd}$ 之间没有细化关系（[@ex-equal-entropy] 给出 $\mathrm{snd}$ 不细化 $\mathrm{fst}$，另一方向同理）：它们的代价、信息与剩余熵都相同，风险却互不包含。表中的数值是我们对这个例子的计算（$\log 2 \approx 0.6931$，$\log 4 \approx 1.3863$），每一行都有 $I_\mu(q) + R_\mu(q) = \log 4 = H(\mu)$。
:::
:::

[第四章](ch04-golden-word.md) 回到黄金比，从黄金词讲起。
