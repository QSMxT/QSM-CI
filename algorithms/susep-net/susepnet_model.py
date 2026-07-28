"""SUSEP-Net (repo internal name "SQ-Net") architecture — vendored from the authors' release.

Dual-branch 3D U-net with two additional guidance encoders + contrastive interaction groups.
Verbatim from the public SUSEP-Net Google-Drive release (SUSEPNet.py, Li/Gao/Sun et al. 2025,
arXiv:2506.13293); only the `torchinfo` import and the `__main__` demo block are dropped so it
imports with just torch. The pretrained SUSEPNet.pth loads into this definition strict=True.

forward(QSM, R2', LFS) -> (chi_pos, chi_neg, ...); the decoder ends in a ReLU so both outputs are
non-negative magnitudes (chi_neg is the diamagnetic magnitude).
"""
import torch
import torch.nn as nn


class ConvBlock(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(ConvBlock, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv3d(in_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm3d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.conv(x)


class ImageEncoder3D(nn.Module):
    def __init__(self):
        super(ImageEncoder3D, self).__init__()
        self.enc1 = ConvBlock(3, 64)
        self.pool1 = nn.MaxPool3d(2)
        self.enc2 = ConvBlock(64, 128)
        self.pool2 = nn.MaxPool3d(2)
        self.enc3 = ConvBlock(128, 256)
        self.pool3 = nn.MaxPool3d(2)

    def forward(self, x):
        feature_maps = []
        enc1 = self.enc1(x)
        feature_maps.append(enc1)
        enc2 = self.enc2(self.pool1(enc1))
        feature_maps.append(enc2)
        enc3 = self.enc3(self.pool2(enc2))
        feature_maps.append(enc3)
        fvin = self.pool3(enc3)
        return fvin, feature_maps


class QSMEncoder3D(nn.Module):
    def __init__(self):
        super(QSMEncoder3D, self).__init__()
        self.fc_pos = nn.Sequential(
            ConvBlock(1, 64), nn.MaxPool3d(2),
            ConvBlock(64, 128), nn.MaxPool3d(2),
            ConvBlock(128, 256), nn.MaxPool3d(2),
        )
        self.fc_neg = nn.Sequential(
            ConvBlock(1, 64), nn.MaxPool3d(2),
            ConvBlock(64, 128), nn.MaxPool3d(2),
            ConvBlock(128, 256), nn.MaxPool3d(2),
        )

    def forward(self, x):
        guide_vector_pos = self.fc_pos(x)
        guide_vector_neg = self.fc_neg(x)
        return guide_vector_pos, guide_vector_neg


class ConvSRU(nn.Module):
    def __init__(self, channels=256):
        super(ConvSRU, self).__init__()
        self.update_gate = ConvBlock(channels, channels)
        self.out_gate = ConvBlock(channels, channels)

    def forward(self, fvin, guide_vector):
        update = torch.sigmoid(self.update_gate(guide_vector))
        out_inputs = torch.tanh(self.out_gate(guide_vector))
        h_new = fvin * (1 - update) + out_inputs * update
        return h_new


class InteractionGroup3D(nn.Module):
    def __init__(self, num_leff_blocks=2):
        super(InteractionGroup3D, self).__init__()
        self.SRU = ConvSRU()
        self.leff_blocks = nn.ModuleList([
            nn.Sequential(
                nn.Conv3d(256, 256, kernel_size=1),
                nn.ReLU(),
                nn.Conv3d(256, 256, kernel_size=3, padding=1),
            ) for _ in range(num_leff_blocks)
        ])

    def forward(self, fvin, guide_vector):
        f_interaction = self.SRU(fvin, guide_vector)
        for leff in self.leff_blocks:
            f_interaction = leff(f_interaction) + f_interaction
        return f_interaction


class CascadeInteractionModule3D(nn.Module):
    def __init__(self, num_groups=2, num_leff_blocks=2):
        super(CascadeInteractionModule3D, self).__init__()
        self.interaction_groups_pos = nn.ModuleList(
            [InteractionGroup3D(num_leff_blocks) for _ in range(num_groups)])
        self.interaction_groups_neg = nn.ModuleList(
            [InteractionGroup3D(num_leff_blocks) for _ in range(num_groups)])
        self.concat_conv = nn.Conv3d(512, 256, kernel_size=1)

    def forward(self, fvin, guide_vector_pos, guide_vector_neg):
        f_chi_pos = fvin
        for group in self.interaction_groups_pos:
            f_chi_pos = group(f_chi_pos, guide_vector_pos)
        f_concat = torch.cat([fvin, f_chi_pos], dim=1)
        f_concat = self.concat_conv(f_concat)
        f_chi_neg = f_concat
        for group in self.interaction_groups_neg:
            f_chi_neg = group(f_chi_neg, guide_vector_neg)
        return f_chi_pos, f_chi_neg


class ImageDecoder3D(nn.Module):
    def __init__(self):
        super(ImageDecoder3D, self).__init__()
        self.upconv3 = nn.ConvTranspose3d(512, 256, kernel_size=2, stride=2)
        self.dec3 = ConvBlock(512, 256)
        self.upconv2 = nn.ConvTranspose3d(256, 128, kernel_size=2, stride=2)
        self.dec2 = ConvBlock(256, 128)
        self.upconv1 = nn.ConvTranspose3d(128, 64, kernel_size=2, stride=2)
        self.dec1 = ConvBlock(128, 64)
        self.conv_last = nn.Conv3d(64, 1, kernel_size=1)
        self.relu = nn.ReLU()

    def forward(self, x, feature_maps):
        dec3 = torch.cat([self.upconv3(x), feature_maps[2]], dim=1)
        dec3 = self.dec3(dec3)
        dec2 = torch.cat([self.upconv2(dec3), feature_maps[1]], dim=1)
        dec2 = self.dec2(dec2)
        dec1 = torch.cat([self.upconv1(dec2), feature_maps[0]], dim=1)
        dec1 = self.dec1(dec1)
        out = self.conv_last(dec1)
        out = self.relu(out)
        return out


class SUSEPNet(nn.Module):
    def __init__(self):
        super(SUSEPNet, self).__init__()
        self.Unet_encoder = ImageEncoder3D()
        self.QSM_encoder = QSMEncoder3D()
        self.CascadeInteractionModule3D = CascadeInteractionModule3D()
        self.bottleneck_pos = ConvBlock(256, 512)
        self.bottleneck_neg = ConvBlock(256, 512)
        self.decoder_pos = ImageDecoder3D()
        self.decoder_neg = ImageDecoder3D()

    def forward(self, QSM_image, R2_prime_image, Lfs_image):
        image_inputs = torch.cat([QSM_image, R2_prime_image, Lfs_image], dim=1)
        fvin, feature_maps = self.Unet_encoder(image_inputs)
        guide_vector_pos, guide_vector_neg = self.QSM_encoder(QSM_image)
        f_chi_pos, f_chi_neg = self.CascadeInteractionModule3D(
            fvin, guide_vector_pos, guide_vector_neg)
        pre_chi_pos = self.bottleneck_pos(f_chi_pos)
        pre_chi_neg = self.bottleneck_neg(f_chi_neg)
        chi_pos = self.decoder_pos(pre_chi_pos, feature_maps)
        chi_neg = self.decoder_neg(pre_chi_neg, feature_maps)
        return chi_pos, chi_neg, f_chi_pos, f_chi_neg, guide_vector_pos, guide_vector_neg
