# 架构与契约 · Architecture and contracts

本文件描述 trureturing 书籍模板的结构，以及各组件之间的接口契约。改动任一组件前先读这里；改动契约时同步更新本文件。

## 1. 原则

1. **真值只在 trureturing。** 书中每条 `theorem / lemma / proposition / corollary` 都必须引用 trureturing 中已被 Lean 内核验证并冻结的声明。冻结成员身份的唯一判据是所钉提交上存在 `Golden/Frozen/state/<module>.lean.json` 且其中列有该声明（trureturing CLAUDE.md §1.3 冻结律）。Lean 代码只写在 trureturing，本仓库不含 `.lean` 文件。
2. **书是投影，不是真源。** 书的文字解释定理；定理的成立由 Lean 声明决定。未证结论只能写成 `conjecture` 或 `problem`。
3. **一次编写，多端导出。** 同一份 Markdown 生成 HTML（mdBook）、PDF（Typst，屏幕版与印刷版）、EPUB 3（Apple Books）。编号、标签、徽章与 Lean 链接由 `tools/tbook/render.py` 统一计算，各端一致。
4. **多语言，默认中文与英文。** 每本书有若干语言版本（edition），第一个为权威版本；`./tbook check` 要求各版本的章节文件、环境序列（种类、id、Lean 引用）逐条一致。
5. **配色单一来源。** 赛博朋克配色只在 `theme/tokens.json` 定义，`./tbook theme` 派生出各端使用的 CSS / Typst / JS。绿色只留给 Lean 已验证，琥珀色只留给“现在/当前选择”，红色标开放问题。
6. **模板可升级。** `template.toml` 列出模板托管的路径；下游只改自己的路径（`books/`、`site.toml`、`trureturing.lock.json`、`i18n/`、`PROJECT.md`、`README.md`）。`./tbook template update` 把托管路径同步到模板的新版本。

## 2. 目录

```
site.toml                 站点配置（下游所有）
trureturing.lock.json     所钉的 trureturing 提交与已解析的声明（由 ./tbook pin 生成，提交入库）
template.toml             模板版本与托管路径（模板所有）
template-manifest.json    托管文件清单与 sha256（模板发布时生成，用于检测下游本地改动）
tbook                     CLI 入口（bash → python3 -m tbook）
books/<slug>/
  book.toml               书的元数据、语言版本、输出开关
  <lang>/SUMMARY.md       每个语言版本一个目录，mdBook SUMMARY 格式
  <lang>/*.md             章节；各版本文件名相同
  assets/                 各语言共享的图片等（章节中写 ../assets/x.svg）
  viz/<id>/               交互可视化（trureturing-visualize 方案）
  viz/visualizations.json 本书可视化注册表
  slides/<deck>/          演示文稿（Slidev，chrono-company-slides 方案）：slides.md（中文）、slides.en.md（英文）
  films/<NNN>-<name>/     视频（trureturing-film 方案）：film.json、script.json、scenes.js
theme/
  tokens.json             设计令牌（唯一来源）
  generated/              由 tokens.json 派生：tokens.css、tokens.typ、tokens.mjs
  i18n/<lang>.toml        界面与排版用语（下游可在 i18n/<lang>.toml 覆盖或新增语言）
  mdbook/                 mdBook 主题（CSS/JS）
  typst/                  PDF 模板（book.typ、cover.typ）
  epub/                   EPUB 样式
  site/                   书库首页与每本书落地页的样式/脚本
  viz/                    可视化共享运行时（theme.css、shell.js）
  slides/                 Slidev 主题
  film/                   视频共享引擎与流水线脚本
templates/                新书、新可视化、新 deck、新视频的起始模板
tools/tbook/              Python 包（构建、校验、发布）
tools/filters/            Pandoc Lua 过滤器
tools/node/               Node 脚本（KaTeX 渲染、可视化校验/测试/缩略图、幻灯片构建）
skills/                   内置 agent skills（.claude/skills → ../skills）
.github/workflows/        CI、Pages、Release、模板同步、Lean 深度验证
```

## 3. 写作语法

全部是 Pandoc Markdown 的子集，GitHub 上可直接预览。

