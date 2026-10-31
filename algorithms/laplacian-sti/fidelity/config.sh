# laplacian-sti: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=matlab-sti-laplacian
FID_SOURCES="FID_STI FID_NIFTI"   # STISuite_V3.0/STISuite_V3.0; Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="nifti sti"
FID_MCC_A="sti"                   # STI Suite is pcode: mcc can't trace into it
FID_WHICH="MRPhaseUnwrap padarray"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp -r "$FID_STI/Core_Functions_P" "$D/sti"
}
