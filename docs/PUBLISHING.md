# 构建与发布 · Building and publishing

## 1. 产物

| 产物 | 命令 | 位置 |
| --- | --- | --- |
| 在线 HTML（mdBook） | `./tbook build html` | `build/html/<slug>/<lang>/` |
| PDF 屏幕版（深色霓虹） | `./tbook build pdf --variant screen` | `build/dist/<slug>/<slug>-<version>-<lang>-screen.pdf` |
| PDF 印刷版（白底） | `./tbook build pdf --variant print` | `build/dist/<slug>/<slug>-<version>-<lang>-print.pdf` |
| EPUB 3（Apple Books） | `./tbook build epub` | `build/dist/<slug>/<slug>-<version>-<lang>.epub` |
| 演示文稿 | `./tbook build slides` | `build/slides/<slug>/`（PDF：`<deck>-<lang>.pdf`） |
| 视频 | `./tbook build films` | `build/films/<slug>/<film id>/`（`film.json` 的 `outputs` 所列文件），并重新发布到已有站点的 `_site/<slug>/films/` |
| 可视化 | `./tbook build viz` | 重新发布到已有的 `_site/<slug>/viz/`（`viz`、`films` 加 `--book` 只重发选定的书，首页与 manifest 保留其他书） |
| 站点（含可视化、视频） | `./tbook build site` | `_site/` |
| 全部 | `./tbook build all` | 以上全部 |

所有构建命令都接受 `--book <slug>`（可重复）与 `--lang <code>`（可重复）。所选的书都没有 `--lang` 指定的语言版本时，构建报错退出（退出码 2），不会静默跳过。

视频与其他产物一样随站点构建：站点在 `_site/<slug>/films/<film id>/<文件>` 同源托管视频（Content-Type 与按字节范围请求都正确，iOS Safari 需要这两点；Release 附件的地址在那里不能播放），不再为单个视频发 Release；视频计入 GitHub Pages 站点 1 GB 的上限。只构建、托管 `film.json` 的 `outputs` 所列的文件：默认只有 720p 旁白版与封面，50 秒的示例视频共约 6.5 MB（视频 6.1 MB、封面 0.5 MB，另有提交的海报 0.16 MB），约合每分钟 7 MB；同时列出 1080p 旁白版、1080p 与 720p 纯配乐时约 70 MB（每分钟约 84 MB）。渲染视频需要视频工具链（`bash theme/film/setup.sh` 与系统的 ffmpeg）。环境变量 `TBOOK_FILMS` 决定缓存未命中时怎么办：`auto`（默认）有工具链就渲染，没有则警告，站点不含该视频；`require` 无法渲染即构建失败；`skip` 从不渲染。三种情况下缓存命中的视频都照常恢复。

## 2. 站点

`_site/` 是 GitHub Pages 的产物：书库首页（每本书一张卡片：封面、简介、在线阅读、下载）、每本书的落地页（目录、下载、验证摘要、可视化/视频/幻灯片）、mdBook 页面、下载文件与 `manifest.json`（机器可读清单：版本、文件、sha256、所钉的 trureturing 提交）。所有链接都是相对链接，站点可以挂在 `/<repo>/` 之下。

本地预览：`./tbook serve`（默认端口 8765，自动挂在 Pages 子路径下；支持按字节范围请求，Safari 也能播放视频；`TBOOK_SERVE_HOST=0.0.0.0` 允许其他设备访问，例如用 iPhone 查看）。

## 3. Apple Books

EPUB 按 Apple Books 的要求生成：EPUB 3、MathML 数学、PNG 封面、导航目录与 landmarks、`dc:language` 与 `ibooks:version` 元数据、`META-INF/com.apple.ibooks.display-options.xml`；样式不强制页面背景，在白/米/灰/夜间主题下都可读（夜间主题切换为霓虹强调色）。每次构建后由 epubcheck 校验。

