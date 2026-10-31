# heidi: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=heidi-heidi
FID_SOURCES="FID_HEIDI FID_NIFTI"   # gitlab.com/R01NS114227/qsm_heidi at 4592631; Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="heidi lsqr nifti"  # inversion_heidi runs from heidi/; the LSQR seed's core is in lsqr/
FID_MCC_A=""                        # plain .m: mcc traces them; the ITK executable is installed in the image
FID_SBATCH="--time=08:00:00"         # NESTA at tolerance eps runs all 8 x 500 iterations: about 100 min in silico
FID_WHICH="computesusceptibility_heidi computesusceptibility_lsqr Core_Nesterov_fs diffusionimagefilter reppath generateunitdipoleresponse discretegradient zealouscrop prepareforconvolution phase2susceptibilityfactor write_nii load_nii_raw lsqr"

# BUILD.md §1. heidi/ keeps the ITK executable and its libraries next to reppath.m, where the
# licensed runs find them; the image installs the same files at /opt/heidi-itk.
fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/heidi" "$D/lsqr" "$D/originals"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp "$FID_HEIDI"/lsqr/*.m "$D/lsqr/"
    cp "$FID_HEIDI"/heidi/*.m "$D/heidi/"
    cp "$FID_HEIDI"/heidi/GradientAnisotropicDiffusionImageFilter "$FID_HEIDI"/heidi/lib*.so.3.20 "$D/heidi/"
    cp "$FID_HEIDI"/heidi/reppath.m "$D/originals/"
    # reppath.m locates the ITK executable next to itself (which('reppath.m')); in the compiled
    # binary that is the extracted archive, so QSMCI_HEIDI_ITK (set by the image) names the folder.
    # Unset, as in the licensed runs, reppath is unchanged.
    perl -0pi -e "s/(function Path = reppath\(\)\r?\n)/\$1    if ~isempty(getenv('QSMCI_HEIDI_ITK')), Path = [getenv('QSMCI_HEIDI_ITK') '\/']; return; end  % QSM-CI, see BUILD.md\n/" "$D/heidi/reppath.m"
}
fid_setup_hook() {
    diff -u --strip-trailing-cr "$1/originals/reppath.m" "$1/heidi/reppath.m" > "$W/reports/deviations.diff" || true
    "$1/heidi/GradientAnisotropicDiffusionImageFilter" 2>&1 | head -3 > "$W/reports/itk-licensed.txt" || true
}
