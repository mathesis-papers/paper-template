# Chapter 3 Refinement, memory and information

[@thm-target-recovery] in [Chapter 2](ch02-refutation-observation.md) answers a yes-or-no question: can a target $t$ be recovered from a readout $p$? The answer is decided by the defect relation, the set of pairs of states $(x, y)$ with the same reading and different targets. On a nonempty state space, a recovery function exists when this relation is empty; when it is nonempty, no function recovers the target.

The question is itself a comparison between two maps. "There is an $r$ with $t = r \circ p$" says that $t$ can be computed from $p$, that is, $p$ is at least as fine as $t$. This chapter treats that comparison as an order on readouts ([@def-refines]) and studies it from three directions.

Refinement and cost
: The finer the readout, the fewer targets have defects and the more values the readout takes ([@thm-refinement-tradeoff]). When recovery fails, the largest set of states that can be kept has an exact size ([@thm-max-compatible]).

Memory
: Readouts change over time. To know an event is for worlds with the same current reading to give it the same value; to forget it is to lose this property while the event stays on the record (see the section on [memory](#sec-memory)).

Information
: Once the states carry a probability distribution, the refinement order becomes a set of entropy inequalities (see the section on [information](#sec-information)). A single entropy value, however, cannot replace the defect relation ([@ex-equal-entropy]).

Every readout in this chapter is a map $q: X \to C$, where $X$ is the state space and $C$ the space of readings. trureturing calls such a map a concept (`Concept X C`, which is just the function type $X \to C$). A target is a map of the same kind, so targets and readouts can be compared within one order.

## Refinement {#sec-refinement}

::: {.definition #def-refines title="Refinement" lean="D5/S3/ConceptDynamics/ConceptJoinUniversal.Refines"}
Let $q_C: X \to C$ and $q_D: X \to D$ be two readouts on the same state space $X$. If there is a map $f: D \to C$ with $q_C = f \circ q_D$, we say that $q_D$ refines $q_C$ and write $\mathrm{Refines}(q_C, q_D)$.
:::

Mind the order of the arguments: the coarser readout comes first. $\mathrm{Refines}(q_C, q_D)$ says that $q_C$ can be computed from $q_D$, and $q_C = f \circ q_D$ is an equality of functions. The first condition in [@thm-target-recovery] is exactly $\mathrm{Refines}(t, p)$: a target can be recovered precisely when the readout refines it. Taking $f$ to be the identity shows that every readout refines itself, and composing two factor maps shows that refinement is transitive. Both facts come straight from the definition, whose Lean name is [`Refines`](lean:D5/S3/ConceptDynamics/ConceptJoinUniversal.Refines).

Refinement can also be phrased in terms of fibers. If $q_C = f \circ q_D$, then $q_D(x) = q_D(y)$ implies $q_C(x) = f(q_D(x)) = f(q_D(y)) = q_C(y)$: every fiber of $q_D$ lies inside a fiber of $q_C$. When $X$ is nonempty the converse holds as well; this is the first equivalence of [@thm-target-recovery] with $p = q_D$ and $t = q_C$.

Two readouts always have a common refinement: record both readings side by side.

::: {.theorem #thm-join-universal title="The universal property of the joint readout" lean="D5/S3/ConceptDynamics/ConceptJoinUniversal.concept_join_universal"}
For readouts $q_C: X \to C$ and $q_D: X \to D$, let the joint readout $\langle q_C, q_D \rangle: X \to C \times D$ be $x \mapsto (q_C(x), q_D(x))$. Then

1. $\mathrm{Refines}(q_C, \langle q_C, q_D \rangle)$;
2. $\mathrm{Refines}(q_D, \langle q_C, q_D \rangle)$;
3. for every readout $q_E: X \to E$, if $\mathrm{Refines}(q_C, q_E)$ and $\mathrm{Refines}(q_D, q_E)$, then $\mathrm{Refines}(\langle q_C, q_D \rangle, q_E)$.
:::

::: proof
The first two items come from the coordinate projections: $q_C = \pi_1 \circ \langle q_C, q_D \rangle$ and $q_D = \pi_2 \circ \langle q_C, q_D \rangle$. For the third, if $q_C = f \circ q_E$ and $q_D = g \circ q_E$, put $h(e) = (f(e), g(e))$; then $\langle q_C, q_D \rangle = h \circ q_E$. The full proof is checked by the Lean kernel.
:::

The first two items say that the joint readout is a common refinement of $q_C$ and $q_D$; the third says that every common refinement refines it. In the refinement order it is therefore the coarsest common refinement, which is what "join" in the Lean name refers to (the joint readout itself is `conceptJoin` in Lean). Read through [@thm-target-recovery]: if two targets can each be recovered from $q_E$, then so can the pair of them, and the recovery map is the pair of the two recovery maps. The theorem is about two readouts, not arbitrary families, and it does not claim that recovery maps are unique.

A finer readout can recover more targets, but it also has to tell more states apart. The next definition gives one quantity for each side.

::: {.definition #def-target-risk title="Target risk and refinement cost" lean="D5/S3/ConceptDynamics/TargetRisk/RefinementRiskCostTradeoff.targetRisk D5/S3/ConceptDynamics/TargetRisk/RefinementRiskCostTradeoff.refinementCost"}
Let $q: X \to C$ be a readout. For a target $t: X \to T$, the defect relation of $q$ for $t$ is
$$
\mathrm{Def}(q, t) = \{(x, y) \in X \times X : q(x) = q(y),\ t(x) \ne t(y)\}.
$$
For a family $\mathcal{T}$ of targets (all maps $X \to T$), the target risk of $q$ consists of the targets whose defect relation is nonempty:
$$
\mathrm{Risk}(q, \mathcal{T}) = \{t \in \mathcal{T} : \mathrm{Def}(q, t) \ne \varnothing\}.
$$
The refinement cost of $q$ is the number of values it actually takes:
$$
\mathrm{Cost}(q) = |q(X)| \in \mathbb{N} \cup \{\infty\},
$$
with the value $\infty$ when $q(X)$ is infinite.
:::

In Lean these are [`targetRisk`](lean:D5/S3/ConceptDynamics/TargetRisk/RefinementRiskCostTradeoff.targetRisk) and [`refinementCost`](lean:D5/S3/ConceptDynamics/TargetRisk/RefinementRiskCostTradeoff.refinementCost); the defect relation is `defectRelation` in the same module, the same relation as in [@thm-target-recovery]. The cost counts the attained values $q(X)$, not the reading space $C$: $C$ may be large, and the cost only sees how many of its values $q$ actually uses[^encard]. When $X$ is nonempty, [@thm-target-recovery] shows that a target lies in $\mathrm{Risk}(q, \mathcal{T})$ exactly when it cannot be recovered from $q$; the definition itself only asks whether the defect relation is nonempty and needs no such assumption.

[^encard]: In Lean, $\mathrm{Cost}(q)$ is `(Set.range q).encard`, a value in the extended natural numbers $\mathbb{N}_\infty = \mathbb{N} \cup \{\infty\}$: a finite set gets its number of elements, and every infinite set gets $\infty$, with no distinction between infinite cardinalities. $\infty$ is larger than every natural number.

::: {.theorem #thm-refinement-tradeoff title="Refinement never adds risk or lowers cost" lean="D5/S3/ConceptDynamics/TargetRisk/RefinementRiskCostTradeoff.refinement_reduces_target_risk_and_raises_cost"}
Let the readouts $q_C: X \to C$ and $q_D: X \to D$ satisfy $\mathrm{Refines}(q_C, q_D)$, and let $\mathcal{T}$ be any family of targets (all maps $X \to T$). Then
$$
\mathrm{Risk}(q_D, \mathcal{T}) \subseteq \mathrm{Risk}(q_C, \mathcal{T}), \qquad \mathrm{Cost}(q_C) \le \mathrm{Cost}(q_D),
$$
where the inequality is in $\mathbb{N} \cup \{\infty\}$.
:::

::: proof
Write $q_C = f \circ q_D$. If $(x, y)$ is a defect pair of $q_D$ for a target $t$, so that $q_D(x) = q_D(y)$ while $t(x) \ne t(y)$, then $q_C(x) = f(q_D(x)) = f(q_D(y)) = q_C(y)$, and the same pair is a defect pair of $q_C$ for $t$. So every target at risk under $q_D$ is at risk under $q_C$. For the cost, $q_C(X) = f(q_D(X))$, and the image of a set under a map is no larger than the set. The full proof is checked by the Lean kernel.
:::

The two directions pull against each other: a finer readout carries less risk and costs more, while a coarser one saves cost but puts more targets at risk. The theorem gives only these two monotonicities. Both the inclusion and the inequality may be equalities, and nothing is said about an optimal balance between risk and cost. With the direction reversed, both fail in general. Write $\mathbb{B} = \{0, 1\}$ (Lean's `Bool`, with $0$ for false and $1$ for true). Three Lean `example`s in the same module check this: on $X = \mathbb{B}$ the constant readout is refined by the identity readout; for the identity target the constant readout is at risk (defect pair $(0, 1)$) while the identity readout is not; and their costs are $1$ and $2$.

When a target cannot be recovered, one can still ask how large a set of states it can be recovered on. Call a subset $A \subseteq X$ compatible with the readout $q$ and the target $t$ if any two states in $A$ with the same reading have the same target value. For nonempty $A$, applying [@thm-target-recovery] to the state space $A$ shows that compatibility means exactly that $t$ can be recovered from $q$ on $A$.

::: {.theorem #thm-max-compatible title="How much can be saved" lean="D5/S3/ConceptDynamics/TargetRisk/MaximumFactorCompatibleSubdomain.maximum_factor_compatible_subdomain"}
Let $X$ be a finite set, $q: X \to B$ a readout and $t: X \to Y$ a target ($B$ and $Y$ need not be finite). Let
$$
N = \sum_{b \in q(X)} \ \max_{r \in X,\ q(r) = b} \ \bigl|\{x \in X : q(x) = b,\ t(x) = t(r)\}\bigr|.
$$
Then

1. every compatible subset $A \subseteq X$ (that is, for all $x, y \in A$, $q(x) = q(y)$ implies $t(x) = t(y)$) satisfies $|A| \le N$;
2. there is a compatible subset $A \subseteq X$ with $|A| = N$.
:::

For each attained value $b$, the fiber $q^{-1}(b)$ splits into blocks by target value. The set $\{x \in X : q(x) = b,\ t(x) = t(r)\}$ is the block containing the representative $r$, and the maximum over $r$ is the size of the largest block in the fiber. So $N$ is the sum, over all fibers, of the sizes of their largest blocks.

::: proof
Upper bound: a compatible $A$ takes a single target value on each fiber $q^{-1}(b)$, so $A \cap q^{-1}(b)$ lies inside one block of that fiber and is no larger than the largest block; summing over fibers gives $|A| \le N$. Attainment: choose one largest block in every fiber; their union is compatible and has exactly $N$ elements. The Lean proof uses choice to pick a representative of a largest block in each fiber, so it only shows that such a subset exists; it says neither that it is unique nor how to choose between several largest blocks. The full proof is checked by the Lean kernel.
:::

By item 2, $N \le |X|$. When $X$ is nonempty, $t$ can be recovered from $q$ if and only if $X$ itself is compatible, if and only if $N = |X|$: the former gives $|X| \le N$ by item 1, and the latter gives, by item 2, a compatible subset with $|X|$ elements, which can only be $X$. In general, at least $|X| - N$ states must be discarded to make the rest compatible (item 1), and discarding that many suffices (item 2). The theorem is purely about counting: it involves no probability weights and says nothing about how wrong one is on the states outside the subset.

::: {.example #ex-partial-recovery title="Partial recovery"}
In [@ex-mod-two], $(1, 2)$ and $(1, 4)$ agree modulo $2$ but have different deficits, so the residues modulo $2$ cannot recover the deficit. How much can be saved? Fix $v_1 = 1$ and take the state space $X = \{0, 1, \dots, 7\}$, the readout $q(v) = v \bmod 2$ and the target $t(v) = c(1, v)$, with the target values taken from the row $v_1 = 1$ of [@ex-small-deficits].

| State $v$ | Readout $q(v) = v \bmod 2$ | Target $t(v) = c(1, v)$ |
| :---: | :---: | :---: |
| 0 | 0 | 0 |
| 1 | 1 | 1 |
| 2 | 0 | 0 |
| 3 | 1 | 0 |
| 4 | 0 | 1 |
| 5 | 1 | 0 |
| 6 | 0 | 1 |
| 7 | 1 | 0 |

On the even fiber $q^{-1}(0) = \{0, 2, 4, 6\}$ the target values are $0, 0, 1, 1$, giving the blocks $\{0, 2\}$ and $\{4, 6\}$; the largest has size $2$. On the odd fiber $q^{-1}(1) = \{1, 3, 5, 7\}$ the target values are $1, 0, 0, 0$, giving $\{1\}$ and $\{3, 5, 7\}$; the largest has size $3$. By [@thm-max-compatible], $N = 2 + 3 = 5$, so at least $8 - 5 = 3$ states must be discarded.

Choosing one largest block in each fiber gives a compatible subset of size $5$. The even fiber has two blocks of equal size, so there are two choices: $\{0, 2, 3, 5, 7\}$, on which $t$ is constantly $0$, and $\{3, 4, 5, 6, 7\}$, on which $t(v) = 1 - q(v)$. The defect pair of [@ex-mod-two] is the pair of states $2$ and $4$, and each subset keeps one of them. We enumerated all $2^8 = 256$ subsets of $X$ in Python: the largest compatible subsets have $5$ elements, and these two are the only ones of that size. This is a computation for this example, not a theorem. The theorem does not claim that the optimal subset is unique, and here there are two.
:::

## Memory {#sec-memory}

So far the readouts have been fixed. An observer's readout changes over time: records are compressed and details are dropped. trureturing describes knowing and forgetting in the same language of fibers. In this section $t$ denotes a time.

::: {.definition #def-knows title="Knowing and forgetting" lean="D5/S3/ObserverMemory/TwoTimeKnowledge.Knows D5/S3/ObserverMemory/TwoTimeKnowledge.Forgot"}
Let the times form a preordered set $\mathrm{Time}$ and let $W$ be a set of worlds. The observer's readout at time $t$ is $r_t: W \to V$, the value of an event $e$ is $v_e: W \to \mathrm{Val}$, and the ledger $L(t)$ is the set of events on record at time $t$.

- The event $e$ is known at time $t$, written $\mathrm{Knows}(e, t)$, if $v_e$ is constant on every fiber of $r_t$: for all $x, y \in W$, $r_t(x) = r_t(y)$ implies $v_e(x) = v_e(y)$.
- The event $e$ is forgotten between times $t_0$ and $t_1$, written $\mathrm{Forgot}(e, t_0, t_1)$, if the following four conditions all hold: $t_0 < t_1$; $e \in L(t)$ for every time $t$ with $t_0 \le t \le t_1$; $\mathrm{Knows}(e, t_0)$; and $\mathrm{Knows}(e, t_1)$ fails.
:::

In Lean these are [`Knows`](lean:D5/S3/ObserverMemory/TwoTimeKnowledge.Knows) and [`Forgot`](lean:D5/S3/ObserverMemory/TwoTimeKnowledge.Forgot); the second condition, staying on record, is `Persists`. Knowing is the fiber condition of [@thm-target-recovery] with readout $r_t$ and target $v_e$; when $W$ is nonempty it is equivalent to the existence of a $g$ with $v_e = g \circ r_t$[^factors]. Forgetting is semantic: the event is still on the record, and what is lost is not the entry but the readout's ability to tell its values apart. It is not the deletion of an entry, nor physical erasure, nor a label for a cognitive state.

[^factors]: Lean expresses this fiber condition with Mathlib's `Function.FactorsThrough`. The name speaks of factoring, but the definition only asks for constancy on fibers and does not require a factor map to exist. The compatibility condition in [@thm-max-compatible] is written the same way in Lean.

::: {.theorem #thm-forgot-iff title="A witness of forgetting" lean="D5/S3/ObserverMemory/TwoTimeKnowledge.forgot_iff_later_fiber_counterexample"}
In the setting of [@def-knows], for every event $e$ and times $t_0, t_1$, $\mathrm{Forgot}(e, t_0, t_1)$ holds if and only if the following four conditions all hold:

1. $t_0 < t_1$;
2. $e \in L(t)$ for every time $t$ with $t_0 \le t \le t_1$;
3. for all $x, y \in W$, $r_{t_0}(x) = r_{t_0}(y)$ implies $v_e(x) = v_e(y)$;
4. there are $x, y \in W$ with $r_{t_1}(x) = r_{t_1}(y)$ and $v_e(x) \ne v_e(y)$.
:::

The first three conditions merely unfold the definition; the fourth turns "$\mathrm{Knows}(e, t_1)$ fails" into a witness: some later fiber contains two worlds with the same reading and different event values. In the notation of [@def-target-risk], condition 3 says $\mathrm{Def}(r_{t_0}, v_e) = \varnothing$ and condition 4 says $\mathrm{Def}(r_{t_1}, v_e) \ne \varnothing$: the witness of forgetting is a later defect pair. trureturing's Blueprint points out that the theorem is only a normalization of quantifiers, not an independent characterization of forgetting, and it says nothing about how fast or how much is forgotten.

The same module also contains a concrete instance (`finite_certificate_instantiates_forgot`). Take $W = \mathbb{B}$ and times from $\mathbb{B}$ as well, with $0 < 1$; the readout at time $0$ is the identity and the readout at time $1$ is constant; the only event takes the world itself as its value, and the ledger always records it. The event is then known at time $0$ and forgotten between times $0$ and $1$, with witness $(x, y) = (0, 1)$.

::: {.corollary #cor-knows-monotone title="A coarser readout knows no more" lean="D5/S3/ObserverMemory/TwoTimeKnowledge.knows_of_later_readout_factors_through_earlier"}
In the setting of [@def-knows], let $t_0, t_1$ be any two times ($t_0 \le t_1$ is not required) such that, for all $x, y \in W$, $r_{t_0}(x) = r_{t_0}(y)$ implies $r_{t_1}(x) = r_{t_1}(y)$. If $\mathrm{Knows}(e, t_1)$, then $\mathrm{Knows}(e, t_0)$.
:::

::: proof
If $r_{t_0}(x) = r_{t_0}(y)$, the hypothesis gives $r_{t_1}(x) = r_{t_1}(y)$, and $\mathrm{Knows}(e, t_1)$ then gives $v_e(x) = v_e(y)$. The full proof is checked by the Lean kernel.
:::

The hypothesis says that every fiber of $r_{t_1}$ is a union of fibers of $r_{t_0}$, that is, $r_{t_1}$ is coarser than $r_{t_0}$; it holds whenever $\mathrm{Refines}(r_{t_1}, r_{t_0})$ (see the discussion after [@def-refines]). This is the memory counterpart of the risk inclusion in [@thm-refinement-tradeoff]: an event without defects under the coarse readout has none under the fine one. A readout that only becomes coarser never comes to know a new event; knowledge can only be kept or lost. The corollary does not say that coarsening forces forgetting: a known event may stay known.

For example, take $W = \mathbb{B}^2$, with $r_{t_0}$ the identity and $r_{t_1}$ the first coordinate $\mathrm{fst}$. An event whose value is the first coordinate is known at both times; an event whose value is the second coordinate is known only at $t_0$. If $t_0 < t_1$ and the second event stays on record throughout, it is forgotten between $t_0$ and $t_1$, with witness $((0, 0), (0, 1))$.

## Information {#sec-information}

The first two sections only asked whether a defect pair exists. Once the states carry a probability distribution, one can also ask how much information a readout keeps. A probability distribution on a finite set $X$ is a function $p: X \to \mathbb{R}$ with $p \ge 0$ and $\sum_{x} p(x) = 1$, and its entropy is
$$
H(p) = -\sum_{x \in X} p(x) \log p(x),
$$
with the convention $0 \log 0 = 0$. Throughout this section $\log$ is the natural logarithm, so entropies are measured in nats. A map $f: X \to Y$ pushes $p$ forward to the distribution $(f_* p)(y) = \sum_{x:\, f(x) = y} p(x)$ on $Y$, the distribution of $f(x)$.

::: {.theorem #thm-entropy-injective title="Entropy is kept exactly when no positive-mass states merge" lean="D5/S3/Entropy/Forgetting/DeterministicEntropyEquality.pushforward_entropy_eq_iff_injective_on_support"}
Let $X$ and $Y$ be finite sets, $p$ a probability distribution on $X$ and $f: X \to Y$. Then $H(f_* p) = H(p)$ if and only if $f$ is injective on the support $\{x \in X : p(x) \ne 0\}$.
:::

::: proof
The Lean proof looks at the joint distribution of $(f(x), x)$: its entropy equals $H(p)$, and its first marginal is $f_* p$. By the chain rule for entropy, $H(p) = H(f_* p) + H(X \mid f(X))$, so equality holds exactly when this conditional entropy vanishes, that is, when the conditional distribution on every fiber of positive probability is concentrated at one point; and that says precisely that $f$ merges no two states of positive probability. The full proof is checked by the Lean kernel.
:::

Injectivity is required only on the support: states of probability zero may share a fiber with other states without affecting the criterion. Another theorem in the same module, `pushforward_entropy_lt_iff_not_injective_on_support` (not cited separately in this book), says that merging two states of positive probability strictly lowers the entropy. Only the two together give $H(f_* p) \le H(p)$; [@thm-entropy-injective] does not state that inequality by itself. In the language of the first two sections, $f$ is injective on the support exactly when the state itself (the identity target) can be recovered from $f$ on the support, and merging two states of positive probability is a defect pair for the identity target.

As a computation: the uniform distribution on four states has entropy $\log 4 \approx 1.3863$. Merging two of the states gives the distribution $(1/2, 1/4, 1/4)$ with entropy $\tfrac32 \log 2 \approx 1.0397$, a strict loss. If $p = (1/2, 1/2, 0)$, merging the third state, of probability zero, into the second leaves the entropy at $\log 2 \approx 0.6931$.

Now to readouts. Let $\mu$ be a probability distribution on a finite set $X$ and $q: X \to C$ a readout with $C$ finite. The information of the readout is the entropy of the distribution of its readings, $I_\mu(q) = H(q_* \mu)$. The residual entropy $R_\mu(q)$ is the uncertainty about the state that remains after reading $q$, the conditional entropy of the joint distribution of $(q(x), x)$ given the first coordinate:
$$
R_\mu(q) = \sum_{c \in C} (q_* \mu)(c) \, H\bigl(\mu(\,\cdot \mid q = c)\bigr),
$$
where $\mu(\,\cdot \mid q = c)$ is $\mu$ restricted to the fiber $q^{-1}(c)$ and renormalized, and terms with $(q_* \mu)(c) = 0$ count as $0$. In Lean these are `conceptInformation` and `conceptResidual`.

::: {.theorem #thm-entropy-monotone title="Refinement and information" lean="D5/S3/ConceptDynamics/Information/RefinementEntropyMonotonicity.refinement_information_residual_monotone"}
Let $X$, $C$ and $D$ be finite sets, $\mu$ a probability distribution on $X$, and let the readouts $q_C: X \to C$ and $q_D: X \to D$ satisfy $\mathrm{Refines}(q_C, q_D)$. Then
$$
I_\mu(q_C) \le I_\mu(q_D), \qquad R_\mu(q_D) \le R_\mu(q_C).
$$
:::

::: proof
Write $q_C = f \circ q_D$; then $(q_C)_* \mu = f_* \bigl((q_D)_* \mu\bigr)$, so the distribution of the coarse readout is a pushforward of that of the fine one. Splitting into two cases, according to whether $f$ is injective on the support of $(q_D)_* \mu$, and using [@thm-entropy-injective] and the strict-loss theorem mentioned above, gives $I_\mu(q_C) \le I_\mu(q_D)$. By the chain rule every readout satisfies $H(\mu) = I_\mu(q) + R_\mu(q)$ (a private lemma of the Lean module), so whatever the information gains, the residual entropy loses. The full proof is checked by the Lean kernel.
:::

The directions match [@thm-refinement-tradeoff]: like cost, information does not decrease under refinement, and like risk, residual entropy does not increase. The theorem does not say when the inequalities are strict. Residual entropy measures uncertainty about the whole state, not about any particular target, and the next example shows that the latter cannot be read off from the former.

::: {.example #ex-equal-entropy title="Equal entropy, different recoverability" lean="D5/S3/ConceptDynamics/Information/EqualEntropyTargetValueContrast.equal_entropy_target_value_contrast"}
Take $X = \mathbb{B}^2$ with the uniform distribution $\mu$ (mass $1/4$ at each point), the readouts $\mathrm{fst}(x_1, x_2) = x_1$ and $\mathrm{snd}(x_1, x_2) = x_2$, and the target $t = \mathrm{fst}$. Write $H(t \mid q)$ for the conditional entropy of the joint distribution of $(q(x), t(x))$ given the first coordinate, the uncertainty about the target that remains after reading $q$. Then

- $H(\mathrm{fst}_* \mu) = H(\mathrm{snd}_* \mu) = \log 2$;
- each readout takes exactly $2$ values, so for both the ratio of values to states is $2/4 = 1/2$;
- $H(t \mid \mathrm{fst}) = 0$ and $H(t \mid \mathrm{snd}) = \log 2$;
- $\mathrm{Refines}(t, \mathrm{fst})$ holds and $\mathrm{Refines}(t, \mathrm{snd})$ does not.
:::

The two readouts have the same entropy, the same number of values and the same compression ratio, yet for the target $\mathrm{fst}$ one is all that is needed and the other is useless: $\mathrm{snd}$ gives $(0, 0)$ and $(1, 0)$ the same reading while the target separates them, which is a defect pair. Recoverability depends on the target, and what decides it is the defect relation, not a single number. This is one concrete example, not a general theorem, and it does not say that entropy is never informative. Numerically, $\log 2 \approx 0.6931$.

::: {.remark #rem-one-order title="Reading [@thm-refinement-tradeoff] alongside [@thm-entropy-monotone]"}
The two theorems give monotonicity along the same refinement order: cost and information do not decrease under refinement, and risk and residual entropy do not increase. The example below puts all four quantities in one table and shows why the two readouts of [@ex-equal-entropy] cannot be compared.

::: {.example #ex-two-bit-readouts title="Four readouts on $\mathbb{B}^2$"}
On $X = \mathbb{B}^2$ take the uniform distribution $\mu$ and the family of targets $\mathcal{T} = \{\mathrm{fst}, \mathrm{snd}\}$, and compare the constant readout $\kappa$, $\mathrm{fst}$, $\mathrm{snd}$ and the identity readout $\mathrm{id}$.

| Readout $q$ | $\mathrm{Cost}(q)$ | $I_\mu(q)$ | $R_\mu(q)$ | $\mathrm{Risk}(q, \mathcal{T})$ |
| :---: | :---: | :---: | :---: | :---: |
| $\kappa$ | $1$ | $0$ | $\log 4$ | $\{\mathrm{fst}, \mathrm{snd}\}$ |
| $\mathrm{fst}$ | $2$ | $\log 2$ | $\log 2$ | $\{\mathrm{snd}\}$ |
| $\mathrm{snd}$ | $2$ | $\log 2$ | $\log 2$ | $\{\mathrm{fst}\}$ |
| $\mathrm{id}$ | $4$ | $\log 4$ | $0$ | $\varnothing$ |

Every readout refines $\kappa$ and is refined by $\mathrm{id}$, so along the two chains $\kappa, \mathrm{fst}, \mathrm{id}$ and $\kappa, \mathrm{snd}, \mathrm{id}$ every column changes monotonically, as the two theorems require. Neither of $\mathrm{fst}$ and $\mathrm{snd}$ refines the other ([@ex-equal-entropy] shows that $\mathrm{snd}$ does not refine $\mathrm{fst}$, and the other direction is symmetric): they have the same cost, information and residual entropy, yet neither risk set contains the other. The values in the table are our computation for this example ($\log 2 \approx 0.6931$, $\log 4 \approx 1.3863$), and every row satisfies $I_\mu(q) + R_\mu(q) = \log 4 = H(\mu)$.
:::
:::

[Chapter 4](ch04-golden-word.md) returns to the golden ratio, starting from the golden word.
