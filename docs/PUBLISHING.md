# 构建与发布 · Building and publishing

## 1. 产物

| 产物 | 命令 | 位置 |
| --- | --- | --- |
| 在线 HTML（mdBook） | `./tbook build html` | `build/html/<slug>/<lang>/` |
| PDF 屏幕版（深色霓虹） | `./tbook build pdf --variant screen` | `build/dist/<slug>/<slug>-<version>-<lang>-screen.pdf` |
| PDF 印刷版（白底） | `./tbook build pdf --variant print` | `build/dist/<slug>/<slug>-<version>-<lang>-print.pdf` |
| EPUB 3（Apple Books） | `./tbook build epub` | `build/dist/<slug>/<slug>-<version>-<lang>.epub` |
| 演示文稿 | `./tbook build slides` | `build/slides/<slug>/` |
| 站点（含可视化、视频页） | `./tbook build site` | `_site/` |
| 全部 | `./tbook build all` | 以上全部 |

所有构建命令都接受 `--book <slug>`（可重复）与 `--lang <code>`（可重复）。

## 2. 站点

`_site/` 是 GitHub Pages 的产物：书库首页（每本书一张卡片：封面、简介、在线阅读、下载）、每本书的落地页（目录、下载、验证摘要、可视化/视频/幻灯片）、mdBook 页面、下载文件与 `manifest.json`（机器可读清单：版本、文件、sha256、所钉的 trureturing 提交）。所有链接都是相对链接，站点可以挂在 `/<repo>/` 之下。

本地预览：`./tbook serve`（默认端口 8765，自动挂在 Pages 子路径下）。

## 3. Apple Books

EPUB 按 Apple Books 的要求生成：EPUB 3、MathML 数学、PNG 封面、导航目录与 landmarks、`dc:language` 与 `ibooks:version` 元数据、`META-INF/com.apple.ibooks.display-options.xml`；样式不强制页面背景，在白/米/灰/夜间主题下都可读（夜间主题切换为霓虹强调色）。每次构建后由 epubcheck 校验。

上架 Apple Books 需要通过 Apple Books for Authors / iTunes Producer 提交；若需要 ISBN，在 `book.toml` 的 `[book.isbn]` 中按语言填写，它会成为 EPUB 的标识符。

## 4. 持续集成与发布

| 工作流 | 触发 | 作用 |
| --- | --- | --- |
| `ci.yml` | PR、推送 | `./tbook check`、主题与单元测试、构建 HTML/PDF/EPUB、可视化浏览器测试、幻灯片构建；产物作为 artifact |
| `pages.yml` | 推送到 `main`、手动 | 构建全部并部署 GitHub Pages |
| `release.yml` | tag `<slug>-v<version>`（单本）或 `v*`（全部） | 构建并创建 GitHub Release，附 PDF、EPUB、幻灯片 PDF |
| `film.yml` | tag `film-<slug>-<NNN>-v<k>`、手动 | 渲染视频（TTS、配乐、逐帧渲染、编码）并发布到 Release |
| `lean-verify.yml` | 每周、手动、可被 Release 调用 | Lake 工程深度验证被引用定理的公理闭包 |
| `trureturing-bump.yml` | 每周、手动 | 把所钉的 trureturing 提交升级到最新并开 PR |
| `template-sync.yml` | 每周、手动（仅下游） | 升级到模板新版本并开 PR |
| `template-release.yml` | tag `v*`（仅模板仓库） | 发布模板版本 |

首次使用：Settings → Pages → Source 选 **GitHub Actions**。可选仓库设置：变量 `REQUIRE_LEAN_VERIFY=true`（Release 前强制深度验证）；Secret `BOT_TOKEN`（让自动 PR 触发 CI）。

## 5. 发版步骤

见 `skills/book-release/SKILL.md`。简言之：`./tbook check` 通过 → 改 `book.toml` 的 `version` → 合入 `main` → `git tag <slug>-v<version> && git push origin <slug>-v<version>`。
