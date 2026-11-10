# toolbox-pipeline-chisep: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=chisep-pipeline
# χ-separation toolbox v1.1.3 (functions/, utils/); STISuite_V3.0/STISuite_V3.0; MEDI_toolbox-2024.11.26;
# NIfTI_20140122; mritools 4.7.1 (ubuntu-22.04 release, unpacked: bin/romeo and matlab/ROMEO.m)
FID_SOURCES="FID_CHISEP_TB FID_STI FID_MEDI FID_NIFTI FID_MRITOOLS"
# The toolbox first, as in chisep-ilsqr: its utils/ shadow the NIfTI loaders.
FID_MATLAB_PATH="+chisep sti medi medi/bet2 mritools nifti"
FID_MCC_A="sti chisep medi mritools"   # pcode (STI, χ-sep) and the code pcode calls (MEDI, ROMEO.m)
FID_WHICH="tukey_windowing Preprocessing4Phase BET bet2 use_arlo r2star_arlo r2star_nnls extract_CSF ROMEO V_SHARP QSM_iLSQR chi_sep_iLSQR chi_sep_MEDI MEDI_L1 load_untouch_nii save_untouch_nii make_nii save_nii"
FID_SBATCH="--mem=64G"
FID_ENV="MRITOOLS_ROMEO=$FID_MRITOOLS/bin/romeo"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/chisep" "$D/medi/bet2" "$D/mritools"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp -r "$FID_STI/Core_Functions_P" "$D/sti"
    cp -r "$FID_CHISEP_TB/functions" "$FID_CHISEP_TB/utils" "$D/chisep/"
    # As chisep-medi: MEDI's top-level functions only (no MEDI_L1ss*, which needs the Symbolic Math
    # Toolbox), plus BET and the bet2 sources, whose mex is built below and whose runmex.m (it
    # calls `mex`, which cannot be deployed) is removed after.
    find "$FID_MEDI/functions" -maxdepth 1 -type f -name '*.m' ! -name 'MEDI_L1ss*' -exec cp {} "$D/medi/" \;
    [ -e "$D/medi/store_CG_results.m" ] || printf 'function store_CG_results(varargin)\nend\n' > "$D/medi/store_CG_results.m"
    cp -r "$FID_MEDI/functions/bet2/." "$D/medi/bet2/"
    rm -f "$D/medi/bet2/"*.mex*
    cp "$FID_MRITOOLS/matlab/ROMEO.m" "$D/mritools/"
}

mex_bet2() { mat "mex_bet2('$1/medi/bet2')"; rm -f "$1/medi/bet2/runmex.m"; }
fid_build_hook() { mex_bet2 "$1"; }
fid_setup_hook() { mex_bet2 "$1"; }
