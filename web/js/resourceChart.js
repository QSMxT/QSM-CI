// Per-run resource-usage graph (extracted from viewer.js).
// Fetch this run's memory/CPU-over-time trace (resources.json) and draw it as a two-axis uPlot:
// memory in GB on the left, CPU in cores on the right (a subtle reference line at 1 core makes
// multi-core use obvious). Served from the Hugging Face Hub (run.resources_url) with a dev fallback
// to results/<id>/resources.json, the same pattern volUrl() uses for the NIfTI volumes. A missing
// trace (404) just leaves the panel hidden; a DNF run has no trace.
//
// ES module: imported by viewer.js. Depends on the global `uPlot` (loaded as an IIFE <script> before
// viewer.js) and the DOM; the current run is passed in via `renderResources(run)`.

let resChart = null;         // the uPlot instance (destroyed + rebuilt per run)
let wired = false;           // guard so the window resize listener is added only once

function resourcesUrl(run) {
  return (run && run.resources_url) || `results/${run.id}/resources.json`;
}

export async function renderResources(run) {
  const panel = document.getElementById("resources-panel");
  const host = document.getElementById("resources-chart");
  if (!panel || !host) return;
  const hidePanel = () => { panel.classList.add("hidden"); };
  if (resChart) { resChart.destroy(); resChart = null; }
  host.innerHTML = "";
  if (!run || run.status === "DNF") { hidePanel(); return; }

  let data;
  try {
    const res = await fetch(resourcesUrl(run), { cache: "no-store" });
    if (!res.ok) { hidePanel(); return; }        // 404 / no trace for this run
    data = await res.json();
  } catch (e) { hidePanel(); return; }
  const t = data.t || [], memB = data.mem_bytes || [], cpu = data.cpu_cores || [];
  if (!t.length) { hidePanel(); return; }

  const memGB = memB.map((b) => b / 1e9);
  const dark = document.documentElement.classList.contains("dark");
  const gridStroke = dark ? "rgba(148,163,184,0.15)" : "rgba(100,116,139,0.15)";
  const axisStroke = dark ? "#94a3b8" : "#64748b";
  const MEM_COLOR = "#6366f1", CPU_COLOR = "#10b981";

  const fmtT = (v) => `${v}s`;
  // Adaptive GB precision: a near-constant ~0.16 GB trace needs decimals; a 12 GB one doesn't.
  const fmtGB = (v) => { const a = Math.abs(v); const d = a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3; return `${v.toFixed(d)} GB`; };
  // Human-readable stage label, e.g. "bfr:pdf" -> "Background removal · pdf".
  const stageLabel = (name) => {
    const [kind, algo] = String(name || "").split(":");
    const KMAP = { field_mapping: "Field mapping", "field-mapping": "Field mapping",
                   unwrap: "Unwrapping", bfr: "Background removal", dipole: "Dipole inversion" };
    const k = KMAP[kind] || (kind || "stage");
    return algo ? `${k} · ${algo}` : k;
  };
  // Two y-scales: "mem" (GB, left) and "cpu" (cores, right). uPlot maps each series to its scale.
  const opts = {
    width: host.clientWidth || 640,
    height: 260,
    cursor: { drag: { x: true, y: false } },
    scales: { x: { time: false }, cpu: { range: (u, min, max) => [0, Math.max(1.1, max * 1.1)] } },
    series: [
      { label: "t", value: (u, v) => (v == null ? "" : `${v}s`) },
      { label: "Memory", scale: "mem", stroke: MEM_COLOR, width: 2, fill: dark ? "rgba(99,102,241,0.12)" : "rgba(99,102,241,0.08)",
        value: (u, v) => (v == null ? "" : fmtGB(v)) },
      { label: "CPU", scale: "cpu", stroke: CPU_COLOR, width: 2,
        value: (u, v) => (v == null ? "" : `${v.toFixed(2)} cores`) },
    ],
    axes: [
      { stroke: axisStroke, grid: { stroke: gridStroke, width: 1 }, ticks: { stroke: gridStroke }, values: (u, vals) => vals.map(fmtT) },
      { scale: "mem", stroke: MEM_COLOR, size: 64, grid: { stroke: gridStroke, width: 1 }, ticks: { stroke: gridStroke },
        values: (u, vals) => vals.map(fmtGB) },
      { scale: "cpu", side: 1, stroke: CPU_COLOR, grid: { show: false },
        values: (u, vals) => vals.map((v) => `${v}`) },
    ],
    // Reference line at 1 core: anything above it means the method used more than one core.
    hooks: {
      // Composed runs concatenate their stages' traces. Shade each stage's time span with a
      // subtle alternating band (drawn behind the series) so the segments are visible at a glance.
      drawClear: [(u) => {
        const stages = Array.isArray(data.stages) ? data.stages : [];
        if (stages.length < 2) return;
        const ctx = u.ctx; ctx.save();
        const bands = dark
          ? ["rgba(148,163,184,0.00)", "rgba(148,163,184,0.10)"]
          : ["rgba(100,116,139,0.00)", "rgba(100,116,139,0.07)"];
        for (let i = 0; i < stages.length; i++) {
          const x0 = u.valToPos(stages[i].t_start, "x", true);
          const x1 = u.valToPos(stages[i].t_end, "x", true);
          if (!isFinite(x0) || !isFinite(x1)) continue;
          ctx.fillStyle = bands[i % 2];
          ctx.fillRect(x0, u.bbox.top, Math.max(0, x1 - x0), u.bbox.height);
        }
        ctx.restore();
      }],
      draw: [(u) => {
        const ctx = u.ctx;
        const stages = Array.isArray(data.stages) ? data.stages : [];
        if (stages.length > 1) {
          // Boundary lines at each stage transition.
          ctx.save();
          ctx.strokeStyle = axisStroke; ctx.globalAlpha = 0.30; ctx.setLineDash([2, 3]);
          for (let i = 1; i < stages.length; i++) {
            const x = u.valToPos(stages[i].t_start, "x", true);
            if (!isFinite(x)) continue;
            ctx.beginPath(); ctx.moveTo(x, u.bbox.top); ctx.lineTo(x, u.bbox.top + u.bbox.height); ctx.stroke();
          }
          ctx.restore();
          // Stage name labels (with a legibility pill) centered in each band; skipped if too narrow.
          ctx.save();
          ctx.font = "600 11px ui-sans-serif, system-ui, sans-serif";
          ctx.textBaseline = "top"; ctx.setLineDash([]);
          for (let i = 0; i < stages.length; i++) {
            const x0 = u.valToPos(stages[i].t_start, "x", true);
            const x1 = u.valToPos(stages[i].t_end, "x", true);
            if (!isFinite(x0) || !isFinite(x1)) continue;
            const label = stageLabel(stages[i].name);
            const w = ctx.measureText(label).width;
            if ((x1 - x0) < w + 14) continue;
            const tx = (x0 + x1) / 2 - w / 2, ty = u.bbox.top + 6;
            ctx.globalAlpha = 1;
            ctx.fillStyle = dark ? "rgba(15,23,42,0.78)" : "rgba(255,255,255,0.82)";
            ctx.fillRect(tx - 5, ty - 2, w + 10, 16);
            ctx.fillStyle = axisStroke; ctx.fillText(label, tx, ty);
          }
          ctx.restore();
        }
        // Reference line at 1 core.
        const y = u.valToPos(1, "cpu", true);
        if (!isFinite(y)) return;
        ctx.save();
        ctx.strokeStyle = CPU_COLOR; ctx.globalAlpha = 0.35; ctx.setLineDash([4, 4]);
        ctx.beginPath(); ctx.moveTo(u.bbox.left, y); ctx.lineTo(u.bbox.left + u.bbox.width, y); ctx.stroke();
        ctx.restore();
      }],
    },
  };
  panel.classList.remove("hidden");           // unhide before construct so clientWidth is real
  resChart = new uPlot(opts, [t, memGB, cpu], host);

  // Keep the chart width in sync with the panel (resize + a one-shot after layout settles).
  const fit = () => { if (resChart) resChart.setSize({ width: host.clientWidth || 640, height: 260 }); };
  requestAnimationFrame(fit);
  if (!wired) { window.addEventListener("resize", () => { if (resChart) fit(); }); wired = true; }

  const peakGB = (data.mem_peak_bytes ? data.mem_peak_bytes / 1e9 : Math.max(...memGB)).toFixed(2);
  const maxCores = (data.cpu_cores_max != null ? data.cpu_cores_max : Math.max(...cpu)).toFixed(2);
  const sub = document.getElementById("resources-sub");
  if (sub) sub.textContent = `Peak memory ${peakGB} GB · up to ${maxCores} CPU cores · sampled every ${data.interval_s || 1}s during the container run.`;
}