上架 Apple Books 需要通过 Apple Books for Authors / iTunes Producer 提交；若需要 ISBN，在 `book.toml` 的 `[book.isbn]` 中按语言填写，它会成为 EPUB 的标识符。

## 4. 持续集成与发布

| 工作流 | 触发 | 作用 |
| --- | --- | --- |
| `ci.yml` | PR、推送到任意分支、手动、被调用 | `check` 作业：`./tbook check`、`./tbook theme --check`、全部单元测试、可视化登记校验与幻灯片检查（模板仓库另跑 `./tbook template manifest --check`，并在删去示例书的工作树中、以及用 `site.toml` 的 `[books] hide = ["example-*"]` 隐藏示例书的工作树中重跑检查与单元测试：下游书库可以隐藏或删除示例书，甚至暂时没有书，CI 照样通过）；`build` 作业：HTML/PDF/EPUB，产物上传为 artifact；`media` 作业：可视化浏览器回归测试、幻灯片构建与 PDF、视频（`TBOOK_FILMS=require`；推送到默认分支或 tag 时不构建视频，由 `pages.yml` 与发版工作流构建）。`build` 与 `media` 经构建缓存（§5）恢复未变的单元，从不保存；调用者须授予 `contents: read` 与 `pages: read` |
| `pages.yml` | 推送到 `main`、手动 | `./tbook check` 后构建全部（含视频，`TBOOK_FILMS=require`）并部署 GitHub Pages；Pages 尚未启用时只构建、不部署，并在作业摘要中提示。唯一保存构建缓存的工作流（§5），同一时间只运行一个 |
| `release.yml` | tag `<slug>-v<version>`（单本，须等于 `book.toml` 的 version）或 `v*`（全部书，仅下游书库，如 `v2026.11.08`、`v3.0.0`） | 构建整个站点（含视频），创建 GitHub Release，附所选书的 PDF、EPUB 与幻灯片 PDF（`<slug>-<deck>-<lang>.pdf`），以及全站的构建缓存（`cache-*.tar` 与 `build-cache.json`，§5）；Release 先建为草稿，附件全部上传后才发布，已发布的 Release 不再改动附件；只有语义化版本的预发布（`book.toml` 的 `1.0.0-rc.1`，或 tag `v3.0.0-rc.1`）标为 pre-release；以日期开头的版本（`YYYY.MM.DD`、`YYYY-MM-DD` 或 `YYYYMMDD`，月、日补零）无论后面跟什么都是正式发布，如同一天的第二次发布 `v2026.11.08-2`；以 `film-` 开头、不指向任何书的 tag（旧的逐片视频 tag）只给出提示并跳过，不发布任何东西，可以删除；`site.toml` 的 `[books] hide` 隐藏的书不发布：`v*` 不含它们，指向它们的 `<slug>-v*` 失败并说明原因 |
| `lean-verify.yml` | 每周、手动、可被 Release 调用 | Lake 工程深度验证被引用定理的公理闭包 |
| `trureturing-bump.yml` | 每周、手动 | 把所钉的 trureturing 提交升级到最新并开 PR；标题前缀 `[refused]`（目标提交不在 `site.toml` 的分支上或无法核实）、`[unresolved]`（有引用无法解析）、`[pin failed]`、`[check fails]`、`[review statements]` 提示需要处理的情况；前三种 PR 不改锁文件，与 `[check fails]` 一样以草稿开出 |
| `template-sync.yml` | 每周、手动（仅下游） | 升级到模板新版本并开 PR（有冲突时标题以 `[conflicts]` 开头，`.template-new` 文件一并提交） |
| `template-release.yml` | tag `v*`（仅模板仓库） | 核对版本与清单、跑 CI 后发布模板版本，附示例站点的构建缓存（同样先建草稿、上传后发布） |

