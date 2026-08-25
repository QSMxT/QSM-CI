#!/usr/bin/env python3
"""qsm-eval — the QSM-CI scorer.

Loads a reconstruction and the (held-out) ground truth, computes the challenge metrics, and writes
`metrics.json` (plus an optional center-slice figure). This is the *only* place ground truth is
read, keeping it out of submitters' containers.

The metrics are a faithful port of the QSM.rs reference implementation
(`tests/common/mod.rs` in https://github.com/astewartau/QSM.rs). `test_metrics.py` and the
`--selfcheck` mode guard against drift. Keep the two in sync when either changes.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation, gaussian_laplace, uniform_filter

# --- core metrics (ported 1:1 from QSM.rs tests/common/mod.rs) ----------------------------------


def linear_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Least-squares fit y = slope*x + intercept. Matches QSM.rs `linear_fit`."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    n = x.size
    sum_x, sum_y = x.sum(), y.sum()
    denom = n * (x * x).sum() - sum_x * sum_x
    if abs(denom) < 1e-30:
        return 0.0, 0.0
    slope = (n * (x * y).sum() - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return float(slope), float(intercept)


def correlation(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    """Pearson correlation within the mask."""
    m = mask > 0
    if not m.any():
        return 0.0
    av, bv = a[m], b[m]
    n = av.size
    num = n * (av * bv).sum() - av.sum() * bv.sum()
    den = math.sqrt((n * (av * av).sum() - av.sum() ** 2) * (n * (bv * bv).sum() - bv.sum() ** 2))
    return float(num / den) if den != 0.0 else 0.0


def xsim(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    """XSIM (SSIM optimized for QSM), 5x5x5 uniform windows. L=1, K1=0.01, K2=0.001.

    Vectorized with truncated boundary windows (out-of-bounds treated as absent), matching the
    per-voxel variable-count neighborhood of the QSM.rs implementation.
    """
    c1, c2, k = 1e-4, 1e-6, 5

    def wsum(x):  # in-bounds neighborhood sum over a 5x5x5 window
        return uniform_filter(x, size=k, mode="constant", cval=0.0) * (k ** 3)

    a = a.astype(float)
    b = b.astype(float)
    cnt = wsum(np.ones_like(a))
    cnt[cnt == 0] = 1.0
    mu_a, mu_b = wsum(a) / cnt, wsum(b) / cnt
    var_a = wsum(a * a) / cnt - mu_a * mu_a
    var_b = wsum(b * b) / cnt - mu_b * mu_b
    cov = wsum(a * b) / cnt - mu_a * mu_b

    num = (2.0 * mu_a * mu_b + c1) * (2.0 * cov + c2)
    den = (mu_a * mu_a + mu_b * mu_b + c1) * (var_a + var_b + c2)
    valid = (mask > 0) & (den > 0.0)
    if not valid.any():
        return 0.0
    return float(np.mean(num[valid] / den[valid]))


def nrmse_challenge(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> tuple[float, float]:
    """Demeaned NRMSE (%) and linearly-detrended NRMSE (%) within the mask."""
    m = mask > 0
    if not m.any():
        return math.nan, math.nan
    recon = a[m] - a[m].mean()
    truth = b[m] - b[m].mean()
    norm_truth = math.sqrt((truth * truth).sum())
    if norm_truth < 1e-30:
        return math.nan, math.nan
    nrmse = 100.0 * math.sqrt(((recon - truth) ** 2).sum()) / norm_truth

    slope, intercept = linear_fit(truth, recon)
    if abs(slope) < 1e-30:
        return nrmse, nrmse
    corrected = (1.0 / slope) * recon + (-intercept / slope)
    nrmse_dt = 100.0 * math.sqrt(((corrected - truth) ** 2).sum()) / norm_truth
    return nrmse, nrmse_dt


def hfen(recon: np.ndarray, truth: np.ndarray, mask: np.ndarray, sigma: float = 1.5) -> float:
    """High-Frequency Error Norm (%): norm of the LoG-filtered error over the norm of the LoG-filtered
    truth, within the mask, ×100. This is the classic 2016 QSM Reconstruction Challenge HFEN — a
    Laplacian-of-Gaussian (σ≈1.5 voxels, 15-voxel kernel) high-pass that measures how well fine
    edges/detail are recovered, complementing the global NRMSE. Lower is better; identical inputs → 0.

    scipy's `gaussian_laplace` gives the LoG directly (a Gaussian-smoothed Laplacian); a truncate of 5
    at σ=1.5 spans ~15 voxels, matching the reference kernel size. The filter is applied over the whole
    volume (edges need neighbourhood context) but the norms are taken only within the mask."""
    m = mask > 0
    if not m.any():
        return math.nan
    lr = gaussian_laplace(recon.astype(np.float64), sigma=sigma, truncate=5.0)
    lt = gaussian_laplace(truth.astype(np.float64), sigma=sigma, truncate=5.0)
    err = lr[m] - lt[m]
    denom = math.sqrt(float((lt[m] * lt[m]).sum()))
    if denom < 1e-30:
        return math.nan
    val = 100.0 * math.sqrt(float((err * err).sum())) / denom
    return val if math.isfinite(val) else math.nan


def dgm_linearity(recon: np.ndarray, truth: np.ndarray, seg: np.ndarray) -> float:
    """|1 - slope| of mean susceptibility across the 6 DGM regions (labels 1-6)."""
    tmeans, rmeans = [], []
    for label in range(1, 7):
        sel = seg == label
        if sel.any():
            tmeans.append(truth[sel].mean())
            rmeans.append(recon[sel].mean())
    if len(tmeans) < 2:
        return math.nan
    slope, _ = linear_fit(np.array(tmeans), np.array(rmeans))
    return abs(1.0 - slope)


def dilate_mask_3d(mask: np.ndarray) -> np.ndarray:
    """26-connected binary dilation with a 3x3x3 cube (matches QSM.rs `dilate_mask_3d`)."""
    return binary_dilation(mask > 0, structure=np.ones((3, 3, 3), bool)).astype(np.uint8)


def _box(shape, xr, yr, zr):
    m = np.zeros(shape, bool)
    m[xr[0]:xr[1], yr[0]:yr[1], zr[0]:zr[1]] = True
    return m


def calcification_metrics(recon, truth, seg) -> tuple[float, float]:
    """(moment deviation, streak artifact level) around the calcification (label 16)."""
    calc = seg == 16
    if not calc.any():
        return math.nan, math.nan
    gt_vals = truth[calc]
    gt_moment = gt_vals.size * gt_vals.mean()

    xs, ys, zs = np.where(calc)
    nx, ny, nz = seg.shape
    x_min, x_max = int(xs.min()), int(xs.max())
    y_min, y_max = int(ys.min()), int(ys.max())
    z_min, z_max = int(zs.min()), int(zs.max())

    n1 = 3
    cube_x = (max(x_min - n1, 0), min(x_max + n1 + 1, nx))
    cube_y = (max(y_min - n1, 0), min(y_max + n1 + 1, ny))
    cube_z = (max(z_min - n1, 0), min(z_max + n1 + 1, nz))
    n2 = 4
    rim_x = (max(cube_x[0] - n2, 0), min(cube_x[1] + n2, nx))
    rim_y = (max(cube_y[0] - n2, 0), min(cube_y[1] + n2, ny))
    rim_z = (max(cube_z[0] - n2, 0), min(cube_z[1] + n2, nz))
    n3 = 4
    outer_x = (max(rim_x[0] - n3, 0), min(rim_x[1] + n3, nx))
    outer_y = (max(rim_y[0] - n3, 0), min(rim_y[1] + n3, ny))
    outer_z = (max(rim_z[0] - n3, 0), min(rim_z[1] + n3, nz))

    shape = seg.shape
    cube_m = _box(shape, cube_x, cube_y, cube_z)
    outer_m = _box(shape, outer_x, outer_y, outer_z)
    rim_box_m = _box(shape, rim_x, rim_y, rim_z)
    no_cube_m = outer_m & ~cube_m
    rim_m = no_cube_m & rim_box_m

    qsm_cube = recon[cube_m]
    qsm_no_cube = recon[no_cube_m]
    rim_recon = recon[rim_m]
    rim_truth = truth[rim_m]

    # Adaptive threshold: least-negative t where no non-cube voxel falls below it.
    threshold = -3.5
    for i in range(0, 351):
        t = -i * 0.01
        if int(np.count_nonzero(qsm_no_cube < t)) == 0:
            threshold = t
            break

    calc_seg = qsm_cube[qsm_cube < threshold]
    if calc_seg.size == 0:
        return abs(gt_moment), math.nan

    calc_mean = float(calc_seg.mean())
    recon_moment = calc_seg.size * calc_mean
    moment_dev = abs(gt_moment - recon_moment)

    if rim_recon.size < 2:
        return moment_dev, math.nan
    slope, intercept = linear_fit(rim_truth, rim_recon)
    residuals = rim_recon - (slope * rim_truth + intercept)
    std_res = float(np.sqrt(((residuals - residuals.mean()) ** 2).mean()))
    streak = std_res / abs(calc_mean) if abs(calc_mean) > 1e-30 else math.nan
    return moment_dev, streak


# χ+ MSPE is averaged over the ROIs where paramagnetic susceptibility is a meaningful
# quantification target — the deep-gray-matter iron nuclei plus cortical gray matter. White
# matter (label 8) is excluded: χ+ there is ~1 ppb, so the percentage error has a near-zero
# denominator and blows up (the paper notes χ+ MSPE in WM reaches thousands of %). χ− MSPE is
# averaged over the white-matter sub-ROIs of the fibre-bundle atlas (passed as `wm_rois`).
MSPE_PARA_ROIS = [1, 2, 3, 4, 5, 6, 7, 9]  # CN,GP,PU,RN,DN,SN,TH,GM (dseg labels; WM=8 excluded)


def roi_mspe(recon, truth, labels, ids, sel_mask, min_vox=50, min_mean=5e-3) -> float:
    """Mean squared percentage error of ROI MEANS (Ridani et al., MRM 10.1002/mrm.70468).

    For each ROI, ((mean_recon - mean_truth) / mean_truth)^2 * 100, averaged across ROIs. This is
    the paper's headline separation metric — a per-region quantification-bias measure, distinct from
    the voxelwise NRMSE. ROIs with fewer than `min_vox` voxels or a near-zero truth mean (|mean| <
    `min_mean` ppm — an unstable percentage denominator) are skipped."""
    vals = []
    for lab in ids:
        sel = (labels == lab) & sel_mask
        if int(sel.sum()) < min_vox:
            continue
        gt_mean = float(truth[sel].mean())
        if abs(gt_mean) < min_mean:
            continue
        vals.append(((float(recon[sel].mean()) - gt_mean) / gt_mean) ** 2 * 100.0)
    return float(np.mean(vals)) if vals else math.nan


def theta_binned_mspe(recon, truth, theta, wm_mask, nbins=9) -> "list[float]":
    """Voxelwise χ− MSPE in 10° fibre-to-B0 angle bins over the white-matter voxels (Ridani et al.,
    MRM 10.1002/mrm.70468, Fig 5). Per bin, the per-voxel squared percentage errors are IQR-filtered
    (1.5×IQR) then averaged. Returns nbins values (bin 0 = 0–10° parallel … bin 8 = 80–90°
    perpendicular); a bin with too few voxels is NaN."""
    edges = np.linspace(0, 90, nbins + 1)
    th = theta[wm_mask]
    r, g = recon[wm_mask], truth[wm_mask]
    ok = g != 0
    th, r, g = th[ok], r[ok], g[ok]
    spe = ((r - g) / g) ** 2 * 100.0
    out = []
    for i in range(nbins):
        sel = (th >= edges[i]) & (th < edges[i + 1] if i < nbins - 1 else th <= edges[i + 1])
        v = spe[sel]
        if v.size < 50:
            out.append(math.nan)
            continue
        q1, q3 = np.percentile(v, [25, 75])
        iqr = q3 - q1
        v = v[(v >= q1 - 1.5 * iqr) & (v <= q3 + 1.5 * iqr)]
        out.append(float(v.mean()))
    return out


def mev_from_profile(profile) -> float:
    """Maximum error variation MEV = (MSPE_parallel − MSPE_perpendicular)/MSPE_parallel × 100 (Ridani
    et al. Eq 15): the fractional drop in χ− error from fibres parallel to B0 (first occupied bin) to
    perpendicular (last occupied bin). Positive ⇒ parallel fibres are harder, as expected."""
    occ = [v for v in profile if v == v]  # drop NaN bins
    if len(occ) < 2 or occ[0] == 0:
        return math.nan
    return (occ[0] - occ[-1]) / occ[0] * 100.0


def chisep_metrics(recon, truth, mask, seg=None, component="para", wm_rois=None, theta=None) -> dict:
    """Metrics for one χ-separation source map.

    `component` is 'para' (χ+, paramagnetic — iron in deep gray matter and venous blood) or 'dia' (χ−,
    diamagnetic — calcification/myelin, stored as a POSITIVE magnitude). Because χ-separation isolates
    the sources, the QSM region metrics apply to the source that owns each feature: χ+ carries the DGM
    iron and venous blood; χ− carries the calcification. The base agreement set
    (nrmse/nrmse_detrend/correlation/xsim) is always reported; with a segmentation we add:
      χ+ : nrmse_dgm, dgm_linearity, nrmse_blood, calc_leak  (calcium wrongly bleeding INTO χ+)
      χ− : calc_moment_dev, calc_streak, iron_leak           (iron/veins wrongly bleeding INTO χ−)
    'leak' is the mean |recon| in the region owned by the OTHER source (which should be ~0 here) — a
    direct cross-contamination / separation-fidelity measure, lower is better."""
    out = field_metrics(recon, truth, mask)
    if seg is None:
        return out
    m = mask > 0
    seg = np.rint(seg).astype(np.int32)
    dgm = m & np.isin(seg, [1, 2, 3, 4, 5, 6])
    blood = (dilate_mask_3d((m & (seg == 11)).astype(np.uint8)) > 0) & m
    calc = m & (seg == 16)

    def leak(sel):  # contamination: mean |recon| where this source should be ~0
        return float(np.abs(recon[sel]).mean()) if sel.any() else math.nan

    if component == "para":
        _, out["nrmse_dgm"] = nrmse_challenge(recon, truth, dgm)
        out["dgm_linearity"] = dgm_linearity(recon, truth, seg)
        _, out["nrmse_blood"] = nrmse_challenge(recon, truth, blood)
        out["calc_leak"] = leak(calc)
        # Paper per-ROI MSPE over the iron nuclei + GM (χ+ quantification target).
        out["mspe"] = roi_mspe(recon, truth, seg, MSPE_PARA_ROIS, m)
    else:  # dia — χ− is a positive magnitude; flip sign so the calcification reads negative
        dev, streak = calcification_metrics(-recon, -truth, seg)
        out["calc_moment_dev"] = dev
        out["calc_streak"] = streak
        out["iron_leak"] = leak(dgm | blood)
        # Paper per-ROI MSPE over the fibre-bundle atlas WM sub-ROIs (χ− anisotropy target, Fig 3).
        wm_bundles = None
        if wm_rois is not None:
            wr = np.rint(wm_rois).astype(np.int32)
            ids = sorted(set(np.unique(wr[m])) - {0})
            out["mspe"] = roi_mspe(recon, truth, wr, ids, m)
            wm_bundles = m & (wr > 0)
        # Orientation dependence (Fig 5): θ-binned χ− MSPE profile + MEV, over the WM fibre bundles
        # (or all WM if no atlas). Needs the fibre-to-B0 angle map θ. Captures the paper's effect and
        # reproduces its SNR trend; the absolute MEV differs from Fig 5 (voxelwise bins vs their
        # bundle-averaged ROIs — a ratio of bin errors is sensitive to that granularity).
        if theta is not None:
            wmm = wm_bundles if wm_bundles is not None else (m & (seg == 8))
            wmm = wmm & (theta > 0)
            if wmm.any():
                prof = theta_binned_mspe(recon, truth, np.asarray(theta, np.float64), wmm)
                out["mspe_theta"] = prof
                out["mev"] = mev_from_profile(prof)
    return out


def field_metrics(recon, truth, mask) -> dict:
    """Metric subset appropriate for a field map (total or local), a scalar field in ppm.

    The region-specific chi metrics (tissue/blood/DGM/calcification) do not apply to field maps,
    so we score global agreement within the mask: demeaned & detrended NRMSE, correlation, XSIM.
    """
    nrmse, nrmse_dt = nrmse_challenge(recon, truth, mask)
    return {
        "nrmse": nrmse,
        "nrmse_detrend": nrmse_dt,
        "correlation": correlation(recon, truth, mask),
        "xsim": xsim(recon, truth, mask),
    }


def challenge_metrics(recon, truth, mask, seg) -> dict:
    """Full sim-track metric suite. Mirrors QSM.rs `ChallengeMetrics::compute`."""
    m = mask > 0
    nrmse, nrmse_dt = nrmse_challenge(recon, truth, mask)

    tissue = m & np.isin(seg, [7, 8, 9])
    _, nrmse_tissue = nrmse_challenge(recon, truth, tissue)

    blood_base = (m & (seg == 11)).astype(np.uint8)
    blood = dilate_mask_3d(blood_base)
    _, nrmse_blood = nrmse_challenge(recon, truth, blood)

    dgm = m & np.isin(seg, [1, 2, 3, 4, 5, 6])
    _, nrmse_dgm = nrmse_challenge(recon, truth, dgm)

    calc_dev, calc_streak = calcification_metrics(recon, truth, seg)

    return {
        "nrmse": nrmse,
        "nrmse_detrend": nrmse_dt,
        "nrmse_tissue": nrmse_tissue,
        "nrmse_blood": nrmse_blood,
        "nrmse_dgm": nrmse_dgm,
        "dgm_linearity": dgm_linearity(recon, truth, seg),
        "calc_moment_dev": calc_dev,
        "calc_streak": calc_streak,
        "correlation": correlation(recon, truth, mask),
        "xsim": xsim(recon, truth, mask),
        "hfen": hfen(recon, truth, mask),
    }


# --- per-region descriptive stats ---------------------------------------------------------------

# Head-phantom dseg label names (qsm-forward realistic head model; see data/sim/README.md — labels
# 1–6 are the DGM nuclei, 12 is unused). An id missing from this map is reported as "label-<id>".
DSEG_LABELS = {
    1: "Caudate nucleus", 2: "Globus pallidus", 3: "Putamen", 4: "Red nucleus",
    5: "Dentate nucleus", 6: "Substantia nigra", 7: "Thalamus", 8: "White matter",
    9: "Grey matter", 10: "CSF", 11: "Blood", 13: "Bone", 14: "Air", 15: "Muscle",
    16: "Calcification",
}


def region_stats(vol, seg, mask, min_vox=10) -> dict:
    """Descriptive statistics per segmentation region: {label: {n, mean, std, median}} over the
    voxels of each nonzero seg label inside `mask`. Values in the volume's native unit (ppm).
    Regions with fewer than `min_vox` voxels in the mask are omitted."""
    out = {}
    for lab in np.unique(seg[mask]):
        if lab == 0:
            continue
        sel = mask & (seg == lab)
        n = int(sel.sum())
        if n < min_vox:
            continue
        v = vol[sel]
        mean, std, med = float(v.mean()), float(v.std()), float(np.median(v))
        # Skip a region whose stats aren't finite (e.g. a NaN voxel in the volume): json.dumps would
        # emit a bare `NaN` token — invalid JSON — and the browser's JSON.parse of results/regions.json
        # then throws, silently wiping ALL regional stats site-wide. Dropping the region keeps the
        # sidecar valid; a region we can't summarise cleanly is not worth poisoning the file for.
        if not (math.isfinite(mean) and math.isfinite(std) and math.isfinite(med)):
            continue
        out[str(int(lab))] = {"n": n, "mean": round(mean, 6),
                              "std": round(std, 6), "median": round(med, 6)}
    return out


def region_summary(recon, truth, seg, mask) -> dict:
    """Per-region descriptive stats for a run: recon and truth, both under the run's SCORE mask.
    Truth is re-summarised per run on purpose — the score mask is the recon's valid support (e.g.
    after BFR erosion), so the truth stats are the paired reference for exactly the voxels this run
    was scored on, not a phantom-wide constant. For a χ− (dia) component both maps are the positive
    magnitude convention used throughout the scorer."""
    m = mask > 0
    rec = region_stats(recon, seg, m)
    tru = region_stats(truth, seg, m)
    return {"labels": {k: DSEG_LABELS.get(int(k), f"label-{k}") for k in sorted(rec, key=int)},
            "recon": rec, "truth": tru}


# --- IO + CLI -----------------------------------------------------------------------------------


def load(path) -> np.ndarray:
    import nibabel as nib

    return np.asarray(nib.load(str(path)).get_fdata(dtype=np.float64))


def write_triptych(out_dir: Path, recon: np.ndarray, truth: np.ndarray) -> None:
    """Center axial slice: recon | truth | |error|, as a grayscale PNG."""
    from PIL import Image

    nx, ny, nz = recon.shape
    z = nz // 2
    lo, hi = -0.1, 0.1

    def win(sl, a, b):
        return np.clip((sl - a) / (b - a), 0, 1)

    r = win(recon[:, :, z], lo, hi)
    t = win(truth[:, :, z], lo, hi)
    e = win(np.abs(recon[:, :, z] - truth[:, :, z]), 0.0, hi)
    sep = np.zeros((nx, 2))
    panel = np.concatenate([r, sep, t, sep, e], axis=1)
    img = (np.rot90(panel) * 255).astype(np.uint8)
    Image.fromarray(img, mode="L").save(out_dir / "slices.png")


def selfcheck() -> None:
    """Sanity check: identical inputs => perfect scores; known easy cases."""
    rng = np.random.default_rng(0)
    truth = rng.standard_normal((16, 16, 16)) * 0.05
    mask = np.ones((16, 16, 16), np.uint8)
    seg = np.zeros((16, 16, 16), np.uint8)
    assert abs(correlation(truth, truth, mask) - 1.0) < 1e-9
    assert abs(xsim(truth, truth, mask) - 1.0) < 1e-6
    n, ndt = nrmse_challenge(truth, truth, mask)
    assert abs(n) < 1e-9 and abs(ndt) < 1e-9
    assert abs(hfen(truth, truth, mask)) < 1e-9
    seg[:8] = 5  # one region: dentate (label 5)
    rs = region_stats(truth, seg, mask > 0)
    v = truth[seg == 5]
    assert rs["5"]["n"] == v.size
    assert abs(rs["5"]["mean"] - float(v.mean())) < 1e-6
    assert abs(rs["5"]["median"] - float(np.median(v))) < 1e-6
    assert abs(rs["5"]["std"] - float(v.std())) < 1e-6
    print("[qsm-eval] selfcheck ok")


def main() -> None:
    p = argparse.ArgumentParser(description="Score a QSM reconstruction against ground truth (QSM-CI).")
    p.add_argument("--recon", type=Path, help="produced artifact to score")
    p.add_argument("--truth", type=Path, help="ground-truth artifact")
    p.add_argument("--kind", choices=["field", "chi", "chisep", "relaxation"], default="chi",
                   help="artifact kind: 'field' (total/local field), 'chi' (susceptibility), "
                        "'chisep' (a χ+/χ− source-separation component; with --seg adds source-specific "
                        "region metrics — DGM/blood for χ+, calcification for χ− — plus a leakage term), "
                        "or 'relaxation' (a generated R2′ map vs the phantom's true R2′; field metric set)")
    p.add_argument("--component", choices=["para", "dia"], default="para",
                   help="χ-separation source for kind=chisep: para=χ+ (paramagnetic), dia=χ− (diamagnetic)")
    p.add_argument("--seg", type=Path, help="segmentation (enables region metrics for kind=chi/chisep)")
    p.add_argument("--wm-rois", type=Path, default=None,
                   help="white-matter sub-ROI label map (fibre-bundle atlas) for the χ− per-ROI MSPE "
                        "(kind=chisep, component=dia)")
    p.add_argument("--theta", type=Path, default=None,
                   help="fibre-to-B0 angle map in degrees for the χ− orientation analysis (θ-binned "
                        "MSPE profile + MEV; kind=chisep, component=dia)")
    p.add_argument("--mask", type=Path)
    p.add_argument("--track", default="sim", choices=["sim", "invivo"], help="dataset label")
    p.add_argument("--stage", default=None, help="stage/span this run implements (recorded)")
    p.add_argument("--artifact", default=None, help="canonical name of the scored artifact (recorded)")
    p.add_argument("--name", default="submission")
    p.add_argument("--image", default=None)
    p.add_argument("--runtime", type=float, default=None)
    p.add_argument("--out", type=Path)
    p.add_argument("--figures", type=Path, default=None)
    p.add_argument("--selfcheck", action="store_true", help="run internal sanity checks and exit")
    args = p.parse_args()

    if args.selfcheck:
        selfcheck()
        return

    recon, truth, mask = load(args.recon), load(args.truth), load(args.mask)
    if recon.shape != truth.shape or recon.shape != mask.shape:
        raise SystemExit(f"shape mismatch: recon {recon.shape}, truth {truth.shape}, mask {mask.shape}")

    regions = None
    if args.kind == "chisep":
        seg = np.rint(load(args.seg)).astype(np.int32) if args.seg else None
        wm_rois = load(args.wm_rois) if args.wm_rois and args.wm_rois.exists() else None
        theta = load(args.theta) if args.theta and args.theta.exists() else None
        metrics = chisep_metrics(recon, truth, mask, seg, args.component, wm_rois, theta)
        if seg is not None:
            regions = region_summary(recon, truth, seg, mask)
    elif args.kind in ("field", "relaxation"):  # same agreement set; relaxation = a generated R2′ (Hz)
        metrics = field_metrics(recon, truth, mask)
    elif args.seg:  # chi with segmentation -> full challenge suite
        seg = np.rint(load(args.seg)).astype(np.int32)
        metrics = challenge_metrics(recon, truth, mask, seg)
        regions = region_summary(recon, truth, seg, mask)
    else:  # chi without segmentation (e.g. in-vivo): no region metrics, but the headline 2016
        # challenge suite still applies — NRMSE (the 2016 headline metric), detrended NRMSE, HFEN
        # (fine-detail error), correlation and XSIM. Region/calcification metrics need the sim
        # segmentation scheme, which the in-vivo dseg does not follow, so they are omitted.
        nrmse, nrmse_dt = nrmse_challenge(recon, truth, mask)
        metrics = {
            "nrmse": nrmse,
            "nrmse_detrend": nrmse_dt,
            "hfen": hfen(recon, truth, mask),
            "correlation": correlation(recon, truth, mask),
            "xsim": xsim(recon, truth, mask),
        }

    result = {
        "name": args.name,
        "track": args.track,
        "stage": args.stage,
        "artifact": args.artifact,
        "kind": args.kind,
        "image": args.image,
        "runtime_s": args.runtime,
        "metrics": {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in metrics.items()},
    }
    if regions:
        result["regions"] = regions
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"[qsm-eval] wrote {args.out}")

    if args.figures:
        args.figures.mkdir(parents=True, exist_ok=True)
        write_triptych(args.figures, recon, truth)
        print(f"[qsm-eval] wrote figures to {args.figures}")


if __name__ == "__main__":
    main()
