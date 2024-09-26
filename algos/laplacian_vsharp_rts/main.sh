#!/usr/bin/env bash
#DOCKER_IMAGE=ubuntu:latest

# == References ==
# - Unwrapping algorithm - Laplacian: Schofield MA, Zhu Y. Fast phase unwrapping algorithm for interferometric applications. Optics letters. 2003 Jul 15;28(14):1194-6. doi:10.1364/OL.28.001194")
# - Unwrapping algorithm - Laplacian: Zhou D, Liu T, Spincemaille P, Wang Y. Background field removal by solving the Laplacian boundary value problem. NMR in Biomedicine. 2014 Mar;27(3):312-9. doi:10.1002/nbm.3064")
# - Background field removal - V-SHARP: Wu B, Li W, Guidon A et al. Whole brain susceptibility mapping using compressed sensing. Magnetic resonance in medicine. 2012 Jan;67(1):137-47. doi:10.1002/mrm.23000
# - QSM algorithm - RTS: Kames C, Wiggermann V, Rauscher A. Rapid two-step dipole inversion for susceptibility mapping with sparsity priors. Neuroimage. 2018 Feb 15;167:276-83. doi:10.1016/j.neuroimage.2017.11.018
# - Julia package - NIfTI: JuliaNeuroscience. GitHub; 2021. https://github.com/JuliaNeuroscience/NIfTI.jl
# - Julia package - QSM: Kames C. kamesy/QSM.jl. GitHub; 2024. https://github.com/kamesy/QSM.jl

echo "[INFO] Downloading Julia"
apt-get update
apt-get install wget -y
wget https://julialang-s3.julialang.org/bin/linux/x64/1.9/julia-1.9.4-linux-x86_64.tar.gz
tar xf julia-1.9.4-linux-x86_64.tar.gz

echo "[INFO] Installing Julia packages"
julia-1.9.4/bin/julia install_packages.jl

echo "[INFO] Starting reconstruction with QSM.jl"
julia-1.9.4/bin/julia pipeline.jl

echo "[INFO] Moving output to expected location"
mkdir -p output
mv out.nii.gz output/chimap.nii.gz

