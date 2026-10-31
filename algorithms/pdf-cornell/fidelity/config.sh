# pdf-cornell: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=matlab-medi-pdf
FID_SOURCES="FID_MEDI FID_NIFTI"   # MEDI_toolbox-2024.11.26 (the folder holding functions/); Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="nifti medi"
FID_MCC_A=""                       # plain .m: mcc traces them
FID_WHICH="PDF Fit_ppm_complex dipole_kernel dipole_term cgsolve padarray"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/medi"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp "$FID_MEDI"/functions/{PDF,Fit_ppm_complex,dipole_kernel,dipole_term,cgsolve}.m "$D/medi/"
}
