#!/usr/bin/env python3
"""QSM-CI wrapper for INR-QSM dipole inversion (stage = dipole), CPU by default.

Consumes  /input/localfield.nii.gz, /input/mask.nii.gz, /input/params.json
Produces  /output/chimap.nii.gz  (susceptibility, ppm)

INR-QSM (Zhang, Feng et al., Medical Image Analysis 2024; github.com/AMRI-Lab/INR-QSM) is an
UNSUPERVISED, subject-specific deep-learning method. It loads NO pretrained reconstruction weights:
a sine-activated coordinate MLP (SIREN) is OPTIMIZED per-subject so that the susceptibility it
represents χ(x) = MLP(coord), pushed through the QSM dipole forward model, reproduces the input local
field, regularized by an edge-weighted TV term and a gradient-domain data-consistency term.

This wrapper REUSES the reference network + operators verbatim from the cloned repo
($INR_QSM_HOME = /opt/INR-QSM/inr-qsm):
  * model.siren_model            — the SIREN coordinate MLP (width/depth/w0 from params)
  * utils.calc_d2_matrix1        — the k-space dipole kernel D = 1/3 − (k·B̂0)²/|k|²
  * utils.build_coordinate_train — normalized [-1,1] coordinate grid (voxel-anisotropy aware)
  * utils.myfftnc / utils.myifftnc — the repo's orthonormal centered FFTs
  * utils.TVLoss, utils.GradientLoss — the repo's edge-weighted regularizers

DELIBERATE DEVIATIONS from the reference main.py (documented in README, so behavior is explicit):
  1. FULL-VOLUME optimization, not the patch-based non-local phase-compensation loop. The reference
     tiles the volume into 96×96×48 patches and runs an iterative "phase compensation" that models
     the non-local field contribution of neighboring patches. That machinery is GPU/memory-heavy and
     fragile. Here χ is a single MLP over the whole volume, so the forward model F⁻¹(D·F·χ) is exact
     and non-local by construction — no patch stitching / compensation is needed. This is a faithful
     simplification of the SAME data-consistency objective, but is NOT byte-identical to the paper's
     patch pipeline and may differ near boundaries.
  2. NO CUDA AMP / float16. The reference uses torch.cuda.amp autocast + GradScaler + fp16 tensors,
     which are CUDA-only; we run float32 on CPU (or GPU if enabled). Same math, CPU-safe.
  3. WG (edge-weight matrix) is computed IN PYTHON. The reference generates WG from a MATLAB
     STISuite FastQSM/STAR-QSM initial recon (data_prep/TVweighting.m). STISuite is proprietary
     MATLAB and not shipped. We reimplement TVweighting.m in Python on an in-house TKD initial χ
     estimate (see _tv_weighting). Approximates, does not reproduce, the STISuite-based WG.

Units. QSM-CI's localfield.nii.gz is the tissue/local field already in ppm (the repo's `phi`, likewise
ppm — see data_prep/demo_use.m "the tissue phase ... should be normalized with a unit of ppm"). Fed
unchanged; output susceptibility is ppm, written unchanged on the input affine.

B0 direction / voxel size come from params.json / QSMCI_* env vars.

RUNTIME/GPU CAVEAT: per-subject optimization (default 50 epochs) is expensive and the reference is
GPU-oriented (~10 GB VRAM). On CPU this may be slow or exceed the CI time limit — see README.
"""
import json
import os
import sys

import numpy as np
import nibabel as nib
import torch

INR_HOME = os.environ.get("INR_QSM_HOME", "/opt/INR-QSM/inr-qsm")
sys.path.insert(0, INR_HOME)

import model as inr_model  # noqa: E402
import utils as inr_utils  # noqa: E402


# --------------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------------
def _load_json(path):
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return {}


def _vec(env_name, key, params, default):
    env = os.environ.get(env_name)
    if env:
        return [float(v) for v in env.split()]
    if key in params and params[key] is not None:
        return [float(v) for v in params[key]]
    return list(default)


def _override(name, cfg, default, cast):
    env = os.environ.get("QSMCI_SET_" + name.upper())
    if env is not None:
        return cast(env)
    if name in cfg and cfg[name] is not None:
        return cast(cfg[name])
    return default


