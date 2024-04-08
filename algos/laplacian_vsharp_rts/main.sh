#!/usr/bin/env bash

# 
# Submission: qsmjl_unwrapLaplacian_vsharp_rts
# 
# == References ==
# - Julia package - QSM.jl: kamesy. GitHub; 2022. https://github.com/kamesy/QSM.jl
# - Julia package - NIfTI: JuliaNeuroscience. GitHub; 2021. https://github.com/JuliaNeuroscience/NIfTI.jl
# 

echo "[INFO] Downloading Julia"
apt-get update
apt-get install wget -y
wget https://julialang-s3.julialang.org/bin/linux/x64/1.9/julia-1.9.4-linux-x86_64.tar.gz
tar xf julia-1.9.4-linux-x86_64.tar.gz

echo "[INFO] Installing Julia packages"
julia-1.9.4/bin/julia install_packages.jl

echo "[INFO] Starting reconstruction with QSM.jl"
julia-1.9.4/bin/julia pipeline.jl

