# decompose-qsm: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=decompose-qsm
FID_SOURCES="FID_NIFTI"            # Jimmy Shen NIfTI_20140122; decompose_utils/ is vendored here
FID_MATLAB_PATH="nifti decompose_utils"
FID_MCC_A="decompose_utils"
FID_WHICH="lsqcurvefit optimoptions parpool gcp"
# The fit is per voxel and independent between voxels, so a central box checks it as well as the
# whole brain would, in a fraction of the time (the full fit takes hours on 8 cores).
FID_ENV="DECOMPOSE_CROPBOX=32"
FID_SBATCH="--time=04:00:00"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp -r "$2/decompose_utils" "$D/decompose_utils"
}
