---
# 01 封面（cover 版式：无页眉页脚，自带书代号、所钉提交与页码）
theme: ../../../../theme/slides
title: "黄金整数与可观测性 · 概览"
info: "示例专著《黄金整数与可观测性》的概览：模板的保证、两章的主要定理、一个开放问题与全部输出。"
htmlAttrs:
  lang: "zh-CN"
deck:
  code: "GOLDEN//OBSERVE"
  book: "黄金整数与可观测性"
  title: "概览"
  version: "0.1.0"
  blurb: "两章、四条 Lean 定理、一个开放问题：十页看懂这本示例专著。"
layout: cover
---

<p class="kicker">示例专著 · 演示文稿</p>
<h1 class="display">黄金整数<br>与<em>可观测性</em></h1>
<p class="lead">一本每条定理都经 Lean 内核验证的示例专著。书负责解释，Lean 负责成立：每条定理都对应 trureturing 中一条已冻结的声明。</p>

---
# 02 模板的保证
section: "模板的保证"
---

<div class="body">
  <p class="kicker">What the template guarantees</p>
  <h2 class="t">每条定理都对应一条<em>冻结的 Lean 声明</em></h2>
  <p class="lead">书中的定理、引理、命题与推论都写明 trureturing 中的声明；构建在所钉的提交上逐条核对，缺一条就不发布。</p>
  <div class="flow mt-l">
    <div class="step"><span class="i">01 · 书</span><b>写明 GID</b><p>每条形式结论带 <code>lean="…"</code>，至少一条。</p></div>
    <div class="step"><span class="i">02 · 锁文件</span><b>钉住提交</b><p><code>trureturing.lock.json</code> 记录提交与解析结果。</p></div>
    <div class="step"><span class="i">03 · 冻结</span><b>只引冻结声明</b><p>列在 <code>Golden/Frozen/state</code> 中，种类为 theorem。</p></div>
    <div class="step ok"><span class="i">04 · 内核</span><b><LeanBadge gid="D5/S1/Deficit/DeficitThreeValued.deficit_three_valued" /></b><p>徽章链接到所钉提交上的 Lean 源码。</p></div>
  </div>
  <div class="g3 mt-l">
    <Stat value="4" label="条定理，全部经 Lean 内核验证" tone="ok" />
    <Stat value="1" label="个开放问题，明确标为 OPEN" tone="warn" />
    <Stat value="0" label="条未验证的引用：./tbook check 拒绝发布" />
  </div>
</div>
<Source>docs/ARCHITECTURE.md §1、§4；trureturing.lock.json</Source>

---
# 03 第一章（section 版式：大号章节编号）
layout: section
chapter: "01"
section: "第一章"
---

<p class="kicker">Chapter 1</p>
<h2 class="t">黄金整数的<em>进位亏量</em></h2>
<p class="lead">每个自然数都唯一地写成互不相邻的 Fibonacci 数之和。把权重 <Tex t="F_i" /> 换成黄金比的幂 <Tex t="\varphi^i" />，得到实数 <Tex t="\beta(n)" />；<Tex t="\beta" /> 不保持加法，差额就是亏量。</p>
<TheoremCard class="compact mt-l" kind="definition" label="定义1.1" title="归一化亏量" gid="D5/S1/Deficit/DeficitInteger.deficit" cite="def-deficit">

$$c(v_1, v_2) = \beta(v_1) + \beta(v_2) - \beta(v_1 + v_2)$$

</TheoremCard>

---
# 04 定理 1.3：三值
section: "第一章 · 亏量"
---

<div class="body">
  <p class="kicker">Theorem 1.3</p>
  <h2 class="t">无论输入多大，亏量只取 <em>−1、0、1</em></h2>
<TheoremCard class="mt" label="定理1.3" title="亏量只取三个值" gid="D5/S1/Deficit/DeficitThreeValued.deficit_three_valued" cite="thm-deficit-three-valued">

对所有自然数 $v_1, v_2$，

