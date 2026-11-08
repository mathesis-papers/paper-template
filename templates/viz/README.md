# 可视化起始模板 · Visualization starter

`./tbook viz new <book> <id> "<CODE//NAME>" "<中文标题>" "<English title>"`（或 `node tools/node/viz-new.mjs …`）从本目录生成
`books/<book>/viz/<id>/{index.html,style.css,main.js}` 与 `books/<book>/viz/tests/<id>.test.mjs`，并在注册表里登记为 `draft`。
本 README 不会被复制。方案沿用 [trureturing-visualize](https://github.com/the-omega-institute/trureturing-visualize)：
纯 HTML/CSS/JS，无构建步骤，只用相对链接；共享运行时在 `theme/viz/`（发布为 `<slug>/viz/assets/`）。

`./tbook viz new …` scaffolds a page from this directory and registers it as a draft. The scheme is that of
trureturing-visualize: plain HTML/CSS/JS, no build step, relative links only; the shared runtime lives in `theme/viz/`
and is published as `<slug>/viz/assets/`.

## 注册表 · Registry (`books/<book>/viz/visualizations.json`)

```json
{
  "version": 1,
  "visualizations": [
    {
      "id": "golden-carry",
      "code": "GOLDEN//CARRY",
      "title": "黄金进位 · …", "title_en": "Golden carry · …",
      "summary": "…", "summary_en": "…",
      "path": "golden-carry/", "thumbnail": "golden-carry/thumb.jpg",
      "status": "live",
      "added": "2026-11-08",
      "tags": ["进位"], "tags_en": ["carries"],
      "theory": [
        { "label": "本书第一章", "label_en": "Chapter 1", "href": "../zh/ch01-golden-deficit.html", "href_en": "../en/ch01-golden-deficit.html" },
        { "label": "Blueprint", "label_en": "Blueprint", "href": "{trureturing}/Blueprint/D5/S1/Deficit/DeficitThreeValued.md" }
      ],
      "lean": [ { "gid": "D5/S1/Deficit/DeficitThreeValued.deficit_three_valued" } ]
    }
  ]
}
```

| 字段 field | 规则 rule |
| --- | --- |
| `id` | kebab-case，等于目录名；不能是 `tests`、`assets` |
| `path` / `thumbnail` | 相对 `viz/`：`<id>/` 与 `<id>/thumb.jpg`（1280×720，`node tools/node/viz-thumbs.mjs <book> <id>`） |
| `status` | `draft`（不发布，不可嵌入书中）或 `live`（需要 `title_en`、`summary`、`summary_en`、至少一条 `theory`、缩略图；应有浏览器测试） |
| `tags_en` | 逐条翻译 `tags` |
| `theory[].href` | `https://…`；`{trureturing}/<path>`（所钉提交上的该文件，必须存在）；或本书章节，相对 `viz/`：`../zh/<chapter>.html`；`href_en` 可选 |
| `lean[].gid` | 必须在 `trureturing.lock.json` 中（写好后运行 `./tbook pin --refresh`，它也收集可视化引用的 GID）；链接由构建固定到所钉提交；`label` 可选 |

## 页面契约 · Page contract (checked by `./tbook check` and `node tools/node/viz-validate.mjs`)

- `<body data-viz-id="<id>">`；`<html data-title-en="…">` 与 `<title>`。
- `<link rel="stylesheet" href="../assets/theme.css">`；`<head>` 内 `<script src="../assets/shell.js"></script>`（`window.TRV`）。
- `<a class="crumb" href="../">` 返回本书的可视化索引；语言切换 `data-lang-set="zh"` / `data-lang-set="en"`。
- 所有可见文字成对：`<span class="zh">…</span><span class="en">…</span>`；脚本文字用 `TRV.L('中文', 'English')` 并在 `TRV.onLang(…)` 中重绘；`aria-label` 写中文、`data-aria-en` 写英文。
- Lean 引用写成 `<a data-lean-gid="<GID>" href="…">`，其他 trureturing 文件写成 `<a data-trureturing-path="<path>" href="…">`：构建与本地预览把 href 固定到所钉提交。只有 Lean 已验证的定理用绿色 `LEAN ✓`；页面计算用 `.lean.num`（NUM）；示意模型 `.lean.model`；开放问题 `.lean.open`。
- 颜色只来自令牌：CSS 用 `var(--cyan)` 等（映射到 `--tr-*`），脚本用 `TRV.palette` / `TRV.rgb`。琥珀色只给“现在/当前选择”。
- `?embed=1`（书中 iframe）隐藏页眉；`?thumb=1`（缩略图）让 `[data-thumb]` 充满画面，页面可定义 `window.TRV_THUMB()`。
- 手机宽度（390px）无横向滚动；尊重 `prefers-reduced-motion`。

## 嵌入书中 · Embedding in a chapter

```markdown
::: {.viz src="golden-carry" height="560"}
图注（可选，可含数学）。
:::
```

HTML：`<iframe>` 指向 `../viz/<id>/index.html?embed=1&lang=<lang>`，附“全屏打开”。PDF/EPUB：缩略图、图注与在线地址。

## 工具 · Tools

```bash
node tools/node/viz-server.mjs                 # local preview at http://127.0.0.1:8766/site/<book>/viz/
node tools/node/viz-validate.mjs [book]        # registry + page contract + links + JS syntax
node tools/node/viz-test.mjs [book] [--shard i/n]   # browser suites books/*/viz/tests/*.test.mjs
node tools/node/viz-thumbs.mjs <book> [id …]   # 1280×720 thumb.jpg (honours PW_CHROMIUM_PATH)
./tbook viz list
```