检查与构建作业（`ci.yml`、`pages.yml`、`release.yml` 的构建、`trureturing-bump.yml`）通过组合动作 `.github/actions/setup` 安装工具链（Python 3.12 + requirements、Node 22 + `npm ci`、按需安装 Chromium、mdBook 0.5.4、CJK 字体；`films: 'true'` 且有（未隐藏的）书带视频时另装 ffmpeg 与备用字体，运行 `theme/film/setup.sh` 安装 `theme/film/requirements.txt` 并下载 Kokoro 模型到 `.cache/film/models`）。

CI 中没有 trureturing 的 checkout，`./tbook check` 通过 GitHub compare API 核对所钉提交在 `site.toml` 的分支上；GitHub Actions 中无法判定即为错误。因此 `ci.yml`、`pages.yml`、`release.yml` 的检查步骤把 `github.token` 作为 `GITHUB_TOKEN` 传入（`trureturing-bump.yml` 用作业的 `GH_TOKEN`），这些作业至少需要 `contents: read` 权限。

首次使用：Settings → Pages → Source 选 **GitHub Actions**。`site.toml` 的 `base_url` 留空时，站点地址取自 `configure-pages`。可选仓库设置：

- 变量 `REQUIRE_LEAN_VERIFY=true`：Release 前强制深度验证。
- Secret `BOT_TOKEN`：细粒度令牌，Contents、Pull requests、**Workflows** 读写。没有它时，自动 PR 由 `GITHUB_TOKEN` 创建，不会触发 CI，且不能推送 `.github/workflows/` 的改动。
- Secret `TRURETURING_TOKEN`（可选）：只在 trureturing 是私有仓库时需要，能读取该仓库内容的令牌。`check`、`pin` 用它读取冻结状态并通过 GitHub API 核对所钉提交是否在分支上；公开仓库不需要。
- Settings → Actions → General → 勾选 “Allow GitHub Actions to create and approve pull requests”（使用 `GITHUB_TOKEN` 开 PR 时需要）。
- Settings → General → Releases → 启用 **immutable releases**（建议）：已发布的 Release 的附件与 tag 不能再改，从 Release 恢复的构建缓存因此不会被事后替换（`docs/VERIFICATION.md` §2）。工作流先建草稿、上传全部附件再发布，与之兼容。

## 5. 构建缓存

构建单元（每个语言版本的 HTML、每种 PDF、EPUB、每本书的幻灯片、每个视频）的输入没有变化时不再构建，而是恢复存下的产物（`tools/tbook/buildcache.py`；键与本地存储见 `docs/ARCHITECTURE.md`）。视频不是特例，与 PDF、幻灯片走同一条路。查找顺序：

1. 本地存储 `.cache/artifacts/`。在 GitHub Actions 中，组合动作 `.github/actions/build-cache` 在构建前恢复它（Actions 缓存，按前缀 `build-cache-v1-` 先找本次运行所在 ref 的最新一份，再找默认分支的），PR 事件中跳过；
2. 设置了 `TBOOK_CACHE_REMOTE=1` 时（构建步骤都设置，并传入 `GITHUB_TOKEN`），查最新的 5 个附有 `build-cache.json` 的已发布 Release（手工发的、没有该文件的 Release 不占名额），下载对应的 `cache-*.tar`，核对 SHA-256 后恢复。没有任何 Actions 缓存的构建（新仓库、缓存被清除、PR）由此从整站 Release 恢复；
3. 都没有时构建，并存入本地存储。

只有 `pages.yml` 保存 Actions 缓存：在默认分支上（push 或手动运行）构建后执行 `./tbook cache prune`（只留当前输入的条目），再由 `./tbook cache key` 算出存储内容的摘要 `build-cache-v1-<sha256>`。它与恢复到的键去掉运行后缀 `-r…` 后的部分相同时不再上传；不同时以 `build-cache-v1-<sha256>-r<run id>-<run attempt>` 保存。运行后缀使每次保存都得到一个新键，成为最新的一份：缓存键不能覆盖，存储回到早先的内容（例如回滚）时，若沿用早先的键，保存会因键已存在而落空，恢复就仍取那份更新却已过时的存储。每次保存的是整个存储，仓库的 Actions 缓存超过上限（默认 10 GB）时，GitHub 先淘汰最久未用的条目，恢复总是取最新的一份。构建失败时也保存，已完成的单元（例如先渲染好的视频）不必重做；构建步骤自己的时限（210 分钟）短于作业的时限，超时只让这一步失败，保存照常进行，重新运行或下一次推送从已完成处继续（作业超时会被取消，保存也随之跳过）。`pages` 并发组使它同一时间只运行一个，后一次运行恢复前一次保存的结果。`ci.yml` 只恢复、不保存，`media` 作业在默认分支与 tag 的推送上不构建视频（`pages.yml` 与发版工作流会构建）；`release.yml` 不保存 Actions 缓存，而是把缓存附在 Release 上。

