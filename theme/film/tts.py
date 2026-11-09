"""Synthesize the narration line by line with Kokoro-82M (ONNX) and write the film's timeline.

Usage: python3 theme/film/tts.py <film dir> [--only N]

Reads script.json (voice, speed, optional "say" pronunciations, scenes with lead / lines / tail)
and writes, under <film dir>/out/:
  tts/lineNN.wav     one 48 kHz mono file per line (trimmed silence); --only N re-synthesizes line N
  narration.wav      every line placed at its start time
  timeline.json      {scenes: [{id, start, end}], lines: [{i, scene, start, end, en, zh}], duration}

timeline.json is the single source of timing: the engine, the subtitles and music.py follow it,
so editing script.json and rerunning this step re-times the whole film.
Model files (kokoro-v1.0.onnx, voices-v1.0.bin) come from $KOKORO_MODEL_DIR (default
.cache/film/models, fetched by setup.sh). Adapted from trureturing-film films/*/tts.py
(Apache-2.0, the-omega-institute).
"""

from __future__ import annotations

import json
import sys

from common import fail, film_dir_arg, load, model_dir, out_dir, tfilm

SR_OUT = 48000
GAP = tfilm.LINE_GAP_SECONDS  # silence between lines inside a scene (the provisional timeline uses the same)
# Pronunciation fixes for words Kokoro reads poorly; script.json "say" adds to and overrides these.
SAY = {
    "trureturing": "True Re-Turing", "Gödel": "Gurdel", "Euler": "Oiler",
    "Riemann": "Reeman", "Möbius": "Mer-bius", "Erdős": "Air-dish", "Schur": "Shoor", "Lean four": "Leen four",
}


def spoken(text: str, say: dict[str, str]) -> str:
    for a, b in say.items():
        text = text.replace(a, b)
    return text


def resample(x, sr_in: int, sr_out: int):
    import numpy as np

    if sr_in == sr_out:
        return x
    n_out = int(round(len(x) * sr_out / sr_in))
    t_in = np.arange(len(x)) / sr_in
    t_out = np.arange(n_out) / sr_out
    return np.interp(t_out, t_in, x).astype(np.float32)


def trim(x, thr: float = 0.004):
    import numpy as np

    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x
    a = max(0, idx[0] - 240)
    b = min(len(x), idx[-1] + 2400)
    return x[a:b]


def main(argv: list[str]) -> int:
    try:
        import numpy as np
        import soundfile as sf
        from kokoro_onnx import Kokoro
    except ImportError as exc:
        fail(f"{exc.name} is not installed; run theme/film/film.sh <film dir> setup")
    film_dir = film_dir_arg([a for a in argv if not a.startswith("--")])
    only = None
    if "--only" in argv:
        only = int(argv[argv.index("--only") + 1])
    film = load(film_dir)
    script = film.script
    if script is None:
        fail(f"{film.id}: script.json is unreadable")
    problems = [m for sev, m in tfilm.validate_script(script) if sev == "error"]
    if problems:
        fail("script.json:\n  " + "\n  ".join(problems))
    models = model_dir()
    onnx, voices = models / "kokoro-v1.0.onnx", models / "voices-v1.0.bin"
    if not onnx.is_file() or not voices.is_file():
        fail(f"Kokoro model files not found in {models}; run theme/film/film.sh <film dir> setup")
    say = {**SAY, **(script.get("say") or {})}
    k = Kokoro(str(onnx), str(voices))
    out = out_dir(film_dir)
    (out / "tts").mkdir(exist_ok=True)
    timeline: dict = {"scenes": [], "lines": []}
    t = 0.0
    chunks = []
    li = 0
    for sc in script["scenes"]:
        s0 = t
        t += float(sc["lead"])
        for j, (en, zh) in enumerate(sc["lines"]):
            path = out / "tts" / f"line{li:02d}.wav"
            if only is None or only == li or not path.exists():
                samples, sr = k.create(spoken(en, say), voice=script["voice"], speed=float(script["speed"]), lang="en-us")
                x = trim(np.asarray(samples, dtype=np.float32))
                x = resample(x, sr, SR_OUT)
                sf.write(str(path), x, SR_OUT)
            x, sr = sf.read(str(path), dtype="float32")
            if sr != SR_OUT:
                fail(f"{path}: sample rate {sr}, expected {SR_OUT}; delete it and rerun")
            dur = len(x) / SR_OUT
            timeline["lines"].append({"i": li, "scene": sc["id"], "start": round(t, 3), "end": round(t + dur, 3),
                                      "en": en, "zh": zh})
            chunks.append((t, x))
            t += dur
            if j < len(sc["lines"]) - 1:
                t += GAP
            li += 1
        t += float(sc["tail"])
        timeline["scenes"].append({"id": sc["id"], "start": round(s0, 3), "end": round(t, 3)})
    timeline["duration"] = round(t, 3)
    timeline["voice"] = script["voice"]
    timeline["speed"] = script["speed"]
    total = np.zeros(int(np.ceil(t * SR_OUT)) + SR_OUT, dtype=np.float32)
    for st, x in chunks:
        a = int(round(st * SR_OUT))
        total[a:a + len(x)] += x
    sf.write(str(out / "narration.wav"), total, SR_OUT)
    (out / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"film: narration {tfilm.format_duration(t)} ({t:.2f} s), {li} lines → {out / 'timeline.json'}")
    for s in timeline["scenes"]:
        print(f"  {s['id']:12s} {s['start']:7.2f} {s['end']:7.2f} {s['end'] - s['start']:6.2f}")
    declared = (film.meta or {}).get("duration", "")
    if declared != tfilm.format_duration(t):
        print(f"film: note: film.json duration is {declared!r}; the narrated cut is {tfilm.format_duration(t)} — "
              "update film.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
