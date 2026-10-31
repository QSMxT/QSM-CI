# lsqr: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=heidi-lsqr
FID_SOURCES="FID_HEIDI FID_NIFTI"   # gitlab.com/R01NS114227/qsm_heidi at 4592631; Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="lsqr nifti"        # inversion_lsqr runs from lsqr/ (its slurm script: matlab -sd lsqr)
FID_MCC_A=""                        # plain .m: mcc traces them
FID_WHICH="computesusceptibility_lsqr generateunitdipoleresponse zealouscrop prepareforconvolution phase2susceptibilityfactor getconstants lsqr"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/lsqr"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp "$FID_HEIDI"/lsqr/*.m "$D/lsqr/"
}
