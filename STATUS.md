# χ-separation in QSM-CI — status & findings

Status of the effort to add **χ-separation** (susceptibility source separation — splitting net χ into
paramagnetic χ+ / iron and diamagnetic χ− / myelin·calcium) to QSM-CI, plus actionable findings from
Paula Stoll's MSc thesis on χ-sep simulation & evaluation.

_Last updated: 2026-07-28._

---

## 1. Where things are at

### Shipped (merged)
**[PR #110](https://github.com/QSMxT/QSM-CI/pull/110)** — ✅ **MERGED** (2026-07-28). On merge `score.yml`
kicked off a full re-run to publish χ-sepnet + susep-net to the live leaderboard; **score CI still running
as of 2026-07-28** (see "CI / re-score status" below). It added:
- A **`chi-separation` stage** (consumes local field, R2′, χ_total, multi-echo GRE → produces χ+ and χ−).
  The `qsm-ci run` CLI, scorer and pipeline were generalised single-output → multi-output.
- **Source-specific scoring** (`eval/qsm_eval.py::chisep_metrics`): χ+ → DGM-iron / vein NRMSE +
  DGM-linearity; χ− → calcification moment/streak; plus a **cross-contamination "leakage"** term.
- **Two working deep-learning methods**, containerised (CPU, run fully offline):
  - **χ-sepnet** (SNU-LIST, ONNX) — χ+ 0.93 / χ− 0.83 xSIM vs GT.
  - **SUSEP-Net** (PyTorch) — χ+ 0.83 / χ− 0.88.
- **Web**: QSM ⇄ χ-separation leaderboard tab, greyscale χ+/χ− detail viewer with source toggle,
  source-specific metrics panel; humanised runtimes; display names (not slugs) on the board + viewer.
- **CI routing** (both `evaluate` and `score`): χ-sep methods fetch a separate chisep phantom (OSF)
  and score isolated-only; QSM methods unchanged.

### CI changes made
- `evaluate.yml` is now a **smoke gate** — `pipeline.py --smoke` crops inputs to a central box, runs
  the submission in its container, and asserts a valid (present/finite/non-empty) output; **no scoring**
  (score.yml does the real scoring on merge). Catches broken run.sh / crashes / permission bugs cheaply.
- `pipeline.yml` (engine-parity test) triggers only on the 3 methods it runs (romeo-fieldmap/vsharp/rts).
- `score.yml` routes χ-sep methods to the chisep phantom as dedicated `--focus` jobs.

### CI / re-score status (2026-07-28)
- Post-merge `score.yml` re-run (run `30325029846`) **in progress**. Status:
  - ✅ **Both χ-sep methods scored fine** — `f-chi-sepnet` (chisep) and `f-susep-net` (chisep) both
    **success**. So the merge goal (publish χ-sepnet + susep-net) is met once the run finalizes.
  - ✅ All 12 sharded QSM jobs (`s00`–`s11`) success.
  - ❌ **`f-inr-qsm` (self-hosted, Linux/X64) failed with exit 137** = OOM-kill. inr-qsm, not a chi-sep
    method. Likely memory contention from a concurrent job on the self-hosted runner.
  - ⏳ **`f-modip` (ubuntu-latest, 360-min)** still running.
- Plan: **retry `f-inr-qsm` once the other self-hosted job clears** so they don't contend for memory. If
  it OOMs again solo, the fix is a bigger runner / per-job memory bump, not a code change.

### Infrastructure
- chisep phantom on OSF (`38un5`); repo secret `OSF_FILE_CHISEP` set. GT (χ+/χ−) held out like the QSM
  phantom. `pack_dataset.py --chisep` / `fetch_dataset.sh chisep` build it.
- Both images public on GHCR (`ghcr.io/astewartau/qsm-ci/{chi-sepnet,susep-net}:v1`).

### Method status
| method | type | status |
|---|---|---|
| **χ-sepnet** | DL (ONNX) | ✅ working, containerised, MERGED (PR #110) |
| **SUSEP-Net** | DL (PyTorch) | ✅ working, containerised, MERGED (PR #110) |
| **χ-sep iLSQR** | iterative (MATLAB) | ⚠️ **works when fed STI-Suite's own `QSM_iLSQR` output** (not the phantom's GT χ_total). Modest (χ+ xsim 0.49 / χ− 0.32). `recon.m` **updated to the working v3 pipeline** (in-house QSM_iLSQR → chi_sep_iLSQR + N_std). Remaining: MATLAB runner needs STI Suite on `$CHISEP_STISUITE`; mcc/matlab-runtime image + score routing to publish. See §1.5. |
| **χ-sep MEDI** | iterative (MATLAB) | scaffolded, untested; needs Bunya test + mcc/runtime image. Held out. |
| **APART-QSM** | iterative (MATLAB) | scaffolded, **blocked** — core solver `apart_qsm_single_ori.m` isn't in the public repo. Needs author request. Held out. |
| **DECOMPOSE-QSM** | iterative (MATLAB) | gated — email `STI.Suite.MRI@gmail.com` (drafted). Not started. |
| **WaveSep** | wavelet (iterative, weight-free) | ✅ **INTEGRATED + scored** — χ+ xsim **0.834** / χ− **0.692** (best iterative; on par with the DL methods). `algorithms/wavesep/` built + container-tested locally. Author gave academic-use permission. Remaining: push GHCR image + score routing. See §1.6. |

### What's left
1. ✅ **PR #110 merged** (2026-07-28); **χ-sepnet + susep-net already scored green** in the re-run.
   Remaining: let `f-modip` finish and **retry the exit-137 (OOM) `f-inr-qsm` job** after the self-hosted
   runner clears, then confirm the leaderboard published (see CI status).
2. ✅ **Bunya iLSQR verdict — scored + wired** (see §1.5). Owner said "put iLSQR up". `recon.m` now uses
   the working v3 pipeline (in-house STI-Suite QSM_iLSQR). Remaining to publish: STI Suite on the runner
   (`$CHISEP_STISUITE`) + mcc/matlab-runtime image + score.yml routing. Can't build/test the MATLAB
   container here (no local MATLAB) — verified via the Bunya run.
2b. ✅ **WaveSep INTEGRATED + scored** (χ+ 0.834 / χ− 0.692; see §1.6). Owner action: `docker push`
   `ghcr.io/astewartau/qsm-ci/wavesep:v1` (make public) + add score.yml routing (chisep phantom).
3. **Two emails** (owner): DECOMPOSE + APART-QSM solver.
4. **Follow-up methods**: MATLAB ones via `mcc` + matlab-runtime images (incl. iLSQR per §1.5); APART
   (blocked); **WaveSep** (scouted §1.6 — weight-free, easy to containerise, but needs a licence OK from
   the author first).
5. **Thesis-driven improvements** — see §3.

### Open decisions / caveats
- **Dr model**: ✅ **RESOLVED — unified on a SINGLE kernel Dr=137 Hz/ppm** across qsm-forward
  (`generate_r2prime`, `generate_dr_maps`, and the chi-sep GRE signal all share one `DR_KERNEL=137`),
  so the saved r2prime == the GRE R2′ content == the SE-derivable R2′ = R2*−R2. Provenance (see §3.2):
  137 is Shin's empirical single kernel (multi-orientation, 2022); 114 is the equivalent COSMOS-referenced
  single value (χ-sepnet). Our old split (114/30) was **ours, unsourced** (the `30` has no published
  basis) and contradicts the single-kernel chi-sep literature. The split survives only as an explicit
  off-by-default opt-in (`generate_r2prime(dr_neg=…)` / `--dr-neg`). **χ-sepnet's internal Dr=114 is left
  as-is** (its own training assumption; not retuned to the phantom — the small 137-vs-114 mismatch is a
  real, informative model error, per "reality doesn't care how they were trained"). Local
  `data/sim/chisep/inputs/r2prime.nii.gz` rebuilt at 137. **Owner action: regenerate + re-upload the OSF
  chisep phantom** (`38un5`) with qsm-forward ≥ v0.29 so the live benchmark uses 137.
- The smoke crop (96³) is safe for chi-sep + most QSM methods, but a method needing the full brain +
  background could false-red; fix is bumping `--smoke-box` or skipping the crop for that stage.
- χ− is intrinsically hard to recover (all methods score it poorly) — we score χ+/χ− separately, which
  the thesis validates.

### 1.5 χ-sep iLSQR — Bunya diagnostic verdict (2026-07-28)
Ran `chi_sep_iLSQR` on the chisep phantom under **native MATLAB (R2023b) on Bunya** (bun109), 3 variants
(`/scratch/user/uqaste15/chisep_ilsqr/`). Scored locally against held-out GT with `qsm_eval.py --kind
chisep` (seg + mask), χ+ and χ−:

| variant | what it changes | χ+ xsim | χ+ corr | χ+ nrmse | χ− xsim | χ− corr | leak |
|---|---|---|---|---|---|---|---|
| v1_baseline | GT χ_total as QSM input, N_std=1 | 0.22 | 0.27 | 136 | 0.17 | 0.14 | 0.029 |
| v2_csf_nstd | + CSF mask + real N_std | 0.22 | 0.27 | 136 | 0.17 | 0.14 | 0.029 |
| **v3_stiqsm** | **+ STI-Suite `QSM_iLSQR` as the QSM input** | **0.49** | **0.84** | **56** | **0.32** | **0.76** | **0.0004** |

**Findings:**
- **NNLS now converges** on native MATLAB (v3 reaches the 0.01 target by iter 7–9; v1/v2 plateau ~0.03–0.07).
  The earlier *local* "NNLS never converged / pure artifact" was an **environment** problem, not the algorithm.
- **CSF mask + real N_std did nothing** (v1 ≡ v2, byte-for-byte ranges).
- **The real lever is the QSM input.** Feeding the phantom's GT χ_total (`chimap.nii`) → garbage; feeding
  a QSM produced by **STI-Suite's own `QSM_iLSQR`** (from the same local field) → a real reconstruction
  (χ+ corr 0.84) and ~70× lower cross-contamination leakage. The toolbox's streaking/NNLS steps are tuned
  to its own QSM scaling/orientation conventions, not an external χ map. (Diag: `QSM_iLSQR` range
  [-3.77, 0.96] vs GT chimap [-2.95, 0.47].)
- **Quality is modest** — χ+ xsim 0.49 vs χ-sepnet 0.93 / SUSEP 0.83. A legitimate iterative *baseline*,
  not a contender. χ− weak (xsim 0.32) as expected.

**Decision (owner):** containerise iLSQR as a baseline? If yes, `run.sh` must run STI-Suite `QSM_iLSQR`
on the input local field first, then `chi_sep_iLSQR` — the phantom supplies field, not a toolbox-native
QSM. Needs `mcc` + matlab-runtime image (like the other MATLAB methods). Artifacts on Bunya:
`chisep_ilsqr/{run_ilsqr_variants.m,out/}`; scored copies pulled to `/tmp/ilsqr_out/`.

### 1.6 WaveSep — INTEGRATED (2026-07-28)
Thesis's top χ+ performer. **Public source, weight-free — now a working QSM-CI submission**
(`algorithms/wavesep/`). Author granted academic-use permission, so the licence blocker is cleared.

**Scored on the chisep phantom** (`qsm_eval.py --kind chisep`, held-out GT):

| component | xsim | corr | nrmse | region | leak |
|---|---|---|---|---|---|
| χ+ (para) | **0.834** | 0.960 | 28.0 | dgm 17.0 | 0.000 |
| χ− (dia)  | **0.692** | 0.921 | 40.6 | calc 14.6 | 0.018 |

Best iterative method by far (iLSQR χ+ 0.49) and on par with the DL methods (χ-sepnet 0.93, SUSEP 0.83)
— consistent with the thesis ranking WaveSep top on χ+. Converges in ~12 iterations (early stop).

**Submission** (`algorithms/wavesep/`): our thin `recon.py` wrapper drives the vendored solver;
`run.sh`, `algorithm.yml`, `Dockerfile`, `BUILD.md` follow the susep-net pattern. Validated three ways
(local venv, wrapper via qsm-ci contract, and the built container) — all identical scores. Container
built locally as `ghcr.io/astewartau/qsm-ci/wavesep:v1` (CPU, ~no deps beyond numpy/pywt/nibabel).
**Owner action: `docker push` the image (make GHCR pkg public) + add score.yml routing** (chisep phantom,
like chi-sepnet/susep-net). The vendored WaveSep source + Dockerfile are gitignored (not redistributed);
committed files are just the 4 wrappers.

Provenance / implementation details below (kept from scouting):
- **Paper:** Fang, Shin, van Zijl, Li, Sulam, *"WaveSep: A Flexible Wavelet-Based Approach for Source
  Separation in Susceptibility Imaging"*, MLCN 2023 (MICCAI workshop), Springer LNCS,
  DOI [10.1007/978-3-031-44858-4_6](https://doi.org/10.1007/978-3-031-44858-4_6). No free preprint found
  (paywalled Springer + PubMed PMID 41816320 only).
- **Code:** [github.com/ZhenghanFang/WaveSep](https://github.com/ZhenghanFang/WaveSep) (author's personal
  GH, JHU — *not* SNU-LIST). Last updated 2025-05.
- **It is NOT a deep net (for the QSM path).** README says "PyTorch" but the QSM separation solver
  (`wavesep/qsm_sep.py` → `solver_wavesep_qsm.py`) is **pure NumPy + PyWavelets** — ISTA-style
  soft-thresholding, `db4` wavelet. **No pretrained weights required.** (The paper's "learned proximal
  operator" refers to the upstream dipole inversion, which WaveSep takes as a pre-reconstructed QSM input.)
- **Deps:** `nibabel, PyWavelets, scikit-image, numpy, matplotlib, tqdm, PyYAML` — CPU-only, no torch/CUDA,
  no weight downloads. Trivial `python:3.10` + `pip install -r requirements.txt` container.
- **Inputs (`data/yml/template_qsm.yml`):** a reconstructed QSM (χ_total), R2′ map(s), brain mask, B0
  direction(s), and a params JSON with `Dr_pos`/`Dr_neg` (a 2025-04 update supports `Dr_pos ≠ Dr_neg`).
  **Supports multiple head orientations** (lists of R2′ + H0). All images must be **LPS**. Outputs χ+
  (`x_pos`) and χ− (`x_neg`).
- **Licence: no LICENSE file** (GitHub `license: null`) but the **author granted academic-use
  permission** for this benchmark, so we don't redistribute the source (gitignored + baked into the
  image). Note: our phantom is single-orientation, so WaveSep's multi-orientation advantage won't show
  (matches thesis pitfall #2) — yet it still tops the iterative methods on χ+ here.

---

## 2. Design notes

- **χ− convention**: stored as a POSITIVE magnitude in both GT and recon outputs.
- **χ-sepnet preprocessing** (reverse-engineered, validated): input channels `[QSM, field, R2′/Dr]`
  z-scored by the training `.mat` stats, Dr=114, field/χ in ppm, 192³ sliding-window patches.
- **SUSEP-Net preprocessing** (from its code): input channels `[QSM, R2′, local field]` z-scored by
  `all_mean_std.mat`; R2′ fed raw in Hz (no Dr scaling); whole-volume; outputs χ+/χ− via a final ReLU.
- **iLSQR failure**: output ~10× underestimated, calcification missing, R2′ had zero effect, NNLS never
  converged locally — a black-box `.p` wiring issue, not the R2′ model. Bunya (native MATLAB) is testing
  the toolbox's intended preprocessing.

---

## 3. Findings from Paula Stoll's MSc thesis

"Development of a Deep Learning Framework for Iron and Myelin Mapping from QSM" (ETH/UQ, Nov 2025;
advisors Bollmann + Stewart). Directly extends the QSM forward model for χ-separation and benchmarks the
same methods we're integrating. Notation: her "Dr" ≈ our relaxivity; "κ" is her R2*↔R2′ scaling.

### 3.1 Phantom / simulation
- **Digital phantom from ONE real 3T subject** (§3.1.1): multi-echo GRE (7 echoes, TE 5.18–29.18 ms,
  1 mm iso), MP2RAGE (R1/T1), multi-echo SE (16 echoes, R2/M0). Processed with QSMxT (ROMEO, V-SHARP,
  RTS, NumART2*), qMRLab, ANTs.
- **Segmentation**: SynthSeg → 7 classes; deep-GM nuclei manually segmented on the QSM; **vessel mask
  from a 3D Frangi filter on R2*.**
- **χ+/χ− generation** (Eq 3.1–3.2): assumes intra-brain χ = iron + myelin, both **linear** in χ
  (Stüber 2014). χ+ = piecewise-constant per-region iron (Table 4.1) **modulated by measured R2* for
  intra-region texture**: `[Fe] = mean[Fe] + c·(R2* − mean R2*)`, **c = 0.0526**. χ− from the R1 map via
  the linear myelin↔R1 relation. Non-brain: piecewise-constant.
- **Per-region iron** (Table 4.1): TH 4.76, WM 1.80, GM 3.87, CSF 0.006, PU 13.32, GP 21.30, CN 9.28,
  DN 10.35, RN 19.48, SN 18.46, vessels 45.80.
- **Anisotropy explicitly NOT modelled** (stated limitation).

### 3.2 R2′ / relaxivity model (✅ RESOLVED — single Dr=137)
- **Static-dephasing R2′** (Eq 3.3): `R2' = Dr·(|χ+| + |χ−|)` — a **SINGLE shared Dr** for both sources
  (dephasing depends on |Δχ|, not sign). Basis: Yablonskiy–Haacke static-dephasing regime (holds only for
  low source concentration + low diffusivity).
- **Provenance dug up (2026-07-28):** thesis Eq 3.3 uses one kernel Dr=137 (ref [54] Shin multi-orientation
  2022). The canonical χ-sep model (Shin 2021 [53]) is explicitly a single spatially-invariant kernel.
  Published single-kernel values: **137** (Shin, empirical) and **114** (χ-sepnet, COSMOS-referenced,
  R²=0.93) — the *same quantity* differing only by QSM algorithm. Our old **split 114/30 was ours**
  (qsm-forward commit edd8db5), **unsourced** (the 30 has no published basis) and inconsistent with both
  the literature (single kernel) and the NeuroPoly phantom we ported (theoretical ~755/700 kernel).
  **Decision: adopt single Dr=137** — see §1 Open decisions for the implementation + owner action.
- **R2* from R2′** (Eq 3.4): `R2* ≈ κ·R2'`, **κ = 1.91** (Dimov 2022).
- **R2**: `R2 = R2* − R2'`; negative relaxation rates clamped to 0.

### 3.3 Signal / noise
- **GRE** steady-state signal with explicit phase-offset φ0 (Eq 1.5).
- **SE signal** (Eq 3.5): `S_SE = M0·(1−e^(−TR·R1))·e^(−TE·R2)` — **her main forward-model extension;
  qsm-forward does not currently emit SE data.**
- Realism (noise, shim, φ0) inherited from the QSM Challenge 2.0 forward model — modest, not heavy
  augmentation. No elaborate background fields / explicit wrapping in her extension.

### 3.4 Evaluation methodology
- Global: pSNR, NRMSE, HFEN, **XSIM** with K1=0.01, K2=0.001, L=1.0 (**confirmed our eval matches**:
  c1=1e-4=(0.01)², c2=1e-6=(0.001)²).
- **Per-region linear regression** (slope + R²) reconstruction-vs-GT across 9 regions (Fig 4.4) — a
  direct quantification-linearity/bias metric. χ+ recovers well (slope ~0.8–0.9, R²~0.98); **χ− poorly**
  (R² down to 0.02–0.39, some negative slopes).
- **Bland–Altman per region** (Fig 4.9) — exposes systematic **underestimation of high-χ regions**
  (e.g. dentate). Line profiles (Fig 4.10) for local peak under-recovery.
- Method comparison (Table 4.2): 7 methods incl. χ-sepnet (R2*/R2′), SUSEP-Net, χ-sep iLSQR/MEDI,
  APART-QSM, **WaveSep**. **WaveSep best on χ+** (NRMSE 32%, XSIM 62.5%); APART/SUSEP underestimate; **χ−
  uniformly poor** (NRMSE 78–87%) across all methods.
- Pitfalls: (1) evaluate χ+/χ− separately — χ− is unreliable; (2) DL didn't beat iterative on *simulated
  single-orientation* data (their in-vivo labels came from multi-orientation — a sim can't reproduce that
  advantage), so caution ranking DL vs iterative on synthetic phantoms; (3) sim can produce
  supra-physiological χ (dentate) that no method recovers — clamp the dynamic range; (4) linear
  iron/myelin↔χ + static-dephasing assumptions (from post-mortem tissue) may not hold in vivo.

### 3.5 Prioritized takeaways
1. **Add SE-signal simulation to qsm-forward** (Eq 3.5) — ✅ **DONE, shipped in qsm-forward v0.28** (on
   PyPI). `generate_se_signal` + `generate_bids(save_se=True)` + `ReconParams.se_TR/se_TEs` + CLI
   `--save-se/--se-TR/--se-TEs`. SE = `M0·(1−e^(−TR·R1))·e^(−TE·R2)`, R2-only decay, no phase; validated
   on the head phantom (monotonic decay + R2 round-trip vs GT). NOTE: R2 is generated independently from
   literature T2 (`generate_t2_map`), so SE is **decoupled from the Dr decision** (item 3). NOT YET wired
   into the QSM-CI phantom — see "next" below.
2. **Add per-region slope+R² regression + Bland–Altman bias metrics** — cheap, high diagnostic value;
   exposes high-χ underestimation and χ− unreliability that global xSIM/NRMSE hide.
3. **Reconcile the Dr model** — ✅ **DONE**: unified on single Dr=137 across qsm-forward (`DR_KERNEL`),
   documented + cited (Shin 2021/2022); split kept as off-by-default opt-in; old 114/30 shown to be
   unsourced. See §1 / §3.2. (κ=1.91 R2*-cross-check still available via the SE chain, unchanged.)
4. **Scout WaveSep** — her top χ+ performer, not yet on our list.
5. **R2*-modulated intra-region texture** (c=0.0526) — avoids flat "cartoon" χ+ maps (needs a real R2*/R1).
6. **Cross-check per-region iron values** (Table 4.1) against our phantom.
7. **Supra-physiological χ clamp** — keep the phantom's dynamic range physiological.
8. xSIM constants — **already matched**, no change.
9. Document known limitations (no anisotropy, static-dephasing-only, linear post-mortem model).

_Thesis PDF: `~/downloads/MasterThesisPstoll.pdf`._
