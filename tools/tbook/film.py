"""Book-local films, following the trureturing-film scheme.

A film is generated entirely by code: a deterministic 1920×1080 Canvas animation
(``theme/film/engine.js`` + the film's ``scenes.js``), English narration synthesized locally
with Kokoro-82M, a procedural score, and burned-in Chinese + English subtitles. The
repository holds **source only**; rendered videos are published as GitHub Release assets by
``.github/workflows/film.yml`` (tag ``film-<slug>-<NNN>-v<k>``) and embedded from there.

Source layout (``books/<slug>/films/``)::

    <NNN>-<name>/film.json     metadata (schema below)
    <NNN>-<name>/script.json   narration + subtitles, the single source of timing
    <NNN>-<name>/scenes.js     SCENES.<scene id> = S => { … } drawn with the shared engine
    <NNN>-<name>/data/*.json   optional data, inlined as DATA.data.<file stem>
    <NNN>-<name>/poster.jpg    small committed poster (≤ 300 KB, written by `film.sh <dir> poster`)
    <NNN>-<name>/README.md     optional notes (scenes, sources of every claim)
    <NNN>-<name>/out/          every build output (git-ignored): index.html, fonts/, tts/, *.wav, *.mp4

``film.json``::

    {
      "id": "001-golden-deficit",                 = directory name
      "title": "…", "title_zh": "…",              English and Chinese titles
      "summary": "…", "summary_zh": "…",          optional one-paragraph blurbs (landing page, films page)
      "subject": "https://github.com/the-omega-institute/trureturing",
      "subject_commit": "<sha>",                  trureturing commit the film was made against (= the lock commit)
      "released": "YYYY-MM-DD",
      "duration": "m:ss",
      "resolution": "1920x1080@30",
      "style": "…",
      "narration": {"language": "en", "engine": "Kokoro-82M v1.0 (onnx)", "voice": "af_heart"},
      "subtitles": ["zh", "en"],
      "lean": ["D5/S1/Deficit/DeficitThreeValued.deficit_three_valued", …],   GIDs, all in trureturing.lock.json
      "release_tag": "film-<slug>-<NNN>-v<k>",
      "outputs": {"narrated": "<asset>.mp4", "music_only": "<asset>.mp4", "cover": "<asset>.jpg",
                  "narrated_720p": "<asset>.mp4", "music_only_720p": "<asset>.mp4"}     (720p optional)
    }

``script.json``::

    {"voice": "af_heart", "speed": 0.94, "say": {"word": "pronunciation"}?, "music": {"bpm": 80,
     "progression": "a-minor"}?, "scenes": [{"id": "zeck", "name": "ZECKENDORF"?, "lead": 1.5, "tail": 0.6,
     "lines": [["English narration", "中文字幕"], …], "music": [pad, bass, arp, kick, hat]?,
     "cues": [{"line": 0, "at": 2.5, "kind": "stamp" | "chime"}]?}]}

Embedding in a chapter: ``::: {.film src="001-golden-deficit"}`` (a film of this book) or
``src="trureturing-film:film-<NNN>-v<k>"`` (a release of the-omega-institute/trureturing-film).
HTML gets a ``<video>`` (poster + the release asset); PDF/EPUB get the poster, the caption and
the address of the film (:func:`render_embed`). :func:`build` publishes ``_site/<slug>/films/``.

The render pipeline lives in ``theme/film/`` (``film.sh <film-dir> <step>``); it imports this
module for the provisional timeline, the engine data and the release notes.
"""

from __future__ import annotations

import html
import json
import posixpath
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import config, lean, paths
from .model import Issue

FILM_DIR_RE = re.compile(r"^(?P<num>\d{3})-(?P<name>[a-z0-9]+(?:-[a-z0-9]+)*)$")
EXTERNAL_PREFIX = "trureturing-film:"
EXTERNAL_RE = re.compile(r"^trureturing-film:film-(?P<num>\d{3})-v(?P<ver>[1-9]\d*)$")
EXTERNAL_REPO = "the-omega-institute/trureturing-film"
TAG_RE = re.compile(r"^film-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)-(?P<num>\d{3})-v(?P<ver>[1-9]\d*)$")
DURATION_RE = re.compile(r"^\d{1,3}:[0-5]\d$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RESOLUTION_RE = re.compile(r"^(?P<w>\d{3,4})x(?P<h>\d{3,4})@(?P<fps>\d{2})$")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
SCENE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
ASSET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.(?:mp4|jpg)$")
LANG_CODE_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]+)*$")
DATA_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.json$")
REQUIRED_OUTPUTS = ("narrated", "music_only", "cover")
OPTIONAL_OUTPUTS = ("narrated_720p", "music_only_720p")
SOURCE_FILES = ("film.json", "script.json", "scenes.js", "poster.jpg", "README.md")
SOURCE_DIRS = ("data", "out")
POSTER = "poster.jpg"
POSTER_MAX_BYTES = 300_000
MUSIC_LAYERS = 5  # pad, bass, arp, kick, hat (theme/film/music.py)
CUE_KINDS = ("stamp", "chime", "impact", "glitch")

# Provisional timing when no narration has been synthesized yet. tts.py measures real line
# lengths; these constants only have to be close enough to lay out and preview the picture.
WORDS_PER_SECOND = 2.6  # Kokoro af_heart at speed ~0.94
MIN_LINE_SECONDS = 1.2
LINE_PAD_SECONDS = 0.3
LINE_GAP_SECONDS = 0.6  # silence between lines inside a scene; must equal GAP in theme/film/tts.py

THEME_FILM = paths.THEME / "film"
TEMPLATES_FILM = paths.TEMPLATES / "film"

# Component-local interface strings. config.s(lang, "film.<key>") wins once these are merged into
# theme/i18n/<lang>.toml (table [film]); until then the values below are used.
STRINGS: dict[str, dict[str, str]] = {
    "zh": {
        "back_to_book": "◂ 返回本书",
        "film": "视频",
        "film_n": "视频 {num}",
        "page": "视频页",
        "release": "发布页",
        "small": "720p",
        "music_only": "纯配乐",
        "cover": "封面",
        "duration": "时长",
        "released": "发布",
        "narration": "英文 AI 旁白 · 中英双语字幕",
        "lean_title": "片中引用的 Lean 定理（已由内核验证并冻结）",
        "subject": "依据 trureturing 提交",
        "subject_stale": "成片依据的提交与本书所钉提交不同；Lean 链接按所钉提交给出",
        "none": "本书还没有视频。",
        "unpublished": "尚未发布：推送标签后由 CI 构建并发布",
        "hero_title": "用动画讲清书中的定理",
        "hero_lede": "每部视频都由代码生成：确定性的 Canvas 动画、本地合成的英文旁白、程序化配乐，内嵌中英双语字幕。"
                     "片中标为 LEAN ✓ 的结论都对应 trureturing 中已由 Lean 内核验证并冻结的声明（链接固定到所钉提交）；"
                     "动画只帮助理解，真值以 Lean 为准。",
        "foot": "本页由构建依据 books/{slug}/films/ 生成；新增视频：./tbook film new。成片发布在 GitHub Releases。",
        "external": "trureturing-film 的视频",
        # in-frame strings (theme/film/engine.js)
        "badge_lean": "Lean 内核验证 · 已冻结",
        "badge_open": "开放问题 · 此处未证明",
        "badge_argued": "论证 · 未经内核检验",
        "badge_computed": "屏幕上的计算 · 不是证明",
        "pinned": "所钉提交",
    },
    "en": {
        "back_to_book": "◂ Back to the book",
        "film": "Film",
        "film_n": "Film {num}",
        "page": "Film page",
        "release": "Release",
        "small": "720p",
        "music_only": "Music only",
        "cover": "Cover",
        "duration": "Length",
        "released": "Released",
        "narration": "English AI narration · Chinese and English subtitles",
        "lean_title": "Lean theorems cited in the film (kernel-verified and frozen)",
        "subject": "Made against trureturing commit",
        "subject_stale": "The film was made against another commit than the book pins; Lean links use the pinned commit",
        "none": "This book has no films yet.",
        "unpublished": "Not released yet: push the release tag and CI builds and publishes it",
        "hero_title": "The theorems of the book, animated",
        "hero_lede": "Every film is generated by code: a deterministic Canvas animation, English narration synthesized "
                     "locally, a procedural score, and burned-in Chinese and English subtitles. Results marked LEAN ✓ "
                     "are declarations kernel-verified in Lean and frozen in trureturing (linked at the pinned commit); "
                     "the animation helps you see, Lean decides what is true.",
        "foot": "Generated by the build from books/{slug}/films/; add a film with ./tbook film new. "
                "Rendered videos are published as GitHub Releases.",
        "external": "Film from trureturing-film",
        "badge_lean": "LEAN KERNEL · VERIFIED · FROZEN",
        "badge_open": "OPEN PROBLEM · NOT PROVED HERE",
        "badge_argued": "ARGUED · NOT KERNEL-CHECKED",
        "badge_computed": "COMPUTED ON SCREEN · NOT A PROOF",
        "pinned": "PINNED",
    },
}
ENGINE_STRING_KEYS = ("badge_lean", "badge_open", "badge_argued", "badge_computed", "pinned", "film")


