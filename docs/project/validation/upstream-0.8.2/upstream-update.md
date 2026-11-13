## 模板升级 0.7.0 → 0.8.2

来源：`https://github.com/the-omega-institute/trureturing-books-template.git` @ `v0.8.2` (`85e533c20bad`)

新增 7 · 更新 57 · 删除 0 · 冲突 0 · 保留本地改动 0

### 新增（7）

- `docs/FORMALIZATION-REQUESTS.md`
- `tools/tbook/evidence.py`
- `tools/tbook/requests.py`
- `tools/tests/kit_harness.mjs`
- `tools/tests/test_viz_kit.py`
- `tools/tests/test_viz_runtime.py`
- `tools/tests/viz_runtime_harness.mjs`

### 更新（57）

- `CLAUDE.md`
- `docs/ARCHITECTURE.md`
- `docs/AUTHORING.md`
- `docs/CHANGELOG.md`
- `docs/PDF-TYPOGRAPHY.md`
- `docs/PUBLISHING.md`
- `docs/UPGRADING.md`
- `docs/VERIFICATION.md`
- `requirements.txt`
- `skills/book-export/SKILL.md`
- `skills/book-slides/SKILL.md`
- `skills/book-viz/SKILL.md`
- `skills/book-write/SKILL.md`
- `skills/theorem-formalize/SKILL.md`
- `templates/viz/README.md`
- `templates/viz/index.html`
- `theme/beamer/README.md`
- `theme/i18n/en.toml`
- `theme/i18n/zh.toml`
- `theme/mdbook/tr-book.css`
- `theme/slides/README.md`
- `theme/slides/components/TheoremCard.vue`
- `theme/typst/academic.typ`
- `theme/viz/kit.js`
- `theme/viz/shell.js`
- `theme/viz/solid-core.js`
- `theme/viz/theme.css`
- `tools/filters/typst-compat.lua`
- `tools/node/slides-check.mjs`
- `tools/node/slides-lib.mjs`
- `tools/node/viz-common.mjs`
- `tools/node/viz-shots.mjs`
- `tools/node/viz-testkit.mjs`
- `tools/node/viz-thumbs.mjs`
- `tools/node/viz-validate.mjs`
- `tools/tbook/academic.py`
- `tools/tbook/check.py`
- `tools/tbook/cli.py`
- `tools/tbook/doctor.py`
- `tools/tbook/ledger.py`
- `tools/tbook/pandoc.py`
- `tools/tbook/render.py`
- `tools/tbook/site.py`
- `tools/tbook/slides.py`
- `tools/tbook/template.py`
- `tools/tbook/viz.py`
- `tools/tests/solid_harness.mjs`
- `tools/tests/test_academic.py`
- `tools/tests/test_html.py`
- `tools/tests/test_pandoc.py`
- `tools/tests/test_pdf_layout.py`
- `tools/tests/test_pdf_math.py`
- `tools/tests/test_slides.py`
- `tools/tests/test_template_layers.py`
- `tools/tests/test_viz.py`
- `tools/tests/test_viz_solid.py`
- `tools/tests/test_written_proof.py`

### 迁移

无需迁移。

### 变更记录

阅读跨越的各版本说明，处理标为“需要手动操作”的条目：https://github.com/the-omega-institute/trureturing-books-template/blob/v0.8.2/docs/CHANGELOG.md

<details>
<summary>docs/CHANGELOG.md</summary>

## [0.8.2] - 2026-11-13

### 修复

- 学术版 PDF 的行内分式按字形实际边界留出上下间距，修复分母与下一行分子相交；保留原有数学字体、适宽与行内流动，并补充中英文真实段落及窄宽度回归检查。

## [0.8.1] - 2026-11-13

### 修复

- 学术 PDF 经 pikepdf/QPDF 无损压缩对象与 Flate 流，保留图像、文本、字体、书签、链接和可选结构标签；仅采用更小的结果。来源书库的中英文长篇预印本在未降采样的情况下超过 50 MB，压缩后分别为 47,234,418 与 49,191,378 字节。

## [0.8.0] - 2026-11-13

### 新增

