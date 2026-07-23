#!/usr/bin/env python
"""QSM-CI wrapper for IR2QSM dipole inversion (PyTorch, CPU).

Mirrors the reference inference in IR2QSM/Evaluate/test.py + test_util.py, but consuming QSM-CI
artifacts (localfield.nii.gz + mask.nii.gz) and writing chimap.nii.gz on the INPUT affine.

Pipeline (faithful to the reference test_util.process_nii_file):

  1. Read localfield.nii.gz — the local/tissue field already in ppm. QSM-CI provides this; IR2QSM
     was trained to map exactly this (their `lfs`, local field shift in ppm) to susceptibility.
  2. NO normalization. Unlike QSMnet/MoDL-QSM, the IR2QSM reference feeds the local field to the
     network directly — there is no dataset mean/std scaling and no norm_factor file in the repo.
     The output is likewise already in ppm (no de-normalization).
  3. Zero-pad each dim up to a multiple of 8. The IR2U-net has depth=4 with (depth-1)=3 max-pool /
     deconv levels, so spatial dims must be divisible by 2**3 = 8. The reference calls
     zero_padding(image, 8); we replicate its centered padding and crop back afterwards.
  4. Run the frozen IR2U-net (Evaluate/IR2Unet.py). model(x) returns (latest_out, all_output); the
     reference keeps `latest_out` (the fully integrated final estimate) — so do we. (all_output[t]
     are the per-iteration intermediates; the reference notes the final output is recommended.)
  5. Multiply by the brain mask and write chimap.nii.gz on the input affine/header (voxel size +
     orientation preserved).

Differences from the reference we deliberately make (all documented in README.md):
  * The reference derives its mask from the padded field's nonzero voxels (`image != 0`); we use the
    supplied QSM-CI mask.nii.gz instead (the canonical brain mask for this stage), applied after
    cropping back to the original grid.
  * The reference saves with affine=np.eye(4), discarding geometry; we round-trip the input NIfTI's
    affine so voxel size + orientation are carried through unchanged (matching qsmnet_infer.py).
  * GPU-only AddNoise: the repo's IR2Unet.forward runs an AddNoise() call in the decoder that is NOT
    gated by self.training, and AddNoise() in IR2UnetBlock.py hardcodes `.to("cuda:0")` — which would
    crash on CPU. We monkeypatch AddNoise to a device-correct implementation before running so CPU
    inference reproduces the reference behavior (see _install_cpu_safe_addnoise below).
"""
import os
import sys

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")  # force CPU

import numpy as np
import nibabel as nib
import torch
import torch.nn as nn

# The pretrained net is defined in the cloned repo's Evaluate/ package (IR2Unet + the blocks in
# IR2UnetBlock). IR2QSM_CODE points at that dir in the image.
IR2QSM_CODE = os.environ.get("IR2QSM_CODE", "/opt/IR2QSM/Evaluate")
sys.path.insert(0, IR2QSM_CODE)

import IR2UnetBlock  # noqa: E402  (imported before IR2Unet so the monkeypatch below sticks)
import IR2Unet       # noqa: E402


def _install_cpu_safe_addnoise():
    """Replace the repo's GPU-hardcoded AddNoise with a device-correct equivalent.

    IR2Unet.forward calls AddNoise() in the decoder unconditionally (not gated by self.training), and
    the upstream AddNoise() does `.to("cuda:0")`, which raises on a CPU-only box. We swap in a version
    that keeps everything on the input tensor's own device, preserving the reference's numerical
    behavior (same additive-noise formula) while running on CPU. In eval() + no_grad() the other
    AddNoise calls are gated out by self.training, so only this decoder call actually fires.
    """
    def AddNoise(ins, SNR):
        sig_power = torch.sum(ins ** 2) / torch.numel(ins)
        noise_power = sig_power / SNR
        noise = torch.sqrt(noise_power) * torch.randn(ins.size(), device=ins.device)
        return ins + noise

    # IR2Unet.py does `from IR2UnetBlock import *`, so AddNoise is resolved in IR2Unet's namespace.
    IR2Unet.AddNoise = AddNoise
    IR2UnetBlock.AddNoise = AddNoise


def zero_pad_to_multiple(vol, m=8):
    """Center zero-pad each dim up to the next multiple of m (mirrors repo's zero_padding, factor 8).

    Returns the padded array plus the per-axis (lo, hi) pads so we can crop the prediction back.
    """
    shape = np.asarray(vol.shape)
    target = np.ceil(shape / float(m)).astype(int) * m
    # Reference uses ceil((up-im)/2) for the low offset; replicate exactly.
    lo = np.ceil((target - shape) / 2.0).astype(int)
    hi = target - shape - lo
    npad = tuple((int(l), int(h)) for l, h in zip(lo, hi))
    return np.pad(vol, npad, mode="constant", constant_values=0), npad


def crop_pad(vol, npad):
    sl = tuple(slice(lo, vol.shape[i] - hi) for i, (lo, hi) in enumerate(npad))
    return vol[sl]


def main():
    in_field, in_mask, out_chi = sys.argv[1], sys.argv[2], sys.argv[3]
    ckpt = os.environ.get("IR2QSM_CKPT", "/opt/IR2QSM/Evaluate/model_IR2Unet.pth")

    _install_cpu_safe_addnoise()

    device = torch.device("cpu")

    # --- read the local field (ppm) + mask ---
    field_img = nib.load(in_field)
    field = np.asarray(field_img.get_fdata(), dtype=np.float32)
    mask = np.asarray(nib.load(in_mask).get_fdata(), dtype=np.float32)

    # pad to /8 (no normalization — IR2QSM consumes ppm local field directly)
    pfield, npad = zero_pad_to_multiple(field, 8)
    x = torch.from_numpy(pfield).float()[None, None, ...]  # (1, 1, X, Y, Z)
    x = x.to(device)

    # --- build + restore the net ---
    # The checkpoint was saved from an nn.DataParallel-wrapped model, so its keys carry a "module."
    # prefix; wrap the same way and load with strict=False (exactly as the reference test.py does).
    net = IR2Unet.IR2Unet()
    net = nn.DataParallel(net)
    state = torch.load(ckpt, map_location=device)
    net.load_state_dict(state, strict=False)
    net.to(device)
    net.eval()

    with torch.no_grad():
        latest_out, _all_out = net(x)

    pred = latest_out.squeeze(0).squeeze(0).to("cpu").numpy()  # (X, Y, Z), padded grid

    # crop back to the original grid, mask, write on the INPUT affine/header
    chi = crop_pad(pred, npad).astype(np.float32)
    chi = chi * (mask > 0)

    os.makedirs(os.path.dirname(os.path.abspath(out_chi)), exist_ok=True)
    nib.save(nib.Nifti1Image(chi, field_img.affine, field_img.header), out_chi)


if __name__ == "__main__":
    main()
