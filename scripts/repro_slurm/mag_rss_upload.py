#!/usr/bin/env python3
"""RSS-combine each harmonization acquisition's multi-echo magnitude into a 3D volume and upload it to
HuggingFace at repro/<acq>/<acq>__magnitude.nii.gz — the per-acquisition reference the viewer's Magnitude
layer loads (deterministic URL, one per acq, shared by every pipeline of that acq). One commit, ~23 files."""
import os, glob
import numpy as np, nibabel
from huggingface_hub import HfApi, CommitOperationAdd

api = HfApi(token=os.environ["HF_QSMXT_KEY"])
REPO = os.environ.get("HF_VOLUMES_REPO", "qsmxt/qsm-ci-volumes")
os.makedirs("/scratch/user/uqaste15/mag_rss", exist_ok=True)
ops = []
for d in sorted(glob.glob("data/harmonization/*/inputs")):
    acq = d.split("/")[-2]
    if acq == "_align":
        continue
    mp = os.path.join(d, "magnitude.nii.gz")
    if not os.path.exists(mp):
        continue
    img = nibabel.load(mp)
    m = np.asanyarray(img.dataobj, dtype="float32")
    rss = np.sqrt(np.sum(m ** 2, axis=3)) if m.ndim == 4 else m   # SNR-weighted structural reference
    out = f"/scratch/user/uqaste15/mag_rss/{acq}__magnitude.nii.gz"
    nibabel.save(nibabel.Nifti1Image(rss.astype("float32"), img.affine), out)
    ops.append(CommitOperationAdd(path_in_repo=f"repro/{acq}/{acq}__magnitude.nii.gz", path_or_fileobj=out))
    print(f"prepared {acq}: {rss.shape}")

api.create_commit(repo_id=REPO, repo_type="dataset", operations=ops,
                  commit_message="Add RSS-combined magnitude per harmonization acquisition (viewer Magnitude layer)")
print(f"uploaded {len(ops)} magnitude volumes to {REPO}")
