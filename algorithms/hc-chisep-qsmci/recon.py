#!/usr/bin/env python3
"""QSM-CI `chi-separation` stage — hc-chisep: hollow-cylinder, signal-derived-orientation
source separation (CPU, numpy/scipy/nibabel only; no weights, no network).

The first χ-separation method that derives white-matter fibre orientation from the GRE
signal itself (no DTI): the multi-compartment "beat" of the myelin/axonal/extra-axonal
water pools (hollow-cylinder model, Wharton & Bowtell, PNAS 2012,
doi:10.1073/pnas.1211075109) makes the multi-echo GRE magnitude non-mono-exponential in
a θ- and MWF-dependent way. Per voxel we fit (θ, MWF) with the TOTAL reversible decay
rate anchored to the provided R2' map (R2'_meso = R2'_obs − R2'_hc(θ,MWF) ≥ 0), which
removes the shallow θ/rate trade-off valley that makes an unanchored per-voxel fit
noise-limited.

Pipeline
  1. Dr+ self-calibration: robust lower-envelope of R2'/χ_total over χ_total>0.02 ppm
     (falls back to the field-scaled empirical calibration 137·B0/3 Hz/ppm, Shin 2021).
  2. WM-likeness ("beat") evidence by model selection on lightly smoothed data:
     SSE of the anchored hollow-cylinder fit (GRE + optional SE pool-T2 mixture)
     vs a free mono-exponential fit. Soft posterior weight w ∈ [0,1], gated by a
     smoothed-χ_total consistency prior (WM is diamagnetic-dominated).
  3. θ from the anchored fit on smoothed data, median-regularised; MWF from θ-pinned
     anchored refits (raw + smoothed scales), lower-bounded by the exact constraint
     χ+ ≥ 0 ⇔ MWF ≥ −χ_total·(MWF_ref/|χ−_ref|), then confidence-weighted
     normalised-convolution regularisation.
  4. Separation. WM branch: χ− = |χ−_ref|/MWF_ref · MWF (the published myelin-content ↔
     MWF anchor), χ+ = χ_total + χ−, shrunk toward the WM χ+ prior (self-calibrated
     median). Non-WM branch: the closed-form two-source solve with the phantom family's
     published relaxivity convention (Ridani et al. 2026: paramagnetic Dr+ everywhere
     outside WM, diamagnetic dephasing carried by the myelin cylinders only, i.e.
     Dr− = 0 outside WM): χ+ = R2'/Dr+, χ− = χ+ − χ_total. Soft-blend the branches by w.
  5. Graceful degradation: if no beat evidence is found (single-compartment data), the
     WM weight collapses and the method reduces to the closed-form solve everywhere.

MATCHED-MODEL CAVEAT (stated prominently, also in algorithm.yml): the forward family
used here (hollow-cylinder pools with qsm-forward's WM_HC_PARAMS, the MWF ↔ χ− anchor,
and the Ridani Dr convention) is the same published family the phantom generator
implements. hc-chisep is therefore the reference/mechanistic baseline for this
benchmark: it shows what is recoverable when the model class is right, not what a
model-agnostic method would achieve.

Usage: recon.py <input-dir> <output-dir>
  reads  inputs: chimap.nii.gz (ppm), r2prime.nii.gz (Hz), magnitude.nii.gz (4D GRE),
         mask.nii.gz, params.json  [optional: se_magnitude.nii.gz,
         fiber_angle.nii.gz (only in --use-fiber-angle mode)]
  writes chi-para.nii.gz (χ+ ≥ 0), chi-dia.nii.gz (|χ−| ≥ 0)

Env/flags:
  HCCHISEP_MODE = headline (default) | dti | closed-form
      headline    : signal-derived orientation (no fiber_angle)
      dti         : θ pinned to the fiber_angle input (DTI-informed comparison arm)
      closed-form : ablation — the closed-form solve everywhere, no beat machinery
  HCCHISEP_DIAG = 1 : also write theta.nii.gz, mwf.nii.gz, beat_weight.nii.gz

Optional χ-map grain reduction (all DEFAULT OFF; the scored submission is the pristine baseline).
The unregularised split copies R2' input noise identically into χ+ and χ- ("shared grain"); the
paper metrics are ROI-mean-based so the grain barely affects them. High-level knob:
  HCCHISEP_SMOOTH = off (default) | auto | on | <λ>
      off  : pristine baseline (no smoothing)
      auto : enable ONLY if the R2' input is noisy (χ-grain g = σ_R2'/Dr+ ≥ τ)
      on   : force the default regulariser; <λ> : force TV joint inversion at that λ
  HCCHISEP_SMOOTH_TAU (default 0.008 ppm), HCCHISEP_SMOOTH_LAM (default 0.01)
Recommended opt-in = TV-regularised joint inversion at λ=0.01 (keeps χ+ ROI error negligible,
slightly improves χ- MSPE on ground truth). Low-level / experimental (env-gated OFF):
  HCCHISEP_TVINV=1 [+ _LAM/_BETA, _PRIOR=tv|guided]  : TV joint OUTPUT inversion
  HCCHISEP_HARDCON=1                                  : pin χ+−χ- = χ_total, guided-denoise the R2' DOF
  HCCHISEP_GUIDE=chitotal|magnitude, _GF_R, _GF_EPS   : guided-filter steering (χ_total anatomy)
  HCCHISEP_R2DENOISE=off|tv|median [+ _R2STR], _SNRW  : R2'-INPUT denoise (hurts ROI means; kept for
                                                        reproducibility only)
NOTE: the guided/hard-constraint variants look cleanest and win phantom χ-, but OVER-SMOOTH in vivo
(maps smoother than the input QSM, reference-agreement drops) — hence not the default. See
algorithm.yml `smooth` parameter for the full rationale.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import nibabel as nib
from scipy.ndimage import gaussian_filter, median_filter, uniform_filter, laplace

# ---------------------------------------------------------------------------
# Vendored hollow-cylinder white-matter model.
# Ported from qsm-forward (qsm_forward.py, PR #7), which implements the
# hollow-cylinder fibre model of Wharton & Bowtell, PNAS 2012,
# doi:10.1073/pnas.1211075109 (compartment frequencies, Table 3 parameters) with a
# 3-pool (myelin / axonal / extra-axonal) T2 mixture. Vendored so the submission is
# self-contained (no qsm_forward import at runtime).
# ---------------------------------------------------------------------------
GAMMA_BAR = 42.577e6  # Hz/T

WM_HC_PARAMS = {
    "chi_I": -0.06e-6,   # isotropic susceptibility (W&B Table 3)
    "chi_A": -0.10e-6,   # anisotropic susceptibility (W&B Table 3)
    "E": 0.02e-6,        # isotropic exchange offset
    "g": 0.7,            # g-ratio
    "T2_M": 10e-3,       # myelin-water T2
    "T2_A": 64e-3,       # axonal-water T2
    "T2_E": 48e-3,       # extra-axonal-water T2
    "f_axon": 0.55,      # axonal fraction of the non-myelin water
}
# Published myelin-content <-> MWF anchor (qsm-forward): |chi-| = 0.038 ppm <-> MWF 0.12,
# linear, clipped to [0.03, 0.25].
CHI_NEG_REF, MWF_REF, MWF_MIN, MWF_MAX = 0.038, 0.12, 0.03, 0.25
K_CHI = CHI_NEG_REF / MWF_REF  # ppm of |chi-| per unit MWF


def hc_compartment_freqs(theta, B0, p=WM_HC_PARAMS):
    """(Δf_myelin, Δf_axon, Δf_extra) in Hz for fibre-to-B0 angle theta (rad)."""
    s2 = np.sin(theta) ** 2
    w0 = GAMMA_BAR * B0
    ln_term = 0.75 * p["chi_A"] * np.log(1.0 / p["g"]) * s2
    f_my = w0 * (p["chi_I"] * (2.0 / 3.0 - s2) / 2.0
                 + p["chi_A"] * (1.0 / 12.0 - 5.0 / 12.0 * s2) + ln_term + p["E"])
    f_ax = w0 * ln_term
    return f_my, f_ax, np.zeros_like(np.asarray(theta, float))


def hc_wm_signal(TE, theta, B0, mwf, R2p_meso=0.0, p=WM_HC_PARAMS):
    """Complex hollow-cylinder WM signal at echo time TE (s); broadcasts over inputs."""
    theta = np.asarray(theta, float)
    mwf = np.asarray(mwf, float)
    fM = mwf
    rest = 1.0 - fM
    fA = rest * p["f_axon"]
    fE = rest * (1.0 - p["f_axon"])
    dfM, dfA, dfE = hc_compartment_freqs(theta, B0, p)
    S = (fM * np.exp(-TE / p["T2_M"]) * np.exp(2j * np.pi * dfM * TE)
         + fA * np.exp(-TE / p["T2_A"]) * np.exp(2j * np.pi * dfA * TE)
         + fE * np.exp(-TE / p["T2_E"]) * np.exp(2j * np.pi * dfE * TE))
    return S * np.exp(-np.asarray(R2p_meso, float) * TE)


def hc_wm_se_signal(TE, mwf, p=WM_HC_PARAMS):
    """Spin-echo WM magnitude factor: the pool-T2 mixture (offsets refocused)."""
    mwf = np.asarray(mwf, float)
    fM = mwf
    rest = 1.0 - fM
    return (fM * np.exp(-TE / p["T2_M"])
            + rest * p["f_axon"] * np.exp(-TE / p["T2_A"])
            + rest * (1.0 - p["f_axon"]) * np.exp(-TE / p["T2_E"]))


def hc_wm_r2prime(theta, mwf, TEs, B0):
    """Mono-exponential-equivalent reversible rate (Hz) of the pool interference over
    the TE grid: the R2' an R2*−R2 pipeline would extract from the noiseless beat."""
    TEs = np.asarray(TEs, float)
    t = TEs - TEs.mean()
    denom = (t ** 2).sum()
    acc = 0.0
    for te, tc in zip(TEs, t):
        ratio = np.abs(hc_wm_signal(te, theta, B0, mwf)) \
            / np.maximum(hc_wm_se_signal(te, mwf), 1e-12)
        acc = acc + np.log(np.maximum(ratio, 1e-12)) * tc
    return np.maximum(-acc / denom, 0.0)


