#!/usr/bin/env python3
"""Export DIP-UP's pretrained wrap-count CNNs (PHU-NET3D, PhaseNet3D) to ONNX, and verify parity.

WHAT THIS EXPORTS, AND WHAT IT DOES NOT
---------------------------------------
DIP-UP (Zhu et al., Information 2025; doi:10.3390/info16070592;
github.com/sunhongfu/DIP-UP) is a *pretrained CNN + test-time Deep Image Prior loop*.
This script exports **only the pretrained CNN**. The DIP loop is gradient descent on the
network weights at inference time, and `tract` -- the pure-Rust engine QSM.rs uses so the
same code runs in WASM -- does inference only. So the exported graph is the
PHU-NET3D / PhaseNet3D *network*, not the DIP-UP *method*, and must not be labelled
"DIP-UP": the authors' reported accuracy includes the loop.

The net is a 9-class wrap-count classifier: for single-echo wrapped phase it predicts a
per-voxel integer wrap count n, and unwrapping is `phase + 2*pi*n`. Two variants:
  * PHU-NET3D   -- 2 input channels [wrapped phase, Laplacian(wrapped phase)], width 64
  * PhaseNet3D  -- 1 input channel  [wrapped phase],                          width 48

The graph outputs raw 9-channel LOGITS. Decoding (softmax -> expected class -> minus
`shift_base` -> mask -> round) stays in the Rust glue, matching how the other models here
keep pre/post-processing out of the graph.

ARCHITECTURE RECONSTRUCTION
---------------------------
The DIP-UP repo ships `Unet_{1,2}Chan_9Class.py`, both of which `from Unet_blocks import *`,
but **does not ship `Unet_blocks.py`**. The block layout is therefore reconstructed in
`dipup_net.py` beside this script, and verified by `load_state_dict(..., strict=True)`
against the released checkpoints -- every key and shape matches, which pins the layout.
The repo also hard-codes `initial_num_layers = 64`; the released PhaseNet3D is width 48,
so the width is passed in rather than taken from the repo source.
(QSM-CI's `algorithms/dip-up/Unet_blocks.py` is an independent reconstruction of the same
blocks and agrees.)

TWO DELIBERATE DEPARTURES, both documented in PROVENANCE.md:
  1. `DROPOUT`. Upstream's `forward` calls `F.dropout(x, 0.2)` with no `training=`
     argument, so dropout stays ACTIVE after `.eval()` -- upstream inference is
     stochastic. Measured on the phantom, that makes the predicted wrap count disagree
     with itself on ~20-30% of voxels between two runs of the same input. We thread
     `training=self.training`, so `.eval()` disables it. This is standard eval semantics
     and a prerequisite for a deterministic graph; it is not what upstream runs.
  2. `SOFTMAX TEMPERATURE` is not in the graph at all (we emit logits). Note for the Rust
     glue: the authors' `Demo_DIP_*.py` uses `softmax(logits * 10000)` -- effectively a
     hard argmax -- while the repo's own `inference.py` and QSM-CI's wrapper use a plain
     `softmax(logits)`. Those are materially different decodings.

Checkpoints: the authors' Dropbox, linked from the DIP-UP README (the repo itself carries
no weights, and the Zenodo deposit 22091288 is marked "Other (Not Open)").
  PHU-NET3D.pth   274981513 B  sha256 ae34eb7c8bc9b59020ca2450bfb822c1334fe92dd0c2cda6062ff8eec087150b
  PhaseNet3D.pth  154721097 B  sha256 1351b0b0e5ecb5433b511afd4ebf5a518c5cbc1c5448ccf490788967b904904b

Usage:
    export_dipup.py --variant PHU-NET3D  --weights PHU-NET3D.pth  --out phunet3d.onnx
    export_dipup.py --variant PhaseNet3D --weights PhaseNet3D.pth --out phasenet3d.onnx
                    [--dump-ref reference/ref_phunet3d.npz]
"""
import argparse

import numpy as np
import torch

from dipup_net import VARIANTS, load


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    ap.add_argument("--weights", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--dump-ref", help="write a reference input/output pair (.npz) for tract parity")
    args = ap.parse_args()

    in_ch, width = VARIANTS[args.variant]
    net = load(args.variant, args.weights)
    n_par = sum(p.numel() for p in net.parameters())
    print(f"{args.variant}: in_ch={in_ch} width={width} params={n_par/1e6:.2f}M (strict load OK)")

    # EncodingDepth 4 -> four 2x pools, so spatial dims must be multiples of 16.
    example = torch.randn(1, in_ch, 32, 32, 32)
    dyn = {2: "D", 3: "H", 4: "W"}
    torch.onnx.export(
        net,
        example,
        args.out,
        input_names=["phase"],
        output_names=["wrap_logits"],
        dynamic_axes={"phase": dyn, "wrap_logits": dyn},
        opset_version=args.opset,
        do_constant_folding=True,
        dynamo=False,
    )
    print(f"wrote {args.out}")

    # Parity: torch vs onnxruntime, at two sizes so the dynamic axes are actually exercised.
    import onnxruntime as ort

    sess = ort.InferenceSession(args.out, providers=["CPUExecutionProvider"])
    torch.manual_seed(0)
    worst_rel = 0.0
    with torch.inference_mode():
        for shape in [(1, in_ch, 32, 32, 32), (1, in_ch, 48, 32, 64)]:
            x = torch.randn(*shape)
            t = net(x).numpy()
            o = sess.run(None, {"phase": x.numpy()})[0]
            md = float(np.max(np.abs(t - o)))
            # These are unnormalized logits, and the two variants differ ~5x in scale
            # (PHU-NET3D reaches |logit| ~ 100, PhaseNet3D ~ 19), so an absolute
            # tolerance is the wrong yardstick -- the relative figure is ~1.1e-6 for
            # both. The decoded class is what the method actually consumes, so that is
            # the hard gate: a logit perturbation that never changes an argmax cannot
            # change a wrap count.
            scale = float(np.max(np.abs(t)))
            rel = md / scale
            cls_t, cls_o = t.argmax(1), o.argmax(1)
            disagree = float((cls_t != cls_o).mean()) * 100
            print(f"  parity {shape}: max|d| = {md:.3e} (|logit|max {scale:.1f}, "
                  f"rel {rel:.3e}), argmax disagreement {disagree:.5f}%")
            assert rel < 1e-5, f"relative parity failed at {shape}: {rel}"
            assert disagree == 0.0, f"argmax disagreement at {shape}: {disagree}%"
            worst_rel = max(worst_rel, rel)
    print(f"parity OK (worst relative {worst_rel:.3e}, argmax exact at both sizes)")

    if args.dump_ref:
        torch.manual_seed(1234)
        x = torch.randn(1, in_ch, 32, 32, 32)
        with torch.inference_mode():
            y = net(x).numpy()
        np.savez_compressed(args.dump_ref, phase=x.numpy(), wrap_logits=y)
        print(f"wrote reference pair {args.dump_ref} (input {tuple(x.shape)}, output {y.shape})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
