#!/usr/bin/env python3
"""Per-pipeline contact sheets: center axial slice of each of the 23 harmonization acquisitions,
for a curated set of pipelines (top sim-leaderboard BFR->dipole combos w/ romeo field-mapping + AMP-PE).
"""
import os, glob
import numpy as np
import nibabel
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.chdir("/scratch/user/uqaste15/qsmci-repro")
OUT = "/scratch/user/uqaste15/contact_sheets"
os.makedirs(OUT, exist_ok=True)

PIPES = [
    "romeo-qsmrs~ismv-qsmrs~hdqsm-qsmrs",
    "romeo-qsmrs~ismv-qsmrs~fansi-nltgv-qsmrs",
    "romeo-qsmrs~ismv-qsmrs~whqsm-qsmrs",
    "romeo-qsmrs~resharp-qsmrs~whqsm-qsmrs",
    "romeo-qsmrs~resharp-qsmrs~hdqsm-qsmrs",
    "romeo-qsmrs~sharp-qsmrs~whqsm-qsmrs",
    "romeo-qsmrs~ismv-qsmrs~fansi-nltv-qsmrs",
    "romeo-qsmrs~resharp-qsmrs~fansi-nltgv-qsmrs",
    "romeo-qsmrs~ismv-qsmrs~amp-pe",
    "romeo-qsmrs~resharp-qsmrs~amp-pe",
]
acqs = sorted(d.split("/")[-2] for d in glob.glob("data/harmonization/*/inputs")
              if "_align" not in d)
WIN = 0.10  # display window in ppm

for pipe in PIPES:
    n = len(acqs); cols = 5; rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 2.4, rows * 2.7))
    axes = np.atleast_1d(axes).ravel()
    for ax in axes:
        ax.axis("off")
    for i, acq in enumerate(acqs):
        ax = axes[i]
        f = f"results/{pipe}-cmp-{acq}/recon.nii.gz"
        if os.path.exists(f):
            d = nibabel.load(f).get_fdata()
            sl = np.rot90(d[:, :, d.shape[2] // 2])
            ax.imshow(sl, cmap="gray", vmin=-WIN, vmax=WIN)
            ax.set_title(acq, fontsize=6)
        else:
            ax.set_title(acq + "  (missing)", fontsize=6, color="red")
    fig.suptitle(f"{pipe}   (center axial, window ±{WIN} ppm)", fontsize=11)
    plt.tight_layout(rect=(0, 0, 1, 0.97))
    p = f"{OUT}/{pipe}.png"
    plt.savefig(p, dpi=110); plt.close()
    have = sum(os.path.exists(f'results/{pipe}-cmp-{a}/recon.nii.gz') for a in acqs)
    print(f"wrote {p}  ({have}/{len(acqs)} acqs present)")
