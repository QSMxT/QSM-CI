#!/usr/bin/env bash
#DOCKER_IMAGE=ubuntu:18.04

set -euo pipefail
set -x

echo "[INFO] Starting TGV_QSM (old) pipeline"

input_dir=${1:-/workdir}
output_dir=${2:-/workdir/output}

mkdir -p "$output_dir/tmp" "$output_dir"

# --- Julia Setup ---
echo "[INFO] Downloading Julia..."
apt-get update
apt-get install wget build-essential libfftw3-dev -y
wget -q https://julialang-s3.julialang.org/bin/linux/x64/1.9/julia-1.9.4-linux-x86_64.tar.gz
tar xf julia-1.9.4-linux-x86_64.tar.gz
JULIA_BIN=/workdir/julia-1.9.4/bin/julia
$JULIA_BIN --version

# --- Setup Julia environment ---
 $JULIA_BIN --project=/workdir/tgv_old_env /workdir/tgv_old_env/install_packages_tgv_old.jl

# --- Step 1: Combine to 4D ---
echo "[INFO] Running combine_to_4d.jl..."
$JULIA_BIN --project=/workdir/tgv_old_env /workdir/combine_to_4d.jl $output_dir
echo "[INFO] Combine step finished successfully."

# --- Step 2: Run ROMEO ---
$JULIA_BIN --project=/workdir/tgv_old_env /workdir/romeo_unwrapping.jl \
  --phase "$output_dir/sub-1_phase_4D.nii" \
  --mag "$output_dir/sub-1_mag_4D.nii" \
  --mask "bids/derivatives/qsm-forward/sub-1/anat/sub-1_mask.nii" \
  --compute-B0 "$output_dir/sub-1_B0.nii" \
  --correct-global \
  --phase-offset-correction bipolar

echo "[INFO] ROMEO step finished successfully."


# --- Step 3: Convertig to radians ---

echo "[INFO] Converting B0 fieldmap to radians..."

$JULIA_BIN --project=/workdir/tgv_old_env /workdir/fieldmap_to_radians.jl \
    "$output_dir/sub-1_B0.nii" \
    "$output_dir"

echo "[INFO] Conversion to radians finished successfully."

# --- 4) Run TGV ---

# -------------------------
# 1) Basic tools
# -------------------------
echo "[INFO] Installing base packages (wget, bzip2, jq, git, build-essential)..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    wget \
    bzip2 \
    jq \
    git \
    build-essential

# -------------------------
# 3) Compiler Toolchain
# -------------------------

# cc Symlink
if command -v cc &> /dev/null; then
  echo "[INFO] cc already exists: $(which cc)"
else
  echo "[INFO] Linking /usr/bin/cc -> gcc..."
  ln -s /usr/bin/gcc /usr/bin/cc
fi

echo "[INFO] Installing Miniconda2..."

if [ ! -f "Miniconda2-4.6.14-Linux-x86_64.sh" ]; then
  wget https://repo.anaconda.com/miniconda/Miniconda2-4.6.14-Linux-x86_64.sh -O Miniconda2-4.6.14-Linux-x86_64.sh
fi
#instal miniconda
bash Miniconda2-4.6.14-Linux-x86_64.sh -b -u -p miniconda2
miniconda2/bin/conda install -y -c anaconda cython==0.29.4
miniconda2/bin/conda install -y numpy
miniconda2/bin/conda install -y pyparsing
miniconda2/bin/pip install scipy==0.17.1 nibabel==2.1.0
miniconda2/bin/pip install --upgrade cython

# Miniconda-symlink check
if [ -L "/workdir/miniconda2/bin/cc" ]; then
  target=$(readlink /workdir/miniconda2/bin/cc || true)
  if [ "$target" != "/usr/bin/gcc" ]; then
    echo "[INFO] Fixing wrong symlink in miniconda2/bin/cc..."
    rm -f /workdir/miniconda2/bin/cc
    ln -s /usr/bin/gcc /workdir/miniconda2/bin/cc
  else
    echo "[INFO] miniconda2/bin/cc symlink is correct."
  fi
else
  echo "[INFO] Creating symlink miniconda2/bin/cc..."
  ln -s /usr/bin/gcc /workdir/miniconda2/bin/cc
fi

echo "[DEBUG] After symlinks:"
ls -l /usr/bin/cc || true
ls -l /workdir/miniconda2/bin/cc || true

# -------------------------
# 4) Clone / Install TGV_QSM
# -------------------------
if [ ! -d "/workdir/TGV_QSM" ]; then
  echo "[INFO] Cloning TGV_QSM..."
  git clone https://github.com/QSMxT/TGV_QSM.git /workdir/TGV_QSM
else
  echo "[INFO] TGV_QSM already exists, pulling latest..."
  cd /workdir/TGV_QSM && git pull || true
fi

cd /workdir/TGV_QSM
echo "[DEBUG] Files in TGV_QSM:"
ls -lh

echo "[DEBUG] Testing gcc from Python..."
/workdir/miniconda2/bin/python -c "import subprocess; print('Running gcc from Python...'); subprocess.call(['/usr/bin/gcc','--version'])"

echo "[INFO] Installing TGV_QSM via Python..."
PATH=/usr/bin:$PATH /workdir/miniconda2/bin/python setup.py install


# -------------------------
# 5) Run TGV_QSM
# -------------------------
TE=$(jq '.EchoTime[0]' /workdir/inputs.json)
B0=$(jq '.MagneticFieldStrength' /workdir/inputs.json)
cd /workdir
/workdir/miniconda2/bin/tgv_qsm \
  -p /workdir/output/sub-1_radians.nii \
  -m /workdir/bids/derivatives/qsm-forward/sub-1/anat/sub-1_mask.nii \
  -f $B0 \
  -t $TE \
  -o sub-1_QSM \
  --no-resampling

# Move output to output_dir
# mkdir -p "$output_dir/test_copies"
# mv "$output_dir/sub-1_phase_4D.nii"    "$output_dir/test_copies/" || true
# mv "$output_dir/sub-1_mag_4D.nii"      "$output_dir/test_copies/" || true
# mv "$output_dir/sub-1_B0.nii"          "$output_dir/test_copies/" || true
# mv "$output_dir/sub-1_radians.nii"     "$output_dir/test_copies/" || true
# cp "$output_dir"/sub-1*QSM*.nii* "$output_dir/test_copies/" 2>/dev/null || true


echo "[INFO] TGV_QSM finished. Output: $output_dir/sub-1_QSM.nii.gz"