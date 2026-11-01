# hdqsm: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=hd-qsm-v2
FID_SOURCES="FID_HDQSM FID_FANSI FID_NIFTI"   # github.com/mglambert/HD-QSM at c456a94; FANSI-toolbox 93044a3 (the kernel); NIfTI_20140122
FID_MATLAB_PATH="nifti hdqsm"
FID_MCC_A=""                                  # plain .m: mcc traces them
FID_WHICH="HDQSM dipole_kernel_angulated"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/hdqsm"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp "$FID_HDQSM/HDQSM.m" "$FID_FANSI/dipole_kernel_angulated.m" "$D/hdqsm/"
}
