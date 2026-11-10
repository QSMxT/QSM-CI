# toolbox-pipeline-decompose-qsmci: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=decompose-pipeline
# STISuite_V3.0/STISuite_V3.0; MEDI_toolbox-2024.11.26 (BET and its bet2 sources); NIfTI_20140122.
# The model functions: decompose_utils/ here, a copy of decompose-qsm's (Tim Ho's).
FID_SOURCES="FID_STI FID_MEDI FID_NIFTI"
FID_MATLAB_PATH="sti medi/bet2 decompose_utils nifti"
FID_MCC_A="sti medi/bet2/bet2.mexa64"   # STI Suite is pcode; the mex is built below
FID_WHICH="BET bet2 MRPhaseUnwrap V_SHARP QSM_star lsqlin lsqnonlin signalModel objective1 objective2 objective3 pscModel dscModel complex_to_real"
FID_SBATCH="--mem=64G --time=12:00:00"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/medi/bet2"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp -r "$FID_STI/Core_Functions_P" "$D/sti"
    cp -r "$FID_MEDI/functions/bet2/." "$D/medi/bet2/"
    rm -f "$D/medi/bet2/"*.mex*
    cp -r "$2/decompose_utils" "$D/decompose_utils"   # vendored, byte-identical to decompose-qsm's
}

mex_bet2() { mat "mex_bet2('$1/medi/bet2')"; rm -f "$1/medi/bet2/runmex.m"; }
fid_build_hook() { mex_bet2 "$1"; }
fid_setup_hook() { mex_bet2 "$1"; }
