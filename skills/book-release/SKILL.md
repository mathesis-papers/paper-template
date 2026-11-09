---
name: book-release
description: 发布一本书或整个书库的版本时使用：更新版本号、打 tag、触发 Release（PDF/EPUB/幻灯片 PDF 与构建缓存附件）与 GitHub Pages 部署（含视频），发版前的深度 Lean 验证，以及构建缓存与 Release 恢复的排错。
---

# 发版与发布

## 适用范围

**用**：发布书的新版本；第一次开启 Pages；Release 或 Pages 工作流失败；构建缓存没有命中或恢复出错。

**权威**：`.github/workflows/{pages,release,lean-verify}.yml`、`.github/actions/build-cache/action.yml` 与 `docs/PUBLISHING.md`（§5 构建缓存）。

## 自动发布

- **Pages**：每次推送到 `main`，`pages.yml` 运行 `./tbook check` 与 `./tbook build all`（含视频；无法渲染的视频让构建失败），把 `_site/` 部署到 GitHub Pages，视频由站点同源托管。首次使用需在 Settings → Pages → Source 选 “GitHub Actions”。
- **CI**：每个 PR 与推送运行检查与构建（`ci.yml`，`media` 作业也构建视频），产物作为 artifact 上传，可下载审阅。
- **构建缓存**：输入没有变化的单元（HTML、PDF、EPUB、幻灯片、视频）不再构建。`pages.yml` 在 `main` 上保存 Actions 缓存，其他构建只恢复；没有 Actions 缓存时（新仓库、PR）从最近的已发布 Release 恢复。视频不再单独发 Release。

## 发布一个版本

1. 选定要发布的书 `<slug>`，确认 `./tbook check` 0 错误、`./tbook build all` 成功。
2. 更新 `books/<slug>/book.toml` 的 `version`（语义化版本），必要时更新 `date`。
3. （建议）手动运行 `lean-verify` 工作流，或把仓库变量 `REQUIRE_LEAN_VERIFY` 设为 `true`，让 Release 前强制深度验证。
4. 提交并推送到 `main`，然后打 tag：
   ```bash
   git tag <slug>-v<version>
   git push origin <slug>-v<version>
   ```
   发布全部书时用 `v<日期或版本>`，例如 `v2026.11.08`、`v2026-11-08` 或 `v3.0.0`（模板仓库自身除外——那里的 `v*` 是模板版本）。
   只有语义化版本的预发布才标为 GitHub pre-release：单本书看 `book.toml` 的 `version`（如 `1.0.0-rc.1`），全部书看 tag 中 `v` 之后的部分（如 `v3.0.0-rc.1`）；其他形式都是正式发布。日期写成 `YYYY.MM.DD`、`YYYY-MM-DD` 或 `YYYYMMDD`，月、日补零：以这样的日期开头的版本无论后面跟什么都是正式发布，同一天再发一次可用 `v2026.11.08-2`。不补零的 `v2026.1.5-2` 恰好是语义化版本的预发布，会标为 pre-release。
5. `release.yml` 校验 tag 与 `book.toml` 版本一致，构建整个站点（未变的单元从缓存恢复，视频也在其中），先建草稿 Release，上传所选书的 PDF（屏幕版、印刷版）、EPUB、幻灯片 PDF 与全站的构建缓存（`cache-*.tar`、`build-cache.json`），全部上传后才发布；说明中列出所钉的 trureturing 提交与定理数。
6. 检查 Release 附件（读者下载与 `build-cache.json` 都在）与 Pages 上的下载链接和视频。
7. （建议，只需一次）在 Settings → General → Releases 启用不可变 Release，发布后的附件与 tag 不能再改（`docs/VERIFICATION.md` §2）。

## 排错

- **Release 停在草稿**：发布作业在上传途中失败。重跑失败的作业即可：它替换草稿的附件后再发布。已发布的 Release 重跑时只更新标题与说明，附件不变。
- **`./tbook cache export` 失败**：有单元不在存储中（通常是构建失败，或视频无法渲染）。看构建步骤的日志，修好后重新打 tag（新版本）或重跑。
- **视频每次都重新渲染**：`./tbook cache status` 看键是否稳定；只有 `main` 上的 `pages.yml` 保存 Actions 缓存，分支与 PR 上的 CI 依赖它或 Release。站点地址不同也会让键不同：CI、Pages 与 Release 都用 `configure-pages` 的地址，`site.toml` 设了 `base_url` 时都用它。
- **从 Release 恢复失败**：日志中 `cache:` 开头的行说明原因（列不出 Release、摘要不符、条目不匹配）；工具随即改为构建，不会用不完整的条目。

## 禁止

- 在 `./tbook check` 有错误时打 tag。
- 复用已发布的 tag，或改写已发布版本的 PDF/EPUB 与构建缓存附件（发新补丁版本）。
- 打 `film-*` tag 或为单个视频发 Release：视频随站点构建与发布。
- 发布后修改书的 `slug` 或环境 `#id`（外链与引用依赖它们）。