def _tkd_initial_chi(phi, kernel_np, thresh=0.15):
    """Truncated k-space division initial χ estimate (numpy), used only to seed the WG edge weights.

    kernel_np is the fftshifted-free centered dipole D from utils.calc_d2_matrix1 (DC at center).
    We divide in the same centered FFT convention the repo uses (np_myfftnc / np_myifftnc)."""
    dim = [0, 1, 2]
    phi_k = inr_utils.np_myfftnc(phi, dim)
    d = kernel_np.copy()
    small = np.abs(d) < thresh
    d_inv = np.where(small, np.sign(d) * thresh, d)
    d_inv[d_inv == 0] = thresh
    chi = np.real(inr_utils.np_myifftnc(phi_k / d_inv, dim))
    return chi


def _tv_weighting(x0, mask, tv_range=(0.5, 0.7)):
    """Python port of data_prep/TVweighting.m: edge-weight matrix from gradient magnitude of x0.

    Returns WG of shape (X, Y, Z, 3), low near strong edges, high in smooth regions, masked."""
    grad = np.zeros(x0.shape + (3,), dtype=np.float64)
    grad[..., 0] = np.abs(np.diff(x0, axis=0, append=x0[-1:, :, :]))
    grad[..., 1] = np.abs(np.diff(x0, axis=1, append=x0[:, -1:, :]))
    grad[..., 2] = np.abs(np.diff(x0, axis=2, append=x0[:, :, -1:]))
    m4 = np.repeat(mask[..., None], 3, axis=-1) > 0
    vals = np.sort(grad[m4])
    if vals.size == 0:
        return (np.ones_like(grad) * m4).astype(np.float32)
    hi = vals[min(int(round(len(vals) * tv_range[1])), len(vals) - 1)]
    lo = vals[min(int(round(len(vals) * tv_range[0])), len(vals) - 1)]
    denom = (hi - lo) if (hi - lo) != 0 else 1.0
    wg = (hi - grad) / denom
    wg = np.clip(wg, 0.0, 1.0) * m4
    return wg.astype(np.float32)