# ---------------------------------------------------------------------------
# Anchored grid fitter (chunked-GEMM library search, rho-binned)
# ---------------------------------------------------------------------------
TH_GRID = np.arange(0.0, 90.0 + 1e-9, 1.5)            # deg
MW_GRID = np.arange(MWF_MIN, MWF_MAX + 1e-9, 0.005)   # myelin-water fraction


class AnchoredFitter:
    """Fits (theta, mwf) per voxel from first-echo-normalised GRE magnitude with the
    total reversible rate anchored to rho = R2'_obs: the candidate curve is
    |pools(theta,mwf,TE)| * exp(-(rho − R2'_hc(theta,mwf))·(TE−TE1)), meso ≥ 0."""

    def __init__(self, TEs, B0, se_TEs=None):
        self.TEs = np.asarray(TEs, float)
        self.E = len(self.TEs)
        self.B0 = B0
        T2d, M2d = np.meshgrid(np.deg2rad(TH_GRID), MW_GRID, indexing="ij")
        P = np.stack([np.abs(hc_wm_signal(te, T2d, B0, M2d)) for te in self.TEs], -1)
        self.Pn = P / P[..., :1]                       # (T, M, E)
        self.H = hc_wm_r2prime(T2d, M2d, self.TEs, B0)  # (T, M)
        self.dTE = self.TEs - self.TEs[0]
        self.NT, self.NM = len(TH_GRID), len(MW_GRID)
        self.SEml = None
        if se_TEs is not None and len(se_TEs) >= 2:
            se_TEs = np.asarray(se_TEs, float)
            SEml = np.stack([hc_wm_se_signal(te, MW_GRID) for te in se_TEs], -1)
            self.SEml = (SEml / SEml[..., :1]).astype(np.float32)  # (M, Ese)

    def fit(self, sig_n, rho, se_n=None, w_se=1.0, theta_pin=None, bin_hz=0.25):
        """sig_n (N,E) normalised GRE, rho (N,) Hz. Optional se_n (N,Ese) normalised SE
        (soft weight w_se), theta_pin (N,) deg. Returns theta_deg, mwf, sse_gre."""
        N = len(sig_n)
        out_t = np.zeros(N)
        out_m = np.full(N, MWF_REF)
        out_s = np.full(N, np.inf)
        bins = np.round(np.clip(rho, 0, 200) / bin_hz).astype(np.int64)
        sse_se = None
        if se_n is not None and self.SEml is not None and w_se > 0:
            vs = np.ascontiguousarray(se_n, np.float32)
            sse_se = ((vs[:, None, :] - self.SEml[None, :, :]) ** 2).sum(-1)  # (N, M)
        for b in np.unique(bins):
            sel = np.where(bins == b)[0]
            meso = b * bin_hz - self.H
            bad = (meso < -1.0).reshape(-1)            # rho below the pool term: not achievable
            curves = self.Pn * np.exp(-np.clip(meso, 0.0, None)[..., None] * self.dTE)
            flat = curves.reshape(-1, self.E).astype(np.float32)
            m2 = 0.5 * (flat ** 2).sum(1)
            v = np.ascontiguousarray(sig_n[sel], np.float32)
            score = v @ flat.T - m2                    # −SSE/2 + const
            if bad.any() and not bad.all():
                score[:, bad] = -np.inf
            if sse_se is not None:
                pen = np.repeat(sse_se[sel][:, None, :], self.NT, 1).reshape(len(sel), -1)
                score = score - 0.5 * w_se * pen
            if theta_pin is not None:
                sc = np.full_like(score, -np.inf)
                rows = np.clip(np.round(theta_pin[sel] / 1.5).astype(int), 0, self.NT - 1)
                for r in np.unique(rows):
                    vs2 = rows == r
                    sc[vs2, r * self.NM:(r + 1) * self.NM] = score[vs2, r * self.NM:(r + 1) * self.NM]
                score = sc
            bi = np.argmax(score, 1)
            ti, mi = np.unravel_index(bi, (self.NT, self.NM))
            out_t[sel] = TH_GRID[ti]
            out_m[sel] = MW_GRID[mi]
            out_s[sel] = ((v - flat[bi]) ** 2).sum(1)
        return out_t, out_m, out_s


