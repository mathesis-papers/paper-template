/* GOLDEN//CARRY · 黄金进位 — the carry deficit when two Zeckendorf representations are added.
   Everything is exact integer arithmetic: β(v) = a + bφ in ℤ[φ] with φ^k = F(k−1) + F(k)·φ, so no rounding enters c.
   The carry rules and their order follow trureturing D5/S1/Digit/Normalize.lean (carryPass): the least position holding
   a 2 fires a repeated carry (R₀: 2W₀ → W₁, R₁: 2W₁ → W₀ + W₂, Rⱼ: 2Wⱼ → Wⱼ₋₂ + Wⱼ₊₁); otherwise the least adjacent
   pair of 1s fires the adjacent carry A: Wⱼ + Wⱼ₊₁ → Wⱼ₊₂. R₀ counts +1, R₁ counts −1, the others 0
   (D5/S1/Deficit/DeficitInteger.carrySign). Colours: cyan +1, magenta −1, amber = the current pair / pass.
   Read-only probe for tests: window.GC_DEBUG. Thumbnail hook: window.TRV_THUMB. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const L = TRV.L, esc = TRV.esc;
  const VMAX = 987, NS = [34, 89, 233, 987];
  const MINUS = '−';

  /* ---------- exact arithmetic ---------- */
  const F = [0, 1];
  while (F.length < 48) F.push(F[F.length - 1] + F[F.length - 2]);
  const Wt = (i) => F[i + 2]; // W_i = F_(i+2): 1, 2, 3, 5, 8, …
  const SUB = '₀₁₂₃₄₅₆₇₈₉';
  const sub = (n) => String(n).split('').map((d) => SUB[+d]).join('');

  /** Zeckendorf digits of n, index i ↔ weight W_i (greedy; the result has no two adjacent 1s). */
  function zeck(n) {
    if (n <= 0) return [];
    let top = 0;
    while (Wt(top + 1) <= n) top++;
    const d = new Array(top + 1).fill(0);
    for (let i = top; i >= 0; i--) if (Wt(i) <= n) { d[i] = 1; n -= Wt(i); }
    return d;
  }
  /** β(v) = Σ φ^(i+2) over the Zeckendorf digits of v, as the pair (a, b) meaning a + bφ. */
  function beta(v) {
    let a = 0, b = 0;
    zeck(v).forEach((x, i) => { if (x) { a += F[i + 1]; b += F[i + 2]; } });
    return { a, b };
  }
  const value = (r) => r.reduce((s, x, i) => s + x * Wt(i), 0);
  const trim = (r) => { const out = r.slice(); while (out.length && out[out.length - 1] === 0) out.pop(); return out; };
  const bump = (r, i, k) => { while (r.length <= i) r.push(0); r[i] += k; };

  /** Normalize raw digits one carry per pass, in the order of trureturing's carryPass. */
  function normalize(raw) {
    const r = raw.slice(), passes = [];
    for (let guard = 0; guard < 100000; guard++) {
      let i = r.findIndex((x) => x >= 2), step;
      if (i === 0) { r[0] -= 2; bump(r, 1, 1); step = { rule: 'R0', at: 0, sign: 1, touched: [0, 1] }; }
      else if (i === 1) { r[1] -= 2; r[0] += 1; bump(r, 2, 1); step = { rule: 'R1', at: 1, sign: -1, touched: [0, 1, 2] }; }
      else if (i >= 2) { r[i] -= 2; r[i - 2] += 1; bump(r, i + 1, 1); step = { rule: 'R', at: i, sign: 0, touched: [i - 2, i, i + 1] }; }
      else {
        i = -1;
        for (let j = 0; j + 1 < r.length; j++) if (r[j] === 1 && r[j + 1] === 1) { i = j; break; }
        if (i < 0) break;
        r[i] -= 1; r[i + 1] -= 1; bump(r, i + 2, 1); step = { rule: 'A', at: i, sign: 0, touched: [i, i + 1, i + 2] };
      }
      step.digits = trim(r);
      passes.push(step);
    }
    return { passes, digits: trim(r) };
  }

  /* the a-coordinate of β(n) for every n the grid can need; c(i, j) = A[i] + A[j] − A[i + j] (the φ part cancels) */
  const A = new Int32Array(2 * VMAX + 2);
  for (let n = 0; n < A.length; n++) A[n] = beta(n).a;
  const cOf = (i, j) => A[i] + A[j] - A[i + j];

  /* ---------- state ---------- */
  const q = new URLSearchParams(location.search);
  const clampV = (x) => Math.max(0, Math.min(VMAX, Math.round(Number(x)) || 0));
  const S = {
    v1: q.has('v1') ? clampV(q.get('v1')) : 17, v2: q.has('v2') ? clampV(q.get('v2')) : 17,
    N: NS.includes(+q.get('n')) ? +q.get('n') : 34, pass: 0, playing: false, hover: null
  };
  let R = null; // derived data of the current pair
  let frames = 0, pending = false, built = '';
  const rng = TRV.mulberry32(20261108);

  function derive() {
    const { v1, v2 } = S, z1 = zeck(v1), z2 = zeck(v2), z3 = zeck(v1 + v2);
    const raw = [];
    for (let i = 0; i < Math.max(z1.length, z2.length); i++) raw.push((z1[i] || 0) + (z2[i] || 0));
    const norm = normalize(raw);
    const b1 = beta(v1), b2 = beta(v2), b3 = beta(v1 + v2);
    const c = { a: b1.a + b2.a - b3.a, b: b1.b + b2.b - b3.b };
    const count = norm.passes.reduce((s, p) => s + p.sign, 0);
    const width = Math.max(1, raw.length, z3.length, ...norm.passes.map((p) => p.digits.length));
    R = { v1, v2, z1, z2, z3, raw, passes: norm.passes, final: norm.digits, b1, b2, b3, c, count, width,
      canonicalOk: norm.digits.join() === z3.join() && value(norm.digits) === v1 + v2 };
  }
  const fresh = () => { if (!R || R.v1 !== S.v1 || R.v2 !== S.v2) derive(); return R; };

  /* ---------- formatting ---------- */
  const fmtInt = (x) => (x < 0 ? MINUS + -x : String(x));
  const fmtSigned = (x) => (x > 0 ? '+' + x : x < 0 ? MINUS + -x : '0');
  const signCls = (x) => (x > 0 ? 'vpos' : x < 0 ? 'vneg' : 'vzero');
  function fmtZphi({ a, b }) {
    if (b === 0) return fmtInt(a);
    const phi = (Math.abs(b) === 1 ? '' : Math.abs(b)) + 'φ';
    if (a === 0) return (b < 0 ? MINUS : '') + phi;
    return `${fmtInt(a)} ${b < 0 ? MINUS : '+'} ${phi}`;
  }
  const digitsStr = (d) => (d.length ? d.slice().reverse().join('') : '0');
  const PHI = (1 + Math.sqrt(5)) / 2, PSI = 1 - PHI;
  const real = ({ a, b }, x) => a + b * x;
  const fx = (x, k = 4) => (x < 0 ? MINUS : '') + Math.abs(x).toFixed(k);
  function ruleText(p) {
    const j = p.at;
    if (p.rule === 'R0') return { code: '2·W₀ → W₁', name: L('R₀ 最低重复进位：β 减少 1', 'R₀ lowest repeated carry: β drops by 1') };
    if (p.rule === 'R1') return { code: '2·W₁ → W₀ + W₂', name: L('R₁ 第二重复进位：β 增加 1', 'R₁ second repeated carry: β rises by 1') };
    if (p.rule === 'R') return { code: `2·W${sub(j)} → W${sub(j - 2)} + W${sub(j + 1)}`, name: L(`R${sub(j)} 内部重复进位：β 不变`, `R${sub(j)} internal repeated carry: β unchanged`) };
    return { code: `W${sub(j)} + W${sub(j + 1)} → W${sub(j + 2)}`, name: L('A 相邻进位：β 不变', 'A adjacent carry: β unchanged') };
  }

  /* ---------- ledger ---------- */
  function cells(d, touched) {
    let h = '';
    for (let i = R.width - 1; i >= 0; i--) {
      const x = d[i] || 0, cls = (x >= 2 ? 'd2' : x === 1 ? 'd1' : 'd0') + (touched && touched.includes(i) ? ' touch' : '');
      h += `<span class="${cls}">${x}</span>`;
    }
    return `<div class="cells">${h}</div>`;
  }
  function buildLedger() {
    const rows = [];
    let head = '';
    for (let i = R.width - 1; i >= 0; i--) head += `<span>${Wt(i)}<small>W${sub(i)}</small></span>`;
    rows.push(`<div class="drow hdr" aria-hidden="true"><span class="lab">${L('权重', 'weight')}</span><div class="cells">${head}</div><span class="what"></span></div>`);
    rows.push(`<div class="drow input" role="listitem"><span class="lab">v₁</span>${cells(R.z1)}<span class="what">Z(${S.v1}) · ${L('值', 'value')} ${S.v1}</span></div>`);
    rows.push(`<div class="drow input" role="listitem"><span class="lab">v₂</span>${cells(R.z2)}<span class="what">Z(${S.v2}) · ${L('值', 'value')} ${S.v2}</span></div>`);
    const sumNote = R.passes.length ? L('逐位和 Z(v₁) + Z(v₂)', 'digitwise sum Z(v₁) + Z(v₂)') : L('逐位和，已是规范形', 'digitwise sum, already canonical');
    rows.push(`<div class="drow sum" role="listitem" data-pass="0"><span class="lab">Σ</span>${cells(R.raw)}<span class="what">${sumNote} · ${L('值', 'value')} ${S.v1 + S.v2}</span></div>`);
    R.passes.forEach((p, k) => {
      const t = ruleText(p), last = k === R.passes.length - 1;
      const cls = p.sign > 0 ? 'pos' : p.sign < 0 ? 'neg' : 'zero';
      const tail = last ? ` · = Z(${S.v1 + S.v2}) <span class="${R.canonicalOk ? 'okmark' : 'badmark'}">${R.canonicalOk ? '✓' : '✗'}</span>` : '';
      rows.push(`<div class="drow pass${last ? ' final' : ''}" role="listitem" data-pass="${k + 1}"><span class="lab">#${k + 1}</span>${cells(p.digits, p.touched)}<span class="what"><span class="sgn ${cls}">${fmtSigned(p.sign)}</span><code>${t.code}</code><span class="name">${esc(t.name)}${tail}</span></span></div>`);
    });
    $('ledger').innerHTML = rows.join('');
    $('tape').innerHTML = R.passes.map((p, k) => `<i class="${p.sign > 0 ? 'pos' : p.sign < 0 ? 'neg' : 'zero'}" data-pass="${k + 1}" title="#${k + 1} ${fmtSigned(p.sign)}"></i>`).join('') || '';
  }
  function markLedger() {
    const K = R.passes.length;
    $('ledger').querySelectorAll('.drow[data-pass]').forEach((row) => {
      const k = +row.dataset.pass;
      row.classList.toggle('now', k === S.pass);
      row.classList.toggle('future', k > S.pass);
      row.setAttribute('aria-current', k === S.pass ? 'step' : 'false');
    });
    $('tape').querySelectorAll('i').forEach((t) => { const k = +t.dataset.pass; t.classList.toggle('now', k === S.pass); t.classList.toggle('future', k > S.pass); });
    const partial = R.passes.slice(0, S.pass).reduce((s, p) => s + p.sign, 0);
    $('tapeSum').innerHTML = K
      ? `${L('至第', 'to pass')} ${S.pass}${L(' 步', '')}: <span class="${signCls(partial)}">${fmtSigned(partial)}</span> · ${L('总计', 'total')} <span class="${signCls(R.count)}">${fmtSigned(R.count)}</span>`
      : `${L('无进位', 'no carries')} · <span class="vzero">0</span>`;
    $('pass').max = String(Math.max(1, K));
    $('pass').value = String(S.pass);
    $('pass').disabled = K === 0;
    $('passLabel').innerHTML = `${L('第', 'PASS ')}${S.pass}${L(' 步', '')} <small>/ ${K}</small>`;
    $('prev').disabled = $('first').disabled = S.pass === 0;
    $('next').disabled = $('last').disabled = S.pass >= K;
    $('play').disabled = K === 0;
    // keep the current row visible inside the ledger's own scroller (never scroll the page)
    const wrap = $('sheetWrap'), row = $('ledger').querySelector('.drow.now');
    if (row) {
      const top = row.offsetTop - 34, bottom = row.offsetTop + row.offsetHeight + 6;
      if (top < wrap.scrollTop) wrap.scrollTop = top;
      else if (bottom > wrap.scrollTop + wrap.clientHeight) wrap.scrollTop = bottom - wrap.clientHeight;
    }
  }

  /* ---------- readouts ---------- */
  function readouts() {
    const { b1, b2, b3, c, count } = R;
    $('roZ1').textContent = digitsStr(R.z1);
    $('roZ2').textContent = digitsStr(R.z2);
    $('roZ3').textContent = digitsStr(R.z3);
    const bline = (b) => `${fmtZphi(b)}<span class="sub">≈ ${fx(real(b, PHI))}</span>`;
    $('roB1').innerHTML = bline(b1);
    $('roB2').innerHTML = bline(b2);
    $('roB3').innerHTML = bline(b3);
    const isInt = c.b === 0, three = isInt && [-1, 0, 1].includes(c.a);
    $('roC').innerHTML = `<b class="${signCls(c.a)}">${isInt ? fmtSigned(c.a) : fmtZphi(c)}</b>`
      + `<span class="sub">= (${fmtInt(b1.a)} + ${fmtInt(b2.a)} ${MINUS} ${fmtInt(b3.a)}) + (${b1.b} + ${b2.b} ${MINUS} ${b3.b})φ</span>`
      + `<span class="sub">${isInt ? L('φ 系数为 0，所以 c 是整数', 'the φ-coefficient is 0, so c is an integer') : L('φ 系数不为 0', 'nonzero φ-coefficient')} · c ∈ {${MINUS}1, 0, 1} <span class="${three ? 'okmark' : 'badmark'}">${three ? '✓' : '✗'}</span></span>`;
    const agree = isInt && count === c.a;
    $('roCount').innerHTML = `#R₀ ${MINUS} #R₁ = ${R.passes.filter((p) => p.sign > 0).length} ${MINUS} ${R.passes.filter((p) => p.sign < 0).length} = <b class="${signCls(count)}">${fmtSigned(count)}</b> <span class="${agree ? 'okmark' : 'badmark'}">${agree ? '= c ✓' : '≠ c ✗'}</span>`;
    const lo = -1 / (PHI * PHI), hi = 1 / PHI;
    const cj = [b1, b2, b3].map((b) => real(b, PSI));
    const inWin = cj.every((x) => x >= lo - 1e-12 && x <= hi + 1e-12);
    const cConj = cj[0] + cj[1] - cj[2];
    $('roConj').innerHTML = `${cj.map((x) => fx(x)).join(' · ')}<span class="sub">∈ [${fx(lo)}, ${fx(hi)}] <span class="${inWin ? 'okmark' : 'badmark'}">${inWin ? '✓' : '✗'}</span> · c′ = ${fx(cConj, 6)}</span>`;
    $('roNote').textContent = L(
      `进位 ${R.passes.length} 次，其中 R₀ ${R.passes.filter((p) => p.rule === 'R0').length} 次、R₁ ${R.passes.filter((p) => p.rule === 'R1').length} 次；其余规则不改变 β。`,
      `${R.passes.length} carr${R.passes.length === 1 ? 'y' : 'ies'}: R₀ ${R.passes.filter((p) => p.rule === 'R0').length}×, R₁ ${R.passes.filter((p) => p.rule === 'R1').length}×; the other rules leave β unchanged.`);
    $('pillPair').innerHTML = `v₁, v₂ <strong>${S.v1}, ${S.v2}</strong>`;
    $('pillPasses').innerHTML = `${L('进位', 'CARRIES')} <strong>${R.passes.length}</strong>`;
    $('pillC').innerHTML = `c <strong class="${signCls(c.a)}">${isInt ? fmtSigned(c.a) : fmtZphi(c)}</strong>`;
  }

  /* ---------- deficit map ---------- */
  const heat = $('heat');
  let geom = null, gridCounts = null, gridCountsN = -1;
  function rgb255(name) { return TRV.rgb[name].map((x) => Math.round(x * 255)); }
  let base = null; // cached cells and ticks: { key, canvas }
  function drawBase(Wc, Hc, dpr, g) {
    const cv = document.createElement('canvas'); cv.width = Wc; cv.height = Hc;
    const ctx = cv.getContext('2d'), { ox, oy, s, nx, ny } = g;
    ctx.fillStyle = TRV.palette.stage; ctx.fillRect(0, 0, Wc, Hc);
    const P = rgb255('cyan'), M = rgb255('magenta'), st = rgb255('stage'), lh = rgb255('lineHot');
    const Z = st.map((x, k) => Math.round(x * 0.55 + lh[k] * 0.45));
    if (s >= 5 * dpr) {
      const gap = Math.max(1, Math.round(s * 0.1));
      const fills = { 1: `rgb(${P})`, '-1': `rgb(${M})`, 0: `rgb(${Z})` };
      for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++) {
        ctx.fillStyle = fills[cOf(x, y)] || TRV.palette.warn;
        ctx.fillRect(ox + x * s, oy + (ny - 1 - y) * s, s - gap, s - gap);
      }
    } else {
      const off = document.createElement('canvas'); off.width = nx; off.height = ny;
      const octx = off.getContext('2d'), img = octx.createImageData(nx, ny), d = img.data;
      for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++) {
        const c = cOf(x, y), C = c > 0 ? P : c < 0 ? M : Z, i = 4 * ((ny - 1 - y) * nx + x);
        d[i] = C[0]; d[i + 1] = C[1]; d[i + 2] = C[2]; d[i + 3] = 255;
      }
      octx.putImageData(img, 0, 0);
      ctx.imageSmoothingEnabled = s < 1;
      ctx.drawImage(off, ox, oy, nx * s, ny * s);
    }
    {
      // Fibonacci ticks on both axes
      ctx.font = `${10 * dpr}px ${TRV.fonts.data}`;
      ctx.fillStyle = TRV.palette.dim;
      let lastX = -1e9, lastY = 1e9;
      ctx.textBaseline = 'top'; ctx.textAlign = 'center';
      const ticks = [0, ...F.slice(2).filter((f) => f <= S.N)];
      for (const f of ticks) {
        const x = ox + (f + 0.5) * s;
        if (x - lastX < 20 * dpr) continue;
        ctx.fillText(String(f), x, oy + ny * s + 5 * dpr); lastX = x;
      }
      ctx.textBaseline = 'middle'; ctx.textAlign = 'right';
      for (const f of ticks) {
        const y = oy + (ny - 1 - f + 0.5) * s;
        if (lastY - y < 13 * dpr) continue;
        ctx.fillText(String(f), ox - 6 * dpr, y); lastY = y;
      }
    }
    return cv;
  }
  function drawHeat() {
    if (TRV.thumbMode) { drawCover(); return; }
    const dpr = TRV.fitCanvas(heat), ctx = heat.getContext('2d');
    const Wc = heat.width, Hc = heat.height;
    const pad = { l: 34 * dpr, r: 8 * dpr, t: 8 * dpr, b: 22 * dpr };
    const pw = Wc - pad.l - pad.r, ph = Hc - pad.t - pad.b;
    const nx = S.N + 1, ny = nx, s = Math.min(pw / nx, ph / ny);
    const ox = pad.l + Math.max(0, (pw - nx * s) / 2), oy = pad.t + ph - ny * s;
    geom = { ox, oy, s, nx, ny, dpr };
    const key = `${Wc}x${Hc}@${dpr}:${S.N}`;
    if (!base || base.key !== key) base = { key, canvas: drawBase(Wc, Hc, dpr, geom) };
    ctx.clearRect(0, 0, Wc, Hc);
    ctx.drawImage(base.canvas, 0, 0);
    // current pair: amber cross and box
    const cx = S.v1, cy = S.v2;
    if (cx < nx && cy < ny) {
      const px = ox + (cx + 0.5) * s, py = oy + (ny - 1 - cy + 0.5) * s, box = Math.max(s, 8 * dpr);
      ctx.strokeStyle = TRV.alpha(TRV.palette.amber, 0.45); ctx.lineWidth = Math.max(1, dpr);
      ctx.beginPath(); ctx.moveTo(px, oy); ctx.lineTo(px, oy + ny * s); ctx.moveTo(ox, py); ctx.lineTo(ox + nx * s, py); ctx.stroke();
      ctx.strokeStyle = TRV.palette.amber; ctx.lineWidth = 2 * dpr;
      ctx.shadowColor = TRV.palette.amber; ctx.shadowBlur = 10 * dpr;
      ctx.strokeRect(px - box / 2, py - box / 2, box, box);
      ctx.shadowBlur = 0;
    }
    {
      if (gridCountsN !== S.N) {
        const n = S.N + 1, k = { '-1': 0, 0: 0, 1: 0, other: 0 };
        for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) { const c = cOf(x, y); if (c === -1 || c === 0 || c === 1) k[c]++; else k.other++; }
        gridCounts = k; gridCountsN = S.N;
      }
      const k = gridCounts, total = (S.N + 1) * (S.N + 1), ok = k.other === 0;
      $('heatCounts').innerHTML = `<span class="vneg">${MINUS}1</span>: ${k['-1']} · <span class="vzero">0</span>: ${k[0]} · <span class="vpos">+1</span>: ${k[1]} — `
        + L(`全部 ${total} 格都在 {${MINUS}1, 0, 1} 中 `, `all ${total} cells lie in {${MINUS}1, 0, 1} `) + `<span class="${ok ? 'okmark' : 'badmark'}">${ok ? '✓' : '✗'}</span>`
        + (S.v1 > S.N || S.v2 > S.N ? ` · ${L('当前一对在网格外', 'the current pair is outside the grid')}` : '');
      $('heatRange').textContent = `0 … ${S.N}`;
      const h = S.hover;
      $('heatHover').innerHTML = h ? `${L('指针', 'pointer')} (${h[0]}, ${h[1]}) → c = <span class="${signCls(cOf(h[0], h[1]))}">${fmtSigned(cOf(h[0], h[1]))}</span>` : '&nbsp;';
    }
  }
  /** Thumbnail cover (?thumb=1): the deficit map over 0 … 34 beside the carry ledger of the current pair. No words,
      so one cover serves both languages; only digits and the codes of the rows. */
  function drawCover() {
    const dpr = TRV.fitCanvas(heat), ctx = heat.getContext('2d'), Wc = heat.width, Hc = heat.height;
    const u = Hc / 720, pal = TRV.palette, mono = TRV.fonts.data;
    geom = null;
    ctx.fillStyle = pal.stage; ctx.fillRect(0, 0, Wc, Hc);
    const glow = ctx.createRadialGradient(Wc * 0.28, Hc * 0.5, 0, Wc * 0.28, Hc * 0.5, Wc * 0.55);
    glow.addColorStop(0, TRV.alpha(pal.cyan, 0.08)); glow.addColorStop(1, TRV.alpha(pal.cyan, 0));
    ctx.fillStyle = glow; ctx.fillRect(0, 0, Wc, Hc);
    // the deficit map
    const n = 35, side = 600 * u, s = side / n, ox = 64 * u, oy = (Hc - side) / 2, gap = Math.max(1, s * 0.12);
    const st = rgb255('stage'), lh = rgb255('lineHot');
    const zero = `rgb(${st.map((x, k) => Math.round(x * 0.55 + lh[k] * 0.45))})`;
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const c = cOf(x, y);
      ctx.fillStyle = c > 0 ? pal.cyan : c < 0 ? pal.magenta : zero;
      ctx.fillRect(ox + x * s, oy + (n - 1 - y) * s, s - gap, s - gap);
    }
    const px = ox + (S.v1 + 0.5) * s - gap / 2, py = oy + (n - 1 - S.v2 + 0.5) * s - gap / 2;
    if (S.v1 < n && S.v2 < n) {
      ctx.strokeStyle = TRV.alpha(pal.amber, 0.5); ctx.lineWidth = 1.5 * u;
      ctx.beginPath(); ctx.moveTo(px, oy); ctx.lineTo(px, oy + side); ctx.moveTo(ox, py); ctx.lineTo(ox + side, py); ctx.stroke();
      ctx.strokeStyle = pal.amber; ctx.lineWidth = 3 * u; ctx.shadowColor = pal.amber; ctx.shadowBlur = 16 * u;
      ctx.strokeRect(px - s * 0.75, py - s * 0.75, s * 1.5, s * 1.5); ctx.shadowBlur = 0;
    }
    // the carry ledger
    const D = fresh();
    const rows = [{ lab: 'v₁', d: D.z1 }, { lab: 'v₂', d: D.z2 }, { lab: 'Σ', d: D.raw, sep: true },
      ...D.passes.map((p, k) => ({ lab: '#' + (k + 1), d: p.digits, sign: p.sign, touched: p.touched }))];
    const rowH = Math.min(50 * u, side / rows.length), cell = rowH * 0.8, x0 = 760 * u, labW = 58 * u;
    const y0 = oy + (side - rows.length * rowH) / 2;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    rows.forEach((r, k) => {
      const y = y0 + k * rowH, cy = y + rowH / 2, last = k === rows.length - 1;
      if (r.sep) { ctx.strokeStyle = pal.lineHot; ctx.setLineDash([4 * u, 4 * u]); ctx.beginPath(); ctx.moveTo(x0, y + 1); ctx.lineTo(x0 + labW + D.width * cell + 90 * u, y + 1); ctx.stroke(); ctx.setLineDash([]); }
      ctx.font = `${15 * u}px ${mono}`; ctx.fillStyle = last ? pal.amber : pal.dim; ctx.textAlign = 'left';
      ctx.fillText(r.lab, x0, cy); ctx.textAlign = 'center';
      for (let i = D.width - 1, col = 0; i >= 0; i--, col++) {
        const x = x0 + labW + col * cell, v = r.d[i] || 0, t = r.touched && r.touched.includes(i);
        if (v >= 1) { ctx.fillStyle = TRV.alpha(v >= 2 ? pal.magenta : pal.cyan, v >= 2 ? 0.2 : 0.14); ctx.fillRect(x + 2 * u, y + (rowH - cell) / 2 + 2 * u, cell - 4 * u, cell - 4 * u); }
        if (t) { ctx.strokeStyle = last ? pal.amber : TRV.alpha(pal.cyan, 0.5); ctx.lineWidth = 1.5 * u; ctx.strokeRect(x + 2 * u, y + (rowH - cell) / 2 + 2 * u, cell - 4 * u, cell - 4 * u); }
        ctx.font = `${(v >= 2 ? 600 : 400)} ${19 * u}px ${mono}`;
        ctx.fillStyle = v >= 2 ? pal.magenta : v === 1 ? (last && t ? pal.amber : pal.ink) : pal.faint;
        ctx.fillText(String(v), x + cell / 2, cy + 1 * u);
      }
      if (r.sign !== undefined) {
        const bx = x0 + labW + D.width * cell + 22 * u, col = r.sign > 0 ? pal.cyan : r.sign < 0 ? pal.magenta : pal.faint;
        ctx.strokeStyle = r.sign ? col : pal.panelEdge; ctx.lineWidth = 1.5 * u; ctx.strokeRect(bx, cy - 13 * u, 56 * u, 26 * u);
        ctx.font = `600 ${15 * u}px ${mono}`; ctx.fillStyle = col; ctx.fillText(fmtSigned(r.sign), bx + 28 * u, cy + 1 * u);
      }
      if (last) {
        ctx.strokeStyle = pal.amber; ctx.lineWidth = 2 * u; ctx.shadowColor = pal.amber; ctx.shadowBlur = 12 * u;
        ctx.strokeRect(x0 - 12 * u, y + 2 * u, labW + D.width * cell + 112 * u, rowH - 4 * u); ctx.shadowBlur = 0;
      }
    });
  }
  function cellAt(ev) {
    if (!geom) return null;
    const r = heat.getBoundingClientRect(), dpr = geom.dpr;
    const px = (ev.clientX - r.left) * dpr, py = (ev.clientY - r.top) * dpr;
    const x = Math.floor((px - geom.ox) / geom.s), y = Math.floor((geom.oy + geom.ny * geom.s - py) / geom.s);
    return x >= 0 && y >= 0 && x < geom.nx && y < geom.ny ? [Math.min(VMAX, x), Math.min(VMAX, y)] : null;
  }
  let dragging = false, downAt = null;
  heat.addEventListener('pointerdown', (ev) => {
    downAt = [ev.clientX, ev.clientY];
    if (ev.pointerType === 'mouse') { dragging = true; heat.setPointerCapture(ev.pointerId); const c = cellAt(ev); if (c) setPair(c[0], c[1]); }
  });
  heat.addEventListener('pointermove', (ev) => {
    const c = cellAt(ev);
    S.hover = c; if (dragging && c) setPair(c[0], c[1]); else schedule();
  });
  heat.addEventListener('pointerup', (ev) => {
    if (!dragging && downAt && Math.hypot(ev.clientX - downAt[0], ev.clientY - downAt[1]) < 8) { const c = cellAt(ev); if (c) setPair(c[0], c[1]); }
    dragging = false; downAt = null;
  });
  heat.addEventListener('pointercancel', () => { dragging = false; downAt = null; });
  heat.addEventListener('pointerleave', () => { S.hover = null; schedule(); });

  /* ---------- render loop (batched in one animation frame) ---------- */
  function render() {
    pending = false;
    const key = `${S.v1},${S.v2},${TRV.lang()}`;
    if (key !== built) {
      fresh();
      buildLedger(); readouts(); built = key;
    }
    markLedger();
    $('v1').value = $('v1Num').value = String(S.v1);
    $('v2').value = $('v2Num').value = String(S.v2);
    $('v1Dec').disabled = S.v1 <= 0; $('v1Inc').disabled = S.v1 >= VMAX;
    $('v2Dec').disabled = S.v2 <= 0; $('v2Inc').disabled = S.v2 >= VMAX;
    document.querySelectorAll('#nChips [data-n]').forEach((b) => b.setAttribute('aria-pressed', String(+b.dataset.n === S.N)));
    document.querySelectorAll('#presets [data-preset]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.preset === `${S.v1},${S.v2}`)));
    $('play').setAttribute('aria-pressed', String(S.playing));
    $('play').textContent = S.playing ? '❚❚' : '▶';
    drawHeat();
    frames++;
  }
  function schedule() { if (!pending) { pending = true; requestAnimationFrame(render); } }

  function setPair(v1, v2) {
    v1 = clampV(v1); v2 = clampV(v2);
    if (v1 === S.v1 && v2 === S.v2) { schedule(); return; }
    S.v1 = v1; S.v2 = v2;
    stop();
    S.pass = fresh().passes.length; // show the finished ledger; step back with ◀
    schedule();
  }
  const K = () => fresh().passes.length;
  function setPass(k) { S.pass = Math.max(0, Math.min(K(), k)); schedule(); }

  /* ---------- playback ---------- */
  let timer = null;
  function stop() { if (timer) clearInterval(timer); timer = null; S.playing = false; }
  function play() {
    if (!K()) return;
    if (S.pass >= K()) S.pass = 0;
    S.playing = true;
    timer = setInterval(() => {
      if (S.pass >= K()) {
        stop();
        TRV.toast($('toast'), L(`规范化完成：${K()} 次进位，带符号计数 <b>${fmtSigned(R.count)}</b> = c`, `Normalized after ${K()} carr${K() === 1 ? 'y' : 'ies'}: signed count <b>${fmtSigned(R.count)}</b> = c`));
        schedule();
        return;
      }
      S.pass++;
      schedule();
    }, TRV.reduceMotion ? 900 : 650);
    schedule();
  }

  /* ---------- controls ---------- */
  for (const k of ['v1', 'v2']) {
    $(k).addEventListener('input', (ev) => setPair(k === 'v1' ? ev.target.value : S.v1, k === 'v2' ? ev.target.value : S.v2));
    $(k + 'Num').addEventListener('change', (ev) => setPair(k === 'v1' ? ev.target.value : S.v1, k === 'v2' ? ev.target.value : S.v2));
    $(k + 'Num').addEventListener('keydown', (ev) => { if (ev.key === 'Enter') ev.target.blur(); });
    $(k + 'Dec').addEventListener('click', () => setPair(S.v1 - (k === 'v1'), S.v2 - (k === 'v2')));
    $(k + 'Inc').addEventListener('click', () => setPair(S.v1 + (k === 'v1'), S.v2 + (k === 'v2')));
  }
  document.querySelectorAll('#presets [data-preset]').forEach((b) => b.addEventListener('click', () => { const [a, c] = b.dataset.preset.split(',').map(Number); setPair(a, c); }));
  $('swap').addEventListener('click', () => setPair(S.v2, S.v1));
  $('random').addEventListener('click', () => setPair(Math.floor(rng() * (VMAX + 1)), Math.floor(rng() * (VMAX + 1))));
  document.querySelectorAll('#nChips [data-n]').forEach((b) => b.addEventListener('click', () => { S.N = +b.dataset.n; S.hover = null; schedule(); }));
  $('first').addEventListener('click', () => { stop(); setPass(0); });
  $('prev').addEventListener('click', () => { stop(); setPass(S.pass - 1); });
  $('next').addEventListener('click', () => { stop(); setPass(S.pass + 1); });
  $('last').addEventListener('click', () => { stop(); setPass(K()); });
  $('play').addEventListener('click', () => { if (S.playing) { stop(); schedule(); } else play(); });
  $('pass').addEventListener('input', (ev) => { stop(); setPass(+ev.target.value); });
  $('ledger').addEventListener('click', (ev) => { const row = ev.target.closest('.drow[data-pass]'); if (row) { stop(); setPass(+row.dataset.pass); } });
  $('tape').addEventListener('click', (ev) => { const t = ev.target.closest('i[data-pass]'); if (t) { stop(); setPass(+t.dataset.pass); } });
  document.addEventListener('keydown', (ev) => {
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    const t = ev.target;
    if (t && (t.closest('input, textarea, select, [contenteditable]') || !$('drawer').hidden)) return;
    if (ev.key === 'ArrowLeft') { stop(); setPass(S.pass - 1); ev.preventDefault(); }
    else if (ev.key === 'ArrowRight') { stop(); setPass(S.pass + 1); ev.preventDefault(); }
    else if (ev.key === 'Home') { stop(); setPass(0); ev.preventDefault(); }
    else if (ev.key === 'End') { stop(); setPass(K()); ev.preventDefault(); }
    else if (ev.key === ' ' && !(t && t.closest('button, a'))) { if (S.playing) { stop(); schedule(); } else play(); ev.preventDefault(); }
    else if (ev.key === 's' || ev.key === 'S') setPair(S.v2, S.v1);
    else if (ev.key === 'r' || ev.key === 'R') $('random').click();
  });
  TRV.drawer({ drawer: $('drawer'), open: $('infoBtn'), close: $('drawerClose') });
  TRV.startGlitch($('app'));
  TRV.onLang(() => { built = ''; schedule(); });
  window.addEventListener('resize', schedule);
  if ('ResizeObserver' in window) new ResizeObserver(schedule).observe(heat);

  /* ---------- start ---------- */
  S.pass = fresh().passes.length;
  schedule();

  /** Thumbnail cover (see drawCover), for the pair (17, 17): nine carries, signed count +1. */
  window.TRV_THUMB = () => new Promise((resolve) => {
    S.v1 = 17; S.v2 = 17; S.pass = fresh().passes.length; built = '';
    schedule();
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  });

  /** Read-only probe for the browser tests (tests/golden-carry.test.mjs). */
  window.GC_DEBUG = {
    frames: () => frames,
    pending: () => pending,
    state: () => ({ v1: S.v1, v2: S.v2, N: S.N, pass: S.pass, passes: K(), playing: S.playing }),
    info: () => {
      fresh();
      return {
        v1: S.v1, v2: S.v2, c: R.c.a, cPhi: R.c.b, count: R.count, beta1: [R.b1.a, R.b1.b], beta2: [R.b2.a, R.b2.b], beta3: [R.b3.a, R.b3.b],
        z1: R.z1.slice(), z2: R.z2.slice(), z3: R.z3.slice(), raw: R.raw.slice(), final: R.final.slice(), canonicalOk: R.canonicalOk,
        passes: R.passes.map((p) => ({ rule: p.rule, at: p.at, sign: p.sign, digits: p.digits.slice() }))
      };
    },
    /** c over 0 … N × 0 … N as a string of '0' | '1' | '2' (c + 1), index v2 · (N + 1) + v1. */
    grid: (n = S.N) => { let out = ''; for (let y = 0; y <= n; y++) for (let x = 0; x <= n; x++) out += String(cOf(x, y) + 1); return out; },
    /** Viewport coordinates of the centre of cell (v1, v2) of the deficit map (for simulated clicks). */
    cellPoint: (v1, v2) => {
      if (!geom) return null;
      const r = heat.getBoundingClientRect(), d = geom.dpr;
      return { x: r.left + (geom.ox + (v1 + 0.5) * geom.s) / d, y: r.top + (geom.oy + (geom.ny - 1 - v2 + 0.5) * geom.s) / d };
    },
    set: (v1, v2) => setPair(v1, v2),
    setN: (n) => { if (NS.includes(n)) { S.N = n; schedule(); } }
  };
})();