# --------------------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------------------
def main():
    IN = sys.argv[1] if len(sys.argv) > 1 else "/input"
    OUT = sys.argv[2] if len(sys.argv) > 2 else "/output"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(1)
    np.random.seed(1)

    lfs_img = nib.load(os.path.join(IN, "localfield.nii.gz"))
    phi = np.asarray(lfs_img.get_fdata(), dtype=np.float64)          # tissue/local field, ppm
    mask = (np.asarray(nib.load(os.path.join(IN, "mask.nii.gz")).dataobj) > 0).astype(np.float64)

    params = _load_json(os.path.join(IN, "params.json"))
    cfg = _load_json(os.path.join(IN, "config.json"))

    voxel_size = _vec("QSMCI_VOXEL_SIZE", "voxel_size", params, [1.0, 1.0, 1.0])
    b0_dir = _vec("QSMCI_B0_DIR", "B0_dir", params, [0.0, 0.0, 1.0])
    hdr_zooms = [float(z) for z in lfs_img.header.get_zooms()[:3]]
    if hdr_zooms and all(z > 0 for z in hdr_zooms):
        voxel_size = hdr_zooms

    # --- reference-default hyperparameters (config.py), with config.json / QSMCI_SET_* overrides ---
    epoch = _override("epoch", cfg, 50, int)
    star_lr = _override("star_lr", cfg, 1e-5, float)
    end_lr = _override("end_lr", cfg, 0.02e-5, float)
    hidden_dim = _override("hidden_dim_num", cfg, 512, int)
    num_layers = _override("num_layers", cfg, 10, int)
    tv_weight = _override("TV_weight", cfg, 0.15, float)
    gd_weight = _override("gd_weight", cfg, 1.0, float)
    w0 = 40  # reference default (w0 == w0_hidden == w0_last == 40)

    print(
        f"INR-QSM: phi {phi.shape}, voxel_size {voxel_size}, B0_dir {b0_dir}, epoch {epoch}, "
        f"star_lr {star_lr}, hidden_dim {hidden_dim}, num_layers {num_layers}, "
        f"TV_weight {tv_weight}, gd_weight {gd_weight}, device {device}",
        flush=True,
    )

    shape = phi.shape

    # --- dipole kernel (repo's k-space kernel; DC at center) ---
    kernel_np = inr_utils.calc_d2_matrix1(shape, voxel_size, b0_dir, device="cpu")
    kernel = torch.tensor(kernel_np, dtype=torch.float32, device=device).unsqueeze(0).unsqueeze(-1)

    # --- edge weights WG from a TKD initial estimate (Python port of the MATLAB data-prep) ---
    x0 = _tkd_initial_chi(phi * mask, kernel_np) * mask
    wg_np = _tv_weighting(x0, mask)
    WG = torch.tensor(wg_np, dtype=torch.float32, device=device).unsqueeze(0)  # (1,X,Y,Z,3)

    # --- normalized coordinate grid + tensors ---
    coor = inr_utils.build_coordinate_train(shape[0], shape[1], shape[2],
                                            shape[0], shape[1], shape[2], voxel_size)
    coor = torch.tensor(coor, dtype=torch.float32, device=device).unsqueeze(0)   # (1,X,Y,Z,3)
    phi_t = torch.tensor(phi, dtype=torch.float32, device=device).unsqueeze(0).unsqueeze(-1)
    mask_t = torch.tensor(mask, dtype=torch.float32, device=device).unsqueeze(0).unsqueeze(-1)

    # --- SIREN coordinate MLP (reference model, optional transfer-learning init for speed) ---
    net = inr_model.siren_model(w0_first=w0, w0_hidden=w0, w0_last=w0,
                                num_layers=num_layers, input_dim=3,
                                hidden_dim=hidden_dim, out_dim=1).to(device)
    tl_path = os.environ.get(
        "INR_QSM_TL_WEIGHTS",
        os.path.join(INR_HOME, "transfer_learning",
                     "pre_trained_weight_for_transfer_learning.pkl"),
    )
    if os.environ.get("INR_QSM_USE_TL", "1") == "1" and os.path.exists(tl_path):
        try:
            net.load_state_dict(torch.load(tl_path, map_location=device))
            print("INR-QSM: loaded transfer-learning init (acceleration only)", flush=True)
        except Exception as e:  # width/depth must match the shipped init; skip if not
            print(f"INR-QSM: transfer-learning init not applied ({e}); random init", flush=True)

    optimizer = torch.optim.Adam(net.parameters(), lr=star_lr)
    # exponential decay star_lr -> end_lr over `epoch` epochs (reference schedule form)
    decay = (end_lr / star_lr) ** (1.0 / max(1, 2 * epoch))
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lambda e: decay ** e)

    l2 = torch.nn.MSELoss()
    tv_loss_fn = inr_utils.TVLoss()
    gd_loss_fn = inr_utils.GradientLoss()

    # --- per-subject optimization: min ||mask·(F⁻¹ D F χ − phi)||² + TV + GD ---
    net.train()
    for e in range(epoch):
        optimizer.zero_grad()
        chi = net(coor) * mask_t                                   # (1,X,Y,Z,1)
        chi_k = inr_utils.myfftnc(chi, dim=[1, 2, 3])
        fwd = inr_utils.myifftnc(chi_k * kernel, dim=[1, 2, 3]).real
        fwd = fwd * mask_t
        target = phi_t * mask_t

        mse = l2(fwd, target)
        tv = tv_weight * tv_loss_fn(chi, "L2", WG)
        gd = gd_weight * gd_loss_fn(fwd, target, "L2", WG)
        loss = mse + tv + gd

        loss.backward()
        optimizer.step()
        scheduler.step()
        print(f"INR-QSM epoch [{e + 1}/{epoch}] lr {scheduler.get_last_lr()[0]:.3e} "
              f"MSE {mse.item():.5f} TV {tv.item():.5f} GD {gd.item():.5f} "
              f"loss {loss.item():.5f}", flush=True)

    # --- final prediction ---
    net.eval()
    with torch.no_grad():
        chi = (net(coor) * mask_t).squeeze(0).squeeze(-1).cpu().numpy().astype(np.float32)

    os.makedirs(OUT, exist_ok=True)
    out_path = os.path.join(OUT, "chimap.nii.gz")
    nib.Nifti1Image(chi, lfs_img.affine, lfs_img.header).to_filename(out_path)
    print("INR-QSM: wrote", out_path, chi.shape, "ppm", flush=True)


if __name__ == "__main__":
    main()
