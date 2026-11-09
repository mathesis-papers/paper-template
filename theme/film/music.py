"""Procedural dark-synth score and sound effects, synced to the film's timeline.

Usage: python3 theme/film/music.py <film dir>

Writes <film dir>/out/music_bed.wav (48 kHz stereo): pads, bass, arpeggio, drums with
per-scene intensity, risers/impacts/glitches on every scene cut, the same rare micro glitches
the engine draws (identical pseudo-random rule), and cue hits from script.json.

script.json controls (all optional):
  "music": {"bpm": 84, "progression": "d-minor" | "a-minor"}
  scene "music": [pad, bass, arp, kick, hat]  levels 0–1.5 (default by position in the film)
  scene "cues": [{"line": k, "at": seconds after the line starts, "kind": "stamp" | "chime" | "impact" | "glitch"}]

Deterministic (fixed seed). Adapted from trureturing-film films/*/music.py (Apache-2.0, the-omega-institute).
"""

from __future__ import annotations

import os
import sys

from common import fail, film_dir_arg, load, out_dir, timeline

SR = 48000
PROGRESSIONS = {  # (root midi, chord tones), one chord per bar
    "d-minor": [(38, [0, 3, 7]), (34, [0, 4, 7]), (41, [0, 4, 7]), (36, [0, 4, 7]),
                (38, [0, 3, 7]), (34, [0, 4, 7]), (43, [0, 3, 7]), (33, [0, 4, 7])],
    "a-minor": [(45, [0, 3, 7]), (41, [0, 4, 7]), (36, [0, 4, 7]), (43, [0, 4, 7]),
                (45, [0, 3, 7]), (41, [0, 4, 7]), (38, [0, 3, 7]), (40, [0, 4, 7])],
}
OPEN_LEVEL = (1.0, 0.4, 0.3, 0.0, 0.1)
MID_LEVELS = ((0.9, 0.7, 0.8, 0.5, 0.4), (1.0, 0.6, 0.7, 0.4, 0.3))
END_LEVEL = (1.0, 0.8, 0.7, 0.5, 0.4)


