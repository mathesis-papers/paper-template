// Capture frames of <film>/out/index.html with headless Chromium and pipe them to ffmpeg (x264).
// Adapted from trureturing-film films/*/render.js (Apache-2.0, the-omega-institute).
//
// usage: node theme/film/render.js <out dir> [--worker 0 --workers 1] [--start s] [--end s] [--fps 30]
//                                  [--size 1920x1080] [--crf 17] [--preset medium] [--output seg_0.mp4]
//
// The frame range [start, end) (default: the whole timeline) is split evenly between `workers`; this process
// renders share `worker` into <out dir>/seg_<worker>.mp4 (or --output). Chromium: $PW_CHROMIUM_PATH when set,
// else Playwright's own. ffmpeg: $FFMPEG, else `ffmpeg` on PATH. Exits non-zero on any page error.
import { spawn } from 'node:child_process';
import { resolve, isAbsolute, join } from 'node:path';
import { existsSync } from 'node:fs';
import { launch, openFilm, frameJPEG, parseArgs, parseSize } from './lib.js';

const { pos, opt } = parseArgs(process.argv.slice(2));
if (!pos[0]) { console.error('usage: node render.js <out dir> [--worker w --workers n] [--start s --end s] [--size WxH]'); process.exit(2); }
const outDir = resolve(pos[0]);
if (!existsSync(join(outDir, 'index.html'))) { console.error(`render: ${outDir}/index.html is missing; run film.sh <dir> build`); process.exit(2); }
const worker = +(opt.worker || 0), workers = +(opt.workers || 1);
const [width, height] = parseSize(opt.size);
const FF = process.env.FFMPEG || 'ffmpeg';

const browser = await launch();
let code = 0;
try {
  const film = await openFilm(browser, outDir);
  const page = film.page;
  const fps = +(opt.fps || (await page.evaluate(() => (window.DATA.film && window.DATA.film.fps) || 30)));
  const duration = await page.evaluate(() => window.DATA.timeline.duration);
  const t0 = opt.start != null ? +opt.start : 0, t1 = Math.min(duration, opt.end != null ? +opt.end : duration);
  const first = Math.round(t0 * fps), total = Math.max(0, Math.ceil(t1 * fps) - first);
  const per = Math.ceil(total / workers);
  const f0 = first + worker * per, f1 = Math.min(first + total, f0 + per);
  let output = opt.output || `seg_${worker}.mp4`;
  if (!isAbsolute(output)) output = join(outDir, output);
  const args = ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', String(opt.preset || 'medium'), '-crf', String(opt.crf || 17), '-pix_fmt', 'yuv420p',
    '-r', String(fps), '-threads', '2', '-movflags', '+faststart', output];
  const ff = spawn(FF, args, { stdio: ['pipe', 'inherit', 'inherit'] });
  const ffDone = new Promise((ok, fail) => { ff.on('error', fail); ff.on('close', c => (c === 0 ? ok() : fail(new Error(`ffmpeg exited with ${c}`)))); });
  const started = Date.now();
  for (let f = f0; f < f1; f++) {
    const jpg = await frameJPEG(page, f / fps, { width, height });
    if (!ff.stdin.write(jpg)) await new Promise(r => ff.stdin.once('drain', r));
    if ((f - f0) % 300 === 0) console.log(`w${worker} frame ${f - f0}/${f1 - f0} ${((Date.now() - started) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end();
  await ffDone;
  const late = film.errors.length ? film.errors : await page.evaluate(() => window.FILM_ERRORS || []);
  if (late.length) throw new Error(`page errors while rendering:\n  ${late.slice(0, 5).join('\n  ')}`);
  console.log(`w${worker} done ${f1 - f0} frames (${(f0 / fps).toFixed(2)}–${(f1 / fps).toFixed(2)} s, ${width}x${height}) ` +
    `in ${((Date.now() - started) / 1000).toFixed(0)}s → ${output}`);
  await film.close();
} catch (e) {
  console.error(`render: ${e.message}`);
  code = 1;
} finally {
  await browser.close();
}
process.exit(code);