- 形式结论支持 `status="written-proof" proof="<proof-id>"`：优先使用匹配的 Lean 验证，仅在没有匹配验证时允许书面证明；每版要求非空证明、裸 DOI、原文定位及 trureturing-requests issue，校验标题与书籍登记，禁止 `lean`，与开放问题分开；HTML、三种 PDF、EPUB、Slidev 与 Beamer 使用紫色书面证明徽章，来源和请求可点击，不计入 Lean 数量，账本单列。新增 `./tbook requests [--json]` 及站点清单需求数据，按 issue 汇总书籍与结果，翻译不重复计数。

- 独立模板层：下游 `template.d/<name>.toml` 与清单、保留的文档/skill/工作流前缀，沿用同一升级命令、三方冲突、迁移、版本与 git 历史规则；安装前拒绝路径认领重叠及认领下游专属排除路径，独立源仓库无需上游配置即可生成层清单。每周 `template-sync` 按来源独立开 PR。来源：第二个出版模板需叠加领域规则而不分叉上游。
- 在 Slidev 之外支持学术 Beamer 演示稿：可选书中语言版本的子集、4:3/16:9 画布、原创 Apache-2.0 白底讨论班主题及演示稿自有主题和图片。结果块、所钉提交与验证账本均从书模型和锁文件生成；TeX 引用检查处理注释、原样文本与嵌套参数。
- 原创讨论班主题提供实色导航、标题与页脚条带，块标题为白字、块正文用 12% 浅色底，开放问题用红色，标题框有均匀阴影，可声明合作者。验证表每帧最多十二条结果，高分辨率纸面静态图占满正文宽度，导航按钮按需启用。
- 纸面可视化静态图链接在线页面，规范图件由现有脚本生成；听众版隐藏备注，另导出备注版 PDF。两种 PDF 均进入幻灯片缓存与发布、章节卡片、站点清单及书籍 Release 附件，附英文报告示例。
- 固定 Tectonic 0.16.9、校验哈希的 Linux 二进制、带版本的 TeX 资源包、时间基准与确定性模式；工具链体检、托管运行器与可选容器支持学术演示稿。源码契约及可复现设置见 `theme/beamer/README.md`。
- 被引用卡的停帧成为契约：会自己播放的卡在页面的卡片表里写 `still`（时间轴上的值或 `'end'`），把表交给 `kit.cards(el, { presets })`，它把声明写到卡上的 `data-still`（也可直接写在 HTML 里），`cards.still(id)` 读回；`TRV.still` 时页面把时钟放到那里。`stageFirstChecks` 对点了之后时间轴在走、却没有 `data-still` 的卡给出警告（`T.warn`：打印 `WARN`、计数，不算失败；`{ still: false }` 关掉）。`viz-testkit.mjs` 新增 `openStill(T, book, id, preset, lang)`（按 `viz-thumbs.mjs` 出图的方式打开那张卡的静止帧，测试里核对停帧读数 = 图注里的数）与共用的 `STILL`、`stillQuery`、`prepareStill`（`viz-thumbs.mjs` 改用它们）。示例页 `golden-carry`、`phase-torus` 与起始页面补了声明，测试核对 CANCEL、FILL、TORUS 的停帧。
- `playsAfter(page, action, read)`（`viz-testkit.mjs`）：先把观察器装进页面再做动作，页面在每一帧与每次 DOM 变化时取样 `{ playing, t }`（默认读时间轴的 ▶ 与滑块），记下“开始播放并越过起点”；只播零点几秒的卡也不会漏。`stageFirstChecks` 的停帧检查用同一观察器，示例测试里 ZOOM-OUT、FILL、SWEEP 改用它。`skills/book-viz` 写明短于一两秒的自动播放一律这样测。
- 画图库：`Axes.xaxis`/`yaxis` 不传 `size` 时刻度字号按画布宽度取手机上不低于 10 px 的值（`Canvas.label_floor`：429 宽以内 12，480 宽 13.5，716 宽 20；`WRAP` 图按最宽一栏），显式传了 `size` 的照旧，示例与已有的图逐字节不变；`fig.overline(x, y, "*c*")` 与 `fig.hat(…)` 在字上画横线与尖帽，取代定位不稳的组合附加符；`mono=True` 文字与 `fig.chip` 里的减号“−”改用正文字体（`tr-fig-sans`，`tr-book.css` 同步；**含这种减号的已有图会被 `./tbook check` 判为过期，升级后运行 `./tbook fig build` 重新生成并提交**）；球的明暗 `sp.shade(role)` / `sp.outline(shade=role)`（受光一点最浓、向边缘变淡，用同心圆盘画成，只用颜色角色）、球冠 `sp.cap(轴, 角, role)` 与 `sp.patch(…, front=True)` 只填朝向读者的部分。示例 `golden-rotation` 的球加了明暗。
- 可视化运行时：`kit.plot` 的 `g.text` 与 `g.legend` 支持下标、上标（字符串里写 `_{…}`、`^{…}`，或传片段数组 `[text, { t, sub: true }, …]`），不含这两种写法的字符串照原样画；新的中性对勾 `.nummark` 给页面自己核对过的数，绿色 `.okmark` 只留给 `.lean` 依据框；`viz-validate` 与 `./tbook check` 对 `.lean` 框之外的 `.okmark` 给警告（示例 `golden-carry` 的两处已改为 `.nummark`）。示例专著的浏览器测试覆盖这三项与图例下标。
- 视频的实体镜头（#45）：`film.json` 写 `"solid": true` 的视频可以在场景里用 `solid(key, { x, y, w, h, yaw, pitch, zoom … })` 画受光的实体，图元与页面的 `kit.solid` 同名（`surface`、`poly`、`glass`、`tube`、`line`、`arrow`、`ring`、`bead`、`fan`），`end(a)` 同步用造型核心 `theme/viz/solid-core.js` 画到离屏 WebGL 画布再 `drawImage` 合成，字幕、标签、徽章与面板仍盖在上面；`sh.anchor(v)` 给二维标签的位置与“是否被实体挡住”。没有时钟、动画循环与随机数，像素比 1：同一时刻两次渲染逐像素相同，与之前画过的帧无关（分段并行截帧与整段相同）。只有 `"solid": true` 的视频才在 `out/solid/` 放造型核心与 three.js 并在启动前导入；不能创建 WebGL 上下文时页面启动失败并说明原因（不回退）。`theme/film/lib.js` 以 `--enable-unsafe-swiftshader` 启动 Chromium，`FILM_CHROMIUM_ARGS` 可加参数；`./tbook doctor` 报告能否画实体镜头。新增 `film.json` 的 `scripts`：书里的经典脚本（如 `viz/<id>/model.js`），内联在 `scenes.js` 之前，让页面与视频共用一处造型。示例片 001 的结尾镜头画示例页 `phase-torus` 的环面，造型移到 `books/example-monograph/viz/phase-torus/model.js`，页面与视频都加载它；旁白、字幕与时间轴不变。有实体镜头的视频的构建键加上 `theme/viz/solid-core.js`、`theme/viz/vendor/` 与 `scripts` 所列脚本。
- `./tbook build films --film <NNN>-<name>`（可重复）：只渲染或恢复这几部视频，本书其他视频只从缓存恢复、不渲染；`build site`、`build all` 不受影响（不接受 `--film`）。
- 实验室运行时与出图工具的七处缺口（#54）：
  - `kit.stage3` 的虚线沿整条投影后的路径连续：`st.path`、`st.line`、`st.arc`、`st.circle` 带 `dash` 时，按前后两侧分成的每一段各用一条子路径，并把虚线相位（`lineDashOffset`）设成它之前的投影长度，采样疏密画出来一样（原先逐段描线，每段都从头起一次虚线，采样一密整条线就成了实线）。不带虚线的路径、闭合路径、背面变淡与绘制顺序不变（浏览器测试逐像素核对与原算法相同）。`kit.solid` 与视频实体镜头共用的 `solid-core.js` 本来就沿整条折线切虚线，新增回归检查。
  - `kit.plot` 新增 `g.arrow([x0, y0], [x1, y1], { color, width, dash, head, headSize, glow, alpha })`：数据坐标，用法同 `st.arrow`。
  - 图例色块新增正文墨色 `.sw.ik`（`var(--ink)`），写法与下游各页自带的那份相同。
  - 舞台左上的标题块（`.hud-tl`）与右上的场景按钮（`.hud-tr`）不再互相压住：`shell.js` 量出两者的文字行与按钮是否相碰，相碰时给舞台加 `.hud-stack`，标题块排到按钮下面（`--hud-tr-bottom`）；不相碰时位置不变，所以宽屏画面照旧。在尺寸、字体、语言与标题文字变化时重算；封面与静态图（`?thumb=1`、`?shot=1`）不动。
  - 大写只作用于词：主题仍把舞台标签、面板与小图标题、卡片代号、按钮排成大写，`shell.js` 新增 `TRV.keepCase`，把其中的希腊字母（及 µ）与单个字母的变量包进 `<span class="keepcase">`（`text-transform: none`），页面加载时整页处理一次，之后页面写入的文字由 `MutationObserver` 处理，`st.tag` / `sc.tag` 写标签时也调用（`kit.setTag`）。δ 不再显示成 Δ，u、m、φ 不再变成 U、M、Φ；两个以上拉丁字母的词照样大写，夹在两个词之间的冠词 a 也照样大写，`textContent` 不变，已写成大写希腊字母的不受影响。CSS 的 `text-transform` 不能按字符豁免，所以在写入的文字上加标记，作者不必逐个加 `raw`。质量门 `stageFirstChecks` 新增“capitals”：中英两种语言、每张卡之后，查被排成大写的小写希腊字母（`capitalGreek(page)`），给警告。
  - 新的依据类名 `.lean.frozen`（`FROZEN`，中性的墨色）：trureturing 中已冻结、但正文没有用定理环境引用的定理。链接照样写 `data-lean-gid`（必须是锁文件里的 `theorem`，`./tbook pin --refresh` 会解析它），不列进登记表的 `lean`。`viz-validate` 与 `./tbook check` 认得它：没有 `data-lean-gid` 链接的 FROZEN 框、`.lean` 框上六种之外的类名给警告；`./tbook check` 另对正文已用定理环境引用、却放在 FROZEN 框里的 GID 给警告。浏览器质量门的依据检查把 FROZEN 框当作中性：要有 Lean 链接，不要求列进登记表。
  - `viz-shots.mjs` 新增 `--width`（可选 `--height`）与 `--preset <卡>`：改桌面、书内、手机三种画面的视口（封面固定 1280×720），开在那张卡上，可与 `--views embed` 组合成章节里那张图的窄宽度画面；文件名带上宽度与卡名（`<id>-embed-390-zh-<卡>.png`）。`--plan` 只列出要拍的画面。不带这些参数时与原来完全一样。
  - 下游升级后可以删掉的绕行：`pulse-area-virtual-z` 的 `dashPath`（改回 `st.path(pts, { dash })`）；`bloch-noise`、`two-angle-addressing`、`zyz-compile`、`eth-horizon-crossover` 的 `.sw.ik`；各页为躲按钮手写的 `.hud-tl { top: 46px }`（手写的 `top` 会盖过运行时的排法）；为保住变量加的 `raw`；用 `p.note` 加 `data-trureturing-path` 写的“已冻结、正文未引用”（`navier-stokes-p-np`、`timeless-causal-crystal`、`gram-causal-elliptope`）可改成 `.lean.frozen` 框，改后运行 `./tbook pin --refresh`。