### 3.1 环境

```markdown
::: {.theorem #thm-deficit title="亏量只取三个值" lean="D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"}
对所有自然数 $v_1, v_2$，$c(v_1, v_2) \in \{-1, 0, 1\}$。
:::
```

| 种类 | 类名 | Lean 引用 | 编号 | 徽章 |
| --- | --- | --- | --- | --- |
| 形式结论 | `theorem` `lemma` `proposition` `corollary` | **必须**，且解析为 Lean `theorem` | 是 | `LEAN ✓`（绿） |
| 定义 | `definition` | 可选；给出则必须解析 | 是 | — |
| 开放 | `conjecture` `problem` | **禁止** | 是 | `OPEN`（红） |
| 非形式 | `example` `remark` | 可选；给出则必须解析 | 是 | — |
| 证明 | `proof` | 可选 | 否 | ∎ |
| 媒体 | `viz` `film` `slides` | 可选 | 否 | — |

- `#id`：形式结论、定义、开放条目必须有 id；id 以字母开头，可含字母、数字、`-`、`_`、`:`。
- `title="…"`：可选，单行，可含行内数学。
- `lean="GID [GID …]"`：一条或多条，空格或逗号分隔。
- 编号：同一顶层章节内，所有编号种类共用一个计数器：`定理2.1`、`定义2.2`（中文、日文不加空格；英文为 `Theorem 2.1`）……前言类（prefix）章节用 `0.n`，附录类（suffix）章节用 `A.n`、`B.n`。
- 简写 `::: proof`（单个类名，无花括号）也可以。

### 3.2 GID

与 trureturing Blueprint 相同：`<模块路径>.<声明名>`，如 `D5/S1/Deficit/DeficitThreeValued.deficit_three_valued`。声明名可以是完整 Lean 名，也可以是其点分后缀；在该模块的冻结状态片中必须恰好匹配一个非私有声明。

### 3.3 引用与链接

- `[@thm-deficit]` → `定理1.2`（链接到该环境；跨章节有效）。
- `` [`deficit_three_valued`](lean:D5/S1/Deficit/DeficitThreeValued.deficit_three_valued) `` → 指向所钉提交上 Lean 源文件（含行号）的永久链接。
- 图片：`![说明](../assets/figure.svg)`。指向书目录内、语言目录外的文件会被复制进构建目录 `_book/`。

### 3.4 媒体

```markdown
::: {.viz src="golden-carry" height="560"}
图注（可选）。
:::

::: {.viz src="trureturing-visualize:robin-lattice"}
:::

::: {.film src="001-golden-deficit"}
:::

::: {.film src="trureturing-film:film-001-v1"}
:::

::: {.slides src="overview"}
:::
```

- HTML：可视化以 iframe 嵌入（`height` 160–2400，默认 560），附“全屏打开”；视频以 `<video>` 播放（海报 + 发布地址）；幻灯片为链接卡片（在线演示、PDF）。
- PDF / EPUB：静态缩略图或海报 + 图注 + 在线地址（由 `site.toml` 的 `base_url` 拼出）。
- 书内媒体的源文件：
  - 可视化：`books/<slug>/viz/visualizations.json`（登记表）+ `viz/<id>/`（`index.html`、`style.css`、`main.js`、`thumb.jpg`）与 `viz/tests/<id>.test.mjs`；页面契约见 `templates/viz/README.md`。
  - 视频：`books/<slug>/films/<NNN>-<name>/`（`film.json`、`script.json`、`scenes.js`、`poster.jpg`）；规范见 `templates/film/README.md`，发布 tag 为 `film-<slug>-<NNN>-v<k>`。
  - 幻灯片：`books/<slug>/slides/<deck>/slides.md`（第一语言）与 `slides.<lang>.md`，逐页对应；写法见 `theme/slides/README.md`。
- 媒体中引用的 Lean GID（登记表的 `lean`、页面的 `data-lean-gid`、`film.json` 的 `lean`、幻灯片的 `<LeanBadge>` / `<TheoremCard>`）与章节引用一样必须在锁文件中，由 `./tbook pin --refresh` 解析、`./tbook check` 复核。
- `[@id]` 只能指向编号环境，不能指向媒体块。

