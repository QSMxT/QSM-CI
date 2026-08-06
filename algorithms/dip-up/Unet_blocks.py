"""U-Net building blocks reconstructed to match the DIP-UP pretrained checkpoints.

The DIP-UP repo (github.com/sunhongfu/DIP-UP) ships PhaseNet3D/Unet_1Chan_9Class.py and
PHU-NET3D/Unet_2Chan_9Class.py, both of which `from Unet_blocks import *`, but the repo does NOT
include Unet_blocks.py (it lives only in the authors' private xQSM/deepMRI tree). These blocks are
reconstructed here to be byte-compatible with the released .pth state_dicts:

  EncodeConv / DecodeConv = Sequential[Conv3d(3,pad1), BatchNorm3d, ReLU, Conv3d(3,pad1),
                                        BatchNorm3d, ReLU]     (weighted params at indices 0,1,3,4)
  MidConv                 = Sequential[Conv3d(in->2in), BN, ReLU, Conv3d(2in->in), BN, ReLU]
  up                      = Sequential[ConvTranspose3d(2,stride2), BN, ReLU]

This layout exactly reproduces the checkpoint keys, e.g.
  EncodeConvs.0.EncodeConv.{0,1,3,4}.*, MidConv1.MidConv.{0,1,3,4}.*,
  DecodeConvs.i.up.{0,1}.*, DecodeConvs.i.DecodeConv.{0,1,3,4}.* and FinalConv.{weight,bias}.
The channel widths (48/96/192/384/768) also match; the released nets use initial_num_layers=48, not
the 64 hard-coded in the repo's Unet_*Chan_9Class.py (dip_up_infer.py patches that to 48 to load).
"""
import torch
import torch.nn as nn


class EncodingBlocks(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.EncodeConv = nn.Sequential(
            nn.Conv3d(in_ch, out_ch, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm3d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv3d(out_ch, out_ch, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm3d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.EncodeConv(x)


class MidBlocks(nn.Module):
    def __init__(self, ch):
        super().__init__()
        self.MidConv = nn.Sequential(
            nn.Conv3d(ch, 2 * ch, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm3d(2 * ch),
            nn.ReLU(inplace=True),
            nn.Conv3d(2 * ch, ch, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm3d(ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.MidConv(x)


class DecodingBlocks(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        # `up` halves the coarse feature map's stride and keeps its channel count (in_ch).
        self.up = nn.Sequential(
            nn.ConvTranspose3d(in_ch, in_ch, kernel_size=2, stride=2),
            nn.BatchNorm3d(in_ch),
            nn.ReLU(inplace=True),
        )
        # After concatenation with the encoder skip (also in_ch channels) DecodeConv sees 2*in_ch.
        self.DecodeConv = nn.Sequential(
            nn.Conv3d(2 * in_ch, in_ch, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm3d(in_ch),
            nn.ReLU(inplace=True),
            nn.Conv3d(in_ch, out_ch, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm3d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x, skip):
        x = self.up(x)
        # Pad to the skip's spatial size if an odd input dim made the transpose-conv output smaller.
        if x.shape[2:] != skip.shape[2:]:
            diff = [s - o for s, o in zip(skip.shape[2:], x.shape[2:])]
            pad = []
            for d in reversed(diff):
                pad.extend([0, d])
            x = nn.functional.pad(x, pad)
        x = torch.cat([x, skip], dim=1)
        return self.DecodeConv(x)
