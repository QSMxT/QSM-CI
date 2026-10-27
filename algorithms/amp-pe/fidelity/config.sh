# amp-pe: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=amp-pe
FID_SOURCES="FID_AMPPE FID_NIFTI"   # EmoryCN2L/QSM_AMP_PE at 15bf8dc; Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="nifti functions +amp_pe_qsm"
# BUILD.md §1: wfilters reaches dbwavf through a dynamic feval, which mcc can't follow.
FID_MCC_A="nifti functions amp_pe_qsm @toolbox/wavelet/wavelet/dbwavf.m"
FID_WHICH="wavedec3 waverec3 wfilters dbwavf dwtmode orthfilt"
FID_SBATCH="--time=03:00:00"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/functions"
    git -C "$FID_AMPPE" rev-parse --short HEAD | grep -qx 15bf8dc || { echo "QSM_AMP_PE is not at 15bf8dc"; return 1; }
    cp -r "$FID_AMPPE"/amp_pe_qsm "$D/"
    cp "$FID_AMPPE"/functions/{GenerateDipoleFT3Drot,SI_operator_withmask}.m "$D/functions/"
    cp "$FID_AMPPE"/functions/PDF_imp/{fftnc,ifftnc}.m "$D/functions/"
    cp "$FID_AMPPE"/functions/from_FANSI/{dipole_kernel_angulated,chiL2}.m "$D/functions/"
    cp -r "$FID_NIFTI" "$D/nifti"
}