### 3.5 数学

`$…$` 行内、`$$…$$` 独行显示（与 trureturing 理论卷一致；不用 `\(` `\)`）。HTML 端由 KaTeX 在构建时渲染；PDF 端由 Pandoc 转为 Typst 数学；EPUB 端输出 MathML（Apple Books 原生支持）。

## 4. 校验（`./tbook check`）

1. 配置：`site.toml`、`book.toml` 字段，语言代码，i18n 表存在。
2. 结构：SUMMARY 可解析、章节文件存在、未列入 SUMMARY 的 `.md`（警告）、fenced div 闭合。
3. 环境规则（见 §3.1 表）。
4. 交叉引用 `[@id]` 指向本版本存在的环境。
5. 多语言对齐：各版本章节文件与顺序相同；每章环境序列（种类、id、Lean 引用）与媒体序列逐条相同。
6. Lean：每个被引用的 GID 都在锁文件中；形式结论引用的必须是 `theorem`；在锁定提交上重新读取冻结状态片，名称、种类、模块、`statement_id` 与锁文件一致（防止锁文件过期或被手改）；未被引用的锁条目（警告）。
7. 媒体：`tbook.viz/film/slides.check(book)` 与 `check_ref(book, src)`。
8. 主题：`theme/generated/*` 与 `tokens.json` 同步。

冻结状态片的读取顺序：`$TRURETURING_DIR` 或 `../trureturing` 的 git checkout（`git show <commit>:<path>`）→ `.cache/trureturing/<commit>/` → `https://raw.githubusercontent.com/<repo>/<commit>/<path>`。

**深度验证**（`./tbook lean-project` + `.github/workflows/lean-verify.yml`）：生成一个依赖所钉 trureturing 的 Lake 工程，导入被引用的模块，逐条检查声明存在、位于预期模块、种类正确，且公理闭包只含 `propext`、`Classical.choice`、`Quot.sound`（无 `sorryAx`）。需要完整 Lean 构建，耗时长，故定期与发版前运行，而不是每个 PR。

## 5. 构建目录契约

```
build/stage/<slug>/<lang>/mdbook/   mdBook 工程：book.toml、src/（章节、SUMMARY、404.md、_book/ 书内文件、
                                    tr/katex/fonts）、theme/head.hbs、tr/（tokens.css、纸面配色、KaTeX CSS、
                                    tr-editions.js、tr-book.css/js）
build/stage/<slug>/<lang>/pandoc/   Pandoc 输入：book.md、_book/、_theme/（Typst 主题副本与 code-<variant>.tmTheme）、
                                    meta.json、main.typ（PDF）、cover.png（EPUB 封面 1600×2560）、
                                    epub/（book.css、metadata.json、colophon.md）
build/html/<slug>/<lang>/           mdBook 输出（含 tr/ 下带哈希的 CSS/JS）
build/dist/<slug>/                  下载文件，文件名由 Book.artifact() 决定：
                                    <slug>-<version>-<lang>-screen.pdf
                                    <slug>-<version>-<lang>-print.pdf
                                    <slug>-<version>-<lang>.epub
build/slides/<slug>/<deck>/<lang>/  Slidev 输出；PDF 在 build/slides/<slug>/<deck>-<lang>.pdf；
                                    manifest.json（schema trureturing-books.slides.v1：base、
                                    decks.<deck>.langs.<lang>.{title,info,blurb,slides,dir,site_path,base,pdf,pdf_name}）
books/<slug>/films/<NNN>-<name>/out/  视频流水线产物（git 忽略）；入口 theme/film/film.sh <film dir> <step>
build/lean-verify/                  ./tbook lean-project 生成的深度验证 Lake 工程
_site/                              GitHub Pages 产物（见 §6）
```

HTML 专有选项：`book.toml` 的 `[html] section-labels = true` 恢复 mdBook 侧栏的 “1.2.” 编号（默认关闭，因为标题已写“第一章 / Chapter 1”）；`site.toml` 的 `[site] branch = "main"` 决定“建议修改”链接指向的分支。语言切换按 `_site/<slug>/<lang>/` 的布局链接到 `../<lang>/<同一页>`。

