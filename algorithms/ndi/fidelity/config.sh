# ndi: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=ndi-v2
FID_SOURCES="FID_FANSI FID_NIFTI"   # gitlab.com/cmilovic/FANSI-toolbox at 93044a3; Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="nifti fansi"
FID_MCC_A=""                        # plain .m: mcc traces them
FID_WHICH="ndi dipole_kernel_angulated susc2field"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/fansi"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp "$FID_FANSI"/Inversion/eNDI/{ndi,susc2field}.m "$D/fansi/"
    cp "$FID_FANSI/Metrics/compute_rmse.m" "$D/fansi/"
    cp "$FID_FANSI/imagesc3d2.m" "$D/fansi/"
    cp "$FID_FANSI/dipole_kernel_angulated.m" "$D/fansi/"
}