$$c(v_1, v_2) \in \{-1,\ 0,\ 1\}.$$

</TheoremCard>
  <p class="lead mt">例如 <Tex t="\beta(1) = \varphi^2" />、<Tex t="\beta(2) = \varphi^3" />，于是 <Tex t="c(1, 1) = 2\varphi^2 - \varphi^3 = 1" />。这个界对任意大的输入都成立，把逐位进位这一算术算法和一个精确结论联系起来，可以作为后续推理的前提反复使用。</p>
</div>
<Source>D5/S1/Deficit/DeficitThreeValued.lean · 第一章 定理1.3</Source>

---
# 05 定理 1.2：整数与进位；定理 1.3 的证明思路
section: "第一章 · 亏量"
---

<div class="body">
  <p class="kicker">Theorem 1.2</p>
  <h2 class="t">亏量是整数，恰好<em>数出了进位</em></h2>
<TheoremCard class="compact mt-s" label="定理1.2" title="亏量是整数，且等于带符号的进位计数" gid="D5/S1/Deficit/DeficitInteger.deficit_integer" cite="thm-deficit-integer">

对所有自然数 $v_1, v_2$，亏量 $c(v_1, v_2)$ 等于它在收缩面（Galois 共轭）上的读数，是一个整数，并且等于把两个 Zeckendorf 表示逐位相加后、规范化过程中两条最低重复进位规则的带符号计数。

</TheoremCard>
  <p class="kicker mt-s">Proof of theorem 1.3 · 定理1.3 的证明思路</p>
  <div class="flow mt-s">
    <div class="step"><span class="i">01 · 收缩面</span><b>换成共轭</b><p>在 <Tex t="\psi = (1-\sqrt5)/2" /> 的幂上求值：每个 <Tex t="\beta'(v)" /> 落在长度恰为 1 的窗口 <Tex t="[-\psi^2, -\psi]" /> 中。</p></div>
    <div class="step"><span class="i">02 · 夹逼</span><b>严格小于 2</b><p>于是收缩面上的读数满足 <Tex t="-2 \lt c(v_1, v_2) \lt 2" />。</p></div>
    <div class="step ok"><span class="i">03 · 整数</span><b>只剩三个值</b><p>由定理1.2 它是整数，所以 <Tex t="c \in \{-1, 0, 1\}" />；完整证明由 Lean 内核检查。</p></div>
  </div>
</div>
<Source>D5/S1/Deficit/DeficitInteger.lean · 第一章 定理1.2 与定理1.3 的证明</Source>

---
# 06 第二章
layout: section
chapter: "02"
section: "第二章"
---

<p class="kicker">Chapter 2</p>
<h2 class="t">反驳与<em>可观测性</em></h2>
<p class="lead">对正整数 <Tex t="n" />，令 <Tex t="a(n)" /> 为满足 <Tex t="(1 + 1/n)^k \le 2" /> 的最大整数 <Tex t="k" />。Greathouse 为 OEIS A175406 猜想了一个取整公式：</p>
<div class="card hot mt">
  <h4>猜想 · Greathouse（OEIS A175406）</h4>
  <Tex display t="a(n) = \left\lfloor \left(n + \tfrac{1}{2}\right) \log 2 \right\rfloor \qquad (n \ge 1)" />
</div>

---
# 07 定理 2.1 与开放问题 2.2
section: "第二章 · 反驳"
---

