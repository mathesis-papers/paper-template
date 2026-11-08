# 视频模板 · Film template

本目录是 `./tbook film new` 的起始模板；每部视频按 [trureturing-film](https://github.com/the-omega-institute/trureturing-film) 的方案完全由代码生成：确定性的 Canvas 动画、本地合成的英文旁白（Kokoro-82M）、程序化配乐，内嵌中英双语字幕。仓库只存源码，成片由 CI 构建后作为 GitHub Release 资产发布，书中以 `<video>` 嵌入。

This directory is the starting point of `./tbook film new`. Every film follows the trureturing-film scheme and is generated entirely by code: a deterministic Canvas animation, English narration synthesized locally with Kokoro-82M, a procedural score, and burned-in Chinese and English subtitles. The repository holds source only; CI renders the film and publishes it as GitHub Release assets, which the book embeds.

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
| `poster.jpg` | 提交入库的小海报（≤ 300 KB，`film.sh <dir> poster` 生成） · the committed poster |
| `README.md` | 可选：场景说明、每条论断的出处 · optional notes, the source of every claim |

其余一切构建产物都在 `<dir>/out/`（已被 `.gitignore` 忽略）。Every build output goes to `<dir>/out/` (git-ignored).

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
  "duration": "0:57",
  "resolution": "1920x1080@30",
  "style": "trureturing cyberpunk · …",
  "narration": {"language": "en", "engine": "Kokoro-82M v1.0 (onnx)", "voice": "af_heart"},
  "subtitles": ["zh", "en"],
  "lean": ["D5/S1/Deficit/DeficitThreeValued.deficit_three_valued"],
  "release_tag": "film-example-monograph-001-v1",
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
| `released`, `duration` | `YYYY-MM-DD`，`m:ss`（`tts` 步骤会提示实际时长） · the `tts` step prints the narrated length |
| `resolution` | 固定 `1920x1080@<fps>` · always 1920×1080 |
| `narration`, `subtitles` | 旁白语言/引擎/声音；字幕只支持 `zh`、`en` · subtitles are `zh` and/or `en` |
| `lean` | 片中引用的 GID，必须都在锁文件中；片中、视频页与 Release 说明都以 LEAN ✓ 链接到所钉提交 · GIDs cited by the film; all must be in the lock |
| `release_tag` | `film-<书 slug>-<NNN>-v<k>`；发布后不再改动，新剪辑递增 `v<k>` · never changes once published; bump `v<k>` for a new cut |
| `outputs` | Release 资产文件名；书中的播放地址是 `https://github.com/<repo>/releases/download/<release_tag>/<outputs.narrated>` · release asset names |

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
F=books/<slug>/films/<NNN>-<name>
theme/film/film.sh $F setup        # pip 包、Kokoro 模型（.cache/film/models）、字体（node_modules/@fontsource）
theme/film/film.sh $F timeline     # 无 TTS 的暂定时间轴（预览用）
theme/film/film.sh $F shot 2 8 14 --poster   # 单帧截图 → out/shots/
theme/film/film.sh $F serve        # 浏览器预览 index.html?play
theme/film/film.sh $F clip 30 3 960x540      # 3 秒无声低清片段 → out/clip.mp4
theme/film/film.sh $F poster       # out/<cover>.jpg 与提交入库的 poster.jpg
theme/film/film.sh $F all          # tts → music → mix → render → mux → small
```

Chromium：设置 `PW_CHROMIUM_PATH` 使用已有浏览器，否则用 Playwright 自带的（`npx playwright install chromium`）。ffmpeg：`$FFMPEG`、`PATH` 或 `imageio-ffmpeg`。

## 发布 · Publish

1. `./tbook check` 无错误；提交 `film.json`、`script.json`、`scenes.js`、`poster.jpg`。
2. 推送与 `release_tag` 相同的标签：`git tag film-<slug>-<NNN>-v1 && git push origin film-<slug>-<NNN>-v1`。
3. `.github/workflows/film.yml` 在 CI 上合成旁白、渲染全部帧、编码，并创建 Release（1080p 带旁白版、纯配乐版、720p 版与封面），说明中列出所依据的提交与 Lean 引用。
4. 在章节中嵌入：`::: {.film src="<NNN>-<name>"}` 或 `::: {.film src="trureturing-film:film-<NNN>-v<k>"}`，块内文字为图注。

## 边界 · Scope

视频是讲解，不是证明。片中标 LEAN ✓ 的结论以 trureturing 中已冻结的 Lean 声明为准；其余是屏幕上的计算或论证，必须如实标注。A film explains; it proves nothing. Only results marked LEAN ✓ rest on frozen Lean declarations; everything else is labelled as computed on screen or argued.
