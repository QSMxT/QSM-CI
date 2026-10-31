# whqsm: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=wh-qsm-v2
FID_SOURCES="FID_FANSI FID_NIFTI"   # gitlab.com/cmilovic/FANSI-toolbox at 93044a3; Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="nifti fansi"
FID_MCC_A=""                        # plain .m: mcc traces them
FID_WHICH="WH_nlTV dipole_kernel_angulated"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/fansi"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp "$FID_FANSI/Inversion/WH-QSM/WH_nlTV.m" "$D/fansi/"
    cp "$FID_FANSI/dipole_kernel_angulated.m" "$D/fansi/"
}
