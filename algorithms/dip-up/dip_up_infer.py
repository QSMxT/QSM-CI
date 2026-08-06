#!/usr/bin/env python3
"""QSM-CI wrapper for DIP-UP phase unwrapping (stage = field-mapping), GPU-capable / CPU-optional.

Consumes  /input/phase.nii.gz (multi-echo, rad), /input/mask.nii.gz, /input/params.json
Produces  /output/totalfield.nii.gz  (total off-resonance field, ppm)

WHAT DIP-UP IS.  DIP-UP (Zhu et al., Information 2025; github.com/sunhongfu/DIP-UP) is a *phase
unwrapping* method, NOT a dipole inversion. A PRETRAINED 3-D CNN predicts the integer wrap-count of a
SINGLE-echo wrapped phase image, and a test-time Deep-Image-Prior (DIP) refinement then fine-tunes
that network on the specific input under two unsupervised constraints (a Laplacian-consistency loss
and a masked total-variation loss). Two base nets ship as pretrained checkpoints:
  * PHU-NET3D   — 2 input channels [wrapped phase, Laplacian(wrapped phase)], width 64  (paper default)
  * PhaseNet3D  — 1 input channel  [wrapped phase],                            width 48

HOW WE MAKE IT A field-mapping SUBMISSION.  DIP-UP only *unwraps one echo* and outputs unwrapped
phase — it does not produce a total field. The QSM-CI field-mapping contract wants a totalfield in
ppm. So this wrapper:
  (1) runs DIP-UP (pretrained net + DIP refinement) on EACH echo's wrapped phase, giving unwrapped
      phase per echo;
  (2) does the per-voxel linear fit of unwrapped phase vs TE and normalizes by B0 to ppm — the SAME
      echo-fit + ppm math as algorithms/laplacian-fieldmap/recon.py and romeo-fieldmap/recon.py.
The novelty benchmarked here is DIP-UP's unwrap operator swapped in for the Laplacian/ROMEO unwrap;
the downstream echo-fit is identical (GAMMA, slope = cov(TE,phi)/var(TE), Hz -> ppm).

The base-net U-Net (Unet_{1,2}Chan_9Class) `from Unet_blocks import *`, but the DIP-UP repo ships no
Unet_blocks.py — it is reconstructed here (Unet_blocks.py, byte-compatible with the released
.pth state_dicts). The repo's Unet_*Chan_9Class.py hard-code initial_num_layers; the released nets
are width 64 (PHU-NET3D) / 48 (PhaseNet3D), so we patch that constant to match each checkpoint.

DOMAIN-SHIFT CAVEAT.  The base net was trained on real brain GRE phase at a specific resolution / TE
(sim 10 ms, in-vivo 5.8 ms) / field. Our sim phantom's wrap patterns and per-echo TEs differ, so the
pretrained wrap-count predictor may NOT transfer. The DIP refinement helps but is seeded by the base
net's prediction. If the unwrapping is poor the total-field correlation will be poor — that is a real
finding, reported, not tuned away. See README.
"""
import json
import math
import os
import re
import sys

import numpy as np
import nibabel as nib
import torch
import torch.nn as nn
import torch.optim as optim

GAMMA = 42.576e6  # Hz/T (identical convention to laplacian-fieldmap / romeo-fieldmap)

DIPUP_HOME = os.environ.get("DIPUP_HOME", "/opt/DIP-UP")
WEIGHTS_DIR = os.environ.get("DIPUP_WEIGHTS", "/opt/dip-up-weights")
HERE = os.path.dirname(os.path.abspath(__file__))

# Per-variant: (repo subdir with the Unet_*Chan class, class name, module file, #input channels,
#               checkpoint file, the initial_num_layers width the released checkpoint actually uses).
_VARIANTS = {
    "PHU-NET3D": ("PHU-NET3D", "Unet_2Chan_9Class", "Unet_2Chan_9Class", 2, "PHU-NET3D.pth", 64),
    "PhaseNet3D": ("PhaseNet3D", "Unet_1Chan_9Class", "Unet_1Chan_9Class", 1, "PhaseNet3D.pth", 48),
}


# --------------------------------------------------------------------------------------------------
# param helpers (mirror the inr-qsm / laplacian-fieldmap conventions)
# --------------------------------------------------------------------------------------------------
def _load_json(path):
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return {}


def _override(name, cfg, default, cast):
    env = os.environ.get("QSMCI_SET_" + name.upper())
    if env is not None:
        return cast(env)
    if name in cfg and cfg[name] is not None:
        return cast(cfg[name])
    return default


