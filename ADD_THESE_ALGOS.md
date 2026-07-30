# QSM algorithms to add

Candidate QSM reconstruction methods **not yet in the QSM-CI benchmark**, across background field
removal (BFR), dipole inversion, chi-separation, and field-mapping/unwrapping. Compiled 2026-07-30
from a fan-out web survey (adversarially verified, see sources per row) plus direct repo/license
checks. The goal is a reproducible container-based benchmark, so each row records the thing that
actually gates inclusion: **is there public code, are weights needed/available, and what is the
license.**

Legend for **Obtainability**: 🟢 public repo, ready to package · 🟡 public repo but license
missing/unclear (needs author OK before redistribution) · 🔴 no public code (request from authors) ·
⚪ not open-source (gated license).

---

## Tier 1 — obtainable now (public code)

### Dipole inversion

| Method | Approach | Paper | Code | Weights | License | Lang | Obtain |
|--------|----------|-------|------|---------|---------|------|--------|
| **AMP-PE** | Bayesian approximate message passing; MAP with Laplace sparse-wavelet prior + Gaussian-mixture noise model on the nonlinear complex forward model | Huang et al., *MRM* 2023 (PMC10664815) | [EmoryCN2L/QSM_AMP_PE](https://github.com/EmoryCN2L/QSM_AMP_PE) | n/a (iterative) | **MIT** | MATLAB (needs Wavelet Toolbox) | 🟢 |
| **DeepQSM** | Fully-convolutional (U-Net) dipole inversion trained *purely on synthetic* dipole-forward data; the original synthetic-trained CNN | Bollmann et al., *NeuroImage* 2019;195:373–383 | Colab/tutorial via [dlQSM](https://github.com/dlQSM/dlQSM); check original repo at integration | Pretrained (synthetic) — confirm asset | Confirm | Python (TF) | 🟡 |
| **AFTER-QSM** | Affine-transformation-equivariant network for high-resolution / arbitrary-orientation dipole inversion | Gao et al. (UQ) | [sunhongfu/deepMRI/AFTER-QSM](https://github.com/sunhongfu/deepMRI/tree/master/AFTER-QSM) | Provided in repo | Confirm (repo-level) | Python (PyTorch) | 🟡 |
| **DCRNet** | Dense-connection reconstruction net for accelerated/robust dipole inversion | Gao et al. | [sunhongfu/deepMRI/DCRNet](https://github.com/sunhongfu/deepMRI/tree/master/DCRNet) | Provided in repo | Confirm | Python (PyTorch) | 🟡 |
| **DIP-UP** | Deep-image-prior, unsupervised/untrained unrolled dipole inversion (subject-specific, no training set) | sunhongfu/deepMRI | [sunhongfu/deepMRI/DIP-UP](https://github.com/sunhongfu/deepMRI/tree/master/DIP-UP) | n/a (untrained) | Confirm | Python (PyTorch) | 🟡 |
| **VaNDI** | Variational/Bayesian formulation of NDI (nonlinear dipole inversion) | listed in dlQSM | [NDI_Toolbox (Dropbox)](https://www.dropbox.com/s/ubabfhwfpjphpo1/NDI_Toolbox.zip?dl=0) via [dlQSM](https://github.com/dlQSM/dlQSM) | n/a | Confirm | MATLAB | 🟡 |

> Note: `sunhongfu/deepMRI` is one repo holding several addable methods (AFTER-QSM, DCRNet, DIP-UP,
> plus already-in-benchmark iQSM/MoDIP/xQSM). Worth a single pass to package the missing ones. Its
> per-subdir license needs confirming — the top repo has no clear LICENSE.

### Chi-separation / source separation

| Method | Approach | Paper | Code | Weights | License | Lang | Obtain |
|--------|----------|-------|------|---------|---------|------|--------|
| **APART-QSM** | Iterative (classical) sub-voxel source separation; alternately solves the voxel-wise magnitude decay kernel and sub-voxel χ+/χ− to split para/diamagnetic components; single- & multi-orientation | Li/Wang et al., *NeuroImage* 274:120148 (2023) | [AMRI-Lab/APART-QSM](https://github.com/AMRI-Lab/APART-QSM) | includes test data | **none (no LICENSE)** — ask before redistributing | MATLAB | 🟡 |

> APART-QSM is already referenced on our `data.html` and in `qsm-forward`'s R2′ rationale as a
> single-kernel chi-sep method; it just isn't a benchmarked *algorithm* yet. Highest-value chi-sep add.

### BFR / single-step (joint BFR+dipole)

| Method | Approach | Paper | Code | Weights | License | Lang | Obtain |
|--------|----------|-------|------|---------|---------|------|--------|
| **wfTFI** | Preconditioned **water-fat total field inversion** — single-step joint BFR+dipole that inverts the total field directly (reduces streaking vs local-field inversion); developed for spine but general | Boehm et al., *MRM* 87(1):417–430 (2022) | [BMRRgroup/wfTFI](https://github.com/BMRRgroup/wfTFI) | n/a | Confirm (not clearly stated) | Python (CUDA/GPU) | 🟡 |
| **TFI / adaptive TFI (TFIR)** | Classic total field inversion (single-step); spatially-adaptive regularization variant TFIR | Liu et al. 2017; Wen et al. 2020 (PMC7522736) | ships in the MEDI toolbox / Hongfu Sun's [sunhongfu/QSM](https://github.com/sunhongfu/QSM) | n/a | MEDI academic license | MATLAB | 🟡 |

---

## Tier 2 — published, code not confirmed public (request from authors / track)

| Method | Stage | Approach | Paper | Status |
|--------|-------|----------|-------|--------|
| **CycleQSM** | dipole | Unsupervised physics-informed CycleGAN with a single generator+discriminator (enabled by the known dipole kernel) | Jung et al., arXiv:2012.03842 (2020) | 🔴 no confirmed public repo — contact KAIST (Jong Chul Ye) |
| **QSMDiff** | dipole | Unsupervised 3D **diffusion** model; 3D-patch training + full-size measurement guidance at inference; also super-res/denoise | Xiong et al., arXiv:2403.14070 (2024) | 🔴 no repo on arXiv page; may land in `sunhongfu/deepMRI` — track. Contact UQ/USyd (Xiong/Sun) |
| **QSM-ARCS** | chi-sep | Single-orientation, **GRE-only** para/diamagnetic separation via adaptive relaxometric-constant estimation (no SE/R2′ acquisition needed) | Kan et al., *NeuroImage* 296:120676 (2024) | 🔴 no code found — contact Hirohito Kan (kan@met.nagoya-u.ac.jp) |
| **mc-chi-separation** | chi-sep | Multi-compartment source separation from GRE only; integrates QSM + myelin water imaging (models myelin/water compartmental relaxation & bulk susceptibility) | ISMRM 2025 abstract #1269 (JHU + SNU) | 🔴 conference abstract only, no paper/code yet — track |
| **SHARQnet** | BFR | CNN background-field removal trained on simulated fields; generalizes without parameter tuning | Bollmann et al. 2019 | ⚪ code "available on request" (steffen.bollmann@cai.uq.edu.au) |
| **SEGUE** | unwrap | 3D region-growing spatial phase unwrapping (distinct from Laplacian & ROMEO) | Karsa & Shmueli, *IEEE TMI* 2019 | ⚪ free 24-month academic license via [UCL Ventures](https://xip.uclb.com/product/SEGUE); `.p`/`.m` only, port restrictions |
| **3D region-partition unwrap** | unwrap | Region partitioning + local polynomial modeling for abdominal QSM | Cheng et al., *Front. Neurosci.* 2023 (PMC10684715) | 🔴 no public code — request from authors |

---

## Not worth adding (verified — no new algorithm)

- **QSM.m** ([kamesy/QSM.m](https://github.com/kamesy/QSM.m)) — BFR module only reimplements methods
  already in the benchmark (SHARP, V-SHARP, RESHARP, PDF, LBV, iSMV) plus a self-disavowed `irsharp`
  ("DO NOT USE… does not work"); dipole module (iLSQR, MEDI, NDI, RTS, Tikhonov, TKD, TSVD, TV) is
  fully covered. **One maybe:** `sstgv.m` (single-step TGV) — check whether it differs from our TGV-QSM.
- **SEPIA** ([kschan0214/sepia](https://github.com/kschan0214/sepia)) — MATLAB GUI *wrapper* over
  MEDI/STI Suite/FANSI/SEGUE/NDI; MIT for its own glue code, no novel method.

## Packaging caveats

- **Missing LICENSE files** on APART-QSM, wfTFI, and the `sunhongfu/deepMRI` subdirs mean default
  "all rights reserved" — get author permission before baking into a redistributed container.
- **SNU-LIST chi-separation toolbox** (the iLSQR/MEDI variants + χ-sepnet we already benchmark) is
  itself gated: v1.2.2 ships via a Google Form email, and the repo has **no LICENSE**. Relevant if we
  ever need to redistribute those images rather than have users fetch them.
- Repo availability/licenses drift — re-verify at integration time.

## Suggested next steps

1. **AMP-PE** first — MIT-licensed, self-contained MATLAB, clean fit for a `dipole` submission.
2. **APART-QSM** — highest-value chi-separation add; email AMRI-Lab for a license/redistribution OK.
3. Batch the **`sunhongfu/deepMRI`** methods (AFTER-QSM, DCRNet, DIP-UP) once licensing is confirmed.
4. **wfTFI** as a `bfr+dipole` single-step entry (Python/GPU — mind our CPU-only CI, cf. INR-QSM/MoDIP).
5. Email for the gated ones (SHARQnet, SEGUE, QSM-ARCS, CycleQSM/QSMDiff authors) if we want coverage.

## Sources

Primary: [Jung DL-QSM review](https://arxiv.org/abs/1912.05410) ·
[AMP-PE](https://pmc.ncbi.nlm.nih.gov/articles/PMC10664815/) ·
[DeepQSM](https://www.sciencedirect.com/science/article/abs/pii/S1053811919302605) ·
[CycleQSM](https://arxiv.org/abs/2012.03842) · [QSMDiff](https://arxiv.org/abs/2403.14070) ·
[APART-QSM](https://github.com/AMRI-Lab/APART-QSM) ·
[QSM-ARCS](https://www.sciencedirect.com/science/article/pii/S105381192400171X) ·
[mc-chi-sep (ISMRM 2025 #1269)](https://archive.ismrm.org/2025/1269.html) ·
[wfTFI](https://github.com/BMRRgroup/wfTFI) · [SEGUE](https://xip.uclb.com/product/SEGUE) ·
[deepMRI](https://github.com/sunhongfu/deepMRI) · [dlQSM list](https://github.com/dlQSM/dlQSM) ·
[QSM.m](https://github.com/kamesy/QSM.m) · [SEPIA](https://github.com/kschan0214/sepia)
</content>
</invoke>
