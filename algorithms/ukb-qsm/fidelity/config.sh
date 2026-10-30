# ukb-qsm: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=matlab-ukb-qsm
FID_SOURCES="FID_STI FID_NIFTI"   # STISuite_V3.0/STISuite_V3.0; Jimmy Shen NIfTI_20140122; ukb/ is vendored here
FID_MATLAB_PATH="nifti sti ukb"
FID_MCC_A="sti ukb"               # STI Suite is pcode: mcc can't trace into it
FID_WHICH="MRPhaseUnwrap V_SHARP QSM_iLSQR bwareaopen imclose imdilate imerode imfill padarray strel"
FID_SBATCH="--mem=48G --time=03:00:00"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp -r "$FID_STI/Core_Functions_P" "$D/sti"
    cp -r "$2/ukb" "$D/ukb"
    rm -f "$D/ukb/UKBiobank_QSM.m.reference"
}
