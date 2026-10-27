# qsmart-matlab: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=matlab-qsmart
FID_SOURCES="FID_QSMART FID_SUN FID_STI"   # wtsyeda/QSMART, sunhongfu/QSM, STISuite_V3.0/STISuite_V3.0
FID_MATLAB_PATH="nifti qsmart frangi curvatures sti"
FID_MCC_A="sti frangi"                    # pcode and mex: mcc can't trace them
# Toolbox functions QSMART, Frangi and STI Suite's pcode call (recon.m's %#function pragma), plus
# the code QSM-CI patched or built.
FID_WHICH="graythresh imbothat imclose imdilate imerode imfilter imgaussfilt3 imopen padarray prctile strel
           vasculature_mask_qsmci QSM_iLSQR FrangiFilter3D eig3volume imgaussian N4BiasFieldCorrection"

# BUILD.md §1: the build tree, and the tree the licensed runs use.
fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/qsmart"; (
    cd "$D"
    cp "$FID_QSMART"/QSMART_toolbox_v1.0/{unwrap_phase,echofit,QSMART_SDF,sdf_curvature,calculate_curvature,adjust_offset,makekspace,myisfield}.m qsmart/
    cp "$FID_SUN"/Misc/lapunwrap.m qsmart/
    cp -r "$FID_QSMART"/matlab-dependencies/NIfTI_20140122 nifti
    cp -r "$FID_QSMART"/matlab-dependencies/frangi_filter_version2a frangi
    rm -f frangi/ExampleVolumeStent.mat frangi/eig3volume.m
    sed -i 's/^\( *\)keyboard\r*$/\1% keyboard  % QSM-CI: stray debug statement removed (fatal in deployed MCR mode)/' frangi/FrangiFilter3D.m
    mkdir -p curvatures && cp "$FID_QSMART"/matlab-dependencies/curvatures/{curvatures.m,license.txt} curvatures/
    cp -r "$FID_STI"/Core_Functions_P sti
    perl -0pi -e 's/scaledGC=GC\.\/max\(abs\(GC\(GC<0\)\)\)\*curvConstant;/negGC=max(abs(GC(GC<0)));\nif isempty(negGC) || negGC==0, negGC=1; end % QSM-CI guard, see BUILD.md\nscaledGC=GC.\/negGC*curvConstant;/' qsmart/calculate_curvature.m
    # The authors' originals of every file QSM-CI changes, for the deviations diff.
    mkdir -p originals
    cp "$FID_QSMART"/QSMART_toolbox_v1.0/{calculate_curvature,vasculature_mask}.m originals/
    cp "$FID_QSMART"/matlab-dependencies/frangi_filter_version2a/FrangiFilter3D.m originals/ )
}

# eig3volume is mex-only: compile it (BUILD.md §2).
fid_build_hook() { mat "cd('$1/frangi'); mex eig3volume.c"; }

fid_setup_hook() {
    local D=$1
    mat "cd('$D/frangi'); mex eig3volume.c"
    # N4 for licensed MATLAB: the image's own N4BiasFieldCorrection, so all runs share one binary.
    mkdir -p "$W/bin"
    cat > "$W/bin/N4BiasFieldCorrection" <<EON
#!/bin/bash
unset LD_LIBRARY_PATH
exec apptainer exec --no-home --cleanenv -B "\$PWD" --pwd "\$PWD" "$SIF" N4BiasFieldCorrection "\$@"
EON
    chmod +x "$W/bin/N4BiasFieldCorrection"
    apptainer exec --cleanenv "$SIF" bash -c 'command -v N4BiasFieldCorrection; N4BiasFieldCorrection --version' \
        | tee "$W/reports/n4-version.txt" || true
    { for f in calculate_curvature vasculature_mask FrangiFilter3D; do
          case $f in
              vasculature_mask) new="$A/vasculature_mask_qsmci.m" ;;
              FrangiFilter3D) new="$D/frangi/FrangiFilter3D.m" ;;
              *) new="$D/qsmart/$f.m" ;;
          esac
          diff -u --strip-trailing-cr "$D/originals/$f.m" "$new" || true
      done; } > "$W/reports/deviations.diff"
}
