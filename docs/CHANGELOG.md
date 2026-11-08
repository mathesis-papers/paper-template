# Changelog

本文件记录 trureturing-books-template 的版本变化，格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。下游升级时请阅读跨越的所有版本，处理标为“需要手动操作”的条目。

## [Unreleased]

### 变更

- 标题按行内 Markdown 读：环境标题与 SUMMARY 章节标题中 `$…$` 之外的反斜杠转义（`C\*-代数`、`\$5`）在 HTML 页头、侧栏、`<title>`、站点、PDF、EPUB 与账本中都显示为标点本身，`$…$` 内的 TeX 不变。此前 HTML 与站点保留反斜杠；SUMMARY 中 `$…$` 外的 `\{` 现在显示为 `{`。
- HTML 注释中的内容不再被改写、检查或编号（含注释块里的环境）；以 `<!--` 开头的注释块没有 `-->` 时 `./tbook check` 报错。行内注释可以跨行，到同一段落内的 `-->` 为止，HTML、PDF、EPUB 都隐藏它；段落在 `-->` 之前结束时 `<!--` 是普通文字，后文还有 `-->` 时 `./tbook check` 警告（Pandoc 会一直隐藏到那里）。
- 代码块按 CommonMark 判定，各端一致：缩进代码块在任何容器（列表项、块引用、脚注、定义）中都是代码，其中的 `[@id]`、`lean:` 链接、图片、链接与公式各端原样显示，`./tbook check` 不再检查它们（此前列表外的缩进代码会被检查与改写）；列表项内容从标记后的第一个字算起（`1. ` 下的代码缩进七格）；定义（`:   …`）的后续段落是正文。
- 引用式链接定义按 CommonMark 判定：以 `[x]:` 开头、后接正文的行（如 `[1]: Knuth, TAOCP.`）是段落，HTML、PDF、EPUB 都显示，其中的链接照常改写与检查；在列表项、块引用与列表续行中也一样。定义可以在这些容器里，标题可以是 `"…"`、`'…'` 或 `(…)` 并含反斜杠转义；引用式图片与带标题的图片复制进构建目录。
- `lean:` 链接的每种单行写法（行内、尖括号地址、带标题、链接文字含成对方括号、引用式定义，含列表项与块引用中的定义，以及自动链接 `<lean:GID>`）由 `./tbook check` 核对、`./tbook pin --refresh` 收录；锁文件不能解析的引用式定义输出 `#`，不再输出 `lean:` 地址。工具读不到的写法（链接跨行、定义的地址在下一行、原始 HTML 的 `href`/`src`）由 `./tbook check` 报错，构建时去掉其中的 `lean:` 地址；环境标题中的 `lean:` 链接报错，只显示文字。
- `UNVERIFIED` 徽章在 PDF 与 EPUB 中也不是链接，EPUB 提示文字为“未经验证”而非“开放问题”；Typst 的 `tr-env` 新增 `badge-url` 参数。
- `trureturing.lock.json` 的 `branch` 必须等于 `site.toml` 的 trureturing 分支，不一致时 `./tbook check` 报错（**需要手动操作**：改过 `site.toml` 的分支而没有重新钉版的书库运行 `./tbook pin`，或在所钉提交也在新分支上时运行 `./tbook pin --refresh`）。分支名必须是 `git check-ref-format --branch` 接受的分支名，且不能是提交 SHA（含缩写）、`refs/…`、`@` 或修订表达式（`<sha>^0`、`dev~1`、`owner:dev`、`dev@{0}`、`HEAD`），否则 `./tbook check` 报错、`./tbook pin` 拒绝。

### 安全

- CI 的 PR 运行不再信任自己先前运行写下的缓存：工作流只在默认分支与 tag 上恢复和保存 `.cache/trureturing`，`tbook` 在 `pull_request*` 事件中也不读取它（状态片取自 `raw.githubusercontent.com`，分支可达性每次问 compare API）；`.github/actions/setup` 的工具链缓存（pip、Playwright 的 Chromium、字体）在 `pull_request*` 事件中既不恢复也不保存，PR 运行每次从网络下载（只拦保存不够：PR 能改自己的工作流，一次推送就能写入 PR 作用域的缓存，下一次推送再恢复它）。npm 缓存按 `package-lock.json` 的完整性校验，照常使用。见 `docs/VERIFICATION.md` §2。
- 提交入库的 `.cache` 符号链接按其自身的名字报错，不再跟随链接去问 git。

### 修复

