---
name: book-film
description: 为书做讲解视频时使用：按 trureturing-film 方案新建并编写视频（确定性 Canvas 动画、Kokoro 英文旁白、程序化配乐、中英双语字幕），本地预览单帧与片段，由构建渲染（未改动时从缓存恢复）并随站点发布，再嵌入书中。
---

# 讲解视频

## 适用范围

**用**：为一章或一组定理制作 1–3 分钟的讲解视频；修改已有视频的脚本或画面；排查视频流水线与构建。

**不用**：可交互的探索（`book-viz`）；面向讲台的演示（`book-slides`）。

**权威**：`templates/film/README.md`（`film.json`、`script.json`、`scenes.js` 规范与流水线）、`theme/film/`（共享引擎与步骤脚本）、`tools/tbook/film.py`（构建单元与站点发布）、示例 `books/example-monograph/films/001-golden-deficit/`。

## 原则

1. **视频是讲解，不是证明。** 片中只有 `film.json` 的 `lean` 列出、且在锁文件中种类为 `theorem` 的声明可以标 `LEAN ✓`（`lean` 列出定义会被 `./tbook check` 报错）；屏幕上的计算用 `badge(a, 'computed')`，论证用 `argued`，开放问题用 `open`。
2. **片中的数字必须精确算出或取自所钉提交。**
3. **旁白英文自然，字幕中文准确**，各一行，不逐字硬译。旁白与字幕写在 `script.json`，它是唯一的时间来源。
4. **颜色只来自令牌**（`C.lean` 绿、`C.now` 琥珀、`C.open` 红、`C.argued` 紫，其余 `C.cyan`、`C.mag`、`C.white`、`C.dim`）。
5. **仓库只存源码**：`film.json`、`script.json`、`scenes.js`、可选 `data/*.json`、`poster.jpg`（≤ 300 KB）。成片是构建产物，与 PDF 一样：构建写到 `build/films/<slug>/<id>/`，站点托管在 `_site/<slug>/films/<id>/`。没有单独的视频 Release。

## 流程

```bash
./tbook film new <book> <NNN>-<name> "<中文标题>" "<English title>"
F=books/<book>/films/<NNN>-<name>
theme/film/setup.sh                  # 每台机器一次：视频 venv（.cache/film/venv）、Kokoro 模型（.cache/film/models）、字体
```

`setup.sh` 把 `theme/film/requirements.txt` 中钉死的包装进独立的视频 venv（Python 3.12 或 3.13），不装进 tbook 的 `.venv`；设置 `PYTHON` 时改为装进该解释器。ffmpeg 来自系统（`apt-get install ffmpeg` 或 `FFMPEG`），Chromium 来自 Playwright 或 `PW_CHROMIUM_PATH`。

1. 写 `script.json`：每个场景 `id`、`name`、`lead`/`tail`、`lines: [[英文旁白, 中文字幕], …]`，可选 `music`、`cues`；发音修正写在 `say`。
2. 写 `scenes.js`：每个场景 `SCENES.<id> = S => { … }`，用 `at(S, k, dur)` / `Q(S, k, '短语')` 与旁白对齐，用 `panel`、`chip`、`stamp`、`leanList`、`closingCard` 等绘制（见 README 的 scenes.js 一节）。
3. 填 `film.json`：`title`/`title_zh`、`summary`/`summary_zh`、`subject_commit`（等于锁文件所钉提交）、`lean`（片中引用的 GID）、`outputs`（视频文件名）。新 GID 后运行 `./tbook pin --refresh`（它收集视频引用的 GID）。
4. 本地迭代（不需要 TTS）：

   ```bash
   theme/film/film.sh $F timeline                 # 暂定时间轴
   theme/film/film.sh $F shot 2 8 14 --poster     # 单帧 → out/shots/，逐张查看
   theme/film/film.sh $F serve                    # 浏览器预览
   theme/film/film.sh $F clip 30 3 960x540        # 3 秒低清片段
   theme/film/film.sh $F poster                   # 生成 poster.jpg，提交入库（只有这一步写它）
   ```

   `./tbook doctor` 会列出缺失的 Chromium、ffmpeg 与字体。
5. 构建视频：

   ```bash
   TBOOK_FILMS=require ./tbook build films --book <book>
   ```

   每部视频是一个构建单元（`./tbook cache status` 中目标为 `films`）：输入未变时从本地缓存或已发布的整站 Release 恢复，否则运行 `film.sh <dir> all`（`FILM_STRICT=1`：只用 TTS 实测的时间轴与自托管字体），把 `outputs` 中的五个文件复制到 `build/films/<slug>/<id>/`。构建不写任何入库文件；`poster.jpg` 只由第 4 步手工更新。渲染后若实际时长与 `film.json` 的 `duration` 不同，构建会警告，按提示更新。
   `TBOOK_FILMS`：`auto`（默认）缓存未命中且工具链齐全时渲染，否则警告并在站点上只显示海报与“视频未构建”；`require` 缺工具链时失败；`skip` 从不渲染（命中缓存仍恢复）。`./tbook build site` 与 `./tbook build all` 同样会渲染或恢复视频。
6. 嵌入章节——**所有语言版本都要加**，`src` 相同，只翻译图注：

   ```markdown
   ::: {.film src="<NNN>-<name>"}
   图注（可含数学与 [@thm-…] 引用）。
   :::
   ```

   外部视频：`::: {.film src="trureturing-film:film-<NNN>-v<k>"}`。HTML 中为 `<video>`：播放站内 `films/<id>/` 的 720p 旁白版，海报为提交的 `poster.jpg`，附 1080p、720p、纯配乐下载；站点没有该视频时显示海报与“视频未构建”。PDF/EPUB 中为海报、图注与站点视频页地址（`site.toml` 没有 `base_url` 时只有海报）。
7. `./tbook build site --book <book> && ./tbook serve` 查看视频页 `<slug>/films/` 与章节中的播放器（手机宽度、深浅主题）。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| `check` 警告 `subject_commit` 与所钉提交不同 | 视频依据的提交过期；复核片中陈述后更新 `subject_commit`，构建会重新渲染 |
| `check` 警告 `release_tag` / `published_tag` 不再使用 | 旧的逐片 Release 字段；删除即可，视频随站点构建 |
| 站点显示“视频未构建” | 缓存未命中且没有渲染：工具链不全（构建日志列出缺项，运行 `theme/film/setup.sh`）或 `TBOOK_FILMS=skip` |
| 改了章节，视频却重新渲染 | 不应发生：键只含视频目录（不含 `out/`、`poster.jpg`、`README.md`）、`theme/film/`、令牌、引擎绘制的书目与 Lean 数据和工具版本；用 `./tbook cache status` 与条目的 `entry.json` 比对输入 |
| 数学符号显示为方框 | 用 `F.math` 字体；CI 安装 `fonts-dejavu-core`、`fonts-freefont-ttf` 作后备 |

## 完成标准

单帧与海报逐张看过；`./tbook check` 通过；`TBOOK_FILMS=require ./tbook build films` 成功；各语言章节都已嵌入，站点视频页、章节播放器（含 iOS Safari）与 PDF 中显示正确。