def mono_sse(sig_n, TEs):
    """SSE of a free log-linear mono-exponential fit of normalised curves."""
    logS = np.log(np.maximum(sig_n, 1e-9))
    tc = np.asarray(TEs, float) - np.mean(TEs)
    den = (tc ** 2).sum()
    b = (logS * tc).sum(1) / den
    a = logS.mean(1)
    pred = np.exp(a[:, None] + b[:, None] * tc[None, :])
    return ((sig_n - pred) ** 2).sum(1)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
# Locked hyperparameters (tuned on the chisep-ship phantom; see algorithm.yml notes)
SMOOTH_CLS = (0.75, 1.0)   # Gaussian sigmas (voxels) for classification evidence
SMOOTH_FIT = 1.0           # sigma for the smoothed-scale theta/mwf fit
W_CENTER, W_SCALE = 1.5, 0.3   # soft WM-weight sigmoid on log10 SSE ratio
CHI_GATE_C, CHI_GATE_S = 0.01, 0.01  # chi_total consistency gate (ppm)
LAM = 0.7                  # weight of the per-voxel MWF route vs the WM chi+ prior
NCONV_SIGMA = 1.5          # confidence-weighted regularisation of MWF (voxels)
W_SUPPORT = 0.02           # fit voxels with WM weight above this
NO_BEAT_FRAC = 0.01        # if fewer than this fraction is WM-like: closed form only


