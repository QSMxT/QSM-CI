#!/usr/bin/env bash
# Assemble the qsmart-matlab build tree (BUILD.md §1) into DEST, so licensed MATLAB can run the
# same recon.m the container was compiled from. Keep this in step with BUILD.md §1.
#
#   assemble_deps.sh QSMART SUN STI DEST
#     QSMART  clone of github.com/wtsyeda/QSMART
#     SUN     clone of github.com/sunhongfu/QSM (for Misc/lapunwrap.m)
#     STI     STISuite_V3.0 folder that holds Core_Functions_P
#     DEST    output folder: qsmart/ nifti/ frangi/ curvatures/ sti/ (+ originals/ for the diffs)
#
# The mex step (eig3volume) is MATLAB-specific and runs separately (job.sh setup).
set -euo pipefail
QSMART=$1; SUN=$2; STI=$3; DEST=$4
mkdir -p "$DEST"; cd "$DEST"
rm -rf qsmart nifti frangi curvatures sti originals

mkdir -p qsmart
cp "$QSMART"/QSMART_toolbox_v1.0/{unwrap_phase,echofit,QSMART_SDF,sdf_curvature,calculate_curvature,adjust_offset,makekspace,myisfield}.m qsmart/
cp "$SUN"/Misc/lapunwrap.m qsmart/

cp -r "$QSMART"/matlab-dependencies/NIfTI_20140122 nifti

cp -r "$QSMART"/matlab-dependencies/frangi_filter_version2a frangi
rm -f frangi/ExampleVolumeStent.mat
rm -f frangi/eig3volume.m
sed -i 's/^\( *\)keyboard\r*$/\1% keyboard  % QSM-CI: stray debug statement removed (fatal in deployed MCR mode)/' frangi/FrangiFilter3D.m
mkdir -p curvatures && cp "$QSMART"/matlab-dependencies/curvatures/{curvatures.m,license.txt} curvatures/

cp -r "$STI"/Core_Functions_P sti

perl -0pi -e 's/scaledGC=GC\.\/max\(abs\(GC\(GC<0\)\)\)\*curvConstant;/negGC=max(abs(GC(GC<0)));\nif isempty(negGC) || negGC==0, negGC=1; end % QSM-CI guard, see BUILD.md\nscaledGC=GC.\/negGC*curvConstant;/' qsmart/calculate_curvature.m

# The authors' originals of every file QSM-CI changes, for the report's diff section.
mkdir -p originals
cp "$QSMART"/QSMART_toolbox_v1.0/calculate_curvature.m originals/
cp "$QSMART"/QSMART_toolbox_v1.0/vasculature_mask.m originals/
cp "$QSMART"/matlab-dependencies/frangi_filter_version2a/FrangiFilter3D.m originals/
echo "assembled into $DEST"
