#!/usr/bin/env bash
set -e

echo "[INFO] Starting combined Laplacian V-SHARP + MEDI pipeline"

input_dir=${1:-/workdir}
output_dir=${2:-/workdir/output}

echo "[DEBUG] Input: $input_dir"
echo "[DEBUG] Output: $output_dir"

mkdir -p "$output_dir/tmp" "$output_dir"

# --- Julia Setup ---
echo "[INFO] Downloading Julia..."
apt-get update
apt-get install wget build-essential libfftw3-dev -y
wget -q https://julialang-s3.julialang.org/bin/linux/x64/1.9/julia-1.9.4-linux-x86_64.tar.gz
tar xf julia-1.9.4-linux-x86_64.tar.gz
JULIA_BIN=/workdir/julia-1.9.4/bin/julia

$JULIA_BIN --version

# --- Laplacian with own environment for the dependencies---
echo "[INFO] Installing Laplacian environment..."
echo "[DEBUG] Listing /workdir/laplacian_env:"
ls -la /workdir/laplacian_env
$JULIA_BIN --project=/workdir/laplacian_env /workdir/laplacian_env/install_packages_laplacian.jl

echo "[INFO] Running Laplacian pipeline..."
$JULIA_BIN --project=/workdir/laplacian_env /workdir/pipeline_laplacian.jl \
    --input "$input_dir" \
    --output "$output_dir/tmp"

# --- MEDI with own environment for the dependencies---
echo "[INFO] Installing MEDI environment..."
$JULIA_BIN --project=/workdir/medi_env /workdir/medi_env/install_packages_medi.jl


echo "[INFO] Running MEDI pipeline..."
$JULIA_BIN --project=/workdir/medi_env /workdir/pipeline_medi.jl \
    --input "$output_dir/tmp" \
    --output "$output_dir"

echo "[INFO] Done. Checking final output..."
ls -lh "$output_dir"


