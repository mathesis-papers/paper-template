---
name: book-release
description: 发布一本书或整个书库的版本时使用：更新版本号、打 tag、触发 Release（PDF/EPUB/幻灯片 PDF 附件）与 GitHub Pages 部署，以及发版前的深度 Lean 验证。
---

# 发版与发布

## 适用范围

**用**：发布书的新版本；第一次开启 Pages；Release 或 Pages 工作流失败。

**权威**：`.github/workflows/{pages,release,lean-verify}.yml` 与 `docs/PUBLISHING.md`。

## 自动发布

- **Pages**：每次推送到 `main`，`pages.yml` 运行 `./tbook check` 与 `./tbook build all`，把 `_site/` 部署到 GitHub Pages。首次使用需在 Settings → Pages → Source 选 “GitHub Actions”。
- **CI**：每个 PR 与推送运行检查与构建（`ci.yml`），产物作为 artifact 上传，可下载审阅。

## 发布一个版本

1. 选定要发布的书 `<slug>`，确认 `./tbook check` 0 错误、`./tbook build all` 成功。
2. 更新 `books/<slug>/book.toml` 的 `version`（语义化版本），必要时更新 `date`。
3. （建议）手动运行 `lean-verify` 工作流，或把仓库变量 `REQUIRE_LEAN_VERIFY` 设为 `true`，让 Release 前强制深度验证。
4. 提交并推送到 `main`，然后打 tag：
   ```bash
   git tag <slug>-v<version>
   git push origin <slug>-v<version>
   ```
   发布全部书时用 `v<日期或版本>`（模板仓库自身除外——那里的 `v*` 是模板版本）。
5. `release.yml` 校验 tag 与 `book.toml` 版本一致，构建 PDF（屏幕版、印刷版）、EPUB 与幻灯片 PDF，创建 GitHub Release，说明中列出所钉的 trureturing 提交与定理数。
6. 检查 Release 附件与 Pages 上的下载链接。

## 禁止

- 在 `./tbook check` 有错误时打 tag。
- 复用已发布的 tag，或改写已发布版本的 PDF/EPUB（发新补丁版本）。
- 发布后修改书的 `slug` 或环境 `#id`（外链与引用依赖它们）。