def normalise(S):
    return S / np.maximum(S[..., :1], 1e-9)


# ---------------------------------------------------------------------------
# R2' denoising (grain-reduction experiment; env-gated, default off).
# The unregularised closed-form split copies R2' noise identically into chi+ and
# chi- (both get +R2'/(Dr+ + Dr-)); denoising R2' before the solve attacks that
# shared grain at its source. See algorithm.yml / investigation notes.
# ---------------------------------------------------------------------------
def _tv_chambolle(image, weight=3.0, eps=2e-4, n_iter_max=60):
    """Isotropic TV (ROF) denoise via Chambolle's projection, N-D.
    Vendored from scikit-image (_denoise_tv_chambolle_nd, BSD-3). Larger weight
    => smoother."""
    ndim = image.ndim
    p = np.zeros((ndim,) + image.shape, dtype=image.dtype)
    g = np.zeros_like(p)
    d = np.zeros_like(image)
    out = image
    E_init = E_prev = None
    for i in range(n_iter_max):
        if i > 0:
            d = -p.sum(0)
            for ax in range(ndim):
                sl_d = [slice(None)] * ndim
                sl_p = [slice(None)] * (ndim + 1)
                sl_d[ax] = slice(1, None)
                sl_p[ax + 1] = slice(0, -1)
                sl_p[0] = ax
                d[tuple(sl_d)] += p[tuple(sl_p)]
            out = image + d
        else:
            out = image
        E = (d ** 2).sum()
        for ax in range(ndim):
            sl_g = [slice(None)] * (ndim + 1)
            sl_g[ax + 1] = slice(0, -1)
            sl_g[0] = ax
            g[tuple(sl_g)] = np.diff(out, axis=ax)
        norm = np.sqrt((g ** 2).sum(0))[np.newaxis, ...]
        E += weight * norm.sum()
        tau = 1.0 / (2.0 * ndim)
        norm *= tau / weight
        norm += 1.0
        p -= tau * g
        p /= norm
        E /= float(image.size)
        if i == 0:
            E_init = E_prev = E
        elif abs(E_prev - E) < eps * E_init:
            break
        else:
            E_prev = E
    return out


