#!/usr/bin/env python3
"""QSMGAN dipole inversion for QSM-CI (CPU-only, patch-based inference).

QSMGAN is a 3D U-Net generator refined by a WGAN-GP that maps a background-removed
LOCAL field (in ppm) directly to susceptibility (chimap, ppm). This is the `dipole`
stage: consumes localfield + mask (+ params), produces chimap.

The generator (UNet3D) is defined here verbatim from the upstream fork
(mmorri10/QSMGAN-LupoLab, models/unet3d.py) so inference does not depend on the
fork's package layout. We load the WGAN-refined generator weights
(WGAN_i64o48/net_best.pt, the checkpoint the upstream NIFTI inference script uses)
and reproduce the upstream patch pipeline (utils/data.py QsmPatchDataHD +
predict.py QsmPredict.run_net):

  * input patch  64^3, output (receptive-field crop) 48^3  ->  i64o48
  * input_scale  = 100   (localfield ppm is multiplied by this before the net)
  * output_scale = 10, output_transform = tanh -> inverse is arctanh
        chi_patch = arctanh(net_out) / output_scale
  * the volume is tiled by 48^3 OUTPUT patches; each 64^3 input patch is the same
    centre with an 8-voxel context margin; out-of-bounds voxels are zero-padded.

Deviations from upstream, deliberate and documented:
  * NO 0.8 mm resolution zoom. QsmPatchDataHD hard-codes a [1,1,1/0.8] zoom for one
    specific HD scanner; QSM-CI localfield is already on the mask grid, so we skip it
    and keep the output on the input grid.
  * The output is masked by mask.nii.gz (QSMGAN outputs ~0 outside the brain anyway).
"""
import json
import os
import sys

import numpy as np
import nibabel as nib
import torch
from torch import nn
from torch.nn import functional as F


# --------------------------------------------------------------------------- model
# Verbatim from mmorri10/QSMGAN-LupoLab code_pytorch_v3/models/unet3d.py.
def center_crop_3d(x, crop_shape):
    assert len(crop_shape) == 3
    w1, w2, w3 = x.shape[2:]
    c1, c2, c3 = crop_shape
    assert w1 >= c1 and w2 >= c2 and w2 >= c3
    s1, s2, s3 = w1 // 2 - c1 // 2, w1 // 2 - c2 // 2, w3 // 2 - c3 // 2
    e1, e2, e3 = s1 + c1, s2 + c2, s3 + c3
    return x[..., s1:e1, s2:e2, s3:e3]


class ConvBlock(nn.Module):
    def __init__(self, in_chans, out_chans, drop_prob, non_lin='ReLU', norm='none'):
        super().__init__()
        self.in_chans, self.out_chans = in_chans, out_chans
        self.drop_prob, self.non_lin, self.norm = drop_prob, non_lin, norm
        layers = []
        for _ in range(2):
            layers.append(nn.Conv3d(in_chans if not layers else out_chans, out_chans,
                                    kernel_size=3, padding=1))
            if norm == 'BatchNorm':
                layers.append(nn.BatchNorm3d(out_chans))
            elif norm == 'InstanceNorm':
                layers.append(nn.InstanceNorm3d(out_chans))
            elif norm == 'LayerNorm':
                layers.append(nn.LayerNorm(out_chans))
            if non_lin == 'ReLU':
                layers.append(nn.ReLU())
            elif non_lin == 'LReLU':
                layers.append(nn.LeakyReLU(0.1))
        self.layers = nn.Sequential(*layers)

    def forward(self, x):
        return self.layers(x)


