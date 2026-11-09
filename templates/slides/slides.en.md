---
# 01 Cover (cover layout: no header or footer; shows the book code, the pinned commit and the page)
# Preview: npx slidev <this file>; build and check: ./tbook build slides --book <book>; rules: skills/book-slides
theme: {{THEME}}
title: "{{BOOK}} · {{TITLE}}"
info: "{{TITLE}}: one sentence on what this deck covers and for whom."
htmlAttrs:
  lang: "{{LANG}}"
deck:
  code: "{{CODE}}"
  book: "{{BOOK}}"
  title: "{{TITLE}}"
  version: "{{VERSION}}"
  blurb: "One-line summary, shown in the slides index and on the book's landing page."
layout: cover
---

<p class="kicker">{{BOOK_HTML}}</p>
<h1 class="display">{{TITLE_HTML}}</h1>
<p class="lead">One sentence on what this deck is about.</p>

---
# 02 Content: section appears on the right of the header; slides with facts name a <Source>
section: "Section"
---

<div class="body">
  <p class="kicker">Section</p>
  <h2 class="t">Write the title as a <em>claim</em></h2>
  <p class="lead">Lead: a sentence or two.</p>
  <div class="g3 mt">
    <div class="card"><h4>Point one</h4><p>Explanation.</p></div>
    <div class="card"><h4>Point two</h4><p>Explanation.</p></div>
    <div class="card hot"><h4>Point three</h4><p>Explanation.</p></div>
  </div>
</div>
<Source>A chapter of the book, or a Lean module in trureturing.</Source>

---
# 03 Theorem slide. Write a theorem as
#      <TheoremCard label="Theorem 1.1" title="…" gid="<GID>" cite="thm-…">(blank line) statement (blank line)</TheoremCard>
#    label and cite match the book; gid must be in trureturing.lock.json (cite it in the book, then ./tbook pin --refresh).
#    Unproved claims take status="open" (red OPEN); arguments not verified in Lean take status="argued" (violet).
section: "Theorem"
---

<div class="body">
  <p class="kicker">Open problem</p>
  <h2 class="t">An unproved claim is an <em class="warn">open problem</em></h2>
<TheoremCard class="mt" label="Open problem" title="Title" status="open">

Statement; inline math is written $x^2$.

</TheoremCard>
</div>

---
# 04 Closing (cover layout)
layout: cover
---

<p class="kicker">{{CODE_HTML}}</p>
<h1 class="display">{{TITLE_HTML}}</h1>
<p class="lead">Read the book online, or check every theorem at the pinned trureturing commit.</p>