<div class="body">
  <p class="kicker">Theorem 2.1 · Open problem 2.2</p>
  <h2 class="t">一个反例推翻猜想；它是否最小<em class="warn">仍然开放</em></h2>
  <div class="g2 mt-s">
    <TheoremCard class="compact" label="定理2.1" title="该取整公式不成立" gid="D5/S0/Certificates/GreathouseLogTwoFloorRefutation.result" cite="thm-greathouse-refuted">
      <p>猜想的公式并非对所有 <Tex t="n \ge 1" /> 成立：</p>
      <dl class="readout">
        <dt><Tex t="n" /></dt><dd class="cy">1121626023352383</dd>
        <dt>公式</dt><dd>777451915729368</dd>
        <dt><Tex t="a(n)" /></dt><dd class="hot">777451915729367<small>小一</small></dd>
      </dl>
    </TheoremCard>
    <TheoremCard class="compact" label="开放问题2.2" title="最小反例" status="open" cite="prob-greathouse-minimal">
      <p><Tex t="n" /> = <span class="mono">1121626023352383</span> 是否是使公式失效的最小 <Tex t="n" />？使公式失效的输入有怎样的刻画？</p>
      <p>trureturing 只证明了这个反例，不主张它最小。</p>
    </TheoremCard>
  </div>
</div>
<Source>D5/S0/Certificates/GreathouseLogTwoFloorRefutation.lean（result : ¬ claim）· 第二章</Source>

---
# 08 定理 2.3：目标恢复
section: "第二章 · 可观测性"
---

<div class="body">
  <p class="kicker">Theorem 2.3</p>
  <h2 class="t">观测能恢复什么：<em>读数相同，目标就必须相同</em></h2>
<TheoremCard class="mt-s" label="定理2.3" title="目标恢复判据" gid="D5/S3/ConceptDynamics/Restoration/TargetRecoveryCriterion.target_recovery_criterion" cite="thm-target-recovery">

设状态空间 $X$ 非空，过程读数 $p: X \to P$，目标 $t: X \to T$。存在恢复函数 $r$ 使 $t = r \circ p$，当且仅当任意两个读数相同的状态有相同的目标值；这又等价于目标缺陷关系为空。

$$\exists\, r,\ t = r \circ p \iff \bigl(p(x) = p(y) \Rightarrow t(x) = t(y)\bigr) \iff \operatorname{defect}(p, t) = \varnothing$$

</TheoremCard>
  <p class="lead mt">边界：定理只断言恢复函数<b>存在</b>，不提供算法，也不给出代价界。</p>
</div>
<Source>D5/S3/ConceptDynamics/Restoration/TargetRecoveryCriterion.lean · 第二章 定理2.3</Source>

---
# 09 输出
section: "输出"
---

<div class="body">
  <p class="kicker">One source, every format</p>
  <h2 class="t">一份 Markdown，<em>六种输出</em></h2>
  <p class="lead">编号、徽章与 Lean 链接在各端一致；中文为权威版本，英文逐条对齐。</p>
  <div class="g3 mt">
    <div class="tile"><i>MDBOOK</i><b>HTML</b><span>在线阅读：KaTeX 数学、中英文切换，定理链接到 Lean 源码。</span></div>
    <div class="tile"><i>TYPST</i><b>PDF</b><span>屏幕版深色、印刷版白底，同一套编号与徽章。</span></div>
    <div class="tile"><i>EPUB 3</i><b>Apple Books</b><span>MathML 数学，在 iPhone、iPad 与 Mac 上阅读。</span></div>
    <div class="tile"><i>TRURETURING-VISUALIZE</i><b>可视化</b><span>交互页面嵌入章节；PDF 与 EPUB 中给出缩略图与地址。</span></div>
    <div class="tile"><i>TRURETURING-FILM</i><b>视频</b><span>脚本、场景与字幕在仓库中，成片随 Release 发布。</span></div>
    <div class="tile now"><i>SLIDEV · 当前</i><b>演示文稿</b><span>就是这一份：在线演示，并附可下载的 PDF。</span></div>
  </div>
</div>
<Source>./tbook build all → build/ 与 _site/（GitHub Pages）</Source>

---
# 10 结尾（cover 版式）
layout: cover
---

<p class="kicker">Read · Verify · Extend</p>
<h1 class="display">书负责解释，<br><em>Lean</em> 负责成立</h1>
<p class="lead">在线阅读，下载 PDF 与 EPUB，或者在所钉的 trureturing 提交上逐条核对每一条定理。</p>
<p class="lead mt mono hl-cyan">./tbook check · ./tbook build all</p>
