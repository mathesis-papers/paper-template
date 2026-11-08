---
# 01 封面（cover 版式：无页眉页脚，自带书代号、所钉提交与页码）
# 预览：npx slidev <本文件>；构建与检查：./tbook build slides --book <书>；规则见 skills/book-slides
theme: {{THEME}}
title: "{{BOOK}} · {{TITLE}}"
info: "{{TITLE}}：一句话说明这份演示讲什么、给谁看。"
htmlAttrs:
  lang: "{{LANG}}"
deck:
  code: "{{CODE}}"
  book: "{{BOOK}}"
  title: "{{TITLE}}"
  version: "{{VERSION}}"
  blurb: "一句话简介，显示在幻灯片目录与书的落地页。"
layout: cover
---

<p class="kicker">{{BOOK_HTML}}</p>
<h1 class="display">{{TITLE_HTML}}</h1>
<p class="lead">一句话说明这份演示讲什么。</p>

---
# 02 正文：section 显示在页眉右侧；含事实的页面在底部用 <Source> 写出处
section: "章节"
---

<div class="body">
  <p class="kicker">Section</p>
  <h2 class="t">标题写成一个<em>判断</em></h2>
  <p class="lead">导语：一两句话。</p>
  <div class="g3 mt">
    <div class="card"><h4>要点一</h4><p>说明。</p></div>
    <div class="card"><h4>要点二</h4><p>说明。</p></div>
    <div class="card hot"><h4>要点三</h4><p>说明。</p></div>
  </div>
</div>
<Source>书的章节，或 trureturing 中的 Lean 模块。</Source>

---
# 03 定理页。定理写成
#      <TheoremCard label="定理1.1" title="…" gid="<GID>" cite="thm-…">（空行）陈述（空行）</TheoremCard>
#    label 与 cite 和书中一致；gid 必须在 trureturing.lock.json 中（先在书中引用，再运行 ./tbook pin --refresh）。
#    未证的结论写 status="open"（红色 OPEN），只有论证、未经 Lean 验证的写 status="argued"（紫色）。
section: "定理"
---

<div class="body">
  <p class="kicker">Open problem</p>
  <h2 class="t">尚未证明的结论写成<em class="warn">开放问题</em></h2>
<TheoremCard class="mt" label="开放问题" title="标题" status="open">

陈述；行内数学写成 $x^2$。

</TheoremCard>
</div>

---
# 04 结尾（cover 版式）
layout: cover
---

<p class="kicker">{{CODE_HTML}}</p>
<h1 class="display">{{TITLE_HTML}}</h1>
<p class="lead">在线阅读本书，或在所钉的 trureturing 提交上核对每一条定理。</p>
