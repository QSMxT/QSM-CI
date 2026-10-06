# ONNX model provenance

How every deep-learning model QSM.rs runs was obtained, converted to ONNX, verified, and hosted.
This is the answer to *"how did you produce/convert this ONNX?"* — each model is reproducible from
the scripts in this directory plus the sources below.

All models are hosted on OSF project **erv6n** (<https://osf.io/erv6n>), public, direct-download
`https://osf.io/download/<id>/`. The `sha256` + `bytes` in QSM.rs's `src/models/registry.rs` are the
authoritative integrity check (the native downloader verifies them).

## Conversion environment

- **PyTorch / MATLAB-ONNX models** (xQSM, SUSEP-Net, iQSM, iQSM+, and the *clean rebuilds* of QSMnet/
  QSMnet+/AutoQSM): a normal CPU venv — `torch 2.13`, `onnx 1.22`, `onnxruntime 1.29`, `nibabel`,
  `scipy` (Python 3.14). `torch.onnx.export(..., opset_version=17, dynamo=False)`.
- **Legacy TensorFlow / Keras** weight extraction: run *inside the QSM-CI Docker images* which pin the
  original stacks — `ghcr.io/astewartau/qsm-ci/qsmnet:v1` and `qsmnet-plus:v1` (TF 1.14), and
  `autoqsm:v1` (TF 1.15 / Keras 2.2.5). We only *dump weights + a reference output* from these; the
  network is rebuilt in PyTorch outside the container (see below).

## The cross-cutting problem, and the recipe

`tract` (the pure-Rust engine QSM.rs uses, chosen so the same code runs in WASM) **cannot execute
`tf2onnx`-converted TensorFlow graphs** — it fails shape-analysis on the NHWC↔NCHW `Reshape`/
`Transpose` and dynamic deconv-shape ops `tf2onnx` emits (confirmed for QSMnet: tried dynamic, static/
onnxsim, `--inputs-as-nchw`; all fail). `onnxruntime` runs them fine, but adding it as a backend means
a ~15–40 MB native C++ lib and no WASM. So the recipe for legacy-TF models is **not** `tf2onnx`:

> **Rebuild the network in PyTorch, port the original weights into it, validate against a reference
> output from the original framework, then `torch.onnx.export`.** This yields a clean NCDHW graph
> tract runs, keeping everything pure-Rust + WASM + tiny-binary.

PyTorch-native models export directly. A few needed in-graph op rewrites so tract can shape-analyse
them (documented per model, and in each `export_*.py`).

## Per-model record

| Model | Source weights | Approach | Script | tract parity vs ref |
|-------|----------------|----------|--------|---------------------|
| **BFRnet** | `algorithms/bfrnet/BFRnet.onnx` (MATLAB `exportONNXNetwork`, see `algorithms/bfrnet/BUILD.md`) | already ONNX — hosted as-is | — | corr 1.000000, 1.4e-7 |
| **xQSM** | `sunhongfu/xQSM` @ `5d13b36`, GH release `v1.0-demo` `xQSM_invivo.pth` | PyTorch → ONNX (direct) | `export_xqsm.py` | corr 1.000000, 3.2e-7 |
| **QSMnet** | `qsm-ci/qsmnet:v1` image, ckpt `QSMnet_64-25` (TF 1.14) | clean rebuild: TF→PyTorch | `dump/dump_qsmnet_tf.py` → `export_qsmnet.py` | corr 1.000000, 1.7e-6 |
| **QSMnet+** | `qsm-ci/qsmnet-plus:v1`, ckpt `QSMnet+_64-25` | clean rebuild (same net, diff norm) | `dump/dump_qsmnet_tf.py` → `export_qsmnet.py` | corr 1.000000, 5e-7 |
| **AutoQSM** | `qsm-ci/autoqsm:v1`, Keras `model_final_1.hdf5` (TF 1.15) | clean rebuild: Keras→PyTorch | `dump/dump_autoqsm_keras.py` → `export_autoqsm.py` | corr 1.000000, 1.1e-7 |
| **SUSEP-Net** | `algorithms/susep-net/SUSEPNet.pth` (authors' GDrive) | PyTorch → ONNX (3-in/2-out) | `export_susepnet.py` | corr 1.000000, ~1e-7 |
| **iQSM** | HF `sunhongfu/iQSM` — `iQSM_50_v2.pth` + `LPLayer_chi_50_v2.pth` | PyTorch → ONNX (min-patch) | `export_iqsm.py` | corr 1.000000, 1.45e-6 |
| **iQSM+** | HF `sunhongfu/iQSM_Plus` — `iQSM_plus.pth` + `LoTLayer_chi.pth` | PyTorch → ONNX (min-patch) | `export_iqsmplus.py` | corr 1.000000, 1.77e-6 |
| **iQFM** | `sunhongfu/iQSM` — `iQFM_40_v2.pth` + `LoTLayer_lfs_40_v2.pth` (the `lfs` head) | PyTorch → ONNX (same as iQSM) | `export_iqfm.py` | corr 1.000000, 1.23e-6 |
| **QSMGAN** | `mmorri10/QSMGAN-LupoLab` — `WGAN_i64o48/net_best.pt` (legacy torch 1.1 ckpt) | PyTorch → ONNX (generator only, 64³→48³) | `export_qsmgan.py` | corr 1.000000, 1.1e-7 |
| **LPCNN** | `Sulam-Group/LPCNN` — `lpcnn_test_Bmodel.pkl` | PyTorch → ONNX (proximal CNN only; FFT unroll in Rust) | `export_lpcnn.py` | corr 1.000000, 1.8e-7 |
| **IR2QSM** | `YangGaoUQ/IR2QSM` — `model_IR2Unet.pth` | PyTorch → ONNX (whole IR2U-net; /8 pad + mask in Rust; inference AddNoise pinned off) | `export_ir2qsm.py` | corr 1.000000, 4.9e-6 |
| **MoDL-QSM** | `qsm-ci/modl-qsm:v1`, Keras `logs/last.h5` (TF 1.15) | dump weights → clean rebuild Keras→PyTorch (CNN prior only; A/Aᴴ unroll in Rust) | `dump/dump_modl_qsm.py` → `export_modl_qsm.py` | corr 1.000000, 5.7e-7 |
| **χ-sepnet** | SNU-LIST toolbox `240904_xsepnet.onnx` (already ONNX; redistributed with permission) | hosted as-is; norm from `.mat` baked in Rust | `extract_chisepnet_norm.py` | corr 1.000000, 1.3e-7 |
| **NeXtQSM** | `QSMxT/nextqsm` TF ckpt (OSF `zqfdc`) | Rust hybrid: rebuild both U-Nets + hand-code the VarNet VJP as a forward graph → ONNX → graph surgery; FFT data-consistency + 6-step unroll in Rust | `export_nextqsm.py` → `nextqsm_fold.py` | corr 0.999980, 5e-2 |
| **HD-BET** | `ghcr.io/astewartau/qsm-ci/hd-bet:v1` — HD-BET 2.0.1 `release_2.0.0/fold_all/checkpoint_final.pth` (Zenodo 14445620, **CC-BY-NC-4.0**) | PyTorch → ONNX via nnU-Net's own `get_network_from_plans` (dynamic spatial axes); nnU-Net pre/post-processing + sliding window in Rust (`bet::hd_bet`) | `export_hdbet.py`, ref `reference/ref_hdbet.py` | mask vs `hd-bet` CLI Dice 0.99999 (9–31 vox) on 3 cases |

The table above is the *hosted and registered* set. **DIP-UP (PHU-NET3D / PhaseNet3D)** was also
exported and verified against tract, but is deliberately neither hosted nor registered — see its own
section below.

NeXtQSM ships **two** ONNX files — `nextqsm-bf.onnx` (BFR U-Net forward) and `nextqsm-vjp.onnx` (the
regularizer gradient) — registered as one model in registry order (BFR first). Its parity target is
the genuine `nextqsm` CLI (`predict_all.py`, TensorFlow), not a stored tensor; the ~5e-2 ppm spread is
inherent TF-vs-tract float32 drift amplified by the chaotic 6-step unroll (a same-engine ONNX-Runtime
unroll shows the same spread), while the map stays corr > 0.9999. It runs at **full brain resolution**
on tract in pure Rust (192×256×256 in ~4 min at ~10 GB; TF does it in ~84 s at 8.6 GB) — see the
ConvTranspose note below for why that took a graph rewrite.

Reference outputs for the parity tests are regenerated by `reference/ref_*.py` (each runs the
*original* framework's inference on the `data/sim/dev` volume). Every clean rebuild is additionally
validated weight-for-weight against the original: e.g. torch-vs-Keras single-patch for AutoQSM
(5e-7), torch-vs-TF for QSMnet (1.4e-5).

## Problems solved (the interesting bits)

- **QSMnet / QSMnet+ (TF1)** — `tf2onnx` output won't run on tract (above). Rebuilt the 3D U-Net in
  PyTorch. Two gotchas found by stage-by-stage activation diffing: BatchNorm uses a `tf.cond`
  training/inference switch whose training branch's `Switch`/`Assign` nodes break graph re-import
  (handled by only *dumping* weights, not freezing); and **QSMnet's LeakyReLU α is 0.1, not TF's 0.2
  default**. TF conv weights `[k,k,k,in,out]`→torch `[out,in,k,k,k]` (transpose 4,3,0,1,2).
- **AutoQSM (Keras)** — patch V-Net (64³→32³). Rebuilt in PyTorch (no BatchNorm — simpler). The
  sliding-window tiling + 8-voxel linear blend is ported into the Rust glue, not the ONNX.
- **iQSM / iQSM+ (LoT-Unet)** — the LoT layer's in-place boundary-zeroing `out[:,:,[0,h-1]...]=0`
  breaks tract in *every* in-graph form (ScatterND bakes constant indices → size-locks; `Pad` fails
  "analyse"; `Slice`+`Concat` fails the `PushSliceUp` pass). Solved by passing the shell mask as a
  graph **input** `border` and applying `conv*border` (a plain `Mul`); the Rust glue builds `border`.
  Also learned the hard way: **don't hand-reimplement the model forward for export** — a subtle bug
  cost hours (nn.Parameter shares storage with `torch.from_numpy`, so `load_state_dict`'s in-place
  `copy_` silently mutated a module global). Fix: load the *exact* original model and monkeypatch only
  the one op.
- **iQSM+ (OA-LFE)** — the orientation blocks build a conv kernel from the B0 direction and convolve
  each channel with it; `torch.onnx` can't trace the dynamic kernel shape. Since the *same* kernel
  hits every channel, `conv3d(x, K.repeat(C))` == `conv3d(x.sum(channels), K)` with a static kernel —
  numerically identical (batch=1) and exportable.
- **NeXtQSM (TF, variational)** — not a single feed-forward net: a BFR U-Net then a 6-step variational
  dipole inversion whose update is `x ← x − ∇ₓ(λ·E_D + E_R)`, where `E_R = mean|VarNet(x)|` needs a
  **backprop through a U-Net**. `torch.onnx` can't export the autograd. Solution: (1) rebuild both
  U-Nets in PyTorch from the dumped TF weights; (2) hand-code the VarNet VJP `∇ₓ mean|VarNet(x)|` as a
  *forward* graph (conv/conv-transpose/relu-mask/split), validated to ~1e-5 vs autograd and the TF
  reference; (3) the FFT data-consistency gradient + unroll live in Rust. The graph returns the
  **unnormalized** `∇ₓ Σ|VarNet(x)|`; Rust divides by N — keeps the ONNX size-agnostic (no Shape/
  ReduceProd/Div). TF `SAME` alignment: stride-2 conv pads `(0,1)`, so its transpose is
  `ConvTranspose(pad0)` + crop-last-voxel (the exact adjoint). tract's optimized path rejects `Pad`
  ("analyse") and crop `Slice` ("PushSliceUp"), so `nextqsm_fold.py` does **graph surgery**: onnxsim
  folds `Pad`→`Conv pads`, spatial-crop `Slice`→`ConvTranspose pads` (per-voxel crop, size-agnostic),
  and `torch.split` channel `Slice`s→`Split`. Result: a pure conv/relu/split graph tract runs on its
  fast path — no ort, no +28 MB. Fold at static shape (compute crop counts), then re-mark D/H/W
  symbolic so it stays fully-convolutional.
- **NeXtQSM — the 43.5 GB ConvTranspose, and why it runs at full res anyway.** The VJP's backprop
  emits `ConvTranspose` for each conv-adjoint. At full brain resolution (192×256×256) two of these are
  stride-1 full-res ops, and *both* tract and ONNX Runtime materialize their col2im buffer whole:
  `12.6M·32·27·4 B = 43.5 GB` → instant OOM (identical failure on both engines; ort is not a fix).
  A single-op probe pinned it down: at 32ch/full-res a regular `Conv` streams in ~6 GB on tract (~4.5 GB
  ort), but the stride-1 `ConvTranspose` demands the full 43.5 GB. The fix is exact and weight-preserving:
  a cross-correlation's adjoint is a cross-correlation with the kernel spatially flipped and its in/out
  channel axes swapped, so `_adj_same` emits `Conv(x, W.transpose(0,1).flip(2,3,4), pad=1)` instead of
  `ConvTranspose`. Only the two full-res stride-1 adjoints need it; the stride-2 ones (downsampled input)
  stay cheap. Result: full-brain NeXtQSM runs on **tract** (pure Rust, WASM-capable) at ~10 GB, and the
  dev-phantom got ~8× faster as a bonus (138 s → 18 s), since the deconv was both memory-hungry and slow.
- **NeXtQSM — the buggy reference trap.** The first dumped "reference" trajectory disagreed with the
  Rust unroll at corr 0.24. Chasing it: the DC-gradient direction matched exactly but was `/151.417`
  too small — a constant `= √N · 0.14787`. TF's standalone RMSE gradient equals the analytic
  `100/(‖bf‖·‖u‖)·D(Dx−bf)` (verified 3 ways incl. TF fft-grad conventions), so the *code* uses
  prefactor 100. Running the genuine `predict_all.py` (TF) confirmed the **real** output matches the
  prefactor-100 Rust unroll at corr 0.99998, while the stored tensor (buggy dump instrumentation with
  an extra `/√N·c` on the DC term) only correlated 0.24 with it. Lesson: validate against the *actual
  package output*, not a hand-dumped intermediate.
- **LPCNN (learned proximal, unrolled)** — 3-iteration proximal gradient: a k-space dipole
  data-consistency step then a learned CNN proximal. Only the CNN (`gen`) is ONNX; the FFT
  data-consistency, the unroll, the trained step size `α=3.7188` and the mean/std normalization live in
  Rust. The dipole kernel is the **fftfreq/DC-at-corner** convention (unshifted), distinct from
  NeXtQSM's fftshifted centered kernel — the model's ortho FFT expects DC at the array corner. The
  Hz↔ppm round-trip cancels, so the field is fed in ppm.
- **IR2QSM (recurrent, stochastic)** — unlike LPCNN/MoDL the *whole* IR2U-net (depth 4, 4 unrolled
  iterations, reverse concatenations, recurrent middle) is one ONNX graph; the Rust glue only /8-pads,
  crops and masks (ppm passthrough, no normalization). The catch: `IR2Unet.forward` has an **ungated**
  inference-time `AddNoise` (`torch.rand(1) > 0.3` per iteration) making the output mildly stochastic.
  We **pin it to the noise-free branch** (monkeypatch `AddNoise`→identity) so the export is deterministic
  and bit-reproducible.
- **MoDL-QSM (Keras, unrolled model-based)** — 3-iteration model-based gradient descent alternating a
  learned 2-channel CNN prior with dipole data-consistency (A/Aᴴ). Legacy TF 1.15/Keras 2.2.5, so the
  QSMnet/AutoQSM recipe applies: **dump weights inside `qsm-ci/modl-qsm:v1`, rebuild the CNN prior in
  PyTorch, port, export**. Only the prior is ONNX; the FFT A/Aᴴ, the unroll, `α=1.1019` and the
  per-channel `NormFactor.mat` mean/std live in Rust. The A/Aᴴ ortho FFT's `√N` cancels linearly in both
  operators, so the crate's standard normalized FFT pair is used unchanged. Output is the STI χ33
  component. Gotcha (reused): the weight-dump script must not sit on `sys.path[0]` or a stray `inspect.py`
  shadows stdlib `inspect` and breaks scipy inside the py36 container.
- **χ-sepnet (SNU-LIST, already ONNX)** — a 192×192×128 3D U-Net mapping z-scored [QSM, field, R2′/Dr]
  → [χ+, χ−]. The onnx is the SNU-LIST toolbox file itself (not exported by us), hosted with permission;
  the z-score constants (Dr=114) come from the toolbox `.mat` (`extract_chisepnet_norm.py`) and are baked
  into the Rust `ChiSepNetNorm`. The Rust glue runs it as an overlapping 0.75-stride sliding window with
  overlap averaging, then de-normalizes.

## DIP-UP (PHU-NET3D / PhaseNet3D) — exported and verified, NOT hosted, NOT registered

Scoping exercise for QSM.rs #123 (a deep-learning phase unwrapper). The export works and `tract`
runs it; the **measured accuracy does not justify shipping it**, so no weights were uploaded and no
`registry.rs` entry was added. Full write-up and numbers: QSM.rs `docs/DIPUP_SCOPING.md`.
Reproduce with `reference/ref_dipup.py` (+ `reference/dipup_baseline.rs`,
`reference/dipup_tract_parity.rs`).

**What it is.** Zhu et al., *Information* 2025, doi:10.3390/info16070592;
<https://github.com/sunhongfu/DIP-UP>. A pretrained 3D U-Net classifies each voxel of a *single-echo*
wrapped phase into one of **9 wrap-count classes**, so unwrapping is `phase + 2π·n` with
`n = class − shift_base` (`shift_base = 5`, giving `n ∈ [−5, +3]`). Two variants, both EncodingDepth 4
(so spatial dims must be multiples of **16**):

| variant | input channels | width | params | exported `.onnx` |
|---|---|---|---|---|
| PHU-NET3D (paper default) | 2 — wrapped phase + its Laplacian | 64 | 68.72 M | 274 862 616 B, sha256 `3c39349c67ed00ce72bde7cd2a1610290f7f47e161a11e76519caa6a85f4d1fc` |
| PhaseNet3D | 1 — wrapped phase | 48 | 38.66 M | 154 621 948 B, sha256 `222f44d71795fd537a27625317022d39c7a86cd3e254b02b4d72d18fcd5760ea` |

Source checkpoints are on the authors' Dropbox (linked from the DIP-UP README — the repo carries no
weights, and Zenodo 22091288 is marked *"Other (Not Open)"*):
`PHU-NET3D.pth` 274 981 513 B sha256 `ae34eb7c8bc9b59020ca2450bfb822c1334fe92dd0c2cda6062ff8eec087150b`;
`PhaseNet3D.pth` 154 721 097 B sha256 `1351b0b0e5ecb5433b511afd4ebf5a518c5cbc1c5448ccf490788967b904904b`.
The repo has **no LICENSE file**.

**The repo does not ship `Unet_blocks.py`.** Both `Unet_{1,2}Chan_9Class.py` do
`from Unet_blocks import *`, so neither the authors' `Demo_DIP_*.py` nor their `inference.py` runs from
a clean clone. The block layout is reconstructed in `dipup_net.py` and pinned by
`load_state_dict(strict=True)` — all 156 keys and every shape match both checkpoints, which leaves no
freedom in the layout. The repo also hard-codes `initial_num_layers = 64`, but PhaseNet3D is width 48,
so width is a constructor argument. (QSM-CI's `algorithms/dip-up/Unet_blocks.py` is an independent
reconstruction and agrees.)

**Export + parity.** `export_dipup.py`, opset 17, `dynamo=False`, dynamic spatial axes, logits out
(decoding stays in the caller). Exports clean — no graph rewrites needed, unlike the TF-origin models.

| check | PhaseNet3D | PHU-NET3D |
|---|---|---|
| torch ↔ onnxruntime, 2 sizes | rel 1.28e-6, argmax exact | rel 1.13e-6, argmax exact |
| **torch ↔ tract** (`dipup_tract_parity.rs`) | corr 1.00000000, rel 1.57e-6, argmax 0/32768 | corr 1.00000000, rel 1.45e-6, argmax 0/32768 |

Parity is scored **relative**, not absolute: these are unnormalized logits and the two variants differ
~5× in scale (|logit| reaches ~108 for PHU-NET3D, ~19 for PhaseNet3D), so an absolute 1e-4 tolerance
flags PHU-NET3D (max|Δ| 1.6e-4) while passing PhaseNet3D at the *same* relative error. The hard gate is
**argmax exactness** — logit drift that never flips a class cannot change a wrap count.

**Two departures from upstream inference**, both deliberate:

1. **Dropout.** Upstream's `forward` calls `F.dropout(x, 0.2)` with no `training=` argument, so
   dropout stays **active after `.eval()`** — published inference is stochastic. Measured: two runs on
   one input disagree on the predicted wrap count at **30% of voxels** (PHU-NET3D) / **22%**
   (PhaseNet3D). We thread `training=self.training`, so `.eval()` disables it. Standard eval
   semantics, required for a deterministic graph, and *not* what upstream runs.
2. **No softmax temperature in the graph.** The authors' `Demo_DIP_*.py` decodes
   `softmax(logits * 10000)` — effectively a hard argmax — while the repo's own `inference.py` and
   QSM-CI's wrapper use a plain `softmax(logits)`. Materially different decodings; we emit logits and
   leave the choice to the caller (on the phantom the two agree to within 0.1 pp).

**The DIP loop is not exported, and cannot be.** The published method wraps the CNN in a test-time
Deep Image Prior loop — RMSprop on the *network weights* at inference, under masked-TV and
Laplacian-consistency losses. `tract` does inference only. So what is exported is the
**PHU-NET3D/PhaseNet3D network**, which must not be labelled "DIP-UP": the authors' reported accuracy
includes the loop. Note also that the repo's packaged entry point defaults to
`checkpoint: null  # (null = random init)`, and its docstring says *"the network is jointly trained on
the input at inference time (no general checkpoint)"* — in that path the loop is the whole method.

**Conventions the public repo leaves ambiguous, settled by measurement** (`ref_dipup.py ablate`):

- *Input must be brain-masked.* The authors' demo derives its mask as `image != 0`, implying
  pre-masked input. Feeding whole-head phase costs PhaseNet3D ~1.4–9 pp of accuracy.
- *Sign is as-is.* Flipping the phase sign collapses wrapped-voxel accuracy to under 10%, so our
  convention matches training.
- *The Laplacian channel is not recoverable.* Training consumed precomputed `*_wph_10ms_Lap.nii`, and
  the repo ships `dker.mat` (a 27-point isotropic Laplacian) but no script that builds them. The
  27-point kernel, QSM-CI's 7-point `torch.roll` stencil, and the sin/cos identity all land within
  ~2 pp of each other — and **ablating the channel to zeros costs only ~1.5–6 pp**, so PHU-NET3D's
  second input earns little and its convention cannot be pinned down. (QSM-CI's wrapper uses a kernel
  that is not the one the repo ships.)

## Re-registering after a re-export

Run `make_registry_entry.py <cache-name> <file.onnx> <osf-url>` to print the Rust `WeightFile { … }`
snippet (sha256 + bytes), paste into `QSM.rs/src/models/registry.rs`. Current OSF ids:
bfrnet `6a8546e927e06d15b781a605`, xqsm `6a8546cd27e06d15b781a601`, qsmnet `6a854e3fa325bd72433d5cb8`,
qsmnet-plus `6a85500bd7ccc815476a888c`, susep-net `6a8552a5329b2090036a8920`,
autoqsm `6a855583bc038122f06a886f`, iqsm `6a8642664b84b0c1461c0a22`, iqsm-plus `6a864b736621f1b55b6c579c`,
nextqsm-bf `6a8677348d4da2a8c67e7de7`, nextqsm-vjp `6a867742f509e68e077e7d89`,
iqfm `6a868e0fa3ff03ba60cbf576`, qsmgan `6a8690fb8f5c5cc95cdf4e80`, lpcnn `6a869386d8df0e691f8358ed`,
ir2qsm `6a8697a178c9afe009df4fcc`, modl-qsm `6a86990685b99bc066df4fae`, chi-sepnet `6a86985039afa3b755835908`.
