# 写作手册 · Authoring guide

本手册面向书的作者（人或 agent）。语法规范见 `docs/ARCHITECTURE.md` §3；这里给出完整示例与常见问题。示例书 `books/example-monograph/` 用到了这里的每一种写法。

## 1. 一本书的组成

```
books/<slug>/
  book.toml          元数据
  zh/SUMMARY.md      中文目录（权威版本，默认）
  zh/*.md            中文章节
  en/SUMMARY.md      英文目录（文件名与中文一致）
  en/*.md            英文章节
  assets/            共享图片
  viz/ films/ slides/  可选媒体
```

### `book.toml`

| 字段 | 说明 |
| --- | --- |
| `book.version` | 语义化版本，进入下载文件名与 Release |
| `book.editions` | 语言版本，第一个为权威版本，默认 `["zh", "en"]` |
| `book.title` / `subtitle` / `description` | 每种语言一行：`zh = "…"`、`en = "…"` |
| `book.authors`、`license`、`isbn`（按语言）、`date` | 进入版权页与 EPUB 元数据 |
| `book.code` | 封面与站点卡片上的代号，形如 `GOLDEN//OBSERVE` |
| `outputs.html` / `pdf` / `epub` | 输出开关；`pdf = ["screen", "print"]` |
| `pdf.paper` | Typst 纸张名（`a4`、`a5`、`us-letter`、`iso-b5`…） |
| `epub.embed_fonts` | 是否嵌入标题与等宽字体 |

### `SUMMARY.md`

与 mdBook 相同：

```markdown
# Summary

[前言](README.md)              ← 前言类（无编号；其中的定理编号为 0.n）

- [第一章 …](ch01.md)          ← 编号章节（定理编号 1.n）
  - [1.1 …](ch01/section.md)   ← 嵌套小节（编号仍归第一章）
- [第二章 …](ch02.md)

[附录 A …](appendix-a.md)      ← 附录类（无编号；其中的定理编号为 A.n）
```

书末的“形式化验证账本”由构建自动追加，不要写进 SUMMARY。章节标题按行内 Markdown 读，转义与数学的显示规则见 §2（`[C\*-代数](ch03.md)` 显示为 C*-代数）。

## 2. 环境

```markdown
::: {.theorem #thm-deficit-three-valued title="亏量只取三个值" lean="D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"}
对所有自然数 $v_1, v_2$，
$$
c(v_1, v_2) \in \{-1, 0, 1\}.
$$
:::
```

| 种类 | 用途 | `lean` |
| --- | --- | --- |
| `theorem` `lemma` `proposition` `corollary` | 已在 Lean 中证明的结论 | 必须 |
| `definition` | 定义 | 建议（指向 Lean `def`） |
| `conjecture` `problem` | 猜想、开放问题 | 禁止 |
| `example` `remark` | 例子、注记 | 可选 |
| `proof` | 证明思路（不编号） | 可选 |

- 一个结论由多条 Lean 声明共同给出时：`lean="GID1 GID2"`。
- `title` 是一行行内 Markdown，可含行内数学：`title="$\beta$ 不保持加法"`。属性值里反斜杠与花括号原样保留；值里的双引号写 `\"`，`\\` 读作一个反斜杠（TeX 的 `\\` 要写成 `\\\\`）。
- 标题的显示规则（环境标题与 SUMMARY 中的章节标题相同）：`$…$` 内是 TeX，原样保留；`$…$` 外，反斜杠加 ASCII 标点是 Markdown 转义，各端（HTML 页头、侧栏、页面 `<title>`、站点目录、PDF、EPUB、账本）都只显示标点本身：`C\*-代数` 显示为 C*-代数，`snake\_case` 显示为 snake_case，`\$5` 显示为 $5 且不会成为公式。除行内数学与 `[@id]` 外，不要在标题里用强调、行内代码等格式：HTML 页头、侧栏与站点把它们当作纯文字，PDF/EPUB 却会排版，两端不一致。
- `title` 中可以引用别的条目：`title="[@thm-deficit-three-valued] 的推广"` 显示为“定理1.3 的推广”（PDF/EPUB 中带链接）。id 不存在时 `./tbook check` 报错。
- 环境可以嵌套（例如 `remark` 里放 `example`），但不要把 `proof` 放进定理内部——写在定理之后。

### 选择正确的 GID

1. 在 trureturing 中找到声明所在文件 `D5/…/Module.lean`，模块路径就是 `D5/…/Module`。
2. 声明名写完整 Lean 名或其唯一后缀：`deficit_three_valued` 或 `Deficit.deficit_three_valued`。模块的命名空间不一定等于模块路径（如 `DeficitThreeValued.lean` 的命名空间是 `D5.S1.Deficit`），后缀匹配会处理这一点。`of_ρ_eq_self`、`mk₂`、`isSome?` 这样的名字照原样写；不是 Lean 标识符的分量写成 `«…»`。
3. 确认 `Golden/Frozen/state/D5/…/Module.lean.json` 存在。不存在 → 模块未冻结，不能引用。
4. 新增 GID 后运行 `./tbook pin --refresh`。

