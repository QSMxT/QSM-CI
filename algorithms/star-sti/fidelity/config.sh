# star-sti: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=matlab-sti-star
FID_SOURCES="FID_STI FID_NIFTI"   # STISuite_V3.0/STISuite_V3.0; Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="nifti sti kiwi sparsa"
# STI Suite is pcode: mcc can't trace into it. QSM_star also needs two Support_Functions folders that
# Core_Functions_P lacks: qsm_kiwi_1 (the @iFDF operator class and its siblings) and SpaRSA (soft
# thresholding for its sparsa_solver_kspace_HW), its solver code without the demo scripts.
FID_MCC_A="sti kiwi sparsa"
FID_WHICH="QSM_star iFDF soft padarray"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/sparsa"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp -r "$FID_STI/Core_Functions_P" "$D/sti"
    cp -r "$FID_STI/Support_Functions/qsm_kiwi_1" "$D/kiwi"
    find "$FID_STI/Support_Functions/SpaRSA" -maxdepth 1 -name '*.m' ! -name 'demo_*' -exec cp {} "$D/sparsa/" \;
}
