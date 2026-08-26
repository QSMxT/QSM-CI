#!/usr/bin/env python3
"""Export the SNU R2PRIMENET_7T checkpoint (r2pnet7T.pth.tar) to ONNX.

Standalone redefinition of Code/network.py's R2convNet (Conv3d = conv+BN+ReLU, MaxPool3d,
ConvTranspose3d, 1x1 out) so the export needs no repo imports (utils.py drags in mat73 /
pytorch_ssim). Dynamic spatial axes; inputs must be multiples of 16 (4 pool levels) — the
submission pads to multiples of 64 like the official test.py. Validates ONNX vs torch on a
random volume before writing.

Usage (in a torch container): python export_r2pnet7t.py <checkpoint.pth.tar> <out.onnx>
"""
import sys

import numpy as np
import torch
import torch.nn as nn


class C(nn.Module):
    def __init__(self, ci, co, k=3):
        super().__init__()
        self.conv = nn.Conv3d(ci, co, kernel_size=k, stride=1, padding=k // 2)
        self.bn = nn.BatchNorm3d(co)
        self.act = nn.ReLU()

    def forward(self, x):
        return self.act(self.bn(self.conv(x)))


class Out(nn.Module):
    def __init__(self, ci, co):
        super().__init__()
        self.conv = nn.Conv3d(ci, co, kernel_size=1)

    def forward(self, x):
        return self.conv(x)


class R2convNet(nn.Module):
    def __init__(self, c=32, k=3):
        super().__init__()
        P = lambda: nn.MaxPool3d(2, 2)
        D = lambda ci, co: nn.ConvTranspose3d(ci, co, kernel_size=2, stride=2)
        self.conv11, self.conv12, self.pool1 = C(1, c, k), C(c, c, k), P()
        self.conv21, self.conv22, self.pool2 = C(c, 2 * c, k), C(2 * c, 2 * c, k), P()
        self.conv31, self.conv32, self.pool3 = C(2 * c, 4 * c, k), C(4 * c, 4 * c, k), P()
        self.conv41, self.conv42, self.pool4 = C(4 * c, 8 * c, k), C(8 * c, 8 * c, k), P()
        self.l_conv1, self.l_conv2 = C(8 * c, 16 * c, k), C(16 * c, 16 * c, k)
        self.deconv4, self.conv51, self.conv52 = D(16 * c, 8 * c), C(16 * c, 8 * c, k), C(8 * c, 8 * c, k)
        self.deconv3, self.conv61, self.conv62 = D(8 * c, 4 * c), C(8 * c, 4 * c, k), C(4 * c, 4 * c, k)
        self.deconv2, self.conv71, self.conv72 = D(4 * c, 2 * c), C(4 * c, 2 * c, k), C(2 * c, 2 * c, k)
        self.deconv1, self.conv81, self.conv82 = D(2 * c, c), C(2 * c, c, k), C(c, c, k)
        self.out = Out(c, 1)

    def forward(self, x):
        cat = lambda a, b: torch.cat((a, b), 1)
        e1 = self.conv12(self.conv11(x))
        e2 = self.conv22(self.conv21(self.pool1(e1)))
        e3 = self.conv32(self.conv31(self.pool2(e2)))
        e4 = self.conv42(self.conv41(self.pool3(e3)))
        m1 = self.l_conv2(self.l_conv1(self.pool4(e4)))
        d4 = self.conv52(self.conv51(cat(self.deconv4(m1), e4)))
        d3 = self.conv62(self.conv61(cat(self.deconv3(d4), e3)))
        d2 = self.conv72(self.conv71(cat(self.deconv2(d3), e2)))
        d1 = self.conv82(self.conv81(cat(self.deconv1(d2), e1)))
        return self.out(d1)


def main():
    ckpt_path, out_path = sys.argv[1], sys.argv[2]
    model = R2convNet()
    ckpt = torch.load(ckpt_path, map_location="cpu")
    sd = ckpt["state_dict"]
    # the repo's wrappers name the inner modules .conv/.bn identically, so keys line up 1:1; strip a
    # DataParallel "module." prefix if present.
    sd = { (k[7:] if k.startswith("module.") else k): v for k, v in sd.items() }
    # Deconv3d wraps its transpose-conv as .deconv — flatten to our bare ConvTranspose3d modules.
    sd = { k.replace(".deconv.", "."): v for k, v in sd.items() }
    missing, unexpected = model.load_state_dict(sd, strict=False)
    assert not missing and not unexpected, f"state_dict mismatch: missing={missing} unexpected={unexpected}"
    model.eval()

    dummy = torch.randn(1, 1, 64, 64, 64)
    torch.onnx.export(model, dummy, out_path, input_names=["r2star"], output_names=["r2prime"],
                      opset_version=17,
                      dynamic_axes={"r2star": {2: "d", 3: "h", 4: "w"},
                                    "r2prime": {2: "d", 3: "h", 4: "w"}})

    import onnxruntime as ort
    sess = ort.InferenceSession(out_path, providers=["CPUExecutionProvider"])
    for shape in ((64, 64, 64), (128, 96, 64)):
        x = torch.randn(1, 1, *shape)
        with torch.no_grad():
            ref = model(x).numpy()
        got = sess.run(None, {"r2star": x.numpy()})[0]
        err = float(np.abs(got - ref).max())
        print(f"shape {shape}: max |onnx - torch| = {err:.3e}")
        assert err < 1e-3, "ONNX/torch mismatch"
    print(f"exported + validated: {out_path}")


if __name__ == "__main__":
    main()
