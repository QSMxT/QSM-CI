#!/usr/bin/env python3
"""wraps4d.py REF CAND MASK — Compare two unwrapped-phase NIfTIs (3-D or 4-D) inside a mask, modulo 2π offsets.
For each volume: k = round((a-b)/2π) per voxel; within each 6-connected component of the mask the
most common k is the allowed offset (both PRELUDE outputs are defined up to 2πk per connected set);
report voxels whose k differs from it, the non-integer residual, and NRMSE after the offset."""
import sys, numpy as np, nibabel as nib
from scipy import ndimage
a = nib.load(sys.argv[1]).get_fdata(); b = nib.load(sys.argv[2]).get_fdata()
m = nib.load(sys.argv[3]).get_fdata() > 0
if a.ndim == 3: a = a[..., None]
if b.ndim == 3: b = b[..., None]
lab, n = ndimage.label(m)
for e in range(a.shape[3]):
    A, B = a[..., e], b[..., e]
    d = (A - B)[m]; k = np.round(d / (2*np.pi)); res = d - 2*np.pi*k
    kfull = np.zeros(m.shape); kfull[m] = k
    off = np.zeros(m.shape)
    for c in range(1, n+1):
        sel = lab == c
        vals, cnt = np.unique(kfull[sel], return_counts=True)
        off[sel] = vals[np.argmax(cnt)]
    Bo = B + 2*np.pi*off
    wrong = (kfull != off)[m]
    diff = (A - Bo)[m]
    nrmse = 100*np.linalg.norm(diff)/np.linalg.norm(A[m])
    print(f"vol {e}: components {n}, voxels {m.sum()}, wrap-count differs {wrong.sum()} "
          f"({100*wrong.mean():.4f} %), |non-integer residual| max {np.abs(res).max():.2e} rad, "
          f"NRMSE after offset {nrmse:.4f} %, max |Δ| {np.abs(diff).max():.3f} rad")
