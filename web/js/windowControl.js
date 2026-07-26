// Dual-range intensity windowing widget (extracted from viewer.js).
// A self-contained control: label, typed lo/hi bounds, Auto, a dual-range slider and an intensity
// histogram drawn behind it. `getVol` returns the NiiVue volume it drives, so the same widget serves
// both the base map and the error overlay. Instances live in `winControls` so a theme toggle or
// resize can repaint every histogram at once. cal_min/cal_max are the source of truth; typed bounds
// may fall outside [global_min, global_max] (the slider thumb clamps, the volume doesn't).
//
// ES module: imported by viewer.js (itself a <script type="module">). Depends only on the DOM and the
// NiiVue instance passed in via `getNv`; no globals beyond `document`/`window`.

// Every live control, so callers can repaint all histograms at once (resize / theme toggle).
export const winControls = [];

const autoWin = (vol) => { vol.cal_min = vol.robust_min ?? vol.global_min; vol.cal_max = vol.robust_max ?? vol.global_max; };
const fmtWin = (v) => (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 1 ? v.toFixed(2) : v.toPrecision(2));
const fmtNum = (v) => String(+Number(v).toPrecision(4));

// `getNv` returns the shared NiiVue instance (created lazily by viewer.js, so it must be read at call
// time, not captured once). `getVol` returns the volume this widget windows.
export function makeWindowControl(getNv, getVol, cmapCfg) {
  const el = document.createElement("div");
  el.innerHTML = `
    <div class="flex items-center gap-2">
      <div class="dualrange flex-1" title="Scroll to zoom the range · drag to pan when zoomed · double-click to reset">
        <canvas class="hist"></canvas>
        <div class="track"></div><div class="fill"></div>
        <input class="rng-lo" type="range" /><input class="rng-hi" type="range" />
        <span class="win-bubble bub-lo" contenteditable="true" inputmode="decimal" spellcheck="false" title="Click to edit this bound"></span>
        <span class="win-bubble bub-hi" contenteditable="true" inputmode="decimal" spellcheck="false" title="Click to edit this bound"></span>
      </div>
      <div class="flex w-28 shrink-0 flex-col gap-1.5">
        <select class="cmap-sel hidden w-full !py-1 !pl-2 !pr-6 text-[11px] leading-tight" title="Colormap"></select>
        <button class="btn-auto w-full rounded-lg bg-white px-2.5 py-1 text-xs font-medium text-gray-700 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-200 dark:ring-gray-700" title="Reset to an automatic window">Auto</button>
      </div>
    </div>
    <div class="zoom-hint mt-0.5 text-[10px] text-gray-400 dark:text-gray-500"></div>`;
  const q = (s) => el.querySelector(s);
  const rngLo = q(".rng-lo"), rngHi = q(".rng-hi"),
    fill = q(".fill"), bubLo = q(".bub-lo"), bubHi = q(".bub-hi"), canvas = q(".hist"),
    dr = q(".dualrange"), hintEl = q(".zoom-hint"), cmapSel = q(".cmap-sel");
  // Optional compact colormap dropdown sits above the Auto button. Fixed-width so a long selection
  // (e.g. "Diverging (red ↔ blue)") truncates rather than widening the control; the native option list
  // still shows each label in full.
  if (cmapCfg) {
    cmapSel.classList.remove("hidden");
    cmapSel.innerHTML = cmapCfg.options.map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
    cmapSel.value = cmapCfg.value;
    cmapSel.addEventListener("change", () => cmapCfg.onChange(cmapSel.value));
  }
  // magnitude=true windows on |value| over [0, maxAbs] — used for the signed error map under a diverging
  // colormap, where cal_min/cal_max act as a magnitude transparency floor + saturation (mirrored to negatives).
  // [dmin,dmax] is the full data range; [vmin,vmax] is the zoomed *view* the slider+histogram span, so
  // scrolling to a narrow view makes each pixel of drag fine. cal_min/cal_max stay the source of truth.
  let dmin = 0, dmax = 1, vmin = 0, vmax = 1, winLo = 0, winHi = 1, hist = null, magnitude = false;
  let pan = null, panRAF = 0;   // active drag-to-pan state (of the zoomed view) + its rAF handle
  const clampV = (x) => Math.min(vmax, Math.max(vmin, x));  // into the zoom view; thumbs pin, cal_* stay exact
  const pct = (x) => (vmax === vmin ? 0 : ((clampV(x) - vmin) / (vmax - vmin)) * 100);

  // Read the volume's current window + data range, reset the zoom to the full range, and sync the UI.
  // Open the histogram zoomed so the window [winLo, winHi] spans ~half the visible range (context on
  // both sides) rather than a sliver of the full data range. Preserves the view width when clamped to
  // the data bounds; leaves the full range when the window is degenerate or already fills it.
  function frameWindow() {
    const W = winHi - winLo;
    if (!(W > 0) || !(dmax > dmin)) { vmin = dmin; vmax = dmax; return; }
    const span = Math.min(dmax - dmin, W * 2);           // window ≈ 50% of the view
    const c = (winLo + winHi) / 2;
    let nmin = c - span / 2, nmax = c + span / 2;
    if (nmin < dmin) { nmin = dmin; nmax = dmin + span; }
    if (nmax > dmax) { nmax = dmax; nmin = dmax - span; }
    vmin = Math.max(dmin, nmin); vmax = Math.min(dmax, nmax);
  }
  function setup() {
    const v = getVol(); if (!v) return;
    if (magnitude) { dmin = 0; dmax = Math.max(Math.abs(v.global_min), Math.abs(v.global_max)) || 1; }
    else { dmin = v.global_min; dmax = v.global_max; }
    winLo = v.cal_min; winHi = v.cal_max;
    frameWindow();   // zoom the initial view so the window takes up ~half the histogram
    applyView();
  }
  // Re-point the slider + histogram at the current zoom view [vmin,vmax] and reposition the window.
  function applyView() {
    const step = (vmax - vmin) / 1000 || 1e-6;
    for (const r of [rngLo, rngHi]) { r.min = vmin; r.max = vmax; r.step = step; }
    const zoomed = vmax - vmin < (dmax - dmin) * 0.999;
    hintEl.textContent = zoomed
      ? `zoomed to ${fmtWin(vmin)} – ${fmtWin(vmax)} · drag to pan · double-click to reset`
      : "scroll over the bar to zoom in for finer control";
    dr.style.cursor = pan ? "grabbing" : zoomed ? "grab" : "";  // affordance: grab when there's room to pan
    buildHistogram(getVol());
    apply(winLo, winHi);
  }
  // Zoom the view by `factor` about the value under `frac` (0..1 across the bar), clamped to the data.
  function zoom(factor, frac) {
    const full = dmax - dmin || 1;
    const span = Math.min(full, Math.max(full / 5000, (vmax - vmin) * factor));
    const center = vmin + frac * (vmax - vmin);
    let nmin = center - frac * span, nmax = nmin + span;
    if (nmin < dmin) { nmin = dmin; nmax = dmin + span; }
    if (nmax > dmax) { nmax = dmax; nmin = dmax - span; }
    vmin = nmin; vmax = nmax;
    applyView();
  }
  function apply(lo, hi) {
    if (!isFinite(lo)) lo = dmin;
    if (!isFinite(hi)) hi = dmax;
    if (lo > hi) [lo, hi] = [hi, lo];
    if (magnitude) { lo = Math.max(0, lo); hi = Math.max(0, hi); }  // magnitudes only
    winLo = lo; winHi = hi;
    const nv = getNv();
    const v = getVol(); if (v) { v.cal_min = lo; v.cal_max = hi; nv.updateGLVolume(); }
    rngLo.value = clampV(lo); rngHi.value = clampV(hi);
    fill.style.left = pct(lo) + "%"; fill.style.width = (pct(hi) - pct(lo)) + "%";
    if (document.activeElement !== bubLo) bubLo.textContent = fmtWin(lo);  // don't clobber a bubble mid-edit
    if (document.activeElement !== bubHi) bubHi.textContent = fmtWin(hi);
    positionBubbles();
    draw();
  }
  // Place the two value bubbles at their thumbs, but when they'd overlap nudge them apart symmetrically
  // (clamped to the bar edges) so both stay readable when the bounds are close together.
  function positionBubbles() {
    const bw = dr.clientWidth || 1;
    let cLo = (pct(winLo) / 100) * bw, cHi = (pct(winHi) / 100) * bw;
    const wLo = bubLo.offsetWidth, wHi = bubHi.offsetWidth, minSep = wLo / 2 + wHi / 2 + 4;
    if (cHi - cLo < minSep) {
      const mid = (cLo + cHi) / 2;
      cLo = mid - minSep / 2; cHi = mid + minSep / 2;
      if (cLo < wLo / 2) { cLo = wLo / 2; cHi = cLo + minSep; }
      if (cHi > bw - wHi / 2) { cHi = bw - wHi / 2; cLo = cHi - minSep; }
    }
    bubLo.style.left = cLo + "px"; bubHi.style.left = cHi + "px";
  }
  // Intensity histogram over the current zoom view. Exact-zero voxels are skipped (the masked background
  // dominates otherwise) and counts are log-scaled so the tissue distribution stays visible next to the mode.
  function buildHistogram(v) {
    hist = null;
    const img = v && v.img;
    if (img && img.length && vmax > vmin) {
      const slope = v.hdr?.scl_slope || 1, inter = v.hdr?.scl_inter || 0;
      const NB = 128, counts = new Float64Array(NB);
      const stride = Math.max(1, Math.floor(img.length / 400000));  // sample large volumes
      for (let i = 0; i < img.length; i += stride) {
        let x = img[i] * slope + inter;
        if (magnitude) x = Math.abs(x);
        if (!isFinite(x) || x === 0 || x < vmin || x > vmax) continue;  // only voxels in the zoom view
        counts[Math.min(NB - 1, Math.max(0, Math.floor(((x - vmin) / (vmax - vmin)) * NB)))]++;
      }
      let max = 0;
      for (let b = 0; b < NB; b++) { counts[b] = Math.log1p(counts[b]); if (counts[b] > max) max = counts[b]; }
      if (max > 0) { for (let b = 0; b < NB; b++) counts[b] /= max; hist = counts; }
    }
    draw();
  }
  function draw() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!hist) return;
    const dark = document.documentElement.classList.contains("dark");
    const px = (x) => ((x - vmin) / (vmax - vmin || 1)) * w;
    const loX = px(winLo), hiX = px(winHi);
    const NB = hist.length, bw = w / NB;
    for (let b = 0; b < NB; b++) {
      const bh = hist[b] * (h - 1);
      if (!bh) continue;
      const x = b * bw, mid = x + bw / 2;
      ctx.fillStyle = mid >= loX && mid <= hiX ? (dark ? "#818cf8" : "#6366f1") : (dark ? "#4b5563" : "#d1d5db");
      ctx.fillRect(x + 0.5, h - bh, Math.max(bw - 1, 0.75), bh);
    }
  }
  // Slider drag moves only the dragged bound, so a typed out-of-range bound on the other side survives.
  const onRange = (e) => {
    const x = parseFloat(e.target.value);
    const [lo, hi] = e.target === rngLo ? [x, winHi] : [winLo, x];
    apply(Math.min(lo, hi), Math.max(lo, hi));
  };
  rngLo.addEventListener("input", onRange);
  rngHi.addEventListener("input", onRange);
  // The value bubbles are editable: click to type an exact bound (out-of-range allowed). On focus show the
  // full-precision value and select it; Enter/blur commits, Escape reverts.
  const bubVal = (b) => (b === bubLo ? winLo : winHi);
  for (const b of [bubLo, bubHi]) {
    b.addEventListener("focus", () => {
      b.textContent = fmtNum(bubVal(b));
      const r = document.createRange(); r.selectNodeContents(b);
      const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
    });
    b.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); b.blur(); }
      else if (e.key === "Escape") { e.preventDefault(); b.textContent = fmtWin(bubVal(b)); b.blur(); }
    });
    b.addEventListener("blur", () => {
      const v = parseFloat(b.textContent);
      apply(b === bubLo ? v : winLo, b === bubHi ? v : winHi);  // apply() handles NaN + lo/hi order
    });
  }
  q(".btn-auto").addEventListener("click", () => { const v = getVol(); if (!v) return; autoWin(v); apply(v.cal_min, v.cal_max); });
  // Scroll to zoom the view about the cursor (finer control in a narrow range); double-click resets.
  dr.addEventListener("wheel", (e) => {
    if (!getVol()) return;
    e.preventDefault();
    const rect = dr.getBoundingClientRect();
    const frac = rect.width ? Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)) : 0.5;
    zoom(e.deltaY < 0 ? 0.8 : 1.25, frac);
  }, { passive: false });
  dr.addEventListener("dblclick", () => { if (!getVol()) return; vmin = dmin; vmax = dmax; applyView(); });
  // Drag across the bar to pan the zoomed-in view (scroll zooms; this slides the [vmin,vmax] window
  // left/right). Ignores drags that begin on a slider thumb or a value bubble — those keep their own
  // behaviour — and does nothing until the view is actually zoomed in. rAF-coalesced so a fast drag
  // repaints the histogram at most once per frame.
  const onThumbOrBubble = (t) => t === rngLo || t === rngHi || !!(t.closest && t.closest(".win-bubble"));
  dr.addEventListener("pointerdown", (e) => {
    if (!getVol() || onThumbOrBubble(e.target)) return;
    if (vmax - vmin >= (dmax - dmin) * 0.999) return;   // not zoomed — nothing to pan
    pan = { x0: e.clientX, x1: e.clientX, vmin0: vmin, vmax0: vmax, w: dr.getBoundingClientRect().width || 1 };
    dr.setPointerCapture(e.pointerId); dr.style.cursor = "grabbing"; e.preventDefault();
  });
  dr.addEventListener("pointermove", (e) => {
    if (!pan) return;
    pan.x1 = e.clientX;
    if (panRAF) return;
    panRAF = requestAnimationFrame(() => {
      panRAF = 0; if (!pan) return;
      const span = pan.vmax0 - pan.vmin0, dx = ((pan.x1 - pan.x0) / pan.w) * span;  // drag right → view moves left
      let nmin = pan.vmin0 - dx, nmax = pan.vmax0 - dx;
      if (nmin < dmin) { nmin = dmin; nmax = dmin + span; }
      if (nmax > dmax) { nmax = dmax; nmin = dmax - span; }
      vmin = nmin; vmax = nmax; applyView();
    });
  });
  const endPan = (e) => {
    if (!pan) return;
    pan = null; if (panRAF) { cancelAnimationFrame(panRAF); panRAF = 0; }
    applyView();  // restores the idle grab/none cursor
    try { dr.releasePointerCapture(e.pointerId); } catch (_) { /* pointer already released */ }
  };
  dr.addEventListener("pointerup", endPan);
  dr.addEventListener("pointercancel", endPan);

  const ctl = { el, setup, redraw: () => { draw(); positionBubbles(); }, setMagnitude: (on) => { magnitude = on; }, cmapSelect: cmapSel };
  winControls.push(ctl);
  return ctl;
}
