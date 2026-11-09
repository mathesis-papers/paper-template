"""Final mixes from out/music_bed.wav and out/narration.wav, with measured ducking.

Usage: python3 theme/film/mix.py <film dir> [--allow-silent]

  out/mix_voice.wav   narration over the score, the bed ducked ~12 dB under speech, -17 dB RMS
  out/mix_music.wav   the score alone, only when a music-only video is requested ($FILM_OUTPUTS, else
                      film.json's outputs; theme/film/plan.py); otherwise a stale one is removed

Without out/narration.wav the step fails, unless --allow-silent (local dry runs before TTS):
then mix_voice.wav is the score alone. Adapted from trureturing-film films/*/mix.py
(Apache-2.0, the-omega-institute).
"""

from __future__ import annotations

import sys

from common import fail, film_dir_arg, load, plan

SR = 48000


def main(argv: list[str]) -> int:
    try:
        import numpy as np
        import soundfile as sf
    except ImportError as exc:
        fail(f"{exc.name} is not installed; run theme/film/setup.sh")
    film_dir = film_dir_arg([a for a in argv if not a.startswith("--")])
    music_only = plan(load(film_dir))["music"]
    out = film_dir / "out"
    if not (out / "music_bed.wav").is_file():
        fail("out/music_bed.wav is missing; run the music step first")
    bed, sr = sf.read(str(out / "music_bed.wav"), dtype="float64")
    if sr != SR or bed.ndim != 2:
        fail(f"out/music_bed.wav must be {SR} Hz stereo")
    n = len(bed)
    if (out / "narration.wav").is_file():
        voice, vsr = sf.read(str(out / "narration.wav"), dtype="float64")
        if vsr != SR:
            fail(f"out/narration.wav must be {SR} Hz")
        if voice.ndim == 2:
            voice = voice.mean(1)
    elif "--allow-silent" in argv:
        print("film: warning: no out/narration.wav; mix_voice.wav is the score alone", file=sys.stderr)
        voice = np.zeros(n)
    else:
        fail("out/narration.wav is missing; run the tts step (or pass --allow-silent for a dry run)")
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]

    def movavg(x, w):
        c = np.cumsum(np.concatenate([[0.0], x]))
        h = w // 2
        i = np.arange(len(x))
        lo = np.clip(i - h, 0, len(x))
        hi = np.clip(i + h, 0, len(x))
        return (c[hi] - c[lo]) / np.maximum(1, hi - lo)

    def db(x):
        return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)

    target = -17.0
    if np.abs(voice).max() > 0:
        rms = np.sqrt(movavg(voice ** 2, int(0.05 * SR)))
        speech = rms > 0.02 * rms.max()
        v_db = db(voice[speech])
        b_db = db(bed.mean(1)[speech])
        act = movavg(speech.astype(float), int(0.5 * SR))
        duck = 1 - 0.6 * np.clip(act * 1.6, 0, 1)  # up to -8 dB while speaking
        g = 10 ** ((v_db - 12 - (b_db + 20 * np.log10(0.4))) / 20)  # ducked bed sits 12 dB under speech
        mix = bed * (g * duck)[:, None] + voice[:, None]
    else:
        mix = bed.copy()
    mix *= 10 ** ((target - db(mix.mean(1))) / 20)
    mix = np.tanh(mix / 0.95) * 0.95
    sf.write(str(out / "mix_voice.wav"), mix.astype(np.float32), SR)
    said = f"film: mixes → {out / 'mix_voice.wav'} (rms {db(mix.mean(1)):.1f} dB, peak {np.abs(mix).max():.3f})"
    if music_only:
        mo = bed * 10 ** ((target + 1 - db(bed.mean(1))) / 20)
        mo = np.tanh(mo / 0.95) * 0.95
        sf.write(str(out / "mix_music.wav"), mo.astype(np.float32), SR)
        said += f", {out / 'mix_music.wav'} (rms {db(mo.mean(1)):.1f} dB)"
    else:
        (out / "mix_music.wav").unlink(missing_ok=True)
        said += " (no music-only video requested: no music-only mix)"
    print(said)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
