# toolbox-pipeline-medi-cornell: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=matlab-medi-pipeline
FID_SOURCES="FID_MEDI FID_NIFTI"   # MEDI_toolbox-2024.11.26 (the folder holding functions/); Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="nifti +medi"      # +: MEDI's subfolders too (bet2/)
# The two mex files the chain calls, compiled from the shipped sources (BUILD.md §2).
FID_MCC_A="medi/mexUnwrap.mexa64 medi/bet2/bet2.mexa64"
FID_WHICH="Fit_ppm_complex unwrapPhase mexUnwrap BET bet2 PDF arlo extract_CSF MEDI_L1 parse_QSM_input gradient_mask dataterm_mask cgsolve reg_CSF SMV sphere_kernel store_CG_results"

# Bunya's g++ 11 builds bet2's mex against GLIBCXX_3.4.29; R2023b loads its own older libstdc++
# first (GLIBCXX_3.4.28), so licensed MATLAB preloads the host's, MathWorks' workaround. The image
# builds its mex with its own compiler and does not need it.
FID_MATLAB_ENV="LD_PRELOAD=/usr/lib64/libstdc++.so.6"
fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp -r "$FID_MEDI/functions" "$D/medi"
    # As medi-cornell: MEDI_L1 names store_CG_results in a debug branch it never takes.
    [ -e "$D/medi/store_CG_results.m" ] || printf 'function store_CG_results(varargin)\nend\n' > "$D/medi/store_CG_results.m"
    # The shipped binaries are not used: both mex files are rebuilt from source below.
    rm -f "$D/medi/mexUnwrap.mexa64" "$D/medi/bet2/bet2.mexa64"
}

mex_all() { mat "cd('$1/medi'); mex mexUnwrap.c; mex_bet2('$1/medi/bet2')"; }
fid_build_hook() { mex_all "$1"; }
fid_setup_hook() { mex_all "$1"; }