# --------------------------------------------------------------------------------------------------
# base-net loading — reconstruct the class at the checkpoint's width, load the pretrained weights
# --------------------------------------------------------------------------------------------------
def _build_net(variant, device):
    subdir, cls_name, mod_name, in_ch, ckpt_name, width = _VARIANTS[variant]
    repo_dir = os.path.join(DIPUP_HOME, subdir)
    # Make Unet_blocks (reconstructed, shipped beside this wrapper) importable next to the repo class.
    # Insert repo_dir first, then HERE, so HERE ends up EARLIER on sys.path — the reconstructed
    # Unet_blocks.py shipped with the wrapper must win over any stray copy inside the repo tree.
    for p in (repo_dir, HERE):
        if p not in sys.path:
            sys.path.insert(0, p)

    # The repo's Unet_*Chan_9Class.py hard-codes initial_num_layers; the released checkpoint width
    # differs (PHU-NET3D 64, PhaseNet3D 48). Patch that constant to the checkpoint's width. Anchor on
    # the ACTIVE assignment (line start + indentation, NOT a `#` comment) — the file also has a
    # commented `# initial_num_layers = 32` that must not be matched.
    src_path = os.path.join(repo_dir, mod_name + ".py")
    src = open(src_path).read()
    src, n = re.subn(
        r"^([ \t]*)initial_num_layers\s*=\s*\d+",
        rf"\g<1>initial_num_layers = {width}",
        src,
        flags=re.MULTILINE,
    )
    if n == 0:
        raise SystemExit(f"could not patch initial_num_layers in {src_path}")
    ns = {"__name__": "_dipup_net"}
    exec(compile(src, src_path, "exec"), ns)  # noqa: S102 — trusted local repo file
    net = ns[cls_name](4)                      # EncodingDepth = 4 (matches the checkpoints)
    net = nn.DataParallel(net)

    ckpt = os.path.join(WEIGHTS_DIR, ckpt_name)
    state = torch.load(ckpt, map_location="cpu", weights_only=False)
    net.load_state_dict(state, strict=True)
    net = net.to(device)
    return net, in_ch


# --------------------------------------------------------------------------------------------------
# DIP-UP losses (ported verbatim from the repo's inference.py / Demo_DIP_*.py)
# --------------------------------------------------------------------------------------------------
def _tv_loss(x, mask):
    dx = x[:, :, 1:, :, :] - x[:, :, :-1, :, :]
    dy = x[:, :, :, 1:, :] - x[:, :, :, :-1, :]
    dz = x[:, :, :, :, 1:] - x[:, :, :, :, :-1]
    return (
        (dx * mask[:, :, 1:, :, :]).abs().sum()
        + (dy * mask[:, :, :, 1:, :]).abs().sum()
        + (dz * mask[:, :, :, :, 1:]).abs().sum()
    )


def _lap_loss(wrapped, unwrapped):
    diff = unwrapped - wrapped
    rounds = torch.round(diff / (2 * math.pi))
    residual = diff - rounds * 2 * math.pi
    return residual.abs().sum()


def _laplacian3d(x):
    """Discrete Laplacian, used to build PHU-NET3D's 2nd input channel (the wrapped-phase Laplacian)."""
    lap = -6.0 * x
    for ax in (2, 3, 4):
        lap = lap + torch.roll(x, 1, ax) + torch.roll(x, -1, ax)
    return lap


