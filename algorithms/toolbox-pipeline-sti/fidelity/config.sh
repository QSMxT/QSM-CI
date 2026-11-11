# toolbox-pipeline-sti: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=sti-pipeline
FID_SOURCES="FID_STI FID_NIFTI"   # STISuite_V3.0/STISuite_V3.0; Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="nifti sti"
FID_MCC_A="sti"                   # STI Suite is pcode: mcc can't trace into it
FID_WHICH="MRPhaseUnwrap V_SHARP PolishMask QSM_iLSQR graythresh bwlabeln regionprops imfill imclose imdilate imerode padarray strel"
FID_SBATCH="--mem=32G"

# Core_Functions_P (MRPhaseUnwrap, V_SHARP, QSM_iLSQR and their helpers) and GUI_Functions_P's
# PolishMask, the one GUI function the pipeline calls outside the GUI's figures. Not
# Support_Functions/ (its wavelet_src/sfb3D_A.m breaks mcc's parser; thresh_tool's level is written
# out in recon.m).
fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp -r "$FID_STI/Core_Functions_P" "$D/sti"
    cp "$FID_STI/GUI_Functions_P/PolishMask.p" "$D/sti/"
}