- PDF/EPUB：带 `{-}`（`.unnumbered`）的标题不再与 Pandoc 的自动 id 冲突、导致 Typst 失败；缩进代码块中的脚注、链接与公式原样保留；紧贴在文字行下的标题也是标题，不再显示字面的 `{#id}`；含公式的标题按 HTML 显示的文字生成 id（`#关于-β-的估计`），含脚注引用的标题按 mdBook 显示的编号生成 id（`## 注释[^a]` → `#注释1`），从 HTML 版复制来的片段链接在 PDF/EPUB 中同样可达（构建 PDF/EPUB 时用 Node 渲染标题中的公式，不可用时退回 TeX 源码并警告）。
- PDF/EPUB：列表项与块引用中以 `[1]:` 开头的文献行不再被 Pandoc 当作链接定义吞掉；定义列表的后续段落不再被当作缩进代码（公式照常渲染，EPUB 通过 epubcheck）。
- 幻灯片：`slides-check` 与 `./tbook check` 只跳过真正位于代码块中的标签，两个代码块之间、GFM 表格之后与 HTML 块里的 `LeanBadge`/`TheoremCard` 不再漏检；代码块按 Slidev 53 所用解析器的块规则识别（含表格与全角空格等 Unicode 空白），缩进代码块与 `<<<` 导入行中的标签显示为代码，不再检查；书的第一语言、语言集合或站点地址变化后，`./tbook build slides` 重新构建，不再复用过期的产物。
- 模板升级：在以合并提交并入的分支上删除的托管文件，此后保持删除，不再被每次升级重新安装（`git log --full-history`）；squash 合并不保留这样的删除，见 `docs/UPGRADING.md` §2。
- `release.yml`：以日期开头的版本（如同一天第二次发布的 `v2026.11.08-2`）是正式发布，不再标为 pre-release；只有严格的语义化版本预发布（`v3.0.0-rc.1`）才是。

## [0.1.0] - 2026-11-08

### 新增

- 多本书、多语言（默认中文、英文）的书库结构：`books/<slug>/<lang>/`，`./tbook check` 校验各语言版本逐条对齐。
- 定理验证：形式结论必须引用 trureturing 中在所钉提交上已冻结（`Golden/Frozen/state`）的 Lean `theorem`；`trureturing.lock.json` 由 `./tbook pin` 生成并在 CI 中复核；`lean-verify` 工作流做公理闭包深度验证。
- 导出：mdBook HTML（KaTeX 预渲染、语言切换）、Typst PDF（深色屏幕版与白底印刷版）、EPUB 3（Apple Books，MathML）；自动生成“形式化验证账本”。
- 媒体：trureturing-visualize 方案的书内交互可视化；trureturing-film 方案的视频流水线；chrono-company-slides 方案（Slidev）的演示文稿；统一的赛博朋克主题，配色唯一来源 `theme/tokens.json`。
- 站点：书库首页、每本书的落地页、下载、`manifest.json`，经 GitHub Pages 发布；`release.yml` 按 tag 发布 PDF/EPUB/幻灯片 PDF。
- 内置 skills（`skills/`，`.claude/skills` 指向它）与 `CLAUDE.md` / `AGENTS.md`。
- 模板升级：`template.toml`、`template-manifest.json`、`./tbook template status|update|manifest`、`template-sync` 与 `trureturing-bump` 工作流。不带 `--to` 的升级从不降级，也不会用同一版本号下的另一个快照覆盖较新的托管文件；迁移脚本取自新版本模板，在新的 Python 进程中运行。
- 钉版与校验：`./tbook pin` 接受完整或缩写的 SHA、分支或 tag，但所钉提交必须在 `site.toml` 的 trureturing 分支（默认 `dev`）上，`./tbook pin` 与 `./tbook check` 都会核对（本地 checkout 或 GitHub compare API；GitHub Actions 中无法判定即为错误，工作流的检查步骤因此传入 `github.token`）；被拒绝的自动 bump 以 `[refused]` 草稿 PR 报告，不改锁文件。GID 的名称分量支持 Unicode 与 `«…»`；源码行号按 `namespace`/`section` 解析出的完整名定位；各语言版本的 SUMMARY 结构必须一致；提交入库的 `.cache/` 文件是错误。
- 徽章与引用：锁文件不能确认的形式结论显示红色 `UNVERIFIED`，不给链接，也不计入“LEAN ✓ n”等统计；环境标题可以含 `[@id]`（显示为引用文字，未知 id 是错误）与 TeX（反斜杠原样保留）；幻灯片用 `kind="definition"` 引用 Lean 定义时显示中性的 `LEAN DEF`。
- 导出：预设数学宏只在 `tools/tbook/mathrender.py` 的 `TEX_MACROS` 中定义，HTML、PDF、EPUB 渲染一致；PDF/EPUB 中脚注与标题 id 按章节独立，指向书内文件的链接改为指向网站上的副本。
- 视频：`film.json` 的 `published_tag` 记录已发布的 Release，未设置时书中只显示海报与“尚未发布”；`film.yml` 发布后在作业摘要中提醒设置它。
- 多语言：没有内置界面表的语言须在 `i18n/<lang>.toml` 的 `[meta]` 中设 `name`、`bcp47`、`short`（不得与其他语言重复）；所选的书都没有 `--lang` 指定的语言版本时，构建以退出码 2 报错，不会静默跳过。