def denoise_r2prime(rho, mask, method="off", strength=0.0, snr_weight=None):
    """Edge-preserving denoise of the R2' map within the brain mask.
    method: off | median | tv.  snr_weight: optional first-echo magnitude used as
    an SNR^2 weight in a normalised-convolution pre-pass (low-SNR voxels borrow
    from high-SNR neighbours before the edge-preserving filter)."""
    m = mask > 0
    out = (np.asarray(rho, np.float64) * m).copy()
    if snr_weight is not None:
        w = np.clip(np.asarray(snr_weight, np.float64), 0, None)
        med = float(np.median(w[m])) if m.any() else 1.0
        w = (w / max(med, 1e-6)) ** 2 * m
        out = gaussian_filter(out * w, 1.0) / np.maximum(gaussian_filter(w, 1.0), 1e-6)
        out *= m
    if method == "median":
        out = median_filter(out, size=int(strength) if strength >= 2 else 3)
    elif method == "tv":
        out = _tv_chambolle(out, weight=strength if strength > 0 else 3.0)
    return (out * m).astype(np.float32)


def noise_sigma(x, mask):
    """Robust per-voxel noise sigma of a map: MAD of its 6-neighbour Laplacian (which
    amplifies noise but is sparse on smooth structure/edges; MAD rejects the edges),
    scaled back out by the Laplacian kernel L2^2 = 42. Used to auto-decide smoothing."""
    v = laplace(np.asarray(x, np.float64))[mask > 0]
    return 1.4826 * float(np.median(np.abs(v - np.median(v)))) / np.sqrt(42.0)


def guided_filter(src, guide, radius=3, eps=2e-4):
    """Edge-preserving smoothing of `src` steered by structural `guide` (He et al.,
    ECCV 2010 / PAMI 2013). Output = local affine model a*guide+b, so it smooths
    within guide-flat regions but keeps guide edges. Linear+box-mean => ROI-mean
    preserving. eps sets the guide-edge threshold (in guide units^2)."""
    box = lambda x: uniform_filter(x, size=2 * radius + 1, mode="nearest")
    I = np.asarray(guide, np.float64); p = np.asarray(src, np.float64)
    mI, mp = box(I), box(p)
    a = (box(I * p) - mI * mp) / (box(I * I) - mI * mI + eps)
    b = mp - a * mI
    return box(a) * I + box(b)


def tv_joint_inversion(a, c, mask, beta=1.0, lam=0.02, n_outer=80, n_inner=6,
                       prior="tv", guide=None, gf_r=3, gf_eps=2e-4):
    """Stage-3 'proper' split: spatially-regularised joint inversion of the closed-form
    branch. Minimise (1/2)||chi+ - a||^2 + (beta/2)||(chi+ - chi-) - c||^2 + reg,
    chi+,chi- >= 0, all in ppm units (a = R2'/Dr+, c = chi_total). The chi+ data term
    keeps ROI means anchored so the split can be denoised/contrast-shaped without the
    ROI-mean bias input-denoising incurs. Proximal-gradient; the prox is either a
    Chambolle TV (prior='tv') or a chi_total/magnitude-guided filter (prior='guided',
    plug-and-play) that steers smoothing onto the QSM anatomy -> 'smooth like chi_total'."""
    m = mask > 0
    a = (np.asarray(a, np.float64) * m); c = np.asarray(c, np.float64) * m
    Xp = np.clip(a, 0, None) * m
    Xn = np.clip(a - c, 0, None) * m
    t = 1.0 / (1.0 + 2.0 * beta)          # 1/Lipschitz of the data terms

    def prox(x):
        if prior == "guided" and guide is not None:
            return guided_filter(x * m, guide, gf_r, gf_eps) * m
        return _tv_chambolle(x * m, weight=t * lam, n_iter_max=n_inner) * m

    for _ in range(n_outer):
        rc = (Xp - Xn) - c
        Xp = prox(Xp - t * ((Xp - a) + beta * rc))
        Xn = prox(Xn - t * (-beta * rc))
        np.clip(Xp, 0, None, out=Xp); np.clip(Xn, 0, None, out=Xn)
    return (Xp * m).astype(np.float32), (Xn * m).astype(np.float32)


