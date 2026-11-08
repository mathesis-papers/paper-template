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

书末的“形式化验证账本”由构建自动追加，不要写进 SUMMARY。

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
- `title` 可含行内数学：`title="$\beta$ 不保持加法"`。
- 环境可以嵌套（例如 `remark` 里放 `example`），但不要把 `proof` 放进定理内部——写在定理之后。

### 选择正确的 GID

1. 在 trureturing 中找到声明所在文件 `D5/…/Module.lean`，模块路径就是 `D5/…/Module`。
2. 声明名写完整 Lean 名或其唯一后缀：`deficit_three_valued` 或 `Deficit.deficit_three_valued`。模块的命名空间不一定等于模块路径（如 `DeficitThreeValued.lean` 的命名空间是 `D5.S1.Deficit`），后缀匹配会处理这一点。
3. 确认 `Golden/Frozen/state/D5/…/Module.lean.json` 存在。不存在 → 模块未冻结，不能引用。
4. 新增 GID 后运行 `./tbook pin --refresh`。

## 3. 数学

- 行内 `$…$`；开头的 `$` 后不能是空格，结尾的 `$` 前不能是空格、后面不能紧跟数字（所以“价格 $5”不会被当作公式）。
- 块级 `$$` 各占一行，前后空行；多行推导用 `aligned`。
- 不用 `\(`、`\)`、`\[`、`\]`。
- 字面美元号写 `\$`。
- 自定义宏：HTML 端支持 KaTeX 预设宏（见 `tools/node/katex-render.mjs`）；PDF 端由 Pandoc 转换，尽量只用标准 LaTeX 数学命令。

## 4. 引用与链接

| 写法 | 结果 |
| --- | --- |
| `[@thm-deficit-three-valued]` | “定理 1.3”，链接到该定理（跨章节可用） |
| ``[`deficit_three_valued`](lean:D5/S1/Deficit/DeficitThreeValued.deficit_three_valued)`` | 指向所钉提交上 Lean 源文件对应行的永久链接 |
| `[第二章](ch02-refutation-observation.md)` | 章节链接（HTML 为页面链接，PDF/EPUB 为内部跳转） |
| `![图注](../assets/figure.svg)` | 图片；放在 `assets/` 的图各语言共享 |

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
| `[@x] refers to no environment` | 检查 id 拼写；id 只在同一语言版本内解析 |
| `not listed in SUMMARY.md` | 加入 SUMMARY 或删除文件 |
