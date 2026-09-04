#!/bin/bash
#SBATCH --job-name=qsmci-repro-inter-hf
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=4:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=slurm-%x-%j.out

# Upload every staged harmonization intermediate (results/_intermediates/<acq>/) into the same
# qsmxt/qsm-ci-volumes `repro/<acq>/` directory as that acquisition's recons, where the viewer's
# Field map / Local field layers look for them. The HF write token is read from a 0600 file.
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
pip install -q huggingface_hub 2>&1 | tail -1
export HF_TOKEN="$(cat ~/.hf_publish_token)"
export HF_VOLUMES_REPO="qsmxt/qsm-ci-volumes"
echo "publishing $(find results/_intermediates -name '*.nii.gz' 2>/dev/null | wc -l) intermediates"
python scripts/publish_repro_intermediates.py results
echo "publish exit: $?"
