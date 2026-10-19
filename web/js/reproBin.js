// Readers for the harmonization payloads' binary columns (written by scripts/repro_format.py, which
// documents the layout): a small JSON index carries a descriptor
//   { dtype: "<f4", shape, decimals: {field: dp}, files: [{ file, fields, bytes, sha256 }] }
// and each file holds one C-order little-endian float32 block of `shape` per field, NaN = no value.
// The stored values are rounded decimals, so they are rounded back here: a value then equals the
// double the old JSON payload parsed to, bit for bit, and every table and figure renders as before.
// Pure functions (no DOM) so tests/test_web_repro_bin.py can run them under node; app.js does the
// fetching and memoising.

// The files of `desc` that hold any of `fields` (all files when fields is omitted).
function reproBinFiles(desc, fields) {
  return (desc?.files || []).filter((f) => !fields || f.fields.some((x) => fields.includes(x)));
}

// { field: Float64Array } from { file name: ArrayBuffer }. Throws when a buffer does not match its
// descriptor, which is what a stale or truncated .bin next to a newer index looks like.
function reproDecodeColumns(desc, buffers, fields) {
  if (desc.dtype !== "<f4") throw new Error(`unsupported dtype ${desc.dtype}`);
  const n = desc.shape.reduce((a, d) => a * d, 1), out = {};
  const le = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;
  for (const f of reproBinFiles(desc, fields)) {
    const buf = buffers[f.file];
    if (!buf || buf.byteLength !== f.bytes || f.bytes !== 4 * n * f.fields.length)
      throw new Error(`${f.file}: ${buf ? buf.byteLength : 0} bytes, the index expects ${f.bytes}`);
    const view = new DataView(buf);
    f.fields.forEach((field, k) => {
      if (fields && !fields.includes(field)) return;
      const d = typeof desc.decimals === "object" ? desc.decimals?.[field] : desc.decimals;
      const src = le ? new Float32Array(buf, 4 * n * k, n) : null, col = new Float64Array(n);
      if (d == null) for (let i = 0; i < n; i++) col[i] = src ? src[i] : view.getFloat32(4 * (n * k + i), true);
      else {
        const s = 10 ** d;
        for (let i = 0; i < n; i++) col[i] = Math.round((src ? src[i] : view.getFloat32(4 * (n * k + i), true)) * s) / s;
      }
      out[field] = col;
    });
  }
  return out;
}

// The pipeline payload the pages read, from results/repro.json + the decoded fit columns (or none:
// the submission page needs only the per-pipeline summary). Shape:
//   { targets, acquisitions, comparisons, exclusion_rules,
//     pairs: [{class, group, key, a, b}], nPairs,
//     pipelines: { id: { row, <summary fields>, rejected: [{class, group, pair, why, …}] } },
//     fits: { slope, ba_bias_ppm, abs_slope_dev } }   // Float64Array [row * nPairs + pair], NaN = no fit
// `row` indexes the fit columns; dropping a pipeline from `pipelines` leaves the columns untouched.
function reproFromIndex(index, cols) {
  const pairs = index.pairs || [], nPairs = pairs.length, summary = index.summary || {}, rej = index.rejected || {};
  const pipelines = {};
  (index.pipelines || []).forEach((id, row) => {
    const node = { row };
    for (const [f, vals] of Object.entries(summary)) node[f] = vals[row];
    node.rejected = (rej[id] || []).map(({ pair, ...r }) =>
      ({ class: pairs[pair].class, group: pairs[pair].group, pair: pairs[pair].key, ...r }));
    pipelines[id] = node;
  });
  const out = { targets: index.targets, acquisitions: index.acquisitions, comparisons: index.comparisons,
                exclusion_rules: index.exclusion_rules, pairs, nPairs, pipelines };
  if (cols) {
    // |a−1| is not stored: it is the slope's distance from 1, to the slope's own 4 decimals.
    const s = cols.slope, abs = new Float64Array(s.length);
    for (let i = 0; i < s.length; i++) abs[i] = Math.round(Math.abs(s[i] - 1) * 1e4) / 1e4;
    out.fits = { ...cols, abs_slope_dev: abs };
  }
  return out;
}

// The regional payload from results/repro_regions.json + its decoded grid:
//   { targets, acquisitions, structures, si: {structure: index}, nRuns,
//     runs: { pipeline: { acq: Float64Array(structures) } } }   // only runs with any value; NaN = none
// Each run is a view onto one grid row, so indexing it costs no copy.
function reproRegionsFromIndex(index, cols) {
  const S = index.structures || [], A = index.acqs || [], ns = S.length, v = cols.chi_ppb, runs = {};
  let nRuns = 0;
  (index.pipelines || []).forEach((p, i) => {
    A.forEach((a, j) => {
      const base = (i * A.length + j) * ns;
      for (let k = 0; k < ns; k++) if (v[base + k] === v[base + k]) {
        (runs[p] ||= {})[a] = v.subarray(base, base + ns);
        nRuns++;
        break;
      }
    });
  });
  return { targets: index.targets, acquisitions: index.acquisitions, structures: S,
           si: Object.fromEntries(S.map((s, k) => [s, k])), runs, nRuns };
}

if (typeof module === "object" && module.exports)
  module.exports = { reproBinFiles, reproDecodeColumns, reproFromIndex, reproRegionsFromIndex };
