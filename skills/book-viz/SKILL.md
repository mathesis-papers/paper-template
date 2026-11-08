---
name: book-viz
description: 为书做交互可视化时使用：按 trureturing-visualize 方案新建、编写、测试、登记并嵌入书内可视化（纯 HTML/CSS/JS、双语、赛博朋克令牌配色、Lean 引用固定到所钉提交），或嵌入 trureturing-visualize 的现成页面。
---

# 交互可视化

## 适用范围

**用**：书中某一节需要可操作的对象（滑块、热图、逐步动画）帮助理解；修改或排查已有可视化；把可视化嵌入章节。

**不用**：静态插图（放 `books/<slug>/assets/`，章节里写图片）；视频（`book-film`）；演示文稿（`book-slides`）。

**权威**：`templates/viz/README.md`（登记表字段与页面契约）、`tools/tbook/viz.py` 的文档字符串、示例 `books/example-monograph/viz/golden-carry/`。

## 原则

1. **可视化只改变看法，不证明任何东西。** 页面上能写 `LEAN ✓` 的只有锁文件中的 `theorem`；页面上的数值计算标 `NUM`（`.lean.num`），示意模型标 `.lean.model`，开放问题标 `.lean.open`。
2. **数字必须真实。** 页面上显示的每个数都由页面精确算出（或取自所钉提交），不编造“实验结果”。
3. **双语逐条成对。** 每段可见文字都写成 `<span class="zh">…</span><span class="en">…</span>`；脚本文字用 `TRV.L('中文', 'English')`，并在 `TRV.onLang(…)` 中重绘。
4. **颜色只来自令牌**（`var(--cyan)` 等，脚本用 `TRV.palette`）。绿色只给 Lean 已验证；琥珀色只给“现在/当前选择”；红色标开放问题。
5. **只用相对链接**；Lean 与 trureturing 文件链接写成 `data-lean-gid` / `data-trureturing-path`，由构建固定到所钉提交。

## 流程

```bash
./tbook viz new <book> <id> "<CODE//NAME>" "<中文标题>" "<English title>"   # 生成 viz/<id>/ 与 viz/tests/<id>.test.mjs，登记为 draft
node tools/node/viz-server.mjs                       # http://127.0.0.1:8766/site/<book>/viz/<id>/（?embed=1、?thumb=1、?lang=en）
```

1. 在 `books/<book>/viz/<id>/` 中编写 `index.html`、`style.css`、`main.js`。先读 `golden-carry` 的写法：共享运行时 `../assets/theme.css`、`../assets/shell.js`（`window.TRV`）、`<body data-viz-id="<id>">`、语言切换 `data-lang-set`、返回索引的 `a.crumb`。
2. 支持 `?embed=1`（书中 iframe，隐藏页眉）与 `?thumb=1`（缩略图，`[data-thumb]` 充满画面，可定义 `window.TRV_THUMB()`）；手机宽度 390px 无横向滚动；尊重 `prefers-reduced-motion`。
3. 完善登记表 `books/<book>/viz/visualizations.json`：`title_en`、`summary`/`summary_en`、`tags`/`tags_en`、至少一条 `theory`（本书章节写 `../zh/<chapter>.html`，trureturing 文件写 `{trureturing}/<path>`）、`lean`（GID 列表）。
4. 写浏览器测试 `books/<book>/viz/tests/<id>.test.mjs`（参照 `golden-carry.test.mjs`：交互、双语、无控制台错误、无横向滚动、关键数值）。
5. 生成缩略图并转为发布状态：

   ```bash
   node tools/node/viz-test.mjs <book>
   node tools/node/viz-thumbs.mjs <book> <id>      # 1280×720 thumb.jpg，提交入库
   ```

   把登记表中的 `"status"` 改为 `"live"`（`draft` 不发布，也不能嵌入书中）。
6. 新引用了 GID 时运行 `./tbook pin --refresh`（它收集可视化引用的 GID），然后：

   ```bash
   node tools/node/viz-validate.mjs <book>
   ./tbook check
   ```

7. 嵌入章节——**所有语言版本都要加**，位置与 `src` 相同，只翻译图注：

   ```markdown
   ::: {.viz src="<id>" height="560"}
   图注（可含数学与 [@thm-…] 引用）。
   :::
   ```

   外部页面：`::: {.viz src="trureturing-visualize:<id>"}`。HTML 中为 iframe + “全屏打开”；PDF/EPUB 中为缩略图、图注与在线地址。
8. 构建并查看：`./tbook build html site --book <book> && ./tbook serve`，在中英文、深浅主题、手机宽度下各看一次；`./tbook build pdf --book <book>` 检查 PDF 中的缩略图面板。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| `check` 报 draft 不能嵌入 | 完成第 5 步，把状态改为 `live` |
| `LEAN ✓` 链接 404 或 GID 未登记 | GID 不在锁文件中：`./tbook pin --refresh`；GID 必须是已冻结的声明 |
| iframe 内显示完整页眉 | 页面没有处理 `?embed=1`（共享运行时会处理，确认引用了 `shell.js`） |
| 缩略图过期 | 重新运行 `viz-thumbs.mjs`；CI 不重新生成缩略图 |
| 手机宽度横向滚动 | 网格列用 `minmax(0, 1fr)`，长数字允许换行 |

## 完成标准

`viz-validate`、`viz-test`、`./tbook check` 全部通过；登记表为 `live` 且有缩略图；各语言章节都已嵌入；在站点与 PDF 中实际看过。
