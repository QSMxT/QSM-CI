#!/bin/bash
#SBATCH --job-name=qsmci-repro-post
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slurm-%x-%j.out

# After the matrix array: merge the per-shard run files into results/index.json, then the
# reproducibility evaluation (register -> SynthSeg -> ROI stats -> ax+b fits), then tar the
# take-home payload (small JSONs + alignment artifacts; recon volumes stay in scratch).
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt   # before set -u (conda gotcha)
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export APPTAINER_CACHEDIR=/scratch/user/uqaste15/apptainer_cache

# ---- merge shard run files (upsert by run id, order preserved) ----------------------------------
python - <<'EOF'
import glob, json, time
from pathlib import Path
idx_p = Path("results/index.json")
doc = json.loads(idx_p.read_text()) if idx_p.exists() else {"runs": []}
runs = {r["id"]: r for r in doc.get("runs", [])}
order = [r["id"] for r in doc.get("runs", [])]
n_new = 0
for f in sorted(glob.glob("results/runs-repro-*.json")):
    for r in json.loads(Path(f).read_text()):
        if r["id"] not in runs:
            order.append(r["id"])
            n_new += 1
        runs[r["id"]] = r
doc["runs"] = [runs[i] for i in order]
doc["generated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
idx_p.write_text(json.dumps(doc, indent=2) + "\n")
print(f"merged {len(glob.glob('results/runs-repro-*.json'))} shard files "
      f"({n_new} new runs, {len(order)} total)")
EOF

# ---- reproducibility evaluation ------------------------------------------------------------------
python scripts/repro_eval.py register
# mri_synthseg (robust, license-free) on the registration target, via the Bunya FreeSurfer MODULE
# — this node's unprivileged apptainer can't build a SIF from the large FreeSurfer OCI image
# (mksquashfs proot ptrace failure), so run it natively. Then install on the target grid.
if [ ! -f data/harmonization/_align/dseg.nii.gz ]; then
    ( source /etc/profile.d/modules.sh && module load freesurfer/7.3.2 && \
      mri_synthseg --i "$PWD/data/harmonization/_align/target_mag_e1.nii.gz" \
                   --o "$PWD/data/harmonization/_align/dseg_synthseg.nii.gz" --robust --threads 8 )
    python - <<'EOF'
import SimpleITK as sitk
fixed = sitk.ReadImage("data/harmonization/_align/target_mag_e1.nii.gz")
seg = sitk.ReadImage("data/harmonization/_align/dseg_synthseg.nii.gz")
res = sitk.Resample(seg, fixed, sitk.Transform(), sitk.sitkNearestNeighbor, 0)
sitk.WriteImage(res, "data/harmonization/_align/dseg.nii.gz")
EOF
fi
python scripts/repro_eval.py stats
python scripts/repro_eval.py fits

# ---- take-home payload ---------------------------------------------------------------------------
tar czf repro_payload.tar.gz \
    results/index.json results/repro_rois.json results/repro.json \
    data/harmonization/_align
echo "payload: $(pwd)/repro_payload.tar.gz"
