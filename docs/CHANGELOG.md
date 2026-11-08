# Changelog

本文件记录 trureturing-books-template 的版本变化，格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。下游升级时请阅读跨越的所有版本，处理标为“需要手动操作”的条目。

## [Unreleased]

## [0.1.0] - 2026-11-08

### 新增

- 多本书、多语言（默认中文、英文）的书库结构：`books/<slug>/<lang>/`，`./tbook check` 校验各语言版本逐条对齐。
- 定理验证：形式结论必须引用 trureturing 中在所钉提交上已冻结（`Golden/Frozen/state`）的 Lean `theorem`；`trureturing.lock.json` 由 `./tbook pin` 生成并在 CI 中复核；`lean-verify` 工作流做公理闭包深度验证。
- 导出：mdBook HTML（KaTeX 预渲染、语言切换）、Typst PDF（深色屏幕版与白底印刷版）、EPUB 3（Apple Books，MathML）；自动生成“形式化验证账本”。
- 媒体：trureturing-visualize 方案的书内交互可视化；trureturing-film 方案的视频流水线；chrono-company-slides 方案（Slidev）的演示文稿；统一的赛博朋克主题，配色唯一来源 `theme/tokens.json`。
- 站点：书库首页、每本书的落地页、下载、`manifest.json`，经 GitHub Pages 发布；`release.yml` 按 tag 发布 PDF/EPUB/幻灯片 PDF。
- 内置 skills（`skills/`，`.claude/skills` 指向它）与 `CLAUDE.md` / `AGENTS.md`。
- 模板升级：`template.toml`、`template-manifest.json`、`./tbook template status|update|manifest`、`template-sync` 与 `trureturing-bump` 工作流。
