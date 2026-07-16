#!/usr/bin/env python
"""QSM-CI wrapper for QSMnet / QSMnet+ dipole inversion (TensorFlow 1.14, CPU).

Shared by the `qsmnet` and `qsmnet-plus` submissions — the only difference is which
checkpoint the image bakes in, selected via the QSMNET_NAME env var (QSMnet_64 / QSMnet+_64).

Pipeline (mirrors SNU-LIST/QSMnet `Code/inference.py`, but consuming a QSM-CI NIfTI instead of
their MATLAB-preprocessed `.mat`):

  1. Read localfield.nii.gz — the local/tissue field already in ppm. QSM-CI provides this; we do
     NOT re-run their MATLAB Laplacian-unwrap / V-SHARP preprocessing (that produced `phs_tissue`
     for their own pipeline; our localfield is the equivalent).
  2. Normalize with the DATASET mean/std stored beside the checkpoint
     (`norm_factor_<name>.mat`: input_mean/input_std for the field, label_mean/label_std for chi):
        field_n = (field - input_mean) / input_std
  3. Zero-pad each dim up to a multiple of 16 (the U-Net has 4 max-pool/deconv levels, so spatial
     dims must be divisible by 2**4). The net is trained at 1 mm isotropic.
  4. Run the frozen 3D U-Net (qsmnet_deep, leaky_relu) from the repo's network_model.py.
  5. De-normalize:  chi = label_std * pred + label_mean   (ppm).
  6. Crop back to the original grid, multiply by the mask, and write chimap.nii.gz on the INPUT
     affine/header (so voxel size + orientation are carried through unchanged).

The repo's own save_nii() applies fliplr/flipud to undo a MATLAB-side orientation convention; we
deliberately skip those flips because we round-trip the input NIfTI's affine directly.
"""
import os
import sys

os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")  # force CPU
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import nibabel as nib
import scipy.io
import tensorflow as tf

# The pretrained net is defined in the cloned repo's Code/ package (network_model.qsmnet_deep +
# the tf.contrib layer helpers in utils). QSMNET_CODE points at that dir in the image.
sys.path.insert(0, os.environ.get("QSMNET_CODE", "/opt/QSMnet/Code"))
import network_model  # noqa: E402


def pad_to_multiple(vol, m=16):
    """Symmetric zero-pad each dim up to the next multiple of m. Returns padded vol + per-axis pad."""
    shape = np.asarray(vol.shape)
    target = np.ceil(shape / float(m)).astype(int) * m
    lo = ((target - shape) // 2).astype(int)
    npad = tuple((int(l), int(t - s - l)) for l, t, s in zip(lo, target, shape))
    return np.pad(vol, npad, mode="constant", constant_values=0), npad


def crop_pad(vol, npad):
    sl = tuple(slice(lo, vol.shape[i] - hi) for i, (lo, hi) in enumerate(npad))
    return vol[sl]


def main():
    in_field, in_mask, out_chi = sys.argv[1], sys.argv[2], sys.argv[3]

    net_dir = os.environ["QSMNET_CKPT_DIR"]        # .../Checkpoints/<name>
    net_name = os.environ["QSMNET_NAME"]           # QSMnet_64 | QSMnet+_64
    epoch = int(os.environ.get("QSMNET_EPOCH", "25"))

    # --- normalization constants stored WITH the checkpoint ---
    norm = scipy.io.loadmat(os.path.join(net_dir, "norm_factor_" + net_name + ".mat"))
    b_mean = float(np.asarray(norm["input_mean"]).squeeze())
    b_std = float(np.asarray(norm["input_std"]).squeeze())
    y_mean = float(np.asarray(norm["label_mean"]).squeeze())
    y_std = float(np.asarray(norm["label_std"]).squeeze())

    # act_func / net_model saved with the checkpoint (['leaky_relu', 'qsmnet_deep']).
    net_info = np.load(os.path.join(net_dir, "network_info_" + net_name + ".npy"))
    act_func = str(net_info[0])
    net_model = str(net_info[1])

    # --- read the local field (ppm) + mask ---
    field_img = nib.load(in_field)
    field = np.asarray(field_img.get_fdata(), dtype=np.float32)
    mask = np.asarray(nib.load(in_mask).get_fdata(), dtype=np.float32)

    # normalize with dataset stats, then pad to /16
    field_n = (field - b_mean) / b_std
    pfield, npad = pad_to_multiple(field_n, 16)
    N = pfield.shape
    x = pfield[np.newaxis, ..., np.newaxis]  # (1, X, Y, Z, 1)

    # --- build + restore the frozen graph ---
    tf.compat.v1.reset_default_graph()
    Z = tf.compat.v1.placeholder("float", [None, N[0], N[1], N[2], 1])
    net_func = getattr(network_model, net_model)
    pred = net_func(Z, act_func, False, False)

    saver = tf.compat.v1.train.Saver()
    with tf.compat.v1.Session() as sess:
        sess.run(tf.compat.v1.global_variables_initializer())
        saver.restore(sess, os.path.join(net_dir, net_name + "-" + str(epoch)))
        out = sess.run(pred, feed_dict={Z: x})

    # de-normalize -> ppm, crop back, mask
    chi = y_std * np.asarray(out).squeeze() + y_mean
    chi = crop_pad(chi, npad).astype(np.float32)
    chi = chi * (mask > 0)

    # write on the INPUT affine/header (voxel size + orientation preserved)
    nib.save(nib.Nifti1Image(chi, field_img.affine, field_img.header), out_chi)


if __name__ == "__main__":
    main()
