# chisep-medi: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=chi-sep-medi
# SNU-LIST χ-separation toolbox (its folder holding functions/ and utils/); Cornell MEDI toolbox
# 2024.11.26 (its folder holding functions/); Jimmy Shen NIfTI_20140122
FID_SOURCES="FID_CHISEP_TB FID_MEDI FID_NIFTI"
# The toolbox first, as its own scripts and the original build put it: its utils/ carry their own
# copies of the NIfTI loaders (and medfilt3), which shadow the others.
FID_MATLAB_PATH="+chisep medi nifti"
FID_MCC_A="medi chisep"           # chi_sep_MEDI is pcode and calls MEDI: mcc can't trace into it
FID_WHICH="chi_sep_MEDI MEDI_L1 load_untouch_nii save_untouch_nii medfilt3 hann hanning imclose imdilate imerode imopen padarray strel tukeywin"
FID_SBATCH="--mem=64G"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/chisep"
    cp -r "$FID_NIFTI" "$D/nifti"
    # MEDI's top-level functions only: -a medi bundles the whole folder, and its bet2/ (MEDI's BET
    # mex, which calls `mex`) and other subfolders are code chi_sep_MEDI never reaches. MEDI_L1ss*
    # (a solver variant that calls the Symbolic Math Toolbox's heaviside, which can't be deployed)
    # is left out for the same reason.
    mkdir -p "$D/medi"
    find "$FID_MEDI/functions" -maxdepth 1 -type f -name '*.m' ! -name 'MEDI_L1ss*' -exec cp {} "$D/medi/" \;
    [ -e "$D/medi/store_CG_results.m" ] || printf 'function store_CG_results(varargin)\nend\n' > "$D/medi/store_CG_results.m"
    cp -r "$FID_CHISEP_TB/functions" "$FID_CHISEP_TB/utils" "$D/chisep/"
}