环境变量：`MDBOOK`（mdBook 路径）、`PANDOC`、`PW_CHROMIUM_PATH`（已有的 Chromium）、`TBOOK_EPUBCHECK=1|warn|0`、`TBOOK_SLIDES_NO_PDF=1`、`TBOOK_SLIDES_NO_CHECK=1`、`SOURCE_DATE_EPOCH`（可复现的时间戳）、`TBOOK_REPO` / `TBOOK_BASE_URL`（覆盖仓库与站点地址）、`TRURETURING_DIR`（本地 trureturing 检出）、`TBOOK_LANG=zh|en`（模板升级摘要语言）。

## 6. 站点结构（`_site/`）

```
index.html                 书库首页（双语切换，书卡片：封面、简介、在线阅读、下载、媒体计数）
404.html                   自包含的 404 页
.nojekyll
assets/                    站点共享样式、tokens.css、site.js、favicon
manifest.json              机器可读清单（schema trureturing-books.site.v1，见下）
<slug>/index.html          书的落地页：版本、语言、下载、目录、验证摘要、可视化/视频/幻灯片
<slug>/cover-<lang>.png    站点封面（640×1024，tbook.cover 生成）
<slug>/<lang>/             mdBook HTML
<slug>/downloads/          PDF、EPUB
<slug>/viz/                index.html（可视化索引）、visualizations.json、assets/（共享运行时）、<id>/
<slug>/films/              index.html、films.json、assets/{tokens.css,films.css,films.js}、<NNN>-<name>/poster.jpg
                           （播放与下载地址指向 GitHub Release 资产）
<slug>/slides/             index.html；<deck>/（中文）、<deck>/en/（英文）、
                           <deck>/<slug>-<deck>-<lang>.pdf
```

`manifest.json` 字段：`generated_at`、`site{title,languages,base_url,repo}`、`template{name,version}`、`trureturing{repo,commit,branch}`、`books[{slug, version, code, title{lang}, editions[{lang,bcp47,primary,html}], landing, verified, open, declarations[], media{viz,films,slides}, files[{path,size,sha256,kind(pdf|epub|cover|slides-pdf),lang,variant}]}]`。设置 `SOURCE_DATE_EPOCH` 可使 `generated_at` 可复现。

站点品牌：`site.toml` 可选 `[site] logo = "TRURETURING//BOOKS"`；缺省时用英文站名生成 `FIRST//REST`。

所有站内链接都是相对链接（站点挂在 `/<repo>/` 下）。`./tbook serve` 在同样的子路径下预览（`TBOOK_SERVE_HOST=0.0.0.0` 可供局域网访问）；`./tbook build site --book x` 只装配选定的书；`./tbook build viz|films` 只重新发布这些部分。媒体发布失败时，站点其余部分仍会写出，命令以非零退出。

## 7. Python 组件接口

核心（不依赖外部工具）：

| 模块 | 职责 |
| --- | --- |
| `config` | `load_site()`、`load_book()`、`load_books()`、`i18n()`、`s(lang, key)`、`Book.artifact()` |
| `summary` | 解析 SUMMARY，章节编号前缀 |
| `mdscan` | 代码块、fenced div、属性、行内代码、`[@id]`、`lean:` 链接 |
| `model` | `load_edition()` → `EditionModel`（章节、环境、编号、引用）；`Issue` |
| `lean` | 名称键解码、GID、冻结状态来源、`resolve()`、`Lock` 与永久链接 |
| `render` | `RenderContext`、`env_view()`、`chapter_markdown()`（mdbook / pandoc 两种 target） |
| `ledger` | 生成“形式化验证账本”章节 |
| `check` / `pin` / `theme` / `newbook` / `build` / `cli` | 命令 |

组件（各自实现，签名固定）：