## 3. 数学

- 行内 `$…$`；开头的 `$` 后不能是空格，结尾的 `$` 前不能是空格、后面不能紧跟数字（所以“价格 $5”不会被当作公式）。
- 块级 `$$` 各占一行，前后空行；多行推导用 `aligned`。
- 不用 `\(`、`\)`、`\[`、`\]`。
- 字面美元号写 `\$`。
- 预设宏（`\norm`、`\floor`、`\ceil`、`\Tr`、`\tr`、`\diag`、`\ketbra`、`\dyad`、`\vv`、`\nicefrac` 等）只在 `tools/tbook/mathrender.py` 的 `TEX_MACROS` 中定义：HTML 端交给 KaTeX，PDF/EPUB 端由 Pandoc 作为 `\newcommand` 展开，三端渲染一致（环境标题中也可用）。其他宏请写成标准 LaTeX 数学命令。
- `\|` 是范数竖线，表格单元格里也一样；绝对值写 `|x|`。

## 4. 引用与链接

| 写法 | 结果 |
| --- | --- |
| `[@thm-deficit-three-valued]` | “定理1.3”，链接到该定理（跨章节可用） |
| ``[`deficit_three_valued`](lean:D5/S1/Deficit/DeficitThreeValued.deficit_three_valued)`` | 指向所钉提交上 Lean 源文件对应行的永久链接 |
| `[该定理][lt]` + `[lt]: lean:D5/…/Module.name` | 引用式写法，同上；尖括号 `(<lean:…>)` 与自动链接 `<lean:…>`（显示为 GID）也可以。各种写法见表下说明 |
| `[第二章](ch02-refutation-observation.md)` | 章节链接（HTML 为页面链接，PDF/EPUB 为内部跳转） |
| `[观测能恢复什么](ch02-refutation-observation.md#观测能恢复什么)` | 章节内标题：片段按目标章节内的标题解析（与 HTML 相同），各章都有的同名标题（如“小结”）不会串章；片段照抄 HTML 页面上的锚点即可，标题含公式或脚注时也一样（`## 关于 $\beta$ 的估计` 的片段是 `#关于-β-的估计`；`## 注释[^a]` 的片段是 `#注释1`，数字是该脚注在本章的编号） |
| `![图注](../assets/figure.svg)` | 图片；放在 `assets/` 的图各语言共享 |
| `![图注][fig]` + `[fig]: ../assets/figure.svg` | 引用式图片，同上 |
| `![图注](<../assets/有 空格.svg>)` | 路径含空格时用尖括号 |
| `[数据表](../assets/data.csv)` | 文件下载：HTML 指向复制进 `_book/` 的文件；PDF/EPUB 不能内嵌非图片文件，改为指向网站上的同一文件（需要 `site.toml` 的 `base_url` 或可推断的 repo，否则只保留文字并警告） |

脚注 `[^1]` 在每章内独立（PDF/EPUB 合并全书时自动加章节前缀）；`@` 只在 `[@id]` 中表示引用，正文里的 `@name` 是普通文字。

代码块里的内容各端都照原样显示，其中的脚注、链接、图片、`[@id]`、`lean:` 链接与公式都不改写、不检查。代码块有两种：围栏代码块（```` ``` ```` 或 `~~~`），与缩进代码块。缩进代码块是比所在位置的内容再缩进四格（一个制表符算四格）的行，所在位置可以是顶层、列表项、块引用、脚注或定义（`:` 开头的行）的正文；列表项的内容从标记后的第一个字算起，所以 `1. 运行：` 下的代码缩进七格，`- 步骤` 下缩进六格，只与内容对齐的缩进行是该项的下一段；脚注的正文缩进四格，其中的代码缩进八格。缩进行紧接在段落行下面时仍属于该段落，代码块前要空一行。

引用式链接定义（`[fig]: ../assets/x.svg "标题"`）必须独占一行（也可以在列表项或块引用里），地址后只能跟可选的标题：`"…"`、`'…'` 或 `(…)`，其中可用反斜杠转义（`"Knuth 的 \"进位\" 图"`），与 CommonMark 相同；`[注]: 原图见 [fig](../assets/x.svg)`、`[1]: Knuth, TAOCP.` 这样后接正文的行是普通段落，在列表项（`- [1]: Knuth, TAOCP.`）、块引用或列表的续行里也一样，各端都显示，其中的链接照常处理。

`lean:` 链接可以用 CommonMark 的任何单行写法：行内或尖括号地址、带 `"…"`、`'…'` 或 `(…)` 标题、链接文字里有成对的方括号（`[x [y] z](lean:…)`）、链接里套图片、自动链接 `<lean:…>`，或引用式定义（也可以在列表项或块引用里）。每种写法的 GID 都由 `./tbook check` 核对、由 `./tbook pin --refresh` 收录。链接必须写在一行内：链接文字、地址或标题跨行，定义的地址写在下一行，以及原始 HTML 里的 `lean:` 地址，工具都读不到，`./tbook check` 报错；构建时去掉这样的 `lean:` 地址（链接只留文字，定义与 HTML 属性的地址写成 `#`），任何输出都没有 `lean:` 地址。环境标题里不能放 `lean:` 链接：`./tbook check` 报错，各端只显示链接文字。