- 旁白短语对不上不再静默：`Q(S, k, '短语')`、`phraseAt`、`badgeQ` 的短语不在第 k 句旁白里（或 `at`/`Q` 的句号越界）时，`./tbook check` 静态扫描 `scenes.js` 里字面量形式的调用并给警告，`film.sh <dir> timeline|build|all` 报出场景、行号与短语（`FILM_STRICT=1` 时失败，构建就这样运行），引擎渲染时也报出写成变量的短语。

### 变更

- 媒体连排两块就报（**下游升级后会出现新警告，需要手动操作**）：`./tbook check` 原先从第三块起才报，现在相邻两块 `.figure`、`.viz`、`.film`、`.slides` 只隔着空行或 HTML 注释时就给警告，每一对报在第二块，点名两块各自的种类、`src`（实验卡带 `preset`，完整实验室标为 the full lab）与行号；不带 `preset` 的完整实验室紧跟同一页面的卡时，另提示把实验室挪到章末最后一段之后，或在两者之间用一句正文交代。示例专著第一章的完整实验室与视频之间补了一句正文（中英同步）。`skills/book-write`、`skills/book-viz`、`skills/book-figure`、`docs/AUTHORING.md` 与 `docs/ARCHITECTURE.md` 改为“相邻两块之间要隔着正文”。来源：#44。
- 引擎（`theme/film/`）改动后，所有视频的构建键都变了，下一次构建会把每部视频重新渲染一次。没有实体镜头的视频画面不变（示例片前四个场景的抽样帧与海报，改动前后逐像素比对相同），LEAN 清单只在命名空间会被误读时改为显示 GID。