仍会重复渲染的情形：PR 事件既不恢复也不保存 Actions 缓存（防投毒，见 `docs/VERIFICATION.md` §2），但可以从已发布的 Release 恢复。所以改动了的视频在每次 PR 运行中渲染以验证；分支推送到本仓库时，它的每次 `ci.yml` 推送运行也渲染（`ci.yml` 不保存）；合入后 `pages.yml` 再渲染一次并保存。此后其他分支、默认分支与 tag 上的构建从 Actions 缓存恢复它；PR 运行只读已发布的 Release，在某个 Release（`release.yml`）附上它的键之前，PR 每推送一次就再渲染一次。

键中的工具版本：Node 取主版本（Chromium 由 `package-lock.json` 中的 Playwright 决定，不单独计入），Pandoc、Typst 取“主.次”（精确版本钉在 `requirements.txt`），mdBook 取精确版本（CI 安装的正是 0.5.4）；其余精确版本由 `package-lock.json`、`theme/film/requirements.txt` 与 `.github/actions/setup` 钉住。所以运行器镜像更新 Node 补丁版本或 ffmpeg 包修订，不会让缓存与已发布的 Release 失效。视频的键覆盖 git 列出的视频文件（不含 `out/`、`poster.jpg`、`README.md`）、`theme/film/`（不含 `site/`）、`theme/generated/tokens.mjs`、`tools/tbook/film.py`、引擎绘制的数据（书的代号、版本与标题，所钉提交，引用的声明及其陈述摘要，片内文字）、`package-lock.json` 中 @fontsource 字体与 Playwright 的版本、Kokoro 模型版本与 Node 主版本；不含站点地址，也不含探测到的 ffmpeg、Chromium 与视频 Python，所以没有视频工具链的构建（`TBOOK_FILMS=auto|skip`）也能恢复视频。

每个 Release 都是一个恢复点：`release.yml` 无论 tag 是单本还是全部书，都构建整个站点，`./tbook cache export release/cache` 为每个单元写一个 tar 和清单 `build-cache.json`，与读者下载一并附上（缺少任何单元则失败）；模板仓库的 `template-release.yml` 为示例站点做同样的事。HTML、PDF、EPUB 与幻灯片的键包含站点地址（视频的键不含），所以 `ci.yml`、`release.yml` 与 `pages.yml` 一样用 `actions/configure-pages` 取得的 Pages 地址构建（`site.toml` 设了 `base_url` 时以它为准），各处的键才一致。

本地：`./tbook cache status` 列出每个单元、键与是否已存；`TBOOK_CACHE=0` 关闭缓存（全部重建、不存储）。本地构建默认只查本地存储；设置 `TBOOK_CACHE_REMOTE=1` 时也从已发布的整站 Release 恢复，本机没有视频工具链时可以这样取得视频（视频的键不含站点地址；其他单元的键含站点地址，只有与 Release 构建时的地址相同才能命中）。谁可以写入缓存、为何可以信任 Release，见 `docs/VERIFICATION.md` §2。

## 6. 发版步骤

见 `skills/book-release/SKILL.md`。简言之：`./tbook check` 通过 → 改 `book.toml` 的 `version` → 合入 `main` → `git tag <slug>-v<version> && git push origin <slug>-v<version>`。
