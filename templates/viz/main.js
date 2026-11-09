/* __CODE__ · __TITLE__
   Starter: a two-source interference field drawn on a 2D canvas with the shared runtime (window.TRV).
   Replace the model and drawing; keep the drawer text honest about book sections, Lean theorems and model limits.
   Text written from script goes through TRV.L(中文, English); re-render it in TRV.onLang(...).
   Colours come from the tokens: TRV.palette.cyan, TRV.rgb.magenta, … (never hard-coded hex). */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const cv = $('view');
  const S = { sep: 0.4 };
  TRV.startGlitch($('app'));
  TRV.drawer({ drawer: $('drawer'), open: $('infoBtn'), close: $('drawerClose') });

  const W = 220, H = 140, k = 0.55;
  const off = document.createElement('canvas'); off.width = W; off.height = H;
  const octx = off.getContext('2d'), img = octx.createImageData(W, H);
  const C = TRV.rgb.cyan.map((x) => x * 255), M = TRV.rgb.magenta.map((x) => x * 255);
  function readout() {
    $('roFringe').textContent = (2 * Math.PI / k / (S.sep * H) * 100).toFixed(1) + TRV.L(' (相对单位)', ' (relative units)');
  }
  function draw(t) {
    const d = img.data, y1 = H / 2 - S.sep * H / 2, y2 = H / 2 + S.sep * H / 2;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const r1 = Math.hypot(x - 12, y - y1), r2 = Math.hypot(x - 12, y - y2);
      const f = (Math.cos(k * r1 - 2 * t) + Math.cos(k * r2 - 2 * t)) * 0.5;
      const a = Math.min(1, Math.abs(f)), i = 4 * (y * W + x), P = f >= 0 ? C : M;
      d[i] = P[0] * a; d[i + 1] = P[1] * a; d[i + 2] = P[2] * a; d[i + 3] = 255;
    }
    octx.putImageData(img, 0, 0);
    TRV.fitCanvas(cv);
    const ctx = cv.getContext('2d');
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(off, 0, 0, cv.width, cv.height);
  }
  $('sep').addEventListener('input', (ev) => { S.sep = parseFloat(ev.target.value); $('oSep').textContent = S.sep.toFixed(2); readout(); });
  TRV.onLang(readout);
  readout();
  const loop = (ms) => { draw(ms / 1000); if (!TRV.reduceMotion) requestAnimationFrame(loop); };
  requestAnimationFrame(loop);
})();
