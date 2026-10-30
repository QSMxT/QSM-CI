# chisep-ilsqr: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=chi-sep-ilsqr
# SNU-LIST χ-separation toolbox (its folder holding functions/ and utils/); STISuite_V3.0/STISuite_V3.0;
# Jimmy Shen NIfTI_20140122
FID_SOURCES="FID_CHISEP_TB FID_STI FID_NIFTI"
# The toolbox first, as its own scripts and the original build put it: its utils/ carry their own
# copies of the NIfTI loaders (and medfilt3), which shadow the others.
FID_MATLAB_PATH="+chisep sti nifti"
FID_MCC_A="sti chisep"            # both are pcode: mcc can't trace into them
FID_WHICH="chi_sep_iLSQR QSM_iLSQR load_untouch_nii save_untouch_nii medfilt3 hann hanning imclose imdilate imerode imopen padarray strel tukeywin"
FID_SBATCH="--mem=64G"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/chisep"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp -r "$FID_STI/Core_Functions_P" "$D/sti"
    cp -r "$FID_CHISEP_TB/functions" "$FID_CHISEP_TB/utils" "$D/chisep/"
}
