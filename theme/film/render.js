// Capture frames of <film>/out/index.html with headless Chromium and pipe them to ffmpeg (x264).
// Adapted from trureturing-film films/*/render.js (Apache-2.0, the-omega-institute).
//
// usage: node theme/film/render.js <out dir> [--worker 0 --workers 1] [--start s] [--end s] [--fps 30]
//                                  [--size 1920x1080] [--renditions master,720p]
//                                  [--crf 17] [--preset medium] [--output seg_0.mp4] [--output-720p seg720_0.mp4]
//
// The frame range [start, end) (default: the whole timeline) is split evenly between `workers`; this process
// renders share `worker`. Every frame is captured once (at --size, default 1920x1080: the scenes are laid out
// for that canvas) and fed to one ffmpeg process that writes each rendition (theme/film/plan.py chooses them):
//   master  the frames as captured, CRF --crf (17), preset --preset (medium) → --output (seg_<worker>.mp4)
//   720p    the frames denoised (hqdn3d) and scaled to 1280x720 with lanczos, CRF 19, preset slow
//           → --output-720p (seg720_<worker>.mp4): the 720p videos, encoded from the frames, never from a master
// Both are H.264 yuv420p at the film's frame rate, x264 with 2 threads (deterministic for the same frames).
// Chromium: $PW_CHROMIUM_PATH when set, else Playwright's own. ffmpeg: $FFMPEG, else `ffmpeg` on PATH. Exits
// non-zero on any page error.
import { spawn } from 'node:child_process';
import { resolve, isAbsolute, join } from 'node:path';
import { existsSync } from 'node:fs';
import { launch, openFilm, frameJPEG, parseArgs, parseSize } from './lib.js';

// The 720p rendition: the same filter and quality as the 720p videos always had (two-pass 900 kb/s from the
// master before; CRF 19 at preset slow measures the same SSIM at a slightly lower bit rate).
const VF_720P = 'hqdn3d=3:2:6:5,scale=1280:720:flags=lanczos,format=yuv420p';
const CRF_720P = '19', PRESET_720P = 'slow';
const RENDITIONS = ['master', '720p'];

const { pos, opt } = parseArgs(process.argv.slice(2));
if (!pos[0]) { console.error('usage: node render.js <out dir> [--worker w --workers n] [--start s --end s] [--size WxH] [--renditions master,720p]'); process.exit(2); }
const outDir = resolve(pos[0]);
if (!existsSync(join(outDir, 'index.html'))) { console.error(`render: ${outDir}/index.html is missing; run film.sh <dir> build`); process.exit(2); }
const worker = +(opt.worker || 0), workers = +(opt.workers || 1);
const [width, height] = parseSize(opt.size);
const renditions = String(opt.renditions || 'master').split(',').filter(Boolean);
if (!renditions.length || renditions.some(r => !RENDITIONS.includes(r))) {
  console.error(`render: --renditions ${opt.renditions}: expected a comma list of ${RENDITIONS.join(', ')}`); process.exit(2);
}
const FF = process.env.FFMPEG || 'ffmpeg';
const place = name => (isAbsolute(name) ? name : join(outDir, name));

/** ffmpeg arguments: the JPEG frames on stdin, one output per rendition. */
function ffmpegArgs(fps, outputs) {
  const x264 = (crf, preset) => ['-c:v', 'libx264', '-preset', preset, '-crf', crf, '-pix_fmt', 'yuv420p',
    '-r', String(fps), '-threads', '2', '-movflags', '+faststart'];
  const args = ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-'];
  const master = x264(String(opt.crf || 17), String(opt.preset || 'medium'));
  const small = x264(CRF_720P, PRESET_720P);
  if (outputs.master && outputs['720p']) {
    args.push('-filter_complex', `[0:v]split=2[m][s];[s]${VF_720P}[v720]`,
      '-map', '[m]', ...master, outputs.master, '-map', '[v720]', ...small, outputs['720p']);
  } else if (outputs.master) {
    args.push(...master, outputs.master);
  } else {
    args.push('-vf', VF_720P, ...small, outputs['720p']);
  }
  return args;
}

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
  const outputs = {};
  if (renditions.includes('master')) outputs.master = place(opt.output || `seg_${worker}.mp4`);
  if (renditions.includes('720p')) outputs['720p'] = place(opt['output-720p'] || `seg720_${worker}.mp4`);
  const ff = spawn(FF, ffmpegArgs(fps, outputs), { stdio: ['pipe', 'inherit', 'inherit'] });
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
    `in ${((Date.now() - started) / 1000).toFixed(0)}s → ${Object.values(outputs).join(', ')}`);
  await film.close();
} catch (e) {
  console.error(`render: ${e.message}`);
  code = 1;
} finally {
  await browser.close();
}
process.exit(code);
