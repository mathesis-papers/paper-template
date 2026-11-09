// Render the film's poster: window.poster() (FILM.poster from scenes.js, else the engine default).
// Adapted from trureturing-film films/*/poster.js (Apache-2.0, the-omega-institute).
//
// usage: node theme/film/poster.js <out dir> <cover file name> [<committed poster path>]
//   <out dir>/<cover>   1920×1080 JPEG (q 92), the release asset
//   <poster path>       1280×720 JPEG under 300 KB for the repository (books/<slug>/films/<dir>/poster.jpg)
import { writeFileSync, existsSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { launch, openFilm, frameJPEG } from './lib.js';

const [outArg, cover, small] = process.argv.slice(2);
if (!outArg || !cover) { console.error('usage: node poster.js <out dir> <cover.jpg> [poster.jpg]'); process.exit(2); }
const outDir = resolve(outArg);
if (!existsSync(join(outDir, 'index.html'))) { console.error(`poster: ${outDir}/index.html is missing; run film.sh <dir> build`); process.exit(2); }
const LIMIT = 300 * 1000;

const browser = await launch();
let code = 0;
try {
  const film = await openFilm(browser, outDir);
  const big = await frameJPEG(film.page, 0, { poster: true, quality: 0.92 });
  writeFileSync(join(outDir, cover), big);
  console.log(`poster: ${join(outDir, cover)} (${(big.length / 1024).toFixed(0)} KB)`);
  if (small) {
    let q = 0.86, jpg;
    for (; q >= 0.5; q -= 0.06) {
      jpg = await frameJPEG(film.page, 0, { poster: true, quality: q, width: 1280, height: 720 });
      if (jpg.length < LIMIT) break;
    }
    if (jpg.length >= LIMIT) jpg = await frameJPEG(film.page, 0, { poster: true, quality: 0.8, width: 960, height: 540 });
    writeFileSync(resolve(small), jpg);
    console.log(`poster: ${resolve(small)} (${(jpg.length / 1024).toFixed(0)} KB, q ${q.toFixed(2)})`);
  }
  await film.close();
} catch (e) {
  console.error(`poster: ${e.message}`);
  code = 1;
} finally {
  await browser.close();
}
process.exit(code);
