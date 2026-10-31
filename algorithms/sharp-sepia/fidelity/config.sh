# sharp-sepia: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=matlab-sharp-sepia
FID_SOURCES="FID_SEPIA FID_MEDI FID_NIFTI"   # kschan0214/sepia db939cc; MEDI_toolbox-2024.11.26; Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="nifti sepia medi"
FID_MCC_A=""                                 # all plain .m: mcc traces them
FID_WHICH="SHARP zeropad_odd_dimension SMV SMV_kernel sphere_kernel padarray"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/sepia" "$D/medi"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp "$FID_SEPIA/misc/background_removal/SHARP/SHARP.m" "$FID_SEPIA/utils/zeropad_odd_dimension.m" "$D/sepia/"
    cp "$FID_MEDI/functions/SMV.m" "$FID_MEDI/functions/SMV_kernel.m" "$FID_MEDI/functions/sphere_kernel.m" "$D/medi/"
}