class FilmError(Exception):
    """A film problem that stops a build or a command."""


def t(lang: str, key: str, **fmt: Any) -> str:
    """Interface string ``film.<key>``: the shared i18n table if it defines it, else the local table."""
    text = config.s(lang, f"film.{key}") if lang in ("zh", "en") or config.has_i18n(lang) else ""
    if not text:
        text = STRINGS.get(lang, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    return text.format(**fmt) if fmt else text


def esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


# --------------------------------------------------------------------------- loading


@dataclass
class Film:
    """One film directory of a book, with its parsed sources (``None`` when unreadable)."""

    book: config.Book
    dir: Path
    meta: dict[str, Any] | None
    script: dict[str, Any] | None
    problems: list[tuple[str, str]] = field(default_factory=list)  # (file name, read error)

    @property
    def id(self) -> str:
        return self.dir.name

    @property
    def number(self) -> str:
        m = FILM_DIR_RE.match(self.dir.name)
        return m.group("num") if m else ""

    @property
    def out(self) -> Path:
        return self.dir / "out"

    @property
    def poster(self) -> Path:
        return self.dir / POSTER

    def title(self, lang: str) -> str:
        meta = self.meta or {}
        en = str(meta.get("title") or self.id)
        zh = str(meta.get("title_zh") or en)
        return zh if lang.startswith("zh") else en

    def summary(self, lang: str) -> str:
        meta = self.meta or {}
        en = str(meta.get("summary") or "")
        zh = str(meta.get("summary_zh") or en)
        return zh if lang.startswith("zh") else en

    @property
    def release_tag(self) -> str:
        return str((self.meta or {}).get("release_tag") or "")

    def output(self, key: str) -> str:
        outputs = (self.meta or {}).get("outputs") or {}
        value = outputs.get(key) if isinstance(outputs, dict) else None
        if isinstance(value, str) and value:
            return value
        return default_outputs(self.book.slug, self.number).get(key, "")

    @property
    def lean(self) -> list[str]:
        gids = (self.meta or {}).get("lean") or []
        return [str(g) for g in gids] if isinstance(gids, list) else []


def _read_json(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{path.name} is missing"
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"cannot read {path.name}: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"{path.name}: invalid JSON at line {exc.lineno}: {exc.msg}"


def load_film(book: config.Book, film_dir: Path) -> Film:
    meta, err_meta = _read_json(film_dir / "film.json")
    script, err_script = _read_json(film_dir / "script.json")
    problems = [(name, e) for name, e in (("film.json", err_meta), ("script.json", err_script)) if e]
    if meta is not None and not isinstance(meta, dict):
        problems.append(("film.json", "film.json must be a JSON object"))
        meta = None
    if script is not None and not isinstance(script, dict):
        problems.append(("script.json", "script.json must be a JSON object"))
        script = None
    return Film(book=book, dir=film_dir, meta=meta, script=script, problems=problems)


def film_dirs(book: config.Book) -> list[Path]:
    """Directories of ``books/<slug>/films/`` named ``<NNN>-<name>``, sorted by name."""
    if not book.films_dir.is_dir():
        return []
    return sorted(p for p in book.films_dir.iterdir() if p.is_dir() and FILM_DIR_RE.match(p.name))


def films(book: config.Book) -> list[Film]:
    return [load_film(book, d) for d in film_dirs(book)]


def get(book: config.Book, film_id: str) -> Film | None:
    d = book.films_dir / film_id
    if not FILM_DIR_RE.match(film_id) or not d.is_dir():
        return None
    return load_film(book, d)


def book_of(film_dir: Path) -> config.Book:
    """The book a film directory belongs to (``books/<slug>/films/<dir>``)."""
    film_dir = Path(film_dir).resolve()
    if film_dir.parent.name != "films":
        raise FilmError(f"{film_dir}: a film directory lives at books/<slug>/films/<NNN>-<name>")
    return config.load_book(film_dir.parent.parent)


def _lock() -> lean.Lock | None:
    try:
        return lean.Lock.load()
    except (lean.LeanError, ValueError, KeyError, OSError):
        return None


# --------------------------------------------------------------------------- names and URLs


def default_outputs(slug: str, num: str, narration: str = "en", subtitles: list[str] | None = None) -> dict[str, str]:
    """Release asset names, e.g. ``example-monograph_001_narrated_EN_subs_ZH-EN.mp4``."""
    subs = "-".join(s.upper() for s in (subtitles or ["zh", "en"]))
    stem = f"{slug}_{num}"
    return {
        "narrated": f"{stem}_narrated_{narration.upper()}_subs_{subs}.mp4",
        "music_only": f"{stem}_music_only_subs_{subs}.mp4",
        "narrated_720p": f"{stem}_720p_narrated.mp4",
        "music_only_720p": f"{stem}_720p_music_only.mp4",
        "cover": f"{stem}_cover.jpg",
    }


def default_tag(slug: str, num: str, version: int = 1) -> str:
    return f"film-{slug}-{num}-v{version}"


def parse_tag(tag: str) -> tuple[str, str, int] | None:
    """``film-<slug>-<NNN>-v<k>`` → (slug, NNN, k)."""
    m = TAG_RE.match(tag or "")
    return (m.group("slug"), m.group("num"), int(m.group("ver"))) if m else None


def release_asset_url(repo: str, tag: str, asset: str) -> str:
    if not (repo and tag and asset):
        return ""
    return f"https://github.com/{repo}/releases/download/{tag}/{asset}"


def release_page_url(repo: str, tag: str) -> str:
    if not (repo and tag):
        return ""
    return f"https://github.com/{repo}/releases/tag/{tag}"


def external_ref(src: str) -> dict[str, str] | None:
    """URLs of ``trureturing-film:film-<NNN>-v<k>`` (None when ``src`` is not such a reference)."""
    m = EXTERNAL_RE.match(src or "")
    if not m:
        return None
    num, tag = m.group("num"), f"film-{m.group('num')}-v{m.group('ver')}"
    return {
        "num": num,
        "tag": tag,
        "narrated": release_asset_url(EXTERNAL_REPO, tag, f"TRURETURING_{num}_narrated_EN_subs_ZH-EN.mp4"),
        "cover": release_asset_url(EXTERNAL_REPO, tag, f"TRURETURING_{num}_cover.jpg"),
        "page": release_page_url(EXTERNAL_REPO, tag),
        "repo": f"https://github.com/{EXTERNAL_REPO}",
    }


def urls(site: config.Site, film: Film) -> dict[str, str]:
    """Release URLs of a local film (empty strings when the GitHub repository is unknown)."""
    repo, tag = site.repo, film.release_tag
    out = {key: release_asset_url(repo, tag, film.output(key)) for key in REQUIRED_OUTPUTS + OPTIONAL_OUTPUTS}
    out["page"] = release_page_url(repo, tag)
    out["site"] = site.book_url(film.book.slug, "films") + f"/#{film.id}" if site.base_url else ""
    return out


# --------------------------------------------------------------------------- timeline


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:['’.-][A-Za-z0-9]+)*", text or ""))


def line_seconds(text: str, wps: float = WORDS_PER_SECOND) -> float:
    """Provisional spoken length of one narration line."""
    return max(MIN_LINE_SECONDS, _words(text) / wps + LINE_PAD_SECONDS)


def provisional_timeline(script: dict, wps: float = WORDS_PER_SECOND) -> dict:
    """A timeline.json derived from script.json at a fixed speaking rate (no TTS needed).

    Same accounting as theme/film/tts.py: each scene starts with ``lead`` seconds, its lines
    follow with LINE_GAP_SECONDS between them, then ``tail`` seconds. Marked ``provisional``.
    """
    if wps <= 0:
        raise ValueError("words per second must be positive")
    timeline: dict[str, Any] = {"scenes": [], "lines": []}
    t = 0.0
    li = 0
    for sc in script.get("scenes") or []:
        s0 = t
        t += float(sc.get("lead", 0) or 0)
        lines = sc.get("lines") or []
        for j, pair in enumerate(lines):
            en, zh = (list(pair) + ["", ""])[:2]
            dur = line_seconds(str(en), wps)
            timeline["lines"].append({"i": li, "scene": sc.get("id", f"s{len(timeline['scenes'])}"),
                                      "start": round(t, 3), "end": round(t + dur, 3), "en": en, "zh": zh})
            t += dur
            if j < len(lines) - 1:
                t += LINE_GAP_SECONDS
            li += 1
        t += float(sc.get("tail", 0) or 0)
        timeline["scenes"].append({"id": sc.get("id", ""), "start": round(s0, 3), "end": round(t, 3)})
    timeline["duration"] = round(t, 3)
    timeline["provisional"] = True
    timeline["words_per_second"] = wps
    return timeline


def timeline_matches(timeline: dict, script: dict) -> str | None:
    """Why ``timeline`` (from tts.py) no longer fits ``script`` (None when it does)."""
    want = [(sc.get("id"), (list(p) + ["", ""])[0], (list(p) + ["", ""])[1])
            for sc in script.get("scenes") or [] for p in sc.get("lines") or []]
    have = [(ln.get("scene"), ln.get("en"), ln.get("zh")) for ln in timeline.get("lines") or []]
    if [sc.get("id") for sc in script.get("scenes") or []] != [s.get("id") for s in timeline.get("scenes") or []]:
        return "scene ids differ from script.json"
    if want != have:
        for k, (a, b) in enumerate(zip(want, have)):
            if a != b:
                return f"line {k} differs from script.json ({b[1]!r} vs {a[1]!r})"
        return f"script.json has {len(want)} lines, the timeline {len(have)}"
    return None


def format_duration(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def parse_duration(text: str) -> int | None:
    if not DURATION_RE.match(text or ""):
        return None
    m, s = text.split(":")
    return int(m) * 60 + int(s)


# --------------------------------------------------------------------------- validation


def validate_meta(meta: dict, film_dir: Path, book: config.Book, lock: lean.Lock | None) -> list[tuple[str, str]]:
    """(severity, message) pairs for film.json."""
    out: list[tuple[str, str]] = []

    def err(msg: str) -> None:
        out.append(("error", msg))

    def warn(msg: str) -> None:
        out.append(("warning", msg))

    m = FILM_DIR_RE.match(film_dir.name)
    num = m.group("num") if m else ""
    if meta.get("id") != film_dir.name:
        err(f"film.json: id must equal the directory name {film_dir.name!r}, got {meta.get('id')!r}")
    for key in ("title", "title_zh"):
        v = meta.get(key)
        if not isinstance(v, str) or not v.strip():
            err(f"film.json: {key} is required (a non-empty string)")
        elif "\n" in v:
            err(f"film.json: {key} must be one line")
    for key in ("summary", "summary_zh"):
        v = meta.get(key)
        if v is not None and (not isinstance(v, str) or not v.strip() or "\n" in v):
            err(f"film.json: {key} must be a one-paragraph string (no line breaks)")
    subject = meta.get("subject")
    if subject is not None and (not isinstance(subject, str) or not subject.startswith("https://")):
        err("film.json: subject must be an https:// URL of the trureturing repository")
    commit = meta.get("subject_commit")
    if not isinstance(commit, str) or not COMMIT_RE.match(commit):
        err("film.json: subject_commit must be the trureturing commit (7–40 lowercase hex) the film was made against")
    elif lock and not lock.commit.startswith(commit):
        warn(f"film.json: subject_commit {commit[:12]} is not the pinned commit {lock.commit[:12]}; re-check the "
             "narration against the pinned commit, set subject_commit and bump release_tag")
    released = meta.get("released")
    if not isinstance(released, str) or not DATE_RE.match(released):
        err("film.json: released must be a date YYYY-MM-DD")
    duration = meta.get("duration")
    if not isinstance(duration, str) or not DURATION_RE.match(duration):
        err("film.json: duration must look like m:ss (e.g. 0:52)")
    res = meta.get("resolution", "1920x1080@30")
    rm = RESOLUTION_RE.match(res) if isinstance(res, str) else None
    if not rm:
        err("film.json: resolution must look like 1920x1080@30")
    elif (rm.group("w"), rm.group("h")) != ("1920", "1080"):
        err("film.json: the engine draws 1920x1080 frames; resolution must be 1920x1080@<fps>")
    narration = meta.get("narration")
    if not isinstance(narration, dict):
        err("film.json: narration must be an object {language, engine, voice}")
    else:
        for key in ("language", "engine", "voice"):
            if not isinstance(narration.get(key), str) or not narration.get(key):
                err(f"film.json: narration.{key} is required")
        if isinstance(narration.get("language"), str) and not LANG_CODE_RE.match(narration["language"]):
            err(f"film.json: narration.language {narration['language']!r} is not a language code")
    subs = meta.get("subtitles")
    if not isinstance(subs, list) or not subs or not all(isinstance(s, str) for s in subs):
        err("film.json: subtitles must list the subtitle languages, e.g. [\"zh\", \"en\"]")
    else:
        bad = [s for s in subs if s not in ("zh", "en")]
        if bad:
            err(f"film.json: subtitles {bad} are not supported; script.json lines carry English and Chinese only")
    gids = meta.get("lean")
    if not isinstance(gids, list) or not all(isinstance(g, str) for g in gids):
        err("film.json: lean must be a list of GIDs (may be empty)")
    else:
        if len(set(gids)) != len(gids):
            err("film.json: lean lists a GID twice")
        for gid in gids:
            try:
                lean.parse_gid(gid)
            except lean.LeanError as exc:
                err(f"film.json: {exc}")
                continue
            if lock is None:
                err(f"film.json: {gid}: trureturing.lock.json is missing or unreadable; run ./tbook pin")
            elif lock.get(gid) is None:
                err(f"film.json: {gid} is not in trureturing.lock.json; cite it in a chapter or run ./tbook pin --refresh")
    tag = meta.get("release_tag")
    parsed = parse_tag(tag) if isinstance(tag, str) else None
    if not parsed:
        err(f"film.json: release_tag must look like {default_tag(book.slug, num or 'NNN')}")
    elif parsed[0] != book.slug or parsed[1] != num:
        err(f"film.json: release_tag {tag} must start with film-{book.slug}-{num}- (this book and film number)")
    outputs = meta.get("outputs")
    if not isinstance(outputs, dict):
        err("film.json: outputs must be an object {narrated, music_only, cover}")
    else:
        names: list[str] = []
        for key in REQUIRED_OUTPUTS + OPTIONAL_OUTPUTS:
            v = outputs.get(key)
            if v is None and key in OPTIONAL_OUTPUTS:
                continue
            if not isinstance(v, str) or not ASSET_RE.match(v):
                err(f"film.json: outputs.{key} must be a release asset file name (letters, digits, . _ -; "
                    f"{'.jpg' if key == 'cover' else '.mp4'})")
                continue
            if key == "cover" and not v.endswith(".jpg") or key != "cover" and not v.endswith(".mp4"):
                err(f"film.json: outputs.{key} has the wrong extension: {v}")
            names.append(v)
        if len(set(names)) != len(names):
            err("film.json: two outputs share a file name")
    return out


def validate_script(script: dict) -> list[tuple[str, str]]:
    """(severity, message) pairs for script.json."""
    out: list[tuple[str, str]] = []

    def err(msg: str) -> None:
        out.append(("error", msg))

    if not isinstance(script.get("voice"), str) or not script.get("voice"):
        err("script.json: voice is required (a Kokoro voice such as af_heart)")
    speed = script.get("speed")
    if not isinstance(speed, (int, float)) or isinstance(speed, bool) or not 0.5 <= speed <= 2.0:
        err("script.json: speed must be a number between 0.5 and 2.0")
    say = script.get("say", {})
    if not isinstance(say, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in say.items()):
        err("script.json: say must map words to pronunciations (strings)")
    music = script.get("music", {})
    if not isinstance(music, dict):
        err("script.json: music must be an object {bpm, progression}")
    elif "bpm" in music and (not isinstance(music["bpm"], (int, float)) or not 40 <= music["bpm"] <= 200):
        err("script.json: music.bpm must be a number between 40 and 200")
    scenes = script.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        err("script.json: scenes must be a non-empty list")
        return out
    seen: set[str] = set()
    for k, sc in enumerate(scenes):
        where = f"script.json: scene {k + 1}"
        if not isinstance(sc, dict):
            err(f"{where} must be an object {{id, lead, tail, lines}}")
            continue
        sid = sc.get("id")
        if not isinstance(sid, str) or not SCENE_ID_RE.match(sid):
            err(f"{where}: id must be a lowercase identifier (a-z, 0-9, _; starting with a letter), got {sid!r}")
        elif sid in seen:
            err(f"{where}: duplicate scene id {sid!r}")
        else:
            seen.add(sid)
            where = f"script.json: scene {sid!r}"
        if "name" in sc and (not isinstance(sc["name"], str) or not sc["name"].strip()):
            err(f"{where}: name must be a non-empty string (shown in the HUD)")
        for key in ("lead", "tail"):
            v = sc.get(key)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not 0 <= v <= 60:
                err(f"{where}: {key} must be a number of seconds between 0 and 60")
        lines = sc.get("lines")
        if not isinstance(lines, list) or not lines:
            err(f"{where}: lines must be a non-empty list of [English, 中文] pairs")
        else:
            for j, pair in enumerate(lines):
                if (not isinstance(pair, list) or len(pair) != 2
                        or not all(isinstance(x, str) and x.strip() for x in pair)):
                    err(f"{where}: line {j} must be [\"English narration\", \"中文字幕\"] (two non-empty strings)")
                elif any("\n" in x for x in pair):
                    err(f"{where}: line {j} must not contain line breaks (subtitles wrap automatically)")
        levels = sc.get("music")
        if levels is not None and (not isinstance(levels, list) or len(levels) != MUSIC_LAYERS
                                   or not all(isinstance(x, (int, float)) and 0 <= x <= 1.5 for x in levels)):
            err(f"{where}: music must list {MUSIC_LAYERS} levels [pad, bass, arp, kick, hat] between 0 and 1.5")
        cues = sc.get("cues")
        if cues is not None:
            if not isinstance(cues, list):
                err(f"{where}: cues must be a list of {{line, at, kind}}")
            else:
                n_lines = len(lines) if isinstance(lines, list) else 0
                for c in cues:
                    if (not isinstance(c, dict) or not isinstance(c.get("line"), int) or not 0 <= c["line"] < max(1, n_lines)
                            or not isinstance(c.get("at", 0), (int, float)) or c.get("kind") not in CUE_KINDS):
                        err(f"{where}: cue {c!r} must be {{\"line\": <index>, \"at\": <seconds>, "
                            f"\"kind\": {'|'.join(CUE_KINDS)}}}")
    return out


SCENE_DEF_RE = re.compile(r"\bSCENES\s*(?:\.\s*(?P<a>[A-Za-z_$][\w$]*)|\[\s*['\"](?P<b>[^'\"]+)['\"]\s*\])\s*=(?!=)")


def scene_ids_defined(scenes_js: str) -> set[str]:
    return {m.group("a") or m.group("b") for m in SCENE_DEF_RE.finditer(scenes_js)}


def node_executable() -> str | None:
    return shutil.which("node")


_SYNTAX_JS = (
    "const fs=require('fs'),vm=require('vm');let bad=0;"
    "for(const f of process.argv.slice(1)){try{new vm.Script(fs.readFileSync(f,'utf8'),{filename:f})}"
    "catch(e){bad=1;console.log(f+'\\t'+String(e.stack||e).split('\\n').slice(0,3).join(' | '))}}"
    "process.exit(bad)"
)


def js_syntax_errors(files: list[Path]) -> dict[Path, str] | None:
    """Classic-script syntax errors per file (as the browser parses them); None without node."""
    node = node_executable()
    if not node or not files:
        return None if not node else {}
    r = subprocess.run([node, "-e", _SYNTAX_JS, *[str(f) for f in files]], capture_output=True, text=True)
    out: dict[Path, str] = {}
    for line in r.stdout.splitlines():
        name, _, msg = line.partition("\t")
        out[Path(name)] = msg
    if r.returncode != 0 and not out:
        out[files[0]] = (r.stderr or r.stdout).strip()[:400]
    return out


def check_film(film: Film, lock: lean.Lock | None) -> list[Issue]:
    issues: list[Issue] = []
    d = film.dir

    def add(sev: str, path: Path, msg: str, line: int = 0) -> None:
        issues.append(Issue(sev, path, line, msg))

    for name, problem in film.problems:
        add("error", d / name, problem)
    if film.meta is not None:
        for sev, msg in validate_meta(film.meta, d, film.book, lock):
            add(sev, d / "film.json", msg)
    if film.script is not None:
        for sev, msg in validate_script(film.script):
            add(sev, d / "script.json", msg)
    scenes = d / "scenes.js"
    if not scenes.is_file():
        add("error", scenes, "scenes.js is missing (define SCENES.<scene id> = S => { … } for every scene)")
    else:
        text = scenes.read_text(encoding="utf-8")
        defined = scene_ids_defined(text)
        if film.script is not None:
            for sc in film.script.get("scenes") or []:
                sid = sc.get("id") if isinstance(sc, dict) else None
                if isinstance(sid, str) and sid not in defined:
                    add("warning", scenes, f"no SCENES.{sid} = … for scene {sid!r} of script.json; the engine shows a "
                                           "placeholder card there")
        errors = js_syntax_errors([scenes])
        for path, msg in (errors or {}).items():
            add("error", scenes, f"JavaScript syntax error: {msg}")
    data_dir = d / "data"
    if data_dir.is_dir():
        for p in sorted(data_dir.iterdir()):
            if p.is_dir() or not DATA_NAME_RE.match(p.name):
                add("error", p, "data/ holds only <identifier>.json files (inlined as DATA.data.<name>)")
                continue
            _, problem = _read_json(p)
            if problem:
                add("error", p, problem)
    if film.poster.is_file():
        size = film.poster.stat().st_size
        if size > POSTER_MAX_BYTES:
            add("warning", film.poster, f"poster.jpg is {size // 1000} KB; keep it under {POSTER_MAX_BYTES // 1000} KB "
                                        "(theme/film/film.sh <dir> poster writes a compact one)")
    else:
        add("warning", film.poster, "poster.jpg is missing; run theme/film/film.sh <film dir> poster and commit it")
    for p in sorted(d.iterdir()):
        if p.name.startswith("."):
            continue
        if p.is_dir() and p.name in SOURCE_DIRS or p.is_file() and p.name in SOURCE_FILES:
            continue
        add("warning", p, "not a film source file; build outputs belong in out/ (git-ignored), sources are "
                          f"{', '.join(SOURCE_FILES)} and data/")
    return issues


def check_ref(book, src: str) -> str | None:
    """Error message if ``src`` does not name a usable film, else None."""
    src = (src or "").strip()
    if not src:
        return "film embed needs src=\"<NNN>-<name>\" or src=\"trureturing-film:film-<NNN>-v<k>\""
    if src.startswith(EXTERNAL_PREFIX):
        if EXTERNAL_RE.match(src):
            return None
        return f"film src {src!r}: external films are written trureturing-film:film-<NNN>-v<k>, e.g. trureturing-film:film-001-v1"
    if not FILM_DIR_RE.match(src):
        return f"film src {src!r}: expected a film directory name <NNN>-<name> (e.g. 001-golden-deficit)"
    d = book.films_dir / src
    if not d.is_dir():
        known = ", ".join(p.name for p in film_dirs(book)) or "none"
        return f"film {src!r} not found in {paths.rel(book.films_dir)} (films: {known})"
    meta, problem = _read_json(d / "film.json")
    if problem:
        return f"film {src}: {problem}"
    if not isinstance(meta, dict) or not meta.get("release_tag"):
        return f"film {src}: film.json has no release_tag"
    return None


def check(book) -> list[Issue]:
    """Validate ``books/<slug>/films/``: schemas, timing source, Lean citations, scene scripts."""
    if not book.films_dir.exists():
        return []
    issues: list[Issue] = []
    lock = _lock()
    numbers: dict[str, str] = {}
    for p in sorted(book.films_dir.iterdir()):
        if p.name.startswith(".") or p.name.lower() == "readme.md":
            continue
        if not p.is_dir() or not FILM_DIR_RE.match(p.name):
            issues.append(Issue("error", p, 0, "films/ holds film directories named <NNN>-<name> (kebab-case), "
                                               "e.g. 001-golden-deficit"))
            continue
        num = FILM_DIR_RE.match(p.name).group("num")
        if num in numbers:
            issues.append(Issue("error", p, 0, f"film number {num} is used twice ({numbers[num]} and {p.name})"))
        numbers[num] = p.name
        issues.extend(check_film(load_film(book, p), lock))
    return issues


def cited_gids(book) -> list[tuple[Path, int, str]]:
    """(film.json, 0, GID) for every Lean declaration the book's films cite."""
    out = []
    for film in films(book):
        for gid in film.lean:
            out.append((film.dir / "film.json", 0, gid))
    return out


# --------------------------------------------------------------------------- data for pages


def lean_refs(gids: list[str], lock: lean.Lock | None) -> list[dict]:
    """{gid, name, short, kind, url, line, statement_id, signature} for each cited GID."""
    out = []
    for gid in gids:
        try:
            g = lean.parse_gid(gid)
        except lean.LeanError:
            continue
        res = lock.get(gid) if lock else None
        name = res.name if res else f"{g.lean_module}.{g.name}"
        out.append({
            "gid": gid,
            "name": name,
            "short": name.rsplit(".", 1)[-1],
            "kind": res.kind if res else "",
            "url": lock.source_url(gid) if lock else "",
            "line": res.line if res else 0,
            "statement_id": res.statement_id if res else "",
            "signature": res.signature if res else "",
        })
    return out


def items(book) -> list[dict]:
    """Films for the book's landing page (``_site/<slug>/index.html``).

    Each item: ``kind`` ("film"), ``id``, ``number``, ``code`` ("FILM 001"), ``title`` and ``summary``
    ({lang: text}; summary may be empty), ``duration``, ``released``,
    ``href`` ("films/index.html#<id>") and ``poster`` ("films/<id>/poster.jpg", "" when missing) relative to the
    landing page, ``poster_file`` (absolute source path or None), ``hub`` ("films/"), ``release_tag``,
    ``watch_url`` / ``download_url`` (the narrated release asset), ``release_url`` (the release page),
    ``cover_url``, ``narration``, ``subtitles`` and ``lean`` ([{gid, name, short, kind, url}]).
    """
    site = config.load_site()
    lock = _lock()
    langs = list(dict.fromkeys([*book.languages, "zh", "en"]))
    out = []
    for film in films(book):
        if film.meta is None:
            continue
        u = urls(site, film)
        out.append({
            "kind": "film",
            "id": film.id,
            "number": film.number,
            "code": f"FILM {film.number}",
            "title": {lang: film.title(lang) for lang in langs},
            "summary": {lang: film.summary(lang) for lang in langs if film.summary(lang)},
            "duration": str(film.meta.get("duration", "")),
            "released": str(film.meta.get("released", "")),
            "href": f"films/index.html#{film.id}",
            "hub": "films/",
            "poster": f"films/{film.id}/{POSTER}" if film.poster.is_file() else "",
            "poster_file": film.poster if film.poster.is_file() else None,
            "release_tag": film.release_tag,
            "watch_url": u["narrated"],
            "download_url": u["narrated"],
            "release_url": u["page"],
            "cover_url": u["cover"],
            "narration": dict(film.meta.get("narration") or {}),
            "subtitles": list(film.meta.get("subtitles") or []),
            "lean": lean_refs(film.lean, lock),
        })
    return out


def engine_strings() -> dict[str, dict[str, str]]:
    out = {}
    for lang in ("zh", "en"):
        table = {key: t(lang, key) for key in ENGINE_STRING_KEYS}
        table["lean"] = config.s(lang, "badge.lean")
        table["open"] = config.s(lang, "badge.open")
        out[lang] = table
    return out


def engine_data(film: Film) -> dict:
    """Everything the engine reads besides the timeline (``window.DATA``): film, book, Lean citations, strings."""
    meta = film.meta or {}
    lock = _lock()
    book = film.book
    rm = RESOLUTION_RE.match(str(meta.get("resolution", "1920x1080@30")))
    fps = int(rm.group("fps")) if rm else 30
    names = {}
    for sc in (film.script or {}).get("scenes") or []:
        if isinstance(sc, dict) and isinstance(sc.get("id"), str):
            names[sc["id"]] = str(sc.get("name") or sc["id"].replace("_", "-").upper())
    return {
        "film": {
            "id": film.id,
            "number": film.number,
            "title": film.title("en"),
            "title_zh": film.title("zh"),
            "duration": meta.get("duration", ""),
            "fps": fps,
            "subtitles": list(meta.get("subtitles") or ["zh", "en"]),
            "release_tag": film.release_tag,
            "subject_commit": meta.get("subject_commit", ""),
        },
        "book": {
            "slug": book.slug,
            "code": book.code,
            "version": book.version,
            "title": {lang: config.pick(book.title, lang, book.languages) for lang in ("zh", "en")},
            "subtitle": {lang: config.pick(book.subtitle, lang, book.languages) for lang in ("zh", "en")},
        },
        "lean": lean_refs(film.lean, lock),
        "pin": {"repo": lock.repo, "commit": lock.commit} if lock else {"repo": "", "commit": ""},
        "names": names,
        "strings": engine_strings(),
    }


def release_notes(film: Film, sha: str = "") -> str:
    """Markdown notes for the film's GitHub Release."""
    meta = film.meta or {}
    lock = _lock()
    lines = [f"**{film.title('en')}** · {film.title('zh')}", ""]
    where = f"`{paths.rel(film.dir)}`"
    lines.append(f"Rendered from {where}" + (f" at {sha}." if sha else ".") + f" Book: `{film.book.slug}` "
                 f"({config.pick(film.book.title, 'en', film.book.languages)} · "
                 f"{config.pick(film.book.title, 'zh', film.book.languages)}).")
    lines.append("")
    commit = meta.get("subject_commit", "")
    repo = lock.repo if lock else "the-omega-institute/trureturing"
    if commit:
        lines.append(f"Subject: [{repo}@{commit[:12]}](https://github.com/{repo}/tree/{commit}).")
    if lock and commit and not lock.commit.startswith(commit):
        lines.append(f"Pinned by the book: `{lock.commit[:12]}`.")
    refs = lean_refs(film.lean, lock)
    if refs:
        lines += ["", "Lean theorems cited (kernel-verified and frozen in trureturing at the pinned commit):", ""]
        for r in refs:
            link = f"[`{r['name']}`]({r['url']})" if r["url"] else f"`{r['name']}`"
            lines.append(f"- LEAN ✓ {link} — `{r['gid']}`")
    narration = meta.get("narration") or {}
    lines += ["", "Files:", ""]
    lines.append(f"- `{film.output('narrated')}`: {narration.get('language', 'en').upper()} AI narration "
                 f"({narration.get('engine', 'Kokoro')}, voice {narration.get('voice', '')}) + score, burned-in "
                 f"{' + '.join(s.upper() for s in meta.get('subtitles') or ['zh', 'en'])} subtitles, 1080p")
    lines.append(f"- `{film.output('music_only')}`: score only, same picture and subtitles, 1080p")
    lines.append(f"- `{film.output('narrated_720p')}`, `{film.output('music_only_720p')}`: 720p compact copies")
    lines.append(f"- `{film.output('cover')}`: cover")
    lines += ["", "The film explains; the Lean declarations decide what is true."]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- embeds


def _caption_title(film: Film | None, lang: str, src: str) -> str:
    if film is None:
        return f"{t(lang, 'external')} · {src[len(EXTERNAL_PREFIX):]}"
    head = t(lang, "film_n", num=film.number) + " · " + film.title(lang)
    duration = (film.meta or {}).get("duration")
    return head + (f" · {duration}" if duration else "")


def render_embed(env, ctx, inner: str, doc) -> str:
    """Markup replacing a ``::: {.film src=…}`` block for ``ctx.target`` ("mdbook" or "pandoc")."""
    src = (env.attrs.get("src") or "").strip()
    lang = ctx.lang
    inner = inner.strip("\n")
    problem = check_ref(ctx.book, src)
    if problem:
        ctx.issues.append(f"{doc.path}: {problem}")
    ext = external_ref(src)
    film = None if ext or problem else get(ctx.book, src)
    head = _caption_title(film, lang, src)
    depth = (doc.chapter.path or "").count("/")
    up = "../" * (depth + 1)  # from <slug>/<lang>/<chapter>.html to <slug>/
    if ext:
        watch, cover, page, film_page = ext["narrated"], ext["cover"], ext["page"], ext["page"]
    elif film is not None:
        u = urls(ctx.site, film)
        watch, page = u["narrated"], u["page"]
        cover = up + f"films/{film.id}/{POSTER}" if film.poster.is_file() else ""
        film_page = up + f"films/index.html?lang={lang}#{film.id}"
        if not film.poster.is_file():
            ctx.issues.append(f"{doc.path}: film {film.id}: no {POSTER}; the player has no poster")
        if not watch:
            ctx.issues.append(f"{doc.path}: film {film.id}: the GitHub repository is unknown (site.repo), "
                              "so the release asset cannot be linked")
    else:
        watch = cover = page = film_page = ""

    if ctx.target == "mdbook":
        caption = inner or esc(head)
        links = []
        if watch:
            links.append(f'<a href="{esc(watch)}" target="_blank" rel="noopener">▶ {esc(config.s(lang, "ui.watch"))}</a>')
        if page:
            links.append(f'<a href="{esc(page)}" target="_blank" rel="noopener">⬇ {esc(config.s(lang, "ui.download"))}</a>')
        if film_page and film_page != page:
            links.append(f'<a href="{esc(film_page)}">{esc(t(lang, "page"))}</a>')
        if watch:
            poster_attr = f' poster="{esc(cover)}"' if cover else ""
            player = (f'<video class="tr-film-player" controls preload="none" playsinline{poster_attr} '
                      f'title="{esc(head)}">\n<source src="{esc(watch)}" type="video/mp4">\n</video>')
        elif cover:
            player = f'<img class="tr-film-poster" src="{esc(cover)}" alt="{esc(head)}" loading="lazy">'
        else:
            player = f'<div class="tr-film-missing">{esc(config.s(lang, "ui.poster_unavailable"))}</div>'
        if film is not None and not watch:
            links.append(f'<span>{esc(t(lang, "unpublished"))}</span>')
        return "\n".join([
            f'<figure class="tr-media tr-film" data-film="{esc(src)}">',
            player,
            '<figcaption class="tr-media-caption">',
            "",
            caption,
            "",
            f'<div class="tr-media-links">{"".join(links)}</div>' if links else "",
            "</figcaption>",
            "</figure>",
        ])

    # pandoc (PDF / EPUB): a static card. This output does not pass through render's link rewriting, so the
    # poster is registered in ctx.book_files and addressed under ctx.book_prefix (_book/…) like ../assets links.
    note = config.s(lang, "ui.film_static_note")
    if ext:
        url = ext["page"]
    elif film is not None:
        url = urls(ctx.site, film)["site"] or watch or page
    else:
        url = ""
    lines = ["::: {.tr-media .tr-film}"]
    if film is not None and film.poster.is_file():
        ctx.book_files.add(film.poster.resolve())
        chapter_dir = posixpath.dirname(doc.chapter.path or "") or "."
        img = posixpath.relpath(posixpath.join(ctx.book_prefix, "films", film.id, POSTER), chapter_dir)
        alt = head.replace("[", "\\[").replace("]", "\\]")
        lines += [f"![{alt}]({img}){{width=100%}}", ""]
        if not inner:
            lines += [f"**{head}**", ""]
    else:
        lines += [f"**{head}**", ""]
    if inner:
        lines += [inner, ""]
    if url:
        # a hard line break keeps the long address from stretching the justified note line
        lines += [f"{note}\\", f"<{url}>"]
    else:
        lines += [t(lang, "unpublished")]
    lines.append(":::")
    return "\n".join(lines)


# --------------------------------------------------------------------------- the films page


def _pair(key: str, **fmt: Any) -> str:
    return f'<span class="zh">{esc(t("zh", key, **fmt))}</span><span class="en">{esc(t("en", key, **fmt))}</span>'


def _pair_text(zh: str, en: str) -> str:
    if zh == en:
        return esc(zh)
    return f'<span class="zh">{esc(zh)}</span><span class="en">{esc(en)}</span>'


def _ui_pair(key: str) -> str:
    return _pair_text(config.s("zh", key), config.s("en", key))


def _code_html(code: str) -> str:
    head, sep, tail = code.partition("//")
    return esc(head) + ("<b>//</b>" + esc(tail) if sep else "")


def _google_fonts() -> str:
    try:
        tokens = json.loads(paths.TOKENS.read_text(encoding="utf-8"))
        return str(tokens.get("font", {}).get("google-fonts-css", ""))
    except (OSError, json.JSONDecodeError):
        return ""


def _film_card(site: config.Site, film: Film, lock: lean.Lock | None) -> str:
    meta = film.meta or {}
    u = urls(site, film)
    poster = f"{film.id}/{POSTER}" if film.poster.is_file() else ""
    title_zh, title_en = film.title("zh"), film.title("en")
    if u["narrated"]:
        poster_attr = f' poster="{esc(poster)}"' if poster else ""
        player = (f'<video controls preload="none" playsinline{poster_attr} title="{esc(title_en)}">'
                  f'<source src="{esc(u["narrated"])}" type="video/mp4"></video>')
    elif poster:
        player = f'<img src="{esc(poster)}" alt="{esc(title_en)}" loading="lazy">'
    else:
        player = f'<div class="missing">{_ui_pair("ui.poster_unavailable")}</div>'
    refs = []
    for r in lean_refs(film.lean, lock):
        name = esc(r["name"])
        link = (f'<a href="{esc(r["url"])}" target="_blank" rel="noopener" title="{esc(r["gid"])}"><code>{name}</code></a>'
                if r["url"] else f"<code>{name}</code>")
        refs.append(f'<li><span class="k ok">LEAN ✓</span>{link}</li>')
    lean_block = ""
    if refs:
        lean_block = (f'<div class="lean"><h4>{_pair("lean_title")}</h4><ul>{"".join(refs)}</ul></div>')
    links = []
    if u["narrated"]:
        links.append(f'<a class="btn primary" href="{esc(u["narrated"])}" target="_blank" rel="noopener">▶ {_ui_pair("ui.watch")}</a>')
    if u["narrated_720p"]:
        links.append(f'<a class="btn" href="{esc(u["narrated_720p"])}" target="_blank" rel="noopener">{_pair("small")}</a>')
    if u["music_only"]:
        links.append(f'<a class="btn" href="{esc(u["music_only"])}" target="_blank" rel="noopener">{_pair("music_only")}</a>')
    if u["page"]:
        links.append(f'<a class="btn" href="{esc(u["page"])}" target="_blank" rel="noopener">⬇ {_pair("release")}</a>')
    if not links:
        links.append(f'<span class="note">{_pair("unpublished")}</span>')
    commit = str(meta.get("subject_commit", ""))
    repo = lock.repo if lock else "the-omega-institute/trureturing"
    subject = ""
    if commit:
        stale = lock is not None and not lock.commit.startswith(commit)
        subject = (f'<p class="subject{" stale" if stale else ""}">{_pair("subject")} '
                   f'<a href="https://github.com/{esc(repo)}/tree/{esc(commit)}" target="_blank" rel="noopener">'
                   f'<code>{esc(commit[:7])}</code></a>'
                   + (f'<br><span class="warn">{_pair("subject_stale")}</span>' if stale else "") + "</p>")
    summary = (f'<p class="sum">{_pair_text(film.summary("zh"), film.summary("en"))}</p>'
               if film.summary("zh") or film.summary("en") else "")
    narration = _pair("narration") if (meta.get("narration") or {}).get("language") == "en" else esc(
        (meta.get("narration") or {}).get("language", ""))
    return f"""      <article class="film panel" id="{esc(film.id)}">
        <div class="player">{player}<span class="num">FILM {esc(film.number)}</span></div>
        <div class="body">
          <p class="kicker">{_pair("film_n", num=film.number)} · <span class="dur">{esc(meta.get("duration", ""))}</span> · {_pair("released")} {esc(meta.get("released", ""))}</p>
          <h3><span class="zh">{esc(title_zh)}</span><span class="en">{esc(title_en)}</span></h3>
          <p class="alt-title"><span class="zh">{esc(title_en)}</span><span class="en">{esc(title_zh)}</span></p>
          {summary}<p class="meta">{narration}</p>
          {lean_block}
          <div class="links">{"".join(links)}</div>
          {subject}
        </div>
      </article>"""


def hub_html(site: config.Site, book: config.Book, lock: lean.Lock | None = None) -> str:
    """The bilingual films page ``_site/<slug>/films/index.html``."""
    all_films = [f for f in films(book) if f.meta is not None]
    title_zh, title_en = config.pick(book.title, "zh", book.languages), config.pick(book.title, "en", book.languages)
    films_zh, films_en = config.s("zh", "ui.films"), config.s("en", "ui.films")
    fonts = _google_fonts()
    cards = "\n".join(_film_card(site, f, lock) for f in all_films) or f'<p class="note">{_pair("none")}</p>'
    pin = ""
    if lock:
        pin = (f'<a class="pill" href="{esc(lock.tree_url)}" target="_blank" rel="noopener">LEAN '
               f'<strong>trureturing@{esc(lock.commit[:7])} ↗</strong></a>')
    head_fonts = ""
    if fonts:
        head_fonts = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                      '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
                      f'<link rel="stylesheet" href="{esc(fonts)}">\n')
    return f"""<!doctype html>
<html lang="zh-CN" data-lang="zh" data-title-zh="{esc(book.code)} · {esc(films_zh)} · {esc(title_zh)}" data-title-en="{esc(book.code)} · {esc(films_en)} · {esc(title_en)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(book.code)} · {esc(films_zh)} · {esc(title_zh)}</title>
<meta name="description" content="{esc(title_zh)} · {esc(films_zh)} · {esc(title_en)} · {esc(films_en)}">
<meta name="generator" content="tbook film">
{head_fonts}<link rel="stylesheet" href="assets/tokens.css">
<link rel="stylesheet" href="assets/films.css">
<script src="assets/films.js"></script>
</head>
<body>
<div class="hub">
  <header class="top">
    <div class="brand">
      <a class="crumb" href="../">{_pair("back_to_book")}</a>
      <h1 class="logo">{_code_html(book.code)}</h1>
      <div class="tagline">{_pair_text(title_zh, title_en)} · <em>{_pair_text(films_zh, films_en)}</em></div>
    </div>
    <nav class="status" aria-label="链接 Links">
      <span class="pill">FILMS <strong>{len(all_films)}</strong></span>
      {pin}
      <div class="langs" role="group" aria-label="语言 Language"><button type="button" data-lang-set="zh" aria-pressed="true">中</button><button type="button" data-lang-set="en" aria-pressed="false">EN</button></div>
    </nav>
  </header>

  <section class="hero panel">
    <h2>{_pair("hero_title")}</h2>
    <p>{_pair("hero_lede")}</p>
  </section>

  <section class="films" aria-label="{esc(films_zh)} {esc(films_en)}">
{cards}
  </section>

  <footer class="foot">
    <span>{_pair("foot", slug=book.slug)}</span>
    <span>trureturing books · {esc(book.license or "")}</span>
  </footer>
</div>
</body>
</html>
"""


def published_registry(site: config.Site, book: config.Book, lock: lean.Lock | None) -> dict:
    data: dict[str, Any] = {"version": 1, "book": book.slug}
    if lock:
        data["trureturing"] = {"repo": lock.repo, "commit": lock.commit}
    data["films"] = []
    for film in films(book):
        if film.meta is None:
            continue
        u = urls(site, film)
        data["films"].append({
            "id": film.id, "number": film.number, "title": film.title("en"), "title_zh": film.title("zh"),
            "summary": film.summary("en"), "summary_zh": film.summary("zh"),
            "duration": film.meta.get("duration", ""), "released": film.meta.get("released", ""),
            "release_tag": film.release_tag, "subject_commit": film.meta.get("subject_commit", ""),
            "poster": f"{film.id}/{POSTER}" if film.poster.is_file() else "",
            "urls": {k: v for k, v in u.items() if v},
            "lean": [{"gid": r["gid"], "name": r["name"], "href": r["url"]} for r in lean_refs(film.lean, lock)],
        })
    return data


def build(site, book, out_dir: Path) -> None:
    """Publish the book's films page and posters into ``out_dir`` (``_site/<slug>/films/``).

    Raises :class:`FilmError` when a film has errors (the same as ``./tbook check`` reports). A book
    without ``films/`` publishes nothing. Videos are not copied: they are release assets.
    """
    out_dir = Path(out_dir)
    if not film_dirs(book):
        return
    lock = _lock()
    problems = [i for i in check(book) if i.severity == "error"]
    if problems:
        shown = "\n  ".join(i.format() for i in problems[:12])
        more = f"\n  … and {len(problems) - 12} more" if len(problems) > 12 else ""
        raise FilmError(f"{book.slug}: {len(problems)} film error(s):\n  {shown}{more}")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    assets = out_dir / "assets"
    assets.mkdir(parents=True)
    tokens_css = paths.GENERATED / "tokens.css"
    if not tokens_css.exists():
        raise FilmError(f"{paths.rel(tokens_css)} is missing; run ./tbook theme")
    shutil.copyfile(tokens_css, assets / "tokens.css")
    for name in ("films.css", "films.js"):
        src = THEME_FILM / "site" / name
        if not src.exists():
            raise FilmError(f"films page asset missing: {paths.rel(src)}")
        shutil.copyfile(src, assets / name)
    for film in films(book):
        if film.poster.is_file():
            (out_dir / film.id).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(film.poster, out_dir / film.id / POSTER)
    (out_dir / "index.html").write_text(hub_html(site, book, lock), encoding="utf-8")
    (out_dir / "films.json").write_text(json.dumps(published_registry(site, book, lock), ensure_ascii=False,
                                                   indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- scaffolding and CLI


def fill_template(text: str, values: dict[str, str]) -> str:
    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key not in values:
            raise FilmError(f"template placeholder @@{key}@@ has no value")
        return values[key]

    return re.sub(r"@@([A-Z][A-Z0-9_]*)@@", repl, text)


def scaffold(book: config.Book, film_id: str, title_zh: str, title_en: str, *, released: str | None = None) -> list[Path]:
    """Create ``books/<slug>/films/<film_id>/`` from templates/film/."""
    m = FILM_DIR_RE.match(film_id)
    if not m:
        raise FilmError(f"film directory name {film_id!r} must look like <NNN>-<name>, e.g. 002-carry-rules")
    if not title_zh.strip() or not title_en.strip():
        raise FilmError("both titles are required: \"<中文标题>\" \"<English title>\"")
    if any("\n" in s or '"' in s or "\\" in s for s in (title_zh, title_en)):
        raise FilmError("titles must be one line without quotes or backslashes")
    num = m.group("num")
    taken = {FILM_DIR_RE.match(p.name).group("num"): p.name for p in film_dirs(book)}
    if num in taken:
        raise FilmError(f"film number {num} is already used by {taken[num]}")
    dst = book.films_dir / film_id
    if dst.exists():
        raise FilmError(f"{paths.rel(dst)} already exists")
    lock = _lock()
    outs = default_outputs(book.slug, num)
    values = {
        "ID": film_id,
        "NUM": num,
        "SLUG": book.slug,
        "TITLE_ZH": title_zh.strip(),
        "TITLE_EN": title_en.strip(),
        "COMMIT": lock.commit if lock else "0000000",
        "REPO": f"https://github.com/{lock.repo}" if lock else "https://github.com/the-omega-institute/trureturing",
        "RELEASED": released or date.today().isoformat(),
        "TAG": default_tag(book.slug, num),
        "BOOK_CODE": book.code,
        **{f"OUT_{k.upper()}": v for k, v in outs.items()},
    }
    created = []
    dst.mkdir(parents=True)
    for name in ("film.json", "script.json", "scenes.js"):
        src = TEMPLATES_FILM / name
        if not src.exists():
            raise FilmError(f"template missing: {paths.rel(src)}")
        out = dst / name
        out.write_text(fill_template(src.read_text(encoding="utf-8"), values), encoding="utf-8")
        created.append(out)
    return created


USAGE = """usage:
  ./tbook film new <book> <NNN-name> "<中文标题>" "<English title>"
  ./tbook film list [<book> …]"""


def cli(args) -> int:
    rest = list(getattr(args, "rest", []) or [])
    action = getattr(args, "action", "")
    if action == "new":
        if len(rest) != 4:
            print(USAGE, file=sys.stderr)
            return 2
        slug, film_id, title_zh, title_en = rest
        try:
            book = config.load_book(slug)
            created = scaffold(book, film_id, title_zh, title_en)
        except (FilmError, config.ConfigError) as exc:
            print(f"film new: {exc}", file=sys.stderr)
            return 1
        for p in created:
            print(f"created {paths.rel(p)}")
        d = paths.rel(created[0].parent)
        print("next: write script.json and scenes.js, then preview with\n"
              f"  theme/film/film.sh {d} timeline && theme/film/film.sh {d} shot 2 8 14\n"
              f"and render the poster with theme/film/film.sh {d} poster (commit {d}/{POSTER}).\n"
              f"Embed it in a chapter with ::: {{.film src=\"{created[0].parent.name}\"}}")
        return 0
    if action == "list":
        try:
            books = config.load_books(rest or None)
        except config.ConfigError as exc:
            print(f"film list: {exc}", file=sys.stderr)
            return 1
        site = config.load_site()
        count = 0
        for book in books:
            for film in films(book):
                count += 1
                meta = film.meta or {}
                poster = "poster" if film.poster.is_file() else "no poster"
                print(f"{book.slug}/{film.id}  {meta.get('duration', '?'):>5}  {film.release_tag or '-'}  "
                      f"lean={len(film.lean)}  {poster}")
                print(f"    {film.title('zh')} · {film.title('en')}")
                watch = urls(site, film)["narrated"]
                if watch:
                    print(f"    {watch}")
        if not count:
            print("no films")
        return 0
    print(USAGE, file=sys.stderr)
    return 2
