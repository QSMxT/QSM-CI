#!/bin/bash
#SBATCH --job-name=qsmci-pack-emtp
#SBATCH --account=a_ai_collab
#SBATCH --partition=general
#SBATCH --qos=normal
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
# One task per acquisition: CPU HD-BET takes ~10+ min a volume, so 72 in series would be ~12 h.
#SBATCH --array=0-71%36
#SBATCH --output=slurm-%x-%A_%a.out

# Pack the EMTP traveling-head drop into data/harmonization/<acq>/inputs and HD-BET-mask each
# acquisition (CPU apptainer), one array task per acquisition. Re-runnable: packed acquisitions are
# kept, missing masks filled in.
#   sbatch scripts/repro_slurm/pack_emtp.slurm /path/to/03_Analysis_Shared
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt   # before set -u (conda gotcha)
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export APPTAINER_CACHEDIR=/scratch/user/uqaste15/apptainer_cache
export QSMCI_SANDBOX_DIR=/scratch/project_mnt/S0169/qsmci_sif   # prebuilt hd-bet .sif: Bunya's apptainer can't convert OCI images

RAW=${1:?usage: sbatch $0 <03_Analysis_Shared dir>}
mapfile -t ACQS < <(python -c "
import json
reg = json.load(open('scripts/datasets.json'))
print('\n'.join(sorted(k for k, v in reg.items() if v.get('track') == 'repro' and k.startswith('s0'))))")
ACQ=${ACQS[$SLURM_ARRAY_TASK_ID]}
echo "== $ACQ"
python scripts/pack_emtp.py --raw "$RAW" --out "data/harmonization" --only "$ACQ" --skip-existing --runner apptainer
