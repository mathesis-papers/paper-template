---
name: book-film
description: 为书做讲解视频时使用：按 trureturing-film 方案新建并编写视频（确定性 Canvas 动画、Kokoro 英文旁白、程序化配乐、中英双语字幕），本地预览单帧与片段，打 film-* 标签由 CI 渲染并发布到 Release，再嵌入书中。
---

# 讲解视频

## 适用范围

**用**：为一章或一组定理制作 1–3 分钟的讲解视频；修改已有视频的脚本或画面；排查视频流水线与发布。

**不用**：可交互的探索（`book-viz`）；面向讲台的演示（`book-slides`）。

**权威**：`templates/film/README.md`（`film.json`、`script.json`、`scenes.js` 规范与流水线）、`theme/film/`（共享引擎与步骤脚本）、`.github/workflows/film.yml`、示例 `books/example-monograph/films/001-golden-deficit/`。

## 原则

1. **视频是讲解，不是证明。** 片中只有 `film.json` 的 `lean` 列出、且在锁文件中种类为 `theorem` 的声明可以标 `LEAN ✓`（`lean` 列出定义会被 `./tbook check` 报错）；屏幕上的计算用 `badge(a, 'computed')`，论证用 `argued`，开放问题用 `open`。
2. **片中的数字必须精确算出或取自所钉提交。**
3. **旁白英文自然，字幕中文准确**，各一行，不逐字硬译。旁白与字幕写在 `script.json`，它是唯一的时间来源。
4. **颜色只来自令牌**（`C.lean` 绿、`C.now` 琥珀、`C.open` 红、`C.argued` 紫，其余 `C.cyan`、`C.mag`、`C.white`、`C.dim`）。
5. **仓库只存源码**：`film.json`、`script.json`、`scenes.js`、可选 `data/*.json`、`poster.jpg`（≤ 300 KB）。其余产物在 `<dir>/out/`（已忽略），成片只发布为 Release 资产。

## 流程

```bash
./tbook film new <book> <NNN>-<name> "<中文标题>" "<English title>"
F=books/<book>/films/<NNN>-<name>
theme/film/film.sh $F setup          # 一次：pip 包、Kokoro 模型（.cache/film/models）、字体
```

1. 写 `script.json`：每个场景 `id`、`name`、`lead`/`tail`、`lines: [[英文旁白, 中文字幕], …]`，可选 `music`、`cues`；发音修正写在 `say`。
2. 写 `scenes.js`：每个场景 `SCENES.<id> = S => { … }`，用 `at(S, k, dur)` / `Q(S, k, '短语')` 与旁白对齐，用 `panel`、`chip`、`stamp`、`leanList`、`closingCard` 等绘制（见 README 的 scenes.js 一节）。
3. 填 `film.json`：`title`/`title_zh`、`summary`/`summary_zh`、`subject_commit`（等于锁文件所钉提交）、`lean`（片中引用的 GID）、`release_tag`（`film-<book>-<NNN>-v1`）、`outputs`。新 GID 后运行 `./tbook pin --refresh`（它收集视频引用的 GID）。
4. 本地迭代（不需要 TTS）：

   ```bash
   theme/film/film.sh $F timeline                 # 暂定时间轴
   theme/film/film.sh $F shot 2 8 14 --poster     # 单帧 → out/shots/，逐张查看
   theme/film/film.sh $F serve                    # 浏览器预览
   theme/film/film.sh $F clip 30 3 960x540        # 3 秒低清片段
   theme/film/film.sh $F poster                   # 生成并提交 poster.jpg
   ```

   需要 Chromium（`PW_CHROMIUM_PATH` 或 `npx playwright install chromium`）与 ffmpeg（`$FFMPEG`、`PATH` 或 `imageio-ffmpeg`）。`./tbook doctor` 会列出缺失项。
5. `./tbook check` 无错误后提交源文件，推送与 `release_tag` 相同的标签：

   ```bash
   git tag film-<book>-<NNN>-v1
   ```

   ```bash
   git push origin film-<book>-<NNN>-v1
   ```

   `film.yml` 在 CI 上合成旁白、配乐、逐帧渲染、编码并创建 Release（1080p 旁白版、纯配乐版、720p 版、封面）。首次 TTS 后若实际时长不同，按日志更新 `film.json` 的 `duration`。Release 出现后把 `film.json` 的 `published_tag` 设为该标签并提交：在此之前书、落地页与视频页只显示海报和“尚未发布”，不嵌入播放器（播放地址指向 `published_tag` 的 Release，避免嵌入不存在的资产）。已发布的标签不再改动；新剪辑递增 `v<k>` 并同步 `release_tag`，新 Release 出现后再更新 `published_tag`。
6. 嵌入章节——**所有语言版本都要加**，`src` 相同，只翻译图注：

   ```markdown
   ::: {.film src="<NNN>-<name>"}
   图注（可含数学与 [@thm-…] 引用）。
   :::
   ```

   外部视频：`::: {.film src="trureturing-film:film-<NNN>-v<k>"}`。HTML 中为 `<video>`（海报 + Release 地址）；PDF/EPUB 中为海报、图注与视频页地址。
7. `./tbook build site --book <book> && ./tbook serve` 查看视频页 `<slug>/films/` 与章节中的播放器。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| `check` 警告 `subject_commit` 与所钉提交不同 | 视频依据的提交过期；复核片中陈述后更新 `subject_commit`，必要时发新剪辑 |
| 视频页显示“尚未发布” | `film.json` 的 `published_tag` 为 `null`：还没推送 `release_tag` 标签，或 CI 失败（查看 `film.yml` 运行日志），或 Release 已发布但还没把 `published_tag` 设为该标签 |
| 数学符号显示为方框 | 用 `F.math` 字体；CI 安装 `fonts-dejavu-core`、`fonts-freefont-ttf` 作后备 |
| Safari 不播放 | Release 资产以 `application/octet-stream` 提供；“观看/下载”链接始终可用 |

## 完成标准

单帧与海报逐张看过；`./tbook check` 通过；标签推送后 Release 资产齐全；各语言章节都已嵌入，站点视频页与 PDF 中显示正确。