class UNet3D(nn.Module):
    def __init__(self, in_chans, out_chans, out_shape, chans, num_pool_layers,
                 drop_prob, non_lin='ReLU', norm=None, tanh=False):
        super().__init__()
        self.out_shape = out_shape
        self.down_sample_layers = nn.ModuleList(
            [ConvBlock(in_chans, chans, drop_prob, non_lin, norm)])
        ch = chans
        for _ in range(num_pool_layers - 1):
            self.down_sample_layers += [ConvBlock(ch, ch * 2, drop_prob, non_lin, norm)]
            ch *= 2
        self.conv = ConvBlock(ch, ch, drop_prob, non_lin, norm)

        self.up_sample_layers = nn.ModuleList()
        for _ in range(num_pool_layers - 1):
            self.up_sample_layers += [ConvBlock(ch * 2, ch // 2, drop_prob, non_lin, norm)]
            ch //= 2
        self.up_sample_layers += [ConvBlock(ch * 2, ch, drop_prob, non_lin, norm)]

        ch = chans * 2 ** (num_pool_layers - 1)
        self.conv_transpose_layers = nn.ModuleList()
        for _ in range(num_pool_layers):
            self.conv_transpose_layers += [nn.ConvTranspose3d(ch, ch, kernel_size=2, stride=2)]
            ch //= 2
        ch *= 2
        conv2 = [nn.Conv3d(ch, out_chans, kernel_size=1),
                 nn.Conv3d(out_chans, out_chans, kernel_size=1)]
        if tanh:
            conv2.append(nn.Tanh())
        self.conv2 = nn.Sequential(*conv2)

    def forward(self, x):
        stack = []
        out = x
        for layer in self.down_sample_layers:
            out = layer(out)
            stack.append(out)
            out = F.avg_pool3d(out, kernel_size=2)
        out = self.conv(out)
        for convtrans, layer in zip(self.conv_transpose_layers, self.up_sample_layers):
            out = convtrans(out)
            out = torch.cat([out, stack.pop()], dim=1)
            out = layer(out)
        out = self.conv2(out)
        out = center_crop_3d(out, self.out_shape)
        return out


# ----------------------------------------------------------------------- inference
def get_patch(vol, center, patch):
    """Zero-padded patch of size `patch` centred at `center` (upstream _get_patch)."""
    def coords(c, p, m):
        L, R = c - p // 2, c + p // 2
        ml, mr = max(L, 0), min(m, R)
        pl = 0 if L >= 0 else -L
        pr = p if R <= m else p - (R - m)
        return ml, mr, pl, pr
    out = np.zeros(patch, dtype=np.float32)
    ml1, mr1, pl1, pr1 = coords(center[0], patch[0], vol.shape[0])
    ml2, mr2, pl2, pr2 = coords(center[1], patch[1], vol.shape[1])
    ml3, mr3, pl3, pr3 = coords(center[2], patch[2], vol.shape[2])
    out[pl1:pr1, pl2:pr2, pl3:pr3] = vol[ml1:mr1, ml2:mr2, ml3:mr3]
    return out


def main():
    in_dir = sys.argv[1] if len(sys.argv) > 1 else '/input'
    out_dir = sys.argv[2] if len(sys.argv) > 2 else '/output'
    weights_dir = os.environ.get('QSMGAN_WEIGHTS', '/opt/qsmgan/WGAN_i64o48')

    torch.set_num_threads(max(1, os.cpu_count() or 1))
    device = torch.device('cpu')

    with open(os.path.join(weights_dir, 'config.json')) as f:
        cfg = json.load(f)
    ips = tuple(cfg['dset_args']['input_patch_size'])    # (64,64,64)
    ops = tuple(cfg['dset_args']['output_patch_size'])   # (48,48,48)
    input_scale = cfg['dset_args']['input_scale']        # 100
    output_scale = cfg['dset_args']['output_scale']      # 10
    tanh_out = cfg['dset_args']['output_transform'] == 'tanh'

    net = UNet3D(**cfg['netG_args']).to(device)
    ckpt = torch.load(os.path.join(weights_dir, 'net_best.pt'), map_location=device)
    net.load_state_dict(ckpt['netG'])
    net.eval()

    lf_nii = nib.load(os.path.join(in_dir, 'localfield.nii.gz'))
    localfield = np.asarray(lf_nii.dataobj, dtype=np.float32)
    localfield = np.nan_to_num(localfield)
    mask = np.asarray(nib.load(os.path.join(in_dir, 'mask.nii.gz')).dataobj)
    mask = (mask > 0).astype(np.float32)

    X, Y, Z = localfield.shape
    predict = np.zeros((X, Y, Z), dtype=np.float32)

    # Tile the volume by OUTPUT (48^3) patches (upstream _calc_centers, sample 'other').
    ox, oy, oz = (ops[0] // 2, ops[1] // 2, ops[2] // 2)
    inv = np.arctanh if tanh_out else (lambda v: v)
    with torch.no_grad():
        for cx in range(ox, X + ox + 1, ops[0]):
            for cy in range(oy, Y + oy + 1, ops[1]):
                for cz in range(oz, Z + oz + 1, ops[2]):
                    inp = get_patch(localfield, (cx, cy, cz), ips) * input_scale
                    t = torch.from_numpy(inp).unsqueeze(0).unsqueeze(0).float().to(device)
                    out = net(t).cpu().squeeze().numpy()
                    if tanh_out:
                        out = np.clip(out, -0.999999, 0.999999)
                    patch = (inv(out) / output_scale).astype(np.float32)
                    # place the 48^3 output patch, clipped to the volume bounds
                    x0, y0, z0 = cx - ops[0] // 2, cy - ops[1] // 2, cz - ops[2] // 2
                    xe = min(x0 + ops[0], X); ye = min(y0 + ops[1], Y); ze = min(z0 + ops[2], Z)
                    px, py, pz = xe - x0, ye - y0, ze - z0
                    if px <= 0 or py <= 0 or pz <= 0:
                        continue
                    predict[x0:xe, y0:ye, z0:ze] = patch[:px, :py, :pz]

    predict = (predict * mask)
    predict = np.nan_to_num(predict).astype(np.float32)

    os.makedirs(out_dir, exist_ok=True)
    out_nii = nib.Nifti1Image(predict, lf_nii.affine, lf_nii.header)
    nib.save(out_nii, os.path.join(out_dir, 'chimap.nii.gz'))
    print(f'QSMGAN: wrote chimap.nii.gz shape={predict.shape} '
          f'range=[{predict.min():.4f},{predict.max():.4f}]')


if __name__ == '__main__':
    main()
