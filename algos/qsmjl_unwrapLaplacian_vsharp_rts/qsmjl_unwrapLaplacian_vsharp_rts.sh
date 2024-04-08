#!/usr/bin/env bash

# 
# Submission: qsmjl_unwrapLaplacian_vsharp_rts
# 
# == References ==
# - Julia package - QSM.jl: kamesy. GitHub; 2022. https://github.com/kamesy/QSM.jl
# - Julia package - NIfTI: JuliaNeuroscience. GitHub; 2021. https://github.com/JuliaNeuroscience/NIfTI.jl
# 

set -e

# create output directory
PIPELINE_NAME="$(basename "$0" .sh)"
mkdir -p "recons/${PIPELINE_NAME}"

echo "[INFO] Downloading Julia"
sudo wget https://julialang-s3.julialang.org/bin/linux/x64/1.9/julia-1.9.4-linux-x86_64.tar.gz
sudo tar xf julia-1.9.4-linux-x86_64.tar.gz

echo "[INFO] Installing Julia packages"
julia-1.9.4/bin/julia ./algos/qsmjl_unwrapLaplacian_vsharp_rts/install_packages.jl

echo "[INFO] Starting reconstruction with QSM.jl"
julia-1.9.4/bin/julia ./algos/qsmjl_unwrapLaplacian_vsharp_rts/pipeline.jl
