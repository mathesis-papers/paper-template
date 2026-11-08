/* trureturing books · decoration of a book's visualization hub (<slug>/viz/index.html).
   The cards are static HTML written by tbook.viz.build (paired .zh/.en fragments, so no re-rendering on language switch);
   this script only pulses the logo and animates the hero's double-slit wave field.
   Adapted from trureturing-visualize/assets/hub.js (Apache-2.0, the-omega-institute); colours come from the tokens. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  TRV.startGlitch($('app'), 11000);

  /* ---------- hero field: plane wave through two slits, real part of the field ---------- */
  const cv = $('field');
  if (!cv) return;
  const W = 200, H = 76;
  const off = document.createElement('canvas'); off.width = W; off.height = H;
  const octx = off.getContext('2d');
  const img = octx.createImageData(W, H);
  const wallX = Math.round(W * 0.5), slitY = [H * 0.5 - 7, H * 0.5 + 7];
  const k = 0.62, omega = 2.2;
  let visible = true, last = 0, colours = null;
  const toRgb = (hex) => TRV.rgb[hex].map((x) => Math.round(x * 255));
  function draw(t) {
    if (!colours) colours = { c: toRgb('cyan'), m: toRgb('magenta'), w: toRgb('lineHot'), bg: TRV.palette.stage };
    const d = img.data, C = colours.c, M = colours.m, WL = colours.w;
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        let f, env;
        if (x < wallX) {
          f = Math.cos(k * x - omega * t) * 0.55;
          env = 0.55;
        } else {
          const dx = x - wallX + 0.5;
          const r1 = Math.hypot(dx, y - slitY[0]), r2 = Math.hypot(dx, y - slitY[1]);
          f = (Math.cos(k * r1 - omega * t) / Math.sqrt(r1 + 2) + Math.cos(k * r2 - omega * t) / Math.sqrt(r2 + 2)) * 2.4;
          env = 1;
        }
        const wall = x === wallX && Math.abs(y - slitY[0]) > 1.5 && Math.abs(y - slitY[1]) > 1.5;
        const i = 4 * (y * W + x);
        if (wall) { d[i] = WL[0]; d[i + 1] = WL[1]; d[i + 2] = WL[2]; d[i + 3] = 255; continue; }
        const a = Math.min(1, Math.abs(f)) * env;
        const P = f >= 0 ? C : M, s = f >= 0 ? a : a * 0.85;
        d[i] = P[0] * s; d[i + 1] = P[1] * s; d[i + 2] = P[2] * s; d[i + 3] = 255;
      }
    }
    octx.putImageData(img, 0, 0);
    TRV.fitCanvas(cv);
    const ctx = cv.getContext('2d');
    ctx.imageSmoothingEnabled = true;
    ctx.fillStyle = colours.bg; ctx.fillRect(0, 0, cv.width, cv.height);
    const scale = Math.max(cv.width / W, cv.height / H);
    const dw = W * scale, dh = H * scale;
    ctx.globalAlpha = 0.9;
    ctx.drawImage(off, (cv.width - dw) / 2, (cv.height - dh) / 2, dw, dh);
    ctx.globalAlpha = 1;
  }
  function loop(ms) {
    if (visible && !document.hidden && ms - last > 33) { draw(ms / 1000); last = ms; }
    requestAnimationFrame(loop);
  }
  if ('IntersectionObserver' in window) new IntersectionObserver((es) => { visible = es[0].isIntersecting; }).observe(cv);
  draw(0.8);
  if (!TRV.reduceMotion) requestAnimationFrame(loop);
  window.addEventListener('resize', () => draw(last / 1000 || 0.8));
})();