def main(argv: list[str]) -> int:
    try:
        import numpy as np
        import soundfile as sf
        from scipy.signal import butter, sosfilt
    except ImportError as exc:
        fail(f"{exc.name} is not installed; run theme/film/setup.sh")
    film_dir = film_dir_arg(argv)
    film = load(film_dir)
    script = film.script or {}
    tl, provisional = timeline(film, allow_provisional=os.environ.get("FILM_STRICT") != "1")
    if provisional:
        print("film: warning: scoring against provisional timing; rerun after tts", file=sys.stderr)
    settings = script.get("music") or {}
    prog = PROGRESSIONS.get(settings.get("progression", "a-minor"))
    if prog is None:
        fail(f"script.json: music.progression must be one of {', '.join(PROGRESSIONS)}")
    bpm = float(settings.get("bpm", 80))

    dur = tl["duration"] + 0.5
    n_total = int(dur * SR)
    rng = np.random.default_rng(7)
    beat = 60.0 / bpm
    bar = 4 * beat
    scenes = tl["scenes"]
    by_id = {sc.get("id"): sc for sc in script.get("scenes") or []}

    def midi(m):
        return 440.0 * 2 ** ((m - 69) / 12)

    def lp(x, f, order=2):
        return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)

    def hp(x, f, order=2):
        return sosfilt(butter(order, f, "high", fs=SR, output="sos"), x)

    def bp(x, lo, hi, order=2):
        return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)

    def saw(ph):
        return 2.0 * (ph - np.floor(ph + 0.5))

    def env_adsr(n, a, d, s, r):
        e = np.ones(n) * s
        na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
        if na:
            e[:na] = np.linspace(0, 1, na)
        if nd:
            e[na:na + nd] = np.linspace(1, s, len(e[na:na + nd]))
        if nr and nr < n:
            e[-nr:] *= np.linspace(1, 0, nr)
        return e

    def add(buf, start, sig, gain=1.0):
        a = int(start * SR)
        if a >= len(buf) or a + len(sig) <= 0:
            return
        if a < 0:
            sig = sig[-a:]
            a = 0
        b = min(len(buf), a + len(sig))
        buf[a:b] += gain * sig[:b - a]

    # ---------- intensity automation per scene ----------
    def level(k):
        custom = (by_id.get(scenes[k]["id"]) or {}).get("music")
        if custom:
            return tuple(custom)
        if k == 0:
            return OPEN_LEVEL
        if k == len(scenes) - 1:
            return END_LEVEL
        return MID_LEVELS[k % 2]

    levels = [level(k) for k in range(len(scenes))]

    def automation(idx):
        ctl_t, ctl_v = [], []
        for k, s in enumerate(scenes):
            v = levels[k][idx]
            ctl_t += [s["start"] + 0.6, max(s["start"] + 0.61, s["end"] - 0.4)]
            ctl_v += [v, v]
        return np.interp(np.arange(n_total) / SR, ctl_t, ctl_v)

    nbars = int(np.ceil(dur / bar)) + 1
    pad = np.zeros((n_total, 2))
    bass = np.zeros(n_total)
    arp = np.zeros((n_total, 2))
    kick = np.zeros(n_total)
    hat = np.zeros(n_total)

    for b in range(nbars):  # pad
        root, tones = prog[b % len(prog)]
        n = int((bar + 1.2) * SR)
        t = np.arange(n) / SR
        e = env_adsr(n, 0.9, 0.5, 0.85, 1.2)
        for ch, det in ((0, -1), (1, 1)):
            sig = np.zeros(n)
            for off in tones + [12]:
                f = midi(root + 24 + off)
                for dv in (-0.08, 0.0, 0.08):
                    fr = f * 2 ** ((dv * det + 0.03 * det) / 12)
                    sig += saw(fr * t + rng.random())
            sig = lp(sig, 900 + 500 * np.sin(b * 0.7) ** 2)
            add(pad[:, ch], b * bar, sig * e, 0.035)
    for b in range(nbars):  # bass, 8th-note pulse
        root, _ = prog[b % len(prog)]
        for q in range(8):
            n = int(beat / 2 * SR)
            t = np.arange(n) / SR
            f = midi(root)
            sig = lp(np.sin(2 * np.pi * f * t) + 0.35 * saw(f * t), 380)
            add(bass, b * bar + q * beat / 2, sig * np.minimum(1, t / 0.03) * np.exp(-t * 3.2), 0.28)
    pattern = [0, 1, 2, 3, 2, 1, 0, 2, 3, 1, 2, 0, 3, 2, 1, 2]
    for b in range(nbars):  # arpeggio, 16ths
        root, tones = prog[b % len(prog)]
        notes = [root + 36 + tones[0], root + 36 + tones[1], root + 36 + tones[2], root + 48 + tones[0]]
        for q in range(16):
            n = int(0.24 * SR)
            t = np.arange(n) / SR
            f = midi(notes[pattern[q]])
            sig = 0.6 * np.sign(np.sin(2 * np.pi * f * t)) + 0.4 * saw(f * t * 1.003)
            sig = lp(sig, 1400 + 1800 * (0.5 + 0.5 * np.sin(b * 0.37 + q * 0.2))) * np.exp(-t * 14)
            pan = 0.5 + 0.35 * np.sin(q * 0.9 + b)
            add(arp[:, 0], b * bar + q * beat / 4, sig * (1 - pan), 0.06)
            add(arp[:, 1], b * bar + q * beat / 4, sig * pan, 0.06)
    dl = int(beat * 0.75 * SR)  # ping-pong delay
    for k in range(1, 4):
        if dl * k < n_total:
            arp[dl * k:, 0] += arp[:-dl * k, 1] * 0.35 ** k
            arp[dl * k:, 1] += arp[:-dl * k, 0] * 0.35 ** k
    kn = int(0.45 * SR)
    kt = np.arange(kn) / SR
    kick_s = np.sin(2 * np.pi * (45 * kt + (110 / 18) * (1 - np.exp(-kt * 18)))) * np.exp(-kt * 7.5)
    kick_s += 0.25 * np.exp(-kt * 80) * rng.standard_normal(kn) * 0.3
    hn = int(0.09 * SR)
    hat_s = hp(rng.standard_normal(hn), 7000) * np.exp(-np.arange(hn) / SR * 55)
    for b in range(nbars):
        for q in range(4):
            t0 = b * bar + q * beat
            add(kick, t0, kick_s, 0.55)
            add(hat, t0 + beat / 2, hat_s, 0.10)
            add(hat, t0 + beat * 0.75, hat_s, 0.045)

    auto = [automation(i) for i in range(5)]
    music = pad * auto[0][:, None] + (bass * auto[1])[:, None] + arp * auto[2][:, None] \
        + (kick * auto[3])[:, None] + (hat * auto[4])[:, None]
    pump = 1 - 0.35 * auto[3] * np.exp(-((np.arange(n_total) / SR) % beat) * 9)  # sidechain from the kick
    music *= pump[:, None]

    # ---------- SFX ----------
    sfx = np.zeros((n_total, 2))

    def riser(tend, d=1.6, g=0.12):
        n = int(d * SR)
        t = np.arange(n) / SR
        x = rng.standard_normal(n)
        out = np.zeros(n)
        chunks = 32
        for c in range(chunks):
            a, b2 = c * n // chunks, (c + 1) * n // chunks
            fc = 300 * (20 ** (c / chunks))
            out[a:b2] = bp(x[max(0, a - 2000):b2], fc * 0.7, min(fc * 1.4, 20000))[-(b2 - a):]
        out *= (t / d) ** 2
        add(sfx[:, 0], tend - d, out, g)
        add(sfx[:, 1], tend - d, out, g * 0.9)

    def impact(t0, g=0.5):
        n = int(1.6 * SR)
        t = np.arange(n) / SR
        s = np.sin(2 * np.pi * (38 * t + 60 / 6 * (1 - np.exp(-t * 6)))) * np.exp(-t * 2.4)
        s = s + lp(rng.standard_normal(n), 2500) * np.exp(-t * 9) * 0.5
        add(sfx[:, 0], t0, s, g)
        add(sfx[:, 1], t0, s, g)

    def glitch(t0, d=0.3, g=0.12):
        n = int(d * SR)
        x = rng.standard_normal(n)
        hold = 60 + int(rng.random() * 200)
        x = np.round(np.repeat(x[::hold], hold)[:n] * 3) / 3
        gate = (np.sin(np.arange(n) / SR * 2 * np.pi * (18 + rng.random() * 30)) > 0).astype(float)
        s = bp(x * gate, 400, 6000)
        add(sfx[:, 0], t0, s, g)
        add(sfx[:, 1], t0 + 0.01, s, g * 0.8)

    def chime(t0, f=880, g=0.08):
        n = int(2.2 * SR)
        t = np.arange(n) / SR
        s = sum(np.sin(2 * np.pi * f * m * t) * np.exp(-t * (2 + m)) / m for m in (1, 2.01, 3.03))
        add(sfx[:, 0], t0, s, g)
        add(sfx[:, 1], t0 + 0.012, s, g)

    for i, s in enumerate(scenes):
        if i > 0:
            riser(s["start"], 1.5, 0.10)
            impact(s["start"], 0.42)
            glitch(s["start"] - 0.05, 0.35, 0.10)
    for slot in range(int(dur / 0.2)):  # the engine's micro-glitch rule: rnd(slot, 77) > 0.965
        x = np.sin(slot * 127.1 + 77 * 311.7 + 17.13) * 43758.5453
        if x - np.floor(x) > 0.965:
            glitch(slot * 0.2, 0.18, 0.05)
    starts: dict[str, list[float]] = {}
    for ln in tl["lines"]:
        starts.setdefault(ln["scene"], []).append(ln["start"])
    for sc in script.get("scenes") or []:
        for cue in sc.get("cues") or []:
            ls = starts.get(sc.get("id"), [])
            if cue.get("line", 0) >= len(ls):
                continue
            t0 = ls[cue["line"]] + float(cue.get("at", 0))
            kind = cue.get("kind")
            if kind == "stamp":
                impact(t0, 0.3)
                glitch(t0, 0.2, 0.08)
            elif kind == "chime":
                chime(t0, 660, 0.09)
            elif kind == "impact":
                impact(t0, 0.4)
            elif kind == "glitch":
                glitch(t0, 0.3, 0.1)
    chime(max(0.0, tl["duration"] - 3.0), 440, 0.1)  # end swell

    bed = music + sfx
    fade_in = np.minimum(1, np.arange(n_total) / (1.5 * SR))
    fade_out = np.minimum(1, (n_total - np.arange(n_total)) / (3.5 * SR))
    bed *= (fade_in * fade_out)[:, None]
    bed = np.tanh(bed * 1.1) / 1.1
    out = out_dir(film_dir) / "music_bed.wav"
    sf.write(str(out), bed.astype(np.float32), SR)
    rms = 20 * np.log10(np.sqrt(np.mean(bed ** 2)) + 1e-12)
    print(f"film: score {dur:.1f} s at {bpm:g} bpm ({settings.get('progression', 'a-minor')}), rms {rms:.1f} dB → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
