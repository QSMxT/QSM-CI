#!/usr/bin/env bash
#DOCKER_IMAGE=vnmd/qsmxt_6.2.0:20231012

# == References ==
# - QSMxT: Stewart AW, Robinson SD, O'Brien K, et al. QSMxT: Robust masking and artifact reduction for quantitative susceptibility mapping. Magnetic Resonance in Medicine. 2022;87(3):1289-1300. doi:10.1002/mrm.29048
# - QSMxT: Stewart AW, Bollman S, et al. QSMxT/QSMxT. GitHub; 2022. https://github.com/QSMxT/QSMxT
# - Python package - Nipype: Gorgolewski K, Burns C, Madison C, et al. Nipype: A Flexible, Lightweight and Extensible Neuroimaging Data Processing Framework in Python. Frontiers in Neuroinformatics. 2011;5. Accessed April 20, 2022. doi:10.3389/fninf.2011.00013
# - Unwrapping algorithm - ROMEO: Dymerska B, Eckstein K, Bachrata B, et al. Phase unwrapping with a rapid opensource minimum spanning tree algorithm (ROMEO). Magnetic Resonance in Medicine. 2021;85(4):2294-2308. doi:10.1002/mrm.28563
# - QSM algorithm - NeXtQSM: Cognolato, F., O'Brien, K., Jin, J. et al. (2022). NeXtQSM—A complete deep learning pipeline for data-consistent Quantitative Susceptibility Mapping trained with hybrid data. Medical Image Analysis, 102700. doi:10.1016/j.media.2022.102700
# - Julia package - MriResearchTools: Eckstein K. korbinian90/MriResearchTools.jl. GitHub; 2022. https://github.com/korbinian90/MriResearchTools.jl
# - Python package - nibabel: Brett M, Markiewicz CJ, Hanke M, et al. nipy/nibabel. GitHub; 2019. https://github.com/nipy/nibabel
# - Python package - numpy: Harris CR, Millman KJ, van der Walt SJ, et al. Array programming with NumPy. Nature. 2020;585(7825):357-362. doi:10.1038/s41586-020-2649-2

#!/usr/bin/env bash
set -e

echo "[INFO] Starting QSM-CI MEDI pipeline"

# Input / Output handling
input_dir=${1:-/workdir/bids}
output_dir=${2:-/workdir/output}
input_dir=$(realpath "$input_dir" 2>/dev/null || echo "$input_dir")
output_dir=$(realpath "$output_dir" 2>/dev/null || echo "$output_dir")

echo "[DEBUG] Using input: $input_dir"
echo "[DEBUG] Using output: $output_dir"

# Julia project setup
echo "[INFO] Installing Julia packages for MEDI (local project)"
julia --project=/workdir/medi_julia /workdir/install_packages.jl

# Run the MEDI pipeline
echo "[INFO] Running MEDI pipeline..."
julia --project=/workdir/medi_julia /workdir/pipeline_medi.jl \
    --input "$input_dir" \
    --output "$output_dir"

# Move output to expected location
echo "[INFO] Checking output..."
mkdir -p "$output_dir"
if [ -f "$output_dir/chimap.nii.gz" ]; then
    echo "[INFO] Found chimap.nii.gz in $output_dir"
else
    echo "[WARNING] No output file generated!"
fi

echo "[INFO] MEDI pipeline completed successfully"



