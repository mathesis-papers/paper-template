// Screenshots of single frames for review: node theme/film/shot.js <out dir> <t1> <t2> … [--size 1920x1080] [--poster]
// Writes <out dir>/shots/t_<t>.jpg (and poster.jpg with --poster). Adapted from trureturing-film films/*/shot.js.
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { launch, openFilm, frameJPEG, parseArgs, parseSize } from './lib.js';

const { pos, opt } = parseArgs(process.argv.slice(2));
if (!pos[0]) { console.error('usage: node shot.js <out dir> <t1> [t2 …] [--size WxH] [--poster]'); process.exit(2); }
const outDir = resolve(pos[0]);
if (!existsSync(join(outDir, 'index.html'))) { console.error(`shot: ${outDir}/index.html is missing; run film.sh <dir> build`); process.exit(2); }
const [width, height] = parseSize(opt.size);
const shots = join(outDir, 'shots');
mkdirSync(shots, { recursive: true });

const browser = await launch();
let code = 0;
try {
  const film = await openFilm(browser, outDir);
  const times = pos.slice(1);
  if (opt.poster) times.push('poster');
  for (const a of times) {
    const t = a === 'poster' ? 0 : parseFloat(a);
    if (Number.isNaN(t)) throw new Error(`not a time: ${a}`);
    const t0 = Date.now();
    const jpg = await frameJPEG(film.page, t, { width, height, quality: 0.88, poster: a === 'poster' });
    const file = join(shots, a === 'poster' ? 'poster.jpg' : `t_${a}.jpg`);
    writeFileSync(file, jpg);
    console.log(`${file} (${Date.now() - t0} ms)`);
  }
  const errs = await film.page.evaluate(() => window.FILM_ERRORS || []);
  if (errs.length) throw new Error(`page errors: ${errs.slice(0, 5).join(' | ')}`);
  await film.close();
} catch (e) {
  console.error(`shot: ${e.message}`);
  code = 1;
} finally {
  await browser.close();
}
process.exit(code);