### 修复

- 共享可视化布局让舞台、导览与下方图条在短窗口中各占一块区域，允许完整实验室纵向滚动；沿用主线标题避让。质量门覆盖双语引用卡的实际框高、窄桌面、手机、静帧，以及文字、图例、控件与滚动可达性。示例进位舞台补足结果行空间，收缩窗口按可用高度布局点云、分行保留完整公式，书内导览采用一句说明；浏览器回归同时核对画布字形边界和结果行像素，`book-viz` 补上相应验收步骤。来源：下游 trureturing-books#157 与模板 #41。
- 可视化：浏览器质量门（`stageFirstChecks` 打开的被引用卡与框高）和 `viz-thumbs.mjs`（要拍、要保留的静帧）读到的章节引用与出版的书一致。`tools/node/viz-common.mjs` 的 `vizCitations` 改为调用构建本身的 `tbook.viz.citations`（`tbook.model.load_edition`，解释器的选法同 `./tbook`）：`book.toml` 的语言版本、`SUMMARY.md` 选中的章节（草稿与未列出的文件不算）、构建的 Markdown 语法（单引号、不加引号、引号里带花括号的属性；代码块与 HTML 注释里的不算）、种类（`.figure .viz` 是静态图）以及 `preset` 与 `height` 的读法。此前它用一条正则扫描各语言目录下的全部 `.md`，漏掉这些写法的真实引用，却把代码块、注释、草稿与未列出文件里的块当作引用。读不了章节时（Python 不可用，`SUMMARY.md` 缺失或有误，列出的章节不存在）报错，不再当作没有引用（`viz-thumbs.mjs` 会据此删去静帧）；没有目录的语言版本没有正文，不引用任何卡。`vizCitations` 与 `citedCards` 的调用方式与返回格式不变。