def _dipup_unwrap_echo(net, in_ch, phase_np, mask_np, device, *, n_iter, lr, lr_decay, shift_base,
                       tv_weight=1.0):
    """DIP-UP unwrap of ONE 3-D echo. Returns unwrapped phase (rad) as a numpy array.

    Pretrained-net wrap-count prediction + test-time DIP refinement (Laplacian + masked-TV losses),
    following the repo's Demo_DIP_*/inference.py: the softmax over 9 wrap classes gives a per-voxel
    expected count, shifted by `shift_base`, masked, and added (x 2pi) to the wrapped phase.
    """
    image = torch.from_numpy(phase_np).float().unsqueeze(0).unsqueeze(0).to(device)  # (1,1,X,Y,Z)
    tissue_mask = torch.from_numpy(mask_np.astype(np.float32)).unsqueeze(0).unsqueeze(0).to(device)

    if in_ch == 2:  # PHU-NET3D: 2nd channel is the Laplacian of the wrapped phase
        lap = _laplacian3d(image)
        features = torch.cat([image, lap], dim=1)
    else:           # PhaseNet3D: wrapped phase only
        features = image

    net.eval()
    opt = optim.RMSprop(net.parameters(), lr=lr)
    idx = torch.arange(0, 9, device=device)[None, :, None, None, None]

    for it in range(n_iter):
        recons = net(features)
        recons_softmax = torch.softmax(recons, dim=1)
        recon_count = (idx * recons_softmax).sum(1, keepdim=True) - shift_base
        recon_count = recon_count * tissue_mask
        recon_uwph = recon_count * 2 * math.pi + image

        loss = tv_weight * _tv_loss(recon_uwph, tissue_mask) + _lap_loss(image, recon_uwph)
        loss.backward()
        opt.step()
        opt.zero_grad()

        # optional variable-LR schedule (repo's 'vlr' mode: 10% decay every 10 iters)
        if lr_decay and it % 10 == 0:
            for g in opt.param_groups:
                g["lr"] *= 0.9

    with torch.no_grad():
        recons = net(features)
        recons_softmax = torch.softmax(recons, dim=1)
        recon_count = (idx * recons_softmax).sum(1, keepdim=True) - shift_base
        recon_count = torch.round(recon_count * tissue_mask)
        uwp = (recon_count * 2 * math.pi + image).squeeze().cpu().numpy()
    return uwp.astype(np.float64)


# --------------------------------------------------------------------------------------------------
# main — unwrap every echo with DIP-UP, then echo-fit -> ppm total field (from laplacian-fieldmap)
# --------------------------------------------------------------------------------------------------
def main(inp, out):
    cfg = _load_json(os.path.join(inp, "config.json"))
    p = _load_json(os.path.join(inp, "params.json"))
    TE = np.asarray(p["TE"], float)
    B0 = float(p["B0"])

    variant = _override("variant", cfg, "PHU-NET3D", str)
    if variant not in _VARIANTS:
        raise SystemExit(f"unknown variant {variant!r}; choose one of {list(_VARIANTS)}")
    n_iter = _override("iterations", cfg, 100, int)
    lr = _override("lr", cfg, 1e-6, float)
    tv_weight = _override("tv_weight", cfg, 1.0, float)          # documented knob (see note below)
    lr_decay = _override("lr_decay", cfg, 1, int)
    shift_base = _override("shift_base", cfg, 5, int)

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(1)
    np.random.seed(1)

    pimg = nib.load(os.path.join(inp, "phase.nii.gz"))
    phase = pimg.get_fdata().astype(np.float64)
    mask = nib.load(os.path.join(inp, "mask.nii.gz")).get_fdata() > 0.5
    if phase.ndim == 3:
        phase = phase[..., None]
    ne = phase.shape[3]
    if TE.size < ne:
        TE = TE[0] * np.arange(1, ne + 1)

    print(
        f"DIP-UP: variant {variant}, echoes {ne}, iters {n_iter}, lr {lr}, lr_decay {bool(lr_decay)}, "
        f"shift_base {shift_base}, device {device}",
        flush=True,
    )
    if tv_weight != 1.0:
        # The reference loss is TV + Lap with unit TV weight. tv_weight is exposed for experimentation;
        # note the repo uses 1.0 and does not tune it. Applied as a scalar on the TV term.
        print(f"DIP-UP: NOTE tv_weight={tv_weight} (reference is 1.0)", flush=True)

    net, in_ch = _build_net(variant, device)

    unwrapped = np.stack(
        [
            _dipup_unwrap_echo(
                net, in_ch, phase[..., e], mask, device,
                n_iter=n_iter, lr=lr, lr_decay=bool(lr_decay), shift_base=shift_base,
                tv_weight=tv_weight,
            )
            for e in range(ne)
        ],
        axis=-1,
    )

    # --- echo-fit -> ppm total field (identical to laplacian-fieldmap / romeo-fieldmap) ---
    dt = TE - TE.mean()
    phibar = unwrapped.mean(axis=3, keepdims=True)
    slope = np.sum(dt[None, None, None, :] * (unwrapped - phibar), axis=3) / np.sum(dt**2)  # rad/s

    field_hz = slope / (2 * np.pi)
    field_ppm = field_hz * 1e6 / (GAMMA * B0) * mask

    os.makedirs(out, exist_ok=True)
    out_path = os.path.join(out, "totalfield.nii.gz")
    nib.save(nib.Nifti1Image(field_ppm.astype(np.float32), pimg.affine), out_path)
    print("DIP-UP: wrote", out_path, field_ppm.shape, "ppm", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/input",
         sys.argv[2] if len(sys.argv) > 2 else "/output")
