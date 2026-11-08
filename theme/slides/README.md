# slidev-theme-trureturing · 演示文稿主题

Slidev 53 主题（chrono-company-slides 方案的赛博朋克版本）。每份演示文稿在 `books/<slug>/slides/<deck>/`：`slides.md` 是书的第一语言（`book.toml` 的 `editions` 第一项，默认中文），其他语言各一个 `slides.<lang>.md`（如 `slides.en.md`），逐页对应，headmatter 写 `theme: ../../../../theme/slides`。不要再建 `slides.<第一语言>.md`（它会被 `slides.md` 遮蔽，检查会报错），也不要用 `src:` 从别的文件导入幻灯片（检查读不到导入的页面，会报错）。

```bash
./tbook slides new <book> <deck> "<中文标题>" "<English title>"   # 从 templates/slides/ 新建
npx slidev books/<book>/slides/<deck>/slides.md                  # 本地预览（改动即时生效）
./tbook check                                                    # 含幻灯片的静态检查
node tools/node/slides-check.mjs                                 # 同上（Node 版，含 UnoCSS 冲突检查）
./tbook build slides --book <book>                               # 构建、逐页版面检查、导出 PDF
```

画布 1920×1080，配色只来自 `theme/generated/tokens.css`；字体随主题打包（Chakra Petch、Noto Sans SC、JetBrains Mono，`@fontsource`，只发 woff2）。绿色只给 Lean 已验证，琥珀色只给“当前”，红色标开放问题，紫色标“有论证、未经内核验证”。

## Headmatter（第一页的 frontmatter）

| 字段 | 说明 |
| --- | --- |
| `theme` | `../../../../theme/slides`（由检查核对） |
| `title` | 浏览器标题与目录页标题；不得含 `<`、`>`、`{{` |
| `info` | 一句话说明 |
| `htmlAttrs.lang` | 语言的 BCP 47 标签：`zh-CN`、`en`（取自 `theme/i18n/<lang>.toml` 的 `meta.bcp47`） |
| `deck.code` | 书代号，如 `GOLDEN//OBSERVE`（页眉、封面） |
| `deck.book` | 书名（页脚、封面） |
| `deck.title` | 这份演示的短标题（页眉、目录页） |
| `deck.version` | 版本（页脚、封面）；各语言一致 |
| `deck.blurb` | 目录页与书落地页上的一句话简介 |

## 版式与每页 frontmatter

- `layout: cover`：封面与结尾。无页眉页脚；自带书代号、所钉 trureturing 提交、HUD 表盘与页码。正文放 `p.kicker`、`h1.display`、`p.lead`。
- `layout: section`：章节页。`chapter: "01"` 为大号描边编号；正文放 `p.kicker`、`h2.t`、`p.lead`，可再放一张卡片。
- 默认版式：页眉（书代号 // 标题，右侧 `section`）与页脚（书名 · 版本、所钉提交、页码）。`bare: true` 去掉页眉页脚。
- 各语言版本逐页的 `layout`、`bare`、`chapter`、`class` 与 `section` 是否存在必须一致。

## 组件

| 组件 | 用法 |
| --- | --- |
| `<LeanBadge gid="<GID>" />` | 绿色 `LEAN ✓`（链接到所钉提交上的 Lean 源码），仅当 `trureturing.lock.json` 把该 GID 解析为 Lean `theorem`；锁文件中没有的 GID 显示红色 `UNVERIFIED`。`kind="definition"` → 青色 `LEAN DEF`（Lean 定义，中性样式，不是“已验证”）。`status="open"` → 红色 `OPEN`；`status="argued"` → 紫色 `ARGUED`。 |
| `<TheoremCard label="定理1.3" title="…" gid="<GID>" cite="thm-…">` | 定理卡：编号、标题、徽章、陈述（默认插槽，前后空一行，可写 Markdown 与 `$…$`）、Lean 名。`cite` 指向书中的环境 id，`./tbook check` 据此核对编号与 GID。`kind="definition"` 用于定义：`gid` 可以是 Lean 定义，卡片为青色中性样式与 `LEAN DEF`，从不显示绿色 `LEAN ✓`；`status="open"` 用于开放问题（不得带 `gid`）。 |
| `<Stat value="4" label="…" tone="ok" />` | 大号数字。`tone`：`cyan`（默认）、`magenta`、`ok`、`warn`、`violet`、`amber`。 |
| `<Source>…</Source>` | 页面底部的出处行。 |
| `<Tex t="\beta(n)" />`、`<Tex display t="…" />` | HTML 块里的 KaTeX（HTML 块中 `$…$` 不会被处理）。 |
| `<PageNo />` | 自带版式页面的“当前页 / 总页数”。 |

GID 只能引用锁文件中已有的声明，且必须是 Lean `theorem`，除非写了 `kind="definition"`：写好后运行 `./tbook pin --refresh`（它也收集幻灯片引用的 GID），再 `./tbook check`。组件写成 `<lean-badge>`、`<theorem-card>` 等 Vue 认可的其他写法时同样受检查。代码块里的标签只作为代码显示，不受检查；代码块之外（包括两个代码块之间）的每个标签都受检查。代码块按 Slidev 所用 markdown-it 的 CommonMark 规则逐行识别：围栏缩进不超过 3 列，可在块引用、列表项与脚注中，随所在容器结束；HTML 块里的 ```` ``` ```` 不是围栏（`tools/tbook/slides.py` 的 `code_lines` 与 `tools/node/slides-lib.mjs` 的 `codeLines` 是同一算法）。

## 样式类（`styles/deck.css`）

`.body`（正文区，`.center` 垂直居中）、`.kicker`、`.display`、`h2.t`（`em` 高亮；`em.warn`、`em.ok`、`em.magenta`）、`.lead`、`.card`（`.hot`、`.ok`、`.warn`、`.violet`）、`.tile`（`.now` 表示“当前”）、`.flow > .step`（`.ok`）、`.readout`（`dt`/`dd`，`dd.cy`、`dd.hot`）、`.g2`/`.g3`/`.g4`/`.g6`/`.split`/`.row`、`ul.plain`、`table.t`、`.eq`、`.mono`、`.muted`、`.dim`、`.sm`、`.xs`、`.hl-cyan`/`.hl-ok`/`.hl-warn`/`.hl-violet`/`.hl-amber`/`.hl-magenta`、`.mt-s`/`.mt`/`.mt-l`。其中与 UnoCSS 工具类同名的主题类（`mt`、`mb-0`、`grow`）已列入 `uno.config.ts` 的 `blocklist`，可以放心使用。不要自创与 UnoCSS 工具类同名的类（如 `c-*`、`p-4`）：`node tools/node/slides-check.mjs` 会报出不在 `blocklist` 中的冲突；确需新增主题类时，同时把它加入 `blocklist`。

## 界面文字

徽章、页脚标签与站点按钮的文字取自 `theme/i18n/<lang>.toml` 的 `[slides]` 表（书库可在 `i18n/<lang>.toml` 覆盖）；`i18n.ts` 中的默认值只作后备。
