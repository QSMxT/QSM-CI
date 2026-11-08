#!/bin/bash
#SBATCH --job-name=qsmci-repro-prep
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --output=slurm-%x-%j.out

# Before a streamed matrix (STREAM_PUBLISH=1): register every acquisition to its subject's target and
# SynthSeg each target, once. Each shard's `repro_eval.py stats --runs` then only reads the transforms
# and segmentations; without this, the 16 shards of one acquisition would each register it at once and
# race on the same .tfm. Idempotent: existing transforms and segmentations are kept.
source ~/venvs/qsmci/bin/activate
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"

python scripts/repro_eval.py register
# mri_synthseg (robust, license-free) on each subject's registration target, via the Bunya FreeSurfer
# MODULE — this node's unprivileged apptainer can't build a SIF from the large FreeSurfer OCI image
# (mksquashfs proot ptrace failure), so run it natively. Then install on the target grid.
for align in data/harmonization/_align/*/; do
    [ -f "$align/dseg.nii.gz" ] && continue
    ( source /etc/profile.d/modules.sh && module load freesurfer/7.3.2 && \
      mri_synthseg --i "$PWD/$align/target_mag_e1.nii.gz" \
                   --o "$PWD/$align/dseg_synthseg.nii.gz" --robust --threads 8 )
    python - "$align" <<'PY'
import sys
import SimpleITK as sitk
align = sys.argv[1]
fixed = sitk.ReadImage(f"{align}/target_mag_e1.nii.gz")
seg = sitk.ReadImage(f"{align}/dseg_synthseg.nii.gz")
res = sitk.Resample(seg, fixed, sitk.Transform(), sitk.sitkNearestNeighbor, 0)
sitk.WriteImage(res, f"{align}/dseg.nii.gz")
PY
done
echo "prep: $(ls data/harmonization/_align/*.tfm | wc -l) transforms, $(ls data/harmonization/_align/*/dseg.nii.gz | wc -l) segmentations"
