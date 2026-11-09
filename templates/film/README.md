# 视频模板 · Film template

本目录是 `./tbook film new` 的起始模板；每部视频按 [trureturing-film](https://github.com/the-omega-institute/trureturing-film) 的方案完全由代码生成：确定性的 Canvas 动画、本地合成的英文旁白（Kokoro-82M）、程序化配乐，内嵌中英双语字幕。仓库只存源码；成片与 PDF 一样是构建产物：`./tbook build films|site|all` 渲染（输入未变时从缓存恢复）到 `build/films/<slug>/<id>/`，站点托管在 `<slug>/films/<id>/`，书中以 `<video>` 嵌入。

This directory is the starting point of `./tbook film new`. Every film follows the trureturing-film scheme and is generated entirely by code: a deterministic Canvas animation, English narration synthesized locally with Kokoro-82M, a procedural score, and burned-in Chinese and English subtitles. The repository holds source only; the videos are build outputs like the PDFs: `./tbook build films|site|all` renders them (or restores them from the build cache when nothing they depend on changed) into `build/films/<slug>/<id>/`, the site hosts them at `<slug>/films/<id>/`, and the book embeds them.

## 新建 · Create

```bash
./tbook film new example-monograph 002-carry-rules "进位规则" "The Carry Rules"
./tbook film list
```

`books/<slug>/films/<NNN>-<name>/` 只放这些源文件 · a film directory holds only:

| 文件 File | 作用 Purpose |
| --- | --- |
| `film.json` | 元数据（下表） · metadata (below) |
| `script.json` | 旁白与字幕，唯一的时间来源 · narration and subtitles, the single source of timing |
| `scenes.js` | 每个场景一个 `SCENES.<id> = S => { … }` · one drawing function per scene |
| `data/*.json` | 可选数据，内联为 `DATA.data.<名>` · optional data, inlined as `DATA.data.<name>` |
| `poster.jpg` | 提交入库的小海报（≤ 300 KB，手工运行 `film.sh <dir> poster` 生成；构建从不改写它） · the committed poster, written by hand with the `poster` step, never by the build |
| `README.md` | 可选：场景说明、每条论断的出处 · optional notes, the source of every claim |

流水线的工作文件都在 `<dir>/out/`（已被 `.gitignore` 忽略），构建把成片复制到 `build/films/<slug>/<id>/`。The pipeline works in `<dir>/out/` (git-ignored); the build copies the videos to `build/films/<slug>/<id>/`.

## film.json

```json
{
  "id": "001-golden-deficit",
  "title": "The Golden Deficit",
  "title_zh": "黄金亏量",
  "summary": "Zeckendorf digits, golden carries and the deficit of beta …",
  "summary_zh": "Zeckendorf 数字、黄金进位与 β 的亏量……",
  "subject": "https://github.com/the-omega-institute/trureturing",
  "subject_commit": "8a24ea4e79de962725aab9d9b49cc605fcc211d8",
  "released": "2026-11-08",
  "duration": "0:50",
  "resolution": "1920x1080@30",
  "style": "trureturing cyberpunk · …",
  "narration": {"language": "en", "engine": "Kokoro-82M v1.0 (onnx)", "voice": "af_heart"},
  "subtitles": ["zh", "en"],
  "lean": ["D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"],
  "outputs": {
    "narrated": "example-monograph_001_narrated_EN_subs_ZH-EN.mp4",
    "music_only": "example-monograph_001_music_only_subs_ZH-EN.mp4",
    "narrated_720p": "example-monograph_001_720p_narrated.mp4",
    "music_only_720p": "example-monograph_001_720p_music_only.mp4",
    "cover": "example-monograph_001_cover.jpg"
  }
}
```

| 字段 Field | 规则 Rule |
| --- | --- |
| `id` | 等于目录名 `<NNN>-<name>` · equals the directory name |
| `title`, `title_zh` | 英文、中文标题，各一行 · English and Chinese titles, one line each |
| `summary`, `summary_zh` | 可选，一段简介（落地页与视频页） · optional one-paragraph blurbs |
| `subject_commit` | 制作时依据的 trureturing 提交，应等于 `trureturing.lock.json` 所钉提交；不等时 `./tbook check` 警告 · the trureturing commit the film was made against; should equal the pinned commit (a warning otherwise) |
| `released`, `duration` | `YYYY-MM-DD`，`m:ss`：旁白版的实际时长（`tts` 步骤与构建在不一致时提示） · the narrated length; the `tts` step and the build warn when it differs |
| `resolution` | 固定 `1920x1080@<fps>` · always 1920×1080 |
| `narration`, `subtitles` | 旁白语言/引擎/声音；字幕只支持 `zh`、`en` · subtitles are `zh` and/or `en` |
| `lean` | 片中引用的定理 GID，必须都在锁文件中且种类为 `theorem`；片中与视频页都以 LEAN ✓ 链接到所钉提交 · theorems cited by the film; each must be in the lock with kind `theorem` |
| `outputs` | 成片文件名：`narrated`、`music_only`（1080p）、`narrated_720p`、`music_only_720p`（可省略，取默认名）、`cover`；站点地址为 `<slug>/films/<id>/<文件名>`，播放器播放 `narrated_720p` · the video file names; the site serves `<slug>/films/<id>/<file>` and the players play `narrated_720p` |

旧的 `release_tag`、`published_tag`（逐片 Release）不再使用，`./tbook check` 给出警告，删除即可。The former `release_tag` and `published_tag` (per-film releases) are no longer used: `./tbook check` warns; remove them.

## script.json

```json
{
  "voice": "af_heart", "speed": 0.94,
  "say": {"Lean": "Leen"},
  "music": {"bpm": 84, "progression": "d-minor"},
  "scenes": [
    {"id": "zeck", "name": "ZECKENDORF", "lead": 1.6, "tail": 0.5,
     "music": [1.0, 0.4, 0.3, 0.0, 0.1],
     "cues": [{"line": 1, "at": 2.8, "kind": "stamp"}],
     "lines": [["English narration.", "中文字幕。"]]}
  ]
}
```

- `id`：小写标识符，对应 `SCENES.<id>`；`name`：HUD 上的场景名。
- `lead` / `tail`：场景开头、结尾的静默秒数；同一场景内相邻两句之间固定 0.6 秒。
- `lines`：`[英文旁白, 中文字幕]`，各一行；字幕自动换行。英文自然，中文准确，不逐字硬译。
- `say`：发音修正（只影响合成，不影响字幕）；`music`：节拍与和声；场景 `music`：五层音量 `[pad, bass, arp, kick, hat]`；`cues`：音效点（`stamp`、`chime`、`impact`、`glitch`）。

## scenes.js

场景函数由共享引擎 `theme/film/engine.js` 调用，`S = { u: 场景内秒数, d: 场景时长, p: u/d, t: 全片时间, f: 帧号, L: 本场景各句 }`。

- 时间：`at(S, k, dur, off)` 从第 k 句开始的 0→1 进度；`Q(S, k, '短语')` 从该短语被说出的时刻开始；`badgeQ(S, [[k, 短语|null, kind], …])` 顶部状态条。
- 绘制：`txt`、`panel`（切角面板）、`box`（角括号框）、`chip`、`dot`、`stamp`、`drawHyper`、`leanList`、`closingCard`。
- 颜色（来自 `theme/tokens.json`）：`C.lean` 绿色只给 Lean 已验证；`C.now` 琥珀色只给当前焦点；`C.open` 红色标开放问题；`C.argued` 紫色标论证但未经内核检验；其余用 `C.cyan`、`C.mag`、`C.white`、`C.dim`。
- `badge(a, kind)`：`lean`（绿）、`open`（红）、`argued`（紫）、`computed`（青，屏幕上的计算，不是证明）。
- 字体：`F.orb`（Orbitron 标题）、`F.disp`（Chakra Petch）、`F.zh`（Noto Sans SC）、`F.mono`（JetBrains Mono 数据）、`F.raj`（Rajdhani 英文字幕）、`F.math`（数学符号）。
- 可选：`FILM.init.push(fn)` 预计算；`FILM.poster = () => { … }` 自定义海报；`FILM.speed[id]` 星空速度；`DATA.data.<名>` 读取 `data/*.json`。
- 片中的数字必须在页面上精确算出或取自所钉提交；把 Lean 已验证的结论与屏幕上的计算区分开（`badge`）。

## 流水线 · Pipeline

```bash
theme/film/setup.sh                # 每台机器一次：视频 venv 与钉死的包（.cache/film/venv）、Kokoro 模型（.cache/film/models）、字体
F=books/<slug>/films/<NNN>-<name>
theme/film/film.sh $F timeline     # 无 TTS 的暂定时间轴（预览用）
theme/film/film.sh $F shot 2 8 14 --poster   # 单帧截图 → out/shots/
theme/film/film.sh $F serve        # 浏览器预览 index.html?play
theme/film/film.sh $F clip 30 3 960x540      # 3 秒无声低清片段 → out/clip.mp4
theme/film/film.sh $F poster       # out/<cover>.jpg 与提交入库的 poster.jpg（只有这一步写它）
theme/film/film.sh $F all          # tts → music → mix → frames → mux → small → cover（构建运行的就是这一步）
```

Python 包钉在 `theme/film/requirements.txt`，`setup.sh` 装进独立的视频 venv（Python 3.12 或 3.13；设置 `PYTHON` 时装进该解释器），tbook 的 `.venv` 不受影响；`film.sh` 与构建在未设置 `PYTHON` 时使用这个 venv。Chromium：设置 `PW_CHROMIUM_PATH` 使用已有浏览器，否则用 Playwright 自带的（`npx playwright install chromium`）。ffmpeg 来自系统：`$FFMPEG` 或 `PATH`（`apt-get install ffmpeg`）。

## 构建与发布 · Build and publish

1. `./tbook check` 无错误；提交 `film.json`、`script.json`、`scenes.js`、`poster.jpg`。
2. `./tbook build films --book <slug>`（`build site`、`build all` 同样）：每部视频是一个构建单元。键覆盖视频依赖的全部输入——视频目录（不含 `out/`、`poster.jpg`、`README.md`）、`theme/film/`、`theme/generated/tokens.mjs`、`tools/tbook/film.py`、引擎绘制的书目与 Lean 数据（所钉提交、引用的声明）及片内文字、字体与 Playwright 的 npm 版本、Kokoro 模型版本，以及 ffmpeg、Node、Chromium、视频 Python 的版本；不含站点地址。键未变时从本地缓存或已发布的整站 Release 恢复，否则以 `FILM_STRICT=1` 运行 `film.sh <dir> all` 并把 `outputs` 的五个文件复制到 `build/films/<slug>/<id>/`。
3. `TBOOK_FILMS`：`auto`（默认）缓存未命中且工具链齐全时渲染，否则警告，站点只显示海报与“视频未构建”；`require` 缺工具链时失败；`skip` 从不渲染（命中缓存仍恢复）。
4. 站点把视频放在 `<slug>/films/<id>/<文件名>`（同源，Content-Type 与按字节范围请求正确，iOS Safari 可以播放）；整站 Release 附带构建缓存，没有缓存的构建可以从中恢复。
5. 在章节中嵌入：`::: {.film src="<NNN>-<name>"}` 或 `::: {.film src="trureturing-film:film-<NNN>-v<k>"}`，块内文字为图注。

1. `./tbook check` passes; commit `film.json`, `script.json`, `scenes.js`, `poster.jpg`.
2. `./tbook build films --book <slug>` (or `build site`, `build all`): each film is a build unit keyed by everything its videos depend on (not the site's address); an unchanged film is restored from the local cache or the latest whole-site release, a changed one is rendered with `film.sh <dir> all` (`FILM_STRICT=1`) into `build/films/<slug>/<id>/`.
3. `TBOOK_FILMS=auto|require|skip` decides what happens when a film must be rendered and the toolchain is missing: leave it out with a warning, fail, or never render.
4. The site serves the videos at `<slug>/films/<id>/<file>`, same origin, which iOS Safari needs.

## 边界 · Scope

视频是讲解，不是证明。片中标 LEAN ✓ 的结论以 trureturing 中已冻结的 Lean 声明为准；其余是屏幕上的计算或论证，必须如实标注。A film explains; it proves nothing. Only results marked LEAN ✓ rest on frozen Lean declarations; everything else is labelled as computed on screen or argued.