HTML 注释 `<!-- … -->` 不出现在任何输出中：其中的图片、链接、`[@id]`、`lean:` 链接与环境都不改写、不检查、不编号，适合放待补的图。注释有两种：

- 注释块：以 `<!--` 开头（最多缩进三格；在列表项等容器中从其内容算起）且本行没有 `-->` 的行，到含 `-->` 的那一行为止。这一整行都按注释处理，所以 `-->` 后面不要接正文（mdBook 会把它当作原始 HTML 原样输出，其中的链接与 `[@id]` 既不改写也不检查）。没有 `-->` 时 `./tbook check` 报错。
- 行内注释：其他位置的 `<!--`，到 `-->` 为止，可以跨行，但只在同一段落内。段落在 `-->` 之前结束（空行、标题、新的列表项、代码块等）时，这个 `<!--` 只是普通文字，HTML 照原样显示；Pandoc 却会一直隐藏到后文的下一个 `-->`，PDF/EPUB 因此与 HTML 不一致，所以后文还有 `-->` 时 `./tbook check` 给出警告。

缩进代码块与行内代码里的 `<!--` 是代码，不开始注释。

## 5. 媒体

```markdown
::: {.viz src="golden-carry" height="560"}
图注：拖动滑块观察进位。
:::

::: {.film src="001-golden-deficit"}
:::

::: {.slides src="overview"}
:::
```

外部资源：`src="trureturing-visualize:<id>"`、`src="trureturing-film:film-001-v1"`。HTML 中为交互嵌入或播放器；PDF/EPUB 中为缩略图/海报加在线地址。媒体块在各语言版本中也必须一一对应。

## 6. 多语言流程

1. 在权威版本（默认中文）中写作、通过 `./tbook check`。
2. 把改动同步到其他语言：相同的文件、相同的环境顺序、相同的 `#id` 与 `lean`。只有正文、标题、图注是翻译的。
3. 再次 `./tbook check`：任何不一致都会报出“item N differs between editions”。
4. 英文要自然、准确。理论术语以 trureturing 的英文名称为准（Lean 声明名、Blueprint 标题）。

## 7. 诚实标注

- 只有 `LEAN ✓` 的条目是已验证结论；正文中不要手写“已证明”“已验证”来修饰未引用 Lean 的命题。
- 构建只在锁文件确认每条 GID 都是已冻结的 Lean 定理时显示 `LEAN ✓`；否则显示红色 `UNVERIFIED`（徽章在各端都不是链接），也不计入“LEAN ✓ n”等统计（`./tbook check` 会报错，不能发布）。页脚与账本只给锁文件解析了的声明链接（例如误引的 Lean 定义，链接到它的源码），锁文件没有的 GID 显示为不带链接的文字。
- 不把存在性写成可构造，不把一个反例写成最小反例，不把示意图的数值写成实验或模拟结果。
- 引用文献中的结论而 trureturing 尚未形式化时，写成 `remark` 并注明“文献结果，未在本书形式化”，不要用 `theorem`。

## 8. `./tbook check` 常见报错

| 报错 | 处理 |
| --- | --- |
| `theorem #… cites no Lean declaration` | 加 `lean="…"`；若未证明，改为 `conjecture` |
| `… is not in trureturing.lock.json` | `./tbook pin --refresh` |
| `module … is not frozen at …` | 该模块在所钉提交上没有状态片：换一个已冻结的声明，或先在 trureturing 中完成冻结，再 `./tbook pin` |
| `no frozen declaration named …` / `ambiguous` | 检查名字；歧义时写更长的后缀 |
| `is a Lean def, but theorem-like environments must cite theorems` | 定义请用 `definition` 环境 |
| `item N differs between editions` | 对齐各语言版本的环境序列 |
| `[@x] refers to no environment` | 检查 id 拼写；id 只在同一语言版本内解析（正文与环境标题中的 `[@x]` 都会检查） |
| `cannot parse this fenced div opening line` | 检查 `::: {…}` 中的引号是否成对；值内的 `"` 写成 `\"` |
| `HTML comment is never closed` | 给以 `<!--` 开头的注释补上 `-->`；否则其后的全部内容都算作注释 |
| `'<!--' … is not closed in its paragraph`（警告） | 在同一段落内补上 `-->`；要显示字面的 `<!--`，写成行内代码 `` `<!--` `` |
| `pinned commit … is not on branch 'dev'` | 所钉提交未合入 `site.toml` 的 trureturing 分支（默认 `dev`）：改钉该分支上的提交（`./tbook pin`） |
| `could not verify that pinned commit …` | 设置 `TRURETURING_DIR` 指向含该提交的 checkout（必要时先 `git fetch`），或联网让 GitHub API 回答（设置 `GITHUB_TOKEN` 可免匿名限额）；GitHub Actions 中这是错误 |
| `not listed in SUMMARY.md` | 加入 SUMMARY 或删除文件 |
