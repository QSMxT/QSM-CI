# medi-cornell: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=matlab-medi
FID_SOURCES="FID_MEDI FID_NIFTI"   # Cornell MEDI toolbox (its folder holding functions/); NIfTI_20140122
FID_MATLAB_PATH="nifti medi"
FID_MCC_A=""
FID_WHICH="MEDI_L1 parse_QSM_input gradient_mask dataterm_mask cgsolve store_CG_results"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp -r "$FID_MEDI/functions" "$D/medi"
    # BUILD.md §1: MEDI_L1 names store_CG_results in a debug branch QSM-CI never takes, and the
    # toolbox doesn't ship it, so mcc needs a stub to resolve it.
    [ -e "$D/medi/store_CG_results.m" ] || printf 'function store_CG_results(varargin)\nend\n' > "$D/medi/store_CG_results.m"
}
