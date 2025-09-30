#!/usr/bin/env python
import sys, os, json
import nibabel as nib
import numpy as np

if len(sys.argv) < 3:
    print("Usage: python fieldmap_to_radians.py <B0_fieldmap.nii> <output_dir>")
    sys.exit(1)

b0_file = sys.argv[1]
outdir  = sys.argv[2]
if not os.path.exists(outdir):
    os.makedirs(outdir)

# --- EchoTime aus inputs.json lesen ---
with open("inputs.json", "r") as f:
    d = json.load(f)
TE = float(d["EchoTime"][0])   # erstes TE aus Array nehmen
print("[INFO] Using EchoTime from inputs.json: {} sec".format(TE))

# --- B0 laden ---
b0_img  = nib.load(b0_file)
b0_data = b0_img.get_fdata()

# --- Hz → Radian ---
radian_data = 2*np.pi * b0_data * TE

# --- Header übernehmen ---
hdr = b0_img.header.copy()
radian_img = nib.Nifti1Image(radian_data.astype(np.float32), b0_img.affine, hdr)

# --- Maske laden für Konsistenz ---
mask_file = "bids/derivatives/qsm-forward/sub-1/anat/sub-1_mask.nii"
if os.path.exists(mask_file):
    mask_img = nib.load(mask_file)
    rad_hdr  = radian_img.header
    rad_hdr.set_qform(mask_img.affine, code=int(mask_img.header['qform_code']))
    rad_hdr.set_sform(mask_img.affine, code=int(mask_img.header['sform_code']))
    print("[INFO] Copied qform/sform from mask.")

# --- Speichern ---
out_file = os.path.join(outdir, "sub-1_radians.nii")
nib.save(radian_img, out_file)
print("[INFO] Saved radians fieldmap -> {}".format(out_file))
print("[INFO] Done.")