```python
# tbook/html.py
def build_edition(site, book, edition, model, lock, out_dir: Path) -> Path
# tbook/pandoc.py
def build_pdf(site, book, edition, model, lock, variant: str, out_path: Path, *, stage_dir=None) -> Path  # screen | print
def build_epub(site, book, edition, model, lock, out_path: Path, *, stage_dir=None) -> Path
# tbook/cover.py
def render_cover(site, book, edition, out_path: Path, *, fmt: str = "png", variant: str = "screen",
                 model=None, lock=None, meta=None, width_px: int = 1600) -> Path
# tbook/viz.py, tbook/film.py, tbook/slides.py
def check_ref(book, src: str) -> str | None          # 错误信息或 None
def check(book) -> list[Issue]
def items(book) -> list[dict]                         # 落地页用的条目
def cited_gids(book) -> list[tuple[Path, int, str]]   # 媒体引用的 GID；pin --refresh 与锁文件校验都计入
def render_embed(env, ctx, inner: str, doc) -> str    # 替换媒体块；ctx.target 为 "mdbook" 或 "pandoc"
def build(site, book, out_dir: Path)                  # viz/film：发布到 _site/<slug>/<viz|films>/；
                                                      # slides：构建到 build/slides/<slug>/（发布用 publish）
def publish(site, book, site_dir: Path, *, build_missing=True) -> list[dict]   # 仅 slides
def cli(args) -> int                                  # ./tbook viz|slides|film new|list …
# tbook/site.py
def build(site, books, out_dir: Path, only: set[str] | None = None, *, build_root: Path | None = None) -> Path
# tbook/template.py
def main(args) -> int                                 # status | update | manifest
# tbook/serve.py, tbook/doctor.py, tbook/leanverify.py
def serve(port: int, directory: str) -> int
def run() -> int
def generate(out_dir) -> Path
```

媒体块的输出：mdbook 目标以块级 `<figure class="tr-media tr-viz|tr-film">`（slides 为链接卡片 `.tr-slides`）开头；pandoc 目标输出 Markdown，包在 `::: {.tr-media .tr-viz|.tr-film|.tr-slides}` 中得到 PDF/EPUB 的媒体面板，图片路径指向 `_book/…` 并加入 `ctx.book_files`。

`render.pandoc_env()` 输出的富属性 fenced div（Lua 过滤器 `tools/filters/tr-env.lua` 按输出格式渲染）：

```
:::::: {#thm-x .tr-env .theorem tr-kind="theorem" tr-status="lean" tr-label="定理" tr-number="1.2"
        tr-ref="定理1.2" tr-title="…" tr-badge="LEAN ✓" tr-lean="GID …" tr-lean-name="Lean 名 …" tr-lean-url="URL …"}
内容
::::::
```

`render.mdbook_env()` 输出的 HTML（样式在 `theme/mdbook/`）：

```html
<section class="tr-env tr-theorem tr-status-lean" id="thm-x" data-kind="theorem">
<header class="tr-env-head"><span class="tr-env-label">定理1.2</span><span class="tr-env-title">（…）</span><a class="tr-badge tr-badge-lean" href="…">LEAN ✓</a></header>

内容

<footer class="tr-env-lean"><a class="tr-lean-decl" href="…"><code>D5.S1.Deficit.deficit_three_valued</code></a></footer>
</section>
```

## 8. 工具链版本

| 工具 | 版本 | 来源 |
| --- | --- | --- |
| Python | ≥ 3.11 | 系统 / `actions/setup-python` |
| Pandoc | 3.9（`pypandoc_binary==1.17`） | `requirements.txt` |
| Typst | `typst==0.15.2`（Python 模块） | `requirements.txt` |
| epubcheck | 5.3.0（Python 包内含 jar，需 Java） | `requirements.txt` |
| mdBook | 0.5.4 | CI 用 `taiki-e/install-action`；本地 `cargo install mdbook --version 0.5.4 --locked` |
| Node | ≥ 22.12 | `package.json` |
| KaTeX | 0.18.10 | `package.json` |
| Slidev | 53.0.0 | `package.json` |
| Playwright | `playwright-chromium@1.56.1` | `package.json`；本地可用 `PW_CHROMIUM_PATH` 指向已有 Chromium |

字体：网页用 Google Fonts（Chakra Petch、JetBrains Mono、Noto Sans SC）；PDF 用系统字体加 `tools/fetch-fonts.sh` 拉取的 TTF（`.cache/fonts/`）；幻灯片与视频用 `@fontsource` 自托管。
