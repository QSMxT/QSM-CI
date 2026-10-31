# resharp: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=resharp
FID_SOURCES="FID_SUN FID_NIFTI"   # github.com/sunhongfu/QSM at c75b138; Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="nifti sun"
FID_MCC_A=""                      # plain .m: mcc traces it
FID_WHICH="resharp padarray cgs"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/sun"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp "$FID_SUN/background_field_removal/resharp.m" "$D/sun/"
}
