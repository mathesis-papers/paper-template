# Changelog

本文件记录 trureturing-books-template 的版本变化，格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。下游升级时请阅读跨越的所有版本，处理标为“需要手动操作”的条目。

## [Unreleased]

### 变更

- 标题按行内 Markdown 读：环境标题与 SUMMARY 章节标题中 `$…$` 之外的反斜杠转义（`C\*-代数`、`\$5`）在 HTML 页头、侧栏、`<title>`、站点、PDF、EPUB 与账本中都显示为标点本身，`$…$` 内的 TeX 不变。此前 HTML 与站点保留反斜杠；SUMMARY 中 `$…$` 外的 `\{` 现在显示为 `{`。
- HTML 注释中的内容不再被改写、检查或编号（含注释块里的环境）；以 `<!--` 开头的注释块没有 `-->` 时 `./tbook check` 报错。
- 引用式链接定义按 CommonMark 判定：以 `[x]:` 开头、后接正文的行（如 `[1]: Knuth, TAOCP.`）是段落，HTML、PDF、EPUB 都显示，其中的链接照常改写与检查。
- `lean:` 链接的引用式写法（`[x]: lean:GID`）与尖括号写法（`(<lean:GID>)`）由 `./tbook check` 核对、`./tbook pin --refresh` 收录；锁文件不能解析的引用式定义输出 `#`，不再输出 `lean:` 地址。
- `UNVERIFIED` 徽章在 PDF 与 EPUB 中也不是链接，EPUB 提示文字为“未经验证”而非“开放问题”；Typst 的 `tr-env` 新增 `badge-url` 参数。

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
