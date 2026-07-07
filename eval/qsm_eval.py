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
from scipy.ndimage import binary_dilation, uniform_filter

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
    }


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
    print("[qsm-eval] selfcheck ok")


def main() -> None:
    p = argparse.ArgumentParser(description="Score a QSM reconstruction against ground truth (QSM-CI).")
    p.add_argument("--recon", type=Path)
    p.add_argument("--truth", type=Path)
    p.add_argument("--seg", type=Path)
    p.add_argument("--mask", type=Path)
    p.add_argument("--track", default="sim", choices=["sim", "invivo"])
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

    if args.track == "sim":
        if not args.seg:
            raise SystemExit("--seg is required for the sim track")
        seg = np.rint(load(args.seg)).astype(np.int32)
        metrics = challenge_metrics(recon, truth, mask, seg)
    else:  # invivo
        metrics = {"correlation": correlation(recon, truth, mask), "xsim": xsim(recon, truth, mask)}

    result = {
        "contract": "v1",
        "name": args.name,
        "track": args.track,
        "image": args.image,
        "runtime_s": args.runtime,
        "metrics": {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in metrics.items()},
    }
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"[qsm-eval] wrote {args.out}")

    if args.figures:
        args.figures.mkdir(parents=True, exist_ok=True)
        write_triptych(args.figures, recon, truth)
        print(f"[qsm-eval] wrote figures to {args.figures}")


if __name__ == "__main__":
    main()
