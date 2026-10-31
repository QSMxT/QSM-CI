#!/bin/bash -l
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
# Lay out the fidelity cases each stage needs, from three contract datasets (a Slurm job):
#   FID_SIM     in silico: <dir>/inputs (phase, magnitude, mask, params) + <dir>/groundtruth
#               (totalfield, localfield)
#   FID_INVIVO  in vivo: contract inputs folder (phase, magnitude, mask, params)
#   FID_CHISEP  χ-separation phantom: inputs folder (localfield, r2prime, chimap, magnitude, mask,
#               params)
#   QSMXT_SIF   a QSMxT image, to derive the in vivo stage inputs
#   FID_ROOT    cases land in $FID_ROOT/cases/<case>
# The in silico stage inputs are the dataset's ground truth. The in vivo ones are derived once, with
# QSMxT: ROMEO total field, V-SHARP local field and its eroded mask, RTS χ, and R2' = 0.52 R2*
# (r2prime-scaled-qsmci's heuristic). Any fixed input serves a fidelity check: the container and
# licensed MATLAB read the same files.
set -eo pipefail
C="$FID_ROOT/cases"; mkdir -p "$C"
cpi() { mkdir -p "$1"; shift; local d=$1; shift; for f in "$@"; do cp "$d/$f" "$C/$CASE/"; done; }
CASE=sim-bfr;    cpi "$C/$CASE" "$FID_SIM/groundtruth" totalfield.nii.gz; cpi "$C/$CASE" "$FID_SIM/inputs" mask.nii.gz params.json magnitude.nii.gz
CASE=sim-dipole; cpi "$C/$CASE" "$FID_SIM/groundtruth" localfield.nii.gz; cpi "$C/$CASE" "$FID_SIM/inputs" mask.nii.gz params.json magnitude.nii.gz
CASE=chisep-mc;  cpi "$C/$CASE" "$FID_CHISEP" localfield.nii.gz r2prime.nii.gz chimap.nii.gz magnitude.nii.gz mask.nii.gz params.json

# In vivo stage inputs, derived with QSMxT.
I=$FID_INVIVO; T="$C/invivo-derive"; mkdir -p "$T"
q() { apptainer exec --cleanenv -B "$I" -B "$T" "$QSMXT_SIF" qsmxt "$@"; }
q --version | tee "$T/qsmxt-version.txt"
q fieldmap romeo "$I/phase.nii.gz" -m "$I/mask.nii.gz" --magnitude "$I/magnitude.nii.gz" \
    --params "$I/params.json" -o "$T/totalfield.nii.gz"
b0dir=$(python3 -c "import json;print(*json.load(open('$I/params.json'))['B0_dir'])")
q bgremove vsharp "$T/totalfield.nii.gz" -m "$I/mask.nii.gz" -o "$T/localfield.nii.gz" \
    --output-mask "$T/mask_vsharp.nii.gz" --b0-direction $b0dir
q invert rts "$T/localfield.nii.gz" -m "$T/mask_vsharp.nii.gz" -o "$T/chimap.nii.gz" --b0-direction $b0dir
tes=$(python3 -c "import json;print(*json.load(open('$I/params.json'))['TE'])")
q r2star "$I/magnitude.nii.gz" -m "$T/mask_vsharp.nii.gz" -o "$T/r2star.nii.gz" --echo-times $tes
module load matlab/R2023b
matlab -nodisplay -batch "i=niftiinfo('$T/r2star.nii.gz'); r=double(niftiread(i)); r=0.52*max(r,0); r(~isfinite(r))=0; i.Datatype='single'; i.BitsPerPixel=32; i.MultiplicativeScaling=1; i.AdditiveOffset=0; niftiwrite(single(r), '$T/r2prime', i, 'Compressed', true);"
CASE=invivo-bfr;    cpi "$C/$CASE" "$T" totalfield.nii.gz; cpi "$C/$CASE" "$I" mask.nii.gz params.json magnitude.nii.gz
CASE=invivo-dipole; cpi "$C/$CASE" "$T" localfield.nii.gz; cpi "$C/$CASE" "$I" params.json magnitude.nii.gz
cp "$T/mask_vsharp.nii.gz" "$C/invivo-dipole/mask.nii.gz"
CASE=invivo-chisep; cpi "$C/$CASE" "$T" localfield.nii.gz r2prime.nii.gz chimap.nii.gz; cpi "$C/$CASE" "$I" params.json magnitude.nii.gz
cp "$T/mask_vsharp.nii.gz" "$C/invivo-chisep/mask.nii.gz"
# DECOMPOSE takes log of the signal, and this acquisition's magnitude is exactly 0 in some echoes of
# masked voxels; the reference fit stops on log(0). invivo-chisep-nz raises those zeros to 1.
rm -rf "$C/invivo-chisep-nz"; cp -r "$C/invivo-chisep" "$C/invivo-chisep-nz"
python3 -c "
import nibabel as nib, numpy as np
f='$C/invivo-chisep-nz/magnitude.nii.gz'; i=nib.load(f); a=np.asarray(i.dataobj)
nib.save(nib.Nifti1Image(np.where(a == 0, 1, a).astype(a.dtype), i.affine, i.header), f)"
ls -la "$C"/*