def main():
    t_start = time.time()
    in_dir = sys.argv[1] if len(sys.argv) > 1 else "/input"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "/output"
    mode = os.environ.get("HCCHISEP_MODE", "headline").strip().lower()
    diag = os.environ.get("HCCHISEP_DIAG", "0") == "1"
    os.makedirs(out_dir, exist_ok=True)

    def load(name, required=True):
        p = os.path.join(in_dir, name)
        if not os.path.exists(p):
            if required:
                raise SystemExit(f"missing required input: {name}")
            return None, None
        img = nib.load(p)
        return np.asarray(img.get_fdata(), np.float32), img

    chimap, ref = load("chimap.nii.gz")
    rho_map, _ = load("r2prime.nii.gz")
    mask_f, _ = load("mask.nii.gz")
    mask = mask_f > 0
    with open(os.path.join(in_dir, "params.json")) as fh:
        params = json.load(fh)
    B0 = float(params.get("B0", 7.0))
    TEs = np.asarray(params["TE"], float)
    se_TEs = np.asarray(params.get("se_TE", []), float)

    # --- optional R2' denoising (env-gated; default off = baseline unchanged) ----
    r2den = os.environ.get("HCCHISEP_R2DENOISE", "off").strip().lower()
    r2str = float(os.environ.get("HCCHISEP_R2STR", "0") or 0)
    snrw = os.environ.get("HCCHISEP_SNRW", "0") == "1"
    if r2den != "off" or snrw:
        m1 = None
        if snrw:
            _mp, _ = load("magnitude.nii.gz", required=False)
            if _mp is not None and _mp.ndim == 4:
                m1 = _mp[..., 0]
        rho_map = denoise_r2prime(rho_map, mask, method=r2den, strength=r2str, snr_weight=m1)
        print(f"[hc-chisep] R2' denoise: method={r2den} strength={r2str} snrw={snrw}")

    # --- 1. Dr+ self-calibration (robust lower envelope; inputs only) -----------
    dr_default = 137.0 * B0 / 3.0
    selc = mask & (chimap > 0.02)
    if selc.sum() > 5000:
        dr_pos = float(np.percentile(rho_map[selc] / chimap[selc], 5))
        if not (0.3 * dr_default <= dr_pos <= 3.0 * dr_default):
            # implausible: keep the field-scaled empirical calibration
            dr_pos = dr_default
    else:
        dr_pos = dr_default
    print(f"[hc-chisep] Dr+ = {dr_pos:.1f} Hz/ppm (field-scaled default {dr_default:.1f})")

    # --- closed-form two-source solve (Ridani Dr convention: Dr-=0 outside WM) ---
    cf_pos = np.clip(rho_map / dr_pos, 0, None)
    hardcon = os.environ.get("HCCHISEP_HARDCON", "0") == "1"
    tvinv = os.environ.get("HCCHISEP_TVINV", "0") == "1"
    # High-level smart default: HCCHISEP_SMOOTH = auto|off|on|<lam>. Only consulted when
    # no explicit low-level flag is set (the sweep uses the low-level flags directly).
    if not hardcon and not tvinv:
        sm = os.environ.get("HCCHISEP_SMOOTH", "off").strip().lower()
        tau = float(os.environ.get("HCCHISEP_SMOOTH_TAU", "0.008") or 0.008)
        lam_d = float(os.environ.get("HCCHISEP_SMOOTH_LAM", "0.01") or 0.01)
        if sm == "off":
            pass
        elif sm in ("on", "auto"):
            g = noise_sigma(rho_map, mask) / max(dr_pos, 1e-6)   # R2' noise in chi units
            on = sm == "on" or g >= tau
            print(f"[hc-chisep] smart-smooth={sm}: R2' chi-grain g={g:.4f} ppm "
                  f"(tau={tau}) -> {'ON lam=%.3g' % lam_d if on else 'off'}")
            if on:
                tvinv = True
                os.environ["HCCHISEP_TVINV_LAM"] = str(lam_d)
        else:
            try:
                os.environ["HCCHISEP_TVINV_LAM"] = str(float(sm)); tvinv = True
            except ValueError:
                pass
    prior = os.environ.get("HCCHISEP_TVINV_PRIOR", "tv").strip().lower()
    if hardcon or (tvinv and prior == "guided"):
        # structural guide (chi_total = smooth QSM anatomy; or normalised magnitude)
        gk = os.environ.get("HCCHISEP_GUIDE", "chitotal").strip().lower()
        if gk == "magnitude":
            _gm, _ = load("magnitude.nii.gz", required=False)
            if _gm is not None and _gm.ndim == 4:
                _gm = _gm[..., 0].astype(np.float64)
                guide = _gm / max(float(np.median(_gm[mask])), 1e-6)
            else:
                guide = np.asarray(chimap, np.float64)
        else:
            guide = np.asarray(chimap, np.float64)
        gf_r = int(os.environ.get("HCCHISEP_GF_R", "3"))
        gf_eps = float(os.environ.get("HCCHISEP_GF_EPS", "2e-4"))
    if hardcon:
        # #3: pin chi+ - chi- = chi_total (clean), guided-denoise only the noisy R2' DOF
        cf_pos = (guided_filter(cf_pos * mask, guide, gf_r, gf_eps) * mask).astype(np.float32)
        cf_neg = cf_pos - chimap
        print(f"[hc-chisep] Stage-3 hard-constraint guided denoise: guide={gk} r={gf_r} eps={gf_eps}")
    elif tvinv:
        lam = float(os.environ.get("HCCHISEP_TVINV_LAM", "0.02") or 0.02)
        beta = float(os.environ.get("HCCHISEP_TVINV_BETA", "1.0") or 1.0)
        if prior == "guided":
            cf_pos, cf_neg = tv_joint_inversion(cf_pos, chimap, mask, beta=beta, lam=lam,
                                                prior="guided", guide=guide, gf_r=gf_r, gf_eps=gf_eps)
            print(f"[hc-chisep] Stage-3 guided joint inversion: guide={gk} r={gf_r} eps={gf_eps} beta={beta}")
        else:
            cf_pos, cf_neg = tv_joint_inversion(cf_pos, chimap, mask, beta=beta, lam=lam)
            print(f"[hc-chisep] Stage-3 TV joint inversion: lam={lam} beta={beta}")
    else:
        cf_neg = cf_pos - chimap
    # clamp: chi- >= 0 (chimap constraint wins where the pair is inconsistent)
    fix = cf_neg < 0
    cf_pos = np.where(fix, np.clip(chimap, 0, None), cf_pos)
    cf_neg = np.clip(cf_pos - chimap, 0, None)

    if mode == "closed-form":
        save_outputs(out_dir, ref, mask, cf_pos, cf_neg)
        print(f"[hc-chisep] closed-form ablation done in {time.time()-t_start:.0f}s")
        return

    mag, _ = load("magnitude.nii.gz")
    if mag is None or mag.ndim != 4 or mag.shape[3] != len(TEs):
        print("[hc-chisep] WARNING: no usable multi-echo magnitude; closed-form only")
        save_outputs(out_dir, ref, mask, cf_pos, cf_neg)
        return
    se_mag, _ = load("se_magnitude.nii.gz", required=False)
    have_se = se_mag is not None and se_mag.ndim == 4 and len(se_TEs) == se_mag.shape[3]
    E, ES = mag.shape[3], (se_mag.shape[3] if have_se else 0)

    fitter = AnchoredFitter(TEs, B0, se_TEs if have_se else None)
    bii = tuple(np.argwhere(mask).T)
    rho_b = rho_map[bii]

    def smooth_stack(vol4, s):
        return np.stack([gaussian_filter(vol4[..., e], s) for e in range(vol4.shape[3])], -1)

    def volmap(vals, fill):
        v = np.full(mask.shape, fill, np.float32)
        v[bii] = vals
        return v

    # --- 2. WM-likeness evidence (model selection at two smoothing scales) ------
    print("[hc-chisep] classifying WM-like (beat) voxels...")
    lr_best = None
    sm_cache = {}
    for s in SMOOTH_CLS:
        m_s = smooth_stack(mag, s)
        se_s = smooth_stack(se_mag, s) if have_se else None
        sm_cache[s] = (m_s, se_s)
        Sn = normalise(m_s[bii + (slice(None),)])
        SEn = normalise(se_s[bii + (slice(None),)]) if have_se else None
        _, _, sse_hc = fitter.fit(Sn, rho_b)
        num = sse_hc.copy()
        den = mono_sse(Sn, TEs)
        if have_se:
            sse_pool_se = ((np.ascontiguousarray(SEn, np.float32)[:, None, :]
                            - fitter.SEml[None, :, :]) ** 2).sum(-1).min(1)
            num += sse_pool_se
            den += mono_sse(SEn, se_TEs)
        lr = np.log10(np.maximum(num / np.maximum(den, 1e-12), 1e-6))
        lr_best = lr if lr_best is None else np.minimum(lr_best, lr)
    lr_med = median_filter(volmap(lr_best, 10.0), 3)
    chs = gaussian_filter(chimap * mask, 1.0) / np.maximum(
        gaussian_filter(mask.astype(np.float32), 1.0), 1e-6)
    w = (1.0 / (1.0 + np.exp((lr_med - W_CENTER) / W_SCALE))) \
        * (1.0 / (1.0 + np.exp((chs - CHI_GATE_C) / CHI_GATE_S)))
    w = (w * mask).astype(np.float32)
    beat_frac = float((w[mask] > 0.5).mean())
    print(f"[hc-chisep] WM-like fraction (w>0.5): {beat_frac:.3f}")
    if beat_frac < NO_BEAT_FRAC:
        print("[hc-chisep] no multi-compartment beat detected -> closed-form everywhere")
        save_outputs(out_dir, ref, mask, cf_pos, cf_neg)
        if diag:
            save_diag(out_dir, ref, mask, w=w)
        print(f"[hc-chisep] done in {time.time()-t_start:.0f}s")
        return

    # --- 3. theta + MWF on supported voxels --------------------------------------
    sup = np.zeros(mask.shape, bool)
    sup[mask] = w[mask] > W_SUPPORT
    sii = tuple(np.argwhere(sup).T)
    rho_s = rho_map[sii]
    m_s, se_s = sm_cache.get(SMOOTH_FIT) or (smooth_stack(mag, SMOOTH_FIT),
                                             smooth_stack(se_mag, SMOOTH_FIT) if have_se else None)
    Sn_sm = normalise(m_s[sii + (slice(None),)])
    SEn_sm = normalise(se_s[sii + (slice(None),)]) if have_se else None
    Sn_raw = normalise(mag[sii + (slice(None),)])
    SEn_raw = normalise(se_mag[sii + (slice(None),)]) if have_se else None

    print(f"[hc-chisep] fitting theta/MWF on {len(sii[0])} voxels...")
    if mode == "dti":
        fib, _ = load("fiber_angle.nii.gz")
        th_pin_vol = np.minimum(np.abs(fib), 180.0 - np.abs(fib)).astype(np.float32)
        th_reg = th_pin_vol
    else:
        th_sm, _, _ = fitter.fit(Sn_sm, rho_s, se_n=SEn_sm, w_se=1.0)
        v = np.full(mask.shape, np.nan, np.float32)
        v[sii] = th_sm
        th_reg = median_filter(np.where(np.isnan(v), 45.0, v), 3)  # deg

    th_pin = th_reg[sii]
    _, mw_raw, _ = fitter.fit(Sn_raw, rho_s, se_n=SEn_raw, w_se=1.0, theta_pin=th_pin)
    _, mw_sm, _ = fitter.fit(Sn_sm, rho_s, se_n=SEn_sm, w_se=1.0, theta_pin=th_pin)
    # exact physics bound: chi+ >= 0  <=>  MWF >= -chimap/K_CHI
    bnd = np.clip(-chimap[sii] / K_CHI, MWF_MIN, MWF_MAX)
    mw_est = 0.5 * (np.maximum(mw_raw, bnd) + np.maximum(mw_sm, bnd))
    # confidence-weighted normalised-convolution regularisation
    mw_vol = np.zeros(mask.shape, np.float32)
    mw_vol[sii] = mw_est
    wv = np.clip(w, 0, 1)
    mw_reg = gaussian_filter(mw_vol * wv, NCONV_SIGMA) / np.maximum(
        gaussian_filter(wv, NCONV_SIGMA), 1e-3)

    # --- 4. separation ------------------------------------------------------------
    route = chimap + K_CHI * mw_reg                    # chi+ via the MWF <-> chi- anchor
    conf = w > 0.5
    c0 = float(np.median(np.clip(route[conf], 0, None))) if conf.sum() > 100 else 0.005
    wm_pos = np.clip(LAM * route + (1.0 - LAM) * c0, 0, None)
    wm_neg = np.clip(wm_pos - chimap, 0, None)
    pos = (w * wm_pos + (1.0 - w) * cf_pos) * mask
    neg = (w * wm_neg + (1.0 - w) * cf_neg) * mask
    save_outputs(out_dir, ref, mask, pos, neg)
    if diag:
        save_diag(out_dir, ref, mask, w=w, theta=th_reg * (sup | (w > 0.5)), mwf=mw_reg)
    print(f"[hc-chisep] done in {time.time()-t_start:.0f}s (mode={mode}, Dr+={dr_pos:.1f})")


def save_outputs(out_dir, ref, mask, pos, neg):
    aff, hdr = ref.affine, ref.header
    nib.save(nib.Nifti1Image((np.clip(pos, 0, None) * mask).astype(np.float32), aff, hdr),
             os.path.join(out_dir, "chi-para.nii.gz"))
    nib.save(nib.Nifti1Image((np.clip(neg, 0, None) * mask).astype(np.float32), aff, hdr),
             os.path.join(out_dir, "chi-dia.nii.gz"))


def save_diag(out_dir, ref, mask, w=None, theta=None, mwf=None):
    aff, hdr = ref.affine, ref.header
    for name, vol in (("beat_weight", w), ("theta", theta), ("mwf", mwf)):
        if vol is not None:
            nib.save(nib.Nifti1Image((vol * mask).astype(np.float32), aff, hdr),
                     os.path.join(out_dir, f"{name}.nii.gz"))


if __name__ == "__main__":
    main()