- PDF 数学导出（#56）：保留上下标后分式、空格与普通符号的 Typst 词法边界；原始 Taylor、monitoredStep 及后续 `se`、`salpha` 复现经过真实转换链编译并测量。
- 实体舞台（#57）：管子参与遮挡，透明曲面和多面体不挡标记，`pick: false` 穿透拾取；逐顶点透明度、球面圆、标签衬底与二维叠加层；投影和指针统一到画布内框。首帧异步准备着色器，点卡更新视口外帧。实体质量门可指定卡，默认尝试两个转动方向，暂停共享时钟后查释放上下文；补齐独立浏览器几何、像素与混合舞台回归检查及上游示例地址。

- 文档语言与原文件保持一致：学术演示稿、站点构建后命令与模板层说明沿用中文；仓库守则明确现有文档、新文档及多语言文档的语言约定。
- 实体舞台的浏览器单元测试（`tools/tests/solid_harness.mjs`）不再把测试页写死挂在 `example-monograph` 下：改为挂在第一本可见、且有 `viz/` 的书下。下游书库用 `site.toml` 的 `hide = ["example-*"]` 隐藏示例书，可视化服务器只服务可见的书，原写法在下游会因取不到运行时而失败；没有可用的书时这组测试跳过。
- 图例（`.hud-bl`）里的 `<sub>`、`<sup>` 贴着前一个字：每一项改为色块加一行行内文字，不再是带间距的 flex 项（下游不必再用 `<bdi>` 包裹）。
- 视频的 LEAN 清单按完整 GID 解析：`DATA.lean` 每条新增 `label`，`leanList` 与视频页显示它——Lean 全名，命名空间不在模块路径上时改显示 GID（下游 `…/Bloch/QubitBloch.B_formula_core` 的 Lean 全名在命名空间 `…Measurement.FourQubitParentConstruction` 里，原样显示会被读成另一个模块的同名声明）；`short` 取自所引 GID 的名字。引擎新增 `leanCite(gid)`，示例片改为按 GID 查引用，不再按短名取第一个匹配。

</details>

### 下一步

1. 重新安装依赖：`pip install -r requirements.txt`、`npm ci`。
2. 验证：`./tbook doctor`、`./tbook check`、`./tbook build all`，并运行单元测试。
