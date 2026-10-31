"""PHU-NET3D / PhaseNet3D (DIP-UP) network definition, reconstructed to load the
released checkpoints.

Mirrors sunhongfu/DIP-UP's Unet_{2,1}Chan_9Class, whose `from Unet_blocks import *`
cannot be satisfied from the public repo (Unet_blocks.py is not in it). Block layout
below reproduces the checkpoint keys/shapes exactly (verified strict=True).

One deliberate departure, `DROPOUT_AT_INFERENCE`: the upstream forward calls
`F.dropout(x, 0.2)` with no `training=` argument, so dropout stays ACTIVE even after
`.eval()` — the upstream net is stochastic at inference. We thread `training=self.training`
so `.eval()` disables it (standard eval semantics, and a prerequisite for a deterministic
ONNX graph).
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


class EncodingBlocks(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.EncodeConv = nn.Sequential(
            nn.Conv3d(in_ch, out_ch, 3, 1, 1), nn.BatchNorm3d(out_ch), nn.ReLU(inplace=True),
            nn.Conv3d(out_ch, out_ch, 3, 1, 1), nn.BatchNorm3d(out_ch), nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.EncodeConv(x)


class MidBlocks(nn.Module):
    def __init__(self, ch):
        super().__init__()
        self.MidConv = nn.Sequential(
            nn.Conv3d(ch, 2 * ch, 3, 1, 1), nn.BatchNorm3d(2 * ch), nn.ReLU(inplace=True),
            nn.Conv3d(2 * ch, ch, 3, 1, 1), nn.BatchNorm3d(ch), nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.MidConv(x)


class DecodingBlocks(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.up = nn.Sequential(
            nn.ConvTranspose3d(in_ch, in_ch, 2, 2), nn.BatchNorm3d(in_ch), nn.ReLU(inplace=True),
        )
        self.DecodeConv = nn.Sequential(
            nn.Conv3d(2 * in_ch, in_ch, 3, 1, 1), nn.BatchNorm3d(in_ch), nn.ReLU(inplace=True),
            nn.Conv3d(in_ch, out_ch, 3, 1, 1), nn.BatchNorm3d(out_ch), nn.ReLU(inplace=True),
        )

    def forward(self, x, skip):
        x = self.up(x)
        return self.DecodeConv(torch.cat([x, skip], dim=1))


class DipUpNet(nn.Module):
    """9-class wrap-count U-Net. `in_ch`=2 -> PHU-NET3D (width 64); 1 -> PhaseNet3D (width 48)."""

    # When True, reproduce upstream's always-on dropout (stochastic inference).
    DROPOUT_AT_INFERENCE = False

    def __init__(self, in_ch, width, EncodingDepth=4):
        super().__init__()
        self.EncodingDepth = EncodingDepth
        enc, dec = [], []
        for layer in range(1, EncodingDepth + 1):
            out = width * 2 ** (layer - 1)
            enc.append(EncodingBlocks(in_ch if layer == 1 else out // 2, out))
        self.EncodeConvs = nn.ModuleList(enc)
        self.MidConv1 = MidBlocks(out)
        for layer in range(1, EncodingDepth + 1):
            n_in = out // 2 ** (layer - 1)
            dec.append(DecodingBlocks(n_in, n_in if layer == EncodingDepth else n_in // 2))
        self.DecodeConvs = nn.ModuleList(dec)
        self.FinalConv = nn.Conv3d(n_in, 9, 1, 1, 0)

    def _drop(self, x):
        train = True if self.DROPOUT_AT_INFERENCE else self.training
        return F.dropout(x, 0.2, training=train)

    def forward(self, x):
        skips = []
        for conv in self.EncodeConvs:
            x = self._drop(conv(x))
            skips.append(x)
            x = F.max_pool3d(x, 2)
        x = self.MidConv1(x)
        for i, conv in enumerate(self.DecodeConvs):
            x = self._drop(conv(x, skips[self.EncodingDepth - i - 1]))
        return self.FinalConv(x)


VARIANTS = {"PHU-NET3D": (2, 64), "PhaseNet3D": (1, 48)}


def load(variant, ckpt_path):
    in_ch, width = VARIANTS[variant]
    net = DipUpNet(in_ch, width)
    sd = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    sd = {(k[7:] if k.startswith("module.") else k): v for k, v in sd.items()}
    net.load_state_dict(sd, strict=True)   # strict: every key must match
    return net.eval()
