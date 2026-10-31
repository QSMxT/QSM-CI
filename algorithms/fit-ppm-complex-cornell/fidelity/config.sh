# fit-ppm-complex-cornell: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=matlab-medi-fitppm
FID_SOURCES="FID_MEDI FID_NIFTI"   # MEDI_toolbox-2024.11.26 (the folder holding functions/); Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="nifti medi"
FID_MCC_A="medi/mexUnwrap.mexa64"  # the mex unwrapPhase.m calls, compiled from the shipped source (BUILD.md)
FID_WHICH="Fit_ppm_complex unwrapPhase mexUnwrap arlo"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/medi"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp "$FID_MEDI"/functions/{Fit_ppm_complex.m,unwrapPhase.m,arlo.m,mexUnwrap.c} "$D/medi/"
}

# BUILD.md §2: compiled from the shipped source, as lbv-cornell's mexMGv6 (whose shipped binary
# predates its source).
fid_build_hook() { mat "cd('$1/medi'); mex mexUnwrap.c"; }
fid_setup_hook() { mat "cd('$1/medi'); mex mexUnwrap.c"; }
