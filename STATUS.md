# χ-separation in QSM-CI — status & findings

Status of the effort to add **χ-separation** (susceptibility source separation — splitting net χ into
paramagnetic χ+ / iron and diamagnetic χ− / myelin·calcium) to QSM-CI, plus actionable findings from
Paula Stoll's MSc thesis on χ-sep simulation & evaluation.

_Last updated: 2026-08-10 (§0 latest session); 2026-07-28 (§1 onward, earlier phase)._

---

## 0. Session 2026-08-08 → 08-10 — faithful Ridani phantom, detrended-NRMSE headline, full rescore, anisotropy verification

### TL;DR
- Shipped a faithful **Ridani (2026)** χ-sep phantom in **`qsm-forward v0.31`** + a `chi-sep` CLI.
- Made the QSM-CI χ-sep leaderboard rank on **detrended NRMSE** (xSIM was too lenient to see anisotropy).
- Re-scored all 6 χ-sep methods against the **new phantom**; delivered an old→new comparison.
- Fixed a chain of infra issues (pre-flattened OSF fetch, decompose timeout, image-access on ci_skip).
- Verified the harder white-matter is the **anisotropy** (not a bug); added an optional **DTI-orientation input**.
- Established the **ceiling**: with the current forward model, WM anisotropy is *not recoverable from the
  GRE/SE signal* — only from DTI. **Next: a multi-compartment hollow-cylinder signal model** (levels 1–3).

### qsm-forward v0.31 (released, PyPI, 52/52 tests)
Faithful Ridani Susceptibility-Separation-Phantom + `qsm-forward chi-sep <data> <bids>`
(`--dr-model {fixed,scaled}`, `--isotropic`, `--no-brain-mask`, `--save-se`). Bottom-up per-tissue χ⁺/χ⁻
with R1/R2*-texture, WM anisotropy (χ⁻ = Δχ·cos²θ + χ₀ from diffusion V1), source/orientation-dependent
R2′ (Dr⁺ spherical, Dr⁻(θ) ∝ sin²θ), source-separation-aware GRE + matched spin-echo. Has an **inert,
unvalidated `chisep_multicompartment` scaffold** — the hook for the next step.

### QSM-CI pull requests
| PR | Status | What |
|----|--------|------|
| #141 | merged | Detrended-NRMSE headline (`avg_ndt`) + Info-tab rewrite (KaTeX equations) + `scripts/validate_phantom.py` |
| #142 | merged | Generator infra: `scripts/gen_chisep.py`, `pack_dataset.py` spin-echo (MESE) packing, dataset README |
| #143 | merged | `apart-qsm` submission **parked** (`ci_skip`, solver omitted); + `image-access.yml` skips `ci_skip`; manifest/taxonomy fixes |
| #144 | merged | **`fetch_dataset.sh`**: fetch chisep as **pre-flattened** (like invivo) — the real unblock for scoring |
| #145 | merged | `decompose-qsm` `timeout_minutes: 720` (was hitting the 360-min self-hosted cap; it runs ~2–7 h) |
| #146 | **open** | Optional **`inputs/fiber_angle.nii.gz`** DTI-orientation input in `gen_chisep.py` |

### Web / Info tab (`web/results.html`)
Info-tab rewrite typeset with **KaTeX** (explicit per-source χ⁺/χ⁻ construction eqs, `χref→χlit`,
overbar = tissue-mean, null solution, a **"The signal"** section with `S(TE) = M₀·exp[−TE·(R2 +
Dr⁺|χ⁺| + Dr⁻(θ)|χ⁻|)]`, the 5× static-dephasing idealisation, Donders/Ridani links). **Detrended-NRMSE
headline** (`Avg detr. NRMSE` default sort; xSIM demoted). Softened null-baseline wording.
Local-only teaching pages: `outreach/chisep-primer.html`, `chisep-explainer.html`.

### Phantom, OSF, fetch
The χ-sep OSF dataset ships **pre-flattened** (`inputs/`+`groundtruth/` at the zip root), NOT BIDS.
`OSF_FILE_CHISEP=38un5`. Cleared the stale `osf-chisep-38un5` Actions cache.

### Rescore: old phantom → new phantom (avg detrended NRMSE, lower=better; all 6 on the new phantom)
| Rank | Method | old → new | note |
|------|--------|-----------|------|
| 1 | **chisep-medi** | 46.3 → **31.6** | only method that improved; new leader |
| 2 | wavesep | 35.7 → 49.2 | was old leader |
| 3 | chisepnet | 44.0 → 56.2 | |
| 4 | susep-net | 58.3 → 56.7 | ~flat |
| 5 | chisep-ilsqr | 65.9 → 74.0 | |
| 6 | decompose-qsm | 110.0 → 135.3 | needed the 720-min cap (ran 436 min) |

Damage concentrated in **χ⁻ (myelin)** = the anisotropy the old phantom lacked. Ranking reshuffled.
Null-solver floor ≈ 37% detrended NRMSE; chisep-medi (31.6) now **beats** it — on the old phantom the
null beat everyone (the degeneracy that motivated the rebuild).

### Anisotropy verification (real, not a bug)
In WM (dseg label **8**): `corr(|χ⁻|_GT, sin²θ) = +0.27`, monotonic ~30% swing (0.033 fibre∥B₀ →
0.042 ⊥B₀); intra-WM χ⁻ CoV ≈ 0.39; null solve self-consistent in WM. **Gotcha:** align V1 (base
0.64 mm/256³) to the packed grid (1 mm/164³) by a direct **0.641 scipy zoom**, NOT `resample_from_to`
(affine mismatch → V1 outside brain → all-zero sin²θ).

### fibre-orientation input (#146)
`gen_chisep.py` writes `inputs/fiber_angle.nii.gz` (fibre-to-B₀ angle in deg from V1, brain-masked;
both `--maps-only` and full paths, anisotropic only). Verified 0–90°, `sin²(angle)` reproduces +0.27.
**Activates on phantom regen + OSF re-upload.**

### Physics findings & the CEILING
- The null solution is **exact** on an isotropic single-Dr phantom (old-phantom degeneracy); anisotropy
  makes R2′ no longer a single-Dr function → breaks it.
- **Current forward-model ceiling:** θ is NOT recoverable from GRE/SE — the phantom models anisotropy
  only as an orientation-modulated **scalar** |χ⁻| feeding an **isotropic dipole** field + a
  **mono-exponential** decay; `validate_phantom` confirms the multi-compartment signature is **inert
  (0.025)**. So without DTI, WM χ⁻ is unrecoverable by *any* method (the "worse WM" is an unbeatable
  floor). Only the optional `fiber_angle` (DTI) helps today.
- In a **real** acquisition θ *is* partly recoverable from GRE/SE via (a) anisotropic-field frequency
  splitting and (b) multi-compartment non-mono-exp decay (hollow-cylinder / Wharton–Bowtell). At
  **single orientation only the multi-compartment route** provides recoverable θ (the tensor field needs
  multi-orientation). → multi-compartment is the high-value, realistic upgrade.

### Multi-compartment hollow-cylinder WM signal — DONE (verified) → qsm-forward PR #7 (NOT merged)
Makes WM anisotropy recoverable from a single GRE/SE acquisition (θ is inert in the shipped scalar +
mono-exp signal; the hollow-cylinder 3-pool model gives a θ-encoding multi-echo beat).
- **Prototype**: `~/repos/qsm/qsm-forward/prototypes/hollow_cylinder/` (`hollow_cylinder.py`, `verify.py`,
  `REPORT.md`). All 3 levels PASS — (1) analytical self-consistency, (2) empirical realism vs
  Wharton–Bowtell/Lee, (3) θ+MWF recoverable to ~1° at SNR 100. Calibrated `χ_I=−0.06, χ_A=−0.10` ppm
  (W&B's −0.12 overshoots ΔR2*).
- **Wired** into `qsm_forward.py` behind `chisep_multicompartment` flag on branch
  `feat/chisep-multicompartment-signal` (astewartau/qsm-forward, **PR #7, unmerged**). 3 commits:
  wiring + self-contained tests (`tests/_hollow_cylinder_ref.py`) + **R2′ fix** (`15a22eb`): WM keeps its
  mesoscopic R2′ (pool T2s carry the irreversible R2, R2′=Dr⁺|χ⁺|+Dr⁻|χ⁻| applied on top via
  `hc_wm_signal(R2p_meso=…)`) so WM keeps susceptibility contrast + stays consistent with `r2prime`.
  Flag-off byte-identical; **62 tests pass**. TODOs: per-tract χ_I/χ_A mapping; denser echo train
  (4 echoes undersample the myelin-water T2~10 ms component).

### ⚠️ CROP / PSF-MISMATCH ARTIFACT in our phantom — ✅ RESOLVED (see "Step-1 RESULTS" below)
`~/repos/qsm/QSM.rs/STATUS.md` (EPG R2/R2′ relaxometry work) Lesson 1: an apparent "R2′ is hard" ceiling
was **not physics** — it was GT built by *image-space downsampling* vs signal built by *k-space
truncation* (two PSFs). **Our chi-sep phantom has this, badly:** the signal-derived R2′ (R2* from
`magnitude` − R2 from `se_magnitude`, mono-exp fits) correlates only **+0.24** with the GT `r2prime`
(QSM.rs: 0.38 cropped → 0.995 no-crop). So a large part of our **"worse WM / high χ⁻ NRMSE / ranking
reshuffle"** is likely this **crop artifact, not anisotropy** — and it would undermine the multicompartment
payoff (θ is in the signal, but the GT it's scored against has a mismatched PSF). NB the anisotropy
*presence* is still real (GT-only corr(|χ⁻|,sin²θ)=+0.27). **Fix (QSM.rs Lesson 2): a *consistent*
GT/signal PSF removes it even with a crop** (their effective-truth reference → 0.995) — so **no native-res
needed; doable at 1 mm locally** (box has 30 GB RAM / 14 cores, above Bunya's 10 GB interactive cap).

### THE PLAN (agreed — do in order; EPG tabled)
1. ✅ **DONE 2026-08-10 — crop artifact isolated & solved** (see "Step-1 RESULTS" below). NB the premise
   "downsample GT like the signal" turned out to be the WRONG fix; the working fix is simulating the
   signal natively at the scoring resolution. Full CI re-score = owner decision (OSF re-upload).
2. **#1 then — multicompartment on the clean phantom.** Regenerate with the PSF fix **+
   `chisep_multicompartment=True`** (PR #7). Re-score + re-do the anisotropy analysis.
3. **EPG tabled for after.** The realistic imperfect-refocusing MESE (`generate_se_signal_epg`,
   `generate_bids(se_refocus_b1=…)`) is **uncommitted WIP in qsm-forward `main`'s working tree** (~225 lines
   in `qsm_forward.py`) — **another agent is actively working on it; DO NOT commit or run destructive git
   ops on qsm-forward main's working tree without stashing it first.** Backup: `/tmp/epg_wip_backup.patch`.
   Fold EPG in once it lands + PR #7 merges (needs combining both qsm-forward states).

**Regen mechanics.** Generator: `scripts/gen_chisep.py` (writes `data/sim/chisep`). The PSF fix likely
lives there / in qsm-forward's `resize` + signal path — check how `gen_chisep_epg.py` does no-crop
(`--voxel 0.64`) and QSM.rs's effective-truth reference, then apply the *consistent-downsampling* fix to
`gen_chisep`. Existing EPG phantoms `data/sim/chisep-epg{,-noiseless,-nocrop}` are **relaxometry-only**
(magnitude/phase/r2_true — NOT full chi-sep datasets), so they can't be scored directly.

R2′-consistency check (reproduce the +0.24): fit R2* from `inputs/magnitude.nii.gz` (TEs from
`params.json`), R2 from `inputs/se_magnitude.nii.gz` (`se_TE`), `R2'=clip(R2*−R2,0)`, corr vs
`inputs/r2prime.nii.gz` in `mask`/WM(`dseg==8`).

### Step-1 RESULTS (2026-08-10, later session) — crop artifact isolated & SOLVED; fix = native-1mm simulation
**TL;DR.** The agreed fix ("downsample GT the same way as the signal") FAILS for this phantom; the
working fix is to **simulate the signal natively at the scoring resolution** (all maps image-space-
downsampled once, then field/GRE/SE generated at 1 mm — no k-space crop anywhere). Implemented as the
new default in `scripts/gen_chisep.py` (`--legacy-psf` = old design), validated end-to-end. The GT is
**byte-identical** to the shipped phantom, so existing scores stay comparable; only the signal changes.

- **Baseline reproduced** (`scripts/check_r2prime_consistency.py`, new): R2′ fit (mono-exp R2* from
  magnitude − R2 from se_magnitude) vs shipped `r2prime` corr **+0.241** brain / +0.236 WM; fit mean
  7.28 Hz vs GT 4.84 Hz.
- **Why the naive kcrop-GT fix fails (twice).** (a) R2′ only reaches **0.34**: the cropped *complex*
  GRE carries **intravoxel dephasing** of the high-res field (R2 from the real-valued SE matches its
  kcropped map at **0.93**; R2* from the complex GRE only **0.50**, ~2 Hz extra decay) — no downsampled
  *map* can represent that; QSM.rs's 0.995 was against a **fit-based** effective truth. (b) the kcropped
  χ GT is **wrecked by Gibbs ringing from extra-cerebral supra-physiological sources** (whole-head χ+
  reaches 18.4 ppm *outside* the brain mask; in-brain GT max is a physiological 0.25 ppm): corr(old,new
  GT) ≈ 0.21, WM |χ−| CoV 0.38→1.31, χ+ min −0.83 ppm. Dead end — code removed.
- **Native-1mm design (VALIDATED, now the generator default).** Maps downsampled once with the same
  `resize` the GT always used → simulate natively, crop no-ops. Checks: **GT md5-identical** to shipped;
  inputs near-identical (chimap corr 0.9999, r2prime 0.994, localfield 0.986 — and localfield is now
  *exactly* dipole-consistent with chimap); anisotropy signature identical (corr(|χ−|,sin²θ)=+0.18,
  WM CoV 0.38); null floor unchanged (37.5% mean detr. NRMSE); multicomp signature still inert (0.028).
  **R2′ consistency: corr = 1.000 noiseless** (fit mean == GT 4.82 Hz); at SNR 100 corr 0.636 ==
  corr(noisy fit, noiseless fit) → purely the 4+4-echo/SNR-100 noise floor (the R2′ subtraction penalty
  methods also face), NOT an artifact. Generator regen is byte-reproducible (md5-checked vs prototype).
- **Attribution: crop vs anisotropy — answered.** Input audit: **wavesep** [chimap,r2prime] and
  **chisepnet / susep-net** [+localfield] are *pure map-world* — inputs and GT already shared the resize
  PSF, so the crop artifact **never entered their scoring loop**; their old→new degradation
  (35.7→49.2, 44.0→56.2) is **real anisotropy**, not crop. Exposed: **decompose-qsm fully** (fits the
  multi-echo magnitude = the 0.24-world), **chisep-medi + chisep-ilsqr mildly** (magnitude as
  weights/noise). **Empirical A/B** (local container runs, old phantom vs 1mm-native): chisepnet avg
  detr. NRMSE **56.25→55.84** (published 56.2 ✓), susep-net **56.67→56.60** (published 56.7 ✓) —
  map-world methods flat, as predicted.
- **Artifacts.** New: `scripts/check_r2prime_consistency.py`; `gen_chisep.py` native-res default.
  Local datasets: `chisep-1mm-noiseless` (effective-truth reference for future relaxometry checks);
  `chisep-1mm-proto` + `chisep-psf` deleted after verification (superseded by the regenerated
  `data/sim/chisep` / recorded above). Recon/score JSONs in `/tmp/rescore/`.
- **Decisions (owner, 2026-08-10): 1mm-native ADOPTED; ONE shipping cycle.** No intermediate OSF
  upload/rescore — verify locally with focused tests, then ship 1mm-native + fiber_angle +
  multicompartment together in a single OSF re-upload + single CI re-score once step 2 is confirmed.
  (The crop-vs-anisotropy attribution is already answered locally, so the intermediate CI cycle adds
  nothing.) **`data/sim/chisep` is now the regenerated 1mm-native + fiber_angle dataset** (old phantom
  backed up at `data/sim/chisep-legacy`): signal/GT md5-identical to the validated `chisep-1mm-proto`,
  plus `inputs/fiber_angle.nii.gz` (0–90°, brain-masked, corr(|χ−|,sin²θ_input)=+0.20 in WM). The
  local generator has #146 folded in (`write_fiber_angle` verbatim).
- **Step 2 next (multicompartment, PR #7) — on this base.** Merge qsm-forward PR #7 (GitHub merge only;
  local qsm-forward tree carries another agent's EPG WIP — don't touch), wire
  `chisep_multicompartment=True` into the native-1mm generator, settle the echo train (4 echoes
  undersample the myelin-water T2~10 ms beat), then verify locally: validate_phantom multicomp
  signature flips non-inert, R2′-consistency holds, θ recoverable from signal, local container A/Bs
  (chisepnet/susep-net pattern from this session). Ship when confirmed: zip inputs/+groundtruth/ →
  replace OSF 38un5 (project y8adf, needs owner OSF_TOKEN; none on this box) → delete Actions cache
  `osf-chisep-38un5` → `gh workflow run score.yml -f scope=<6 chisep methods>`. Runners verified
  online 2026-08-10.

### Step-2 RESULTS (2026-08-10, same session) — multicompartment verified at 1mm-native; 3 PR #7 fixes; echo train settled
**TL;DR.** The hollow-cylinder WM signal works on the 1mm-native base and θ IS recoverable from a
single GRE (oracle probe corr ~0.7, median error ~10°). Getting there surfaced **three real PR #7
defects**, fixed as local commits on a clone of the PR branch at `/tmp/qsmf-pr7` (NOT pushed — owner
review): `953d395` (SE must share the pool-T2 core), `2283825` (WM R2′ was double-counted), `41d4f67`
(NaN fibre angles silently zeroed ~13k WM voxels). 65/65 tests pass. **Bonus: the null solver
collapses 37.5% → 98%** — the benchmark is now far more discriminating. Echo train settled: **8 GRE
echoes 3–45 ms (step 6)**.

- **Defect 1 — SE inconsistency (`953d395`).** With multicompartment on, WM's GRE decays with the
  hollow-cylinder pool T2s but the SE still used the mono-exp R2 map → signal-derived R2′=R2*−R2 in WM
  drifted ~2× from the shipped map. Fix: the 180° pulse refocuses the pools' frequency offsets AND the
  mesoscopic R2′, leaving the plain pool-T2 mixture (what myelin-water imaging measures) — new
  `hc_wm_se_signal`, used for WM SE when the flag is on.
- **Defect 2 — WM R2′ double-count (`2283825`), the big one.** The pool frequency offsets dephasing
  against each other in the GRE ARE mechanistic reversible R2′ (0→18.6 Hz over θ at the shipped
  protocol) — the same physics the imposed Dr⁻(θ)|χ⁻| term (~0→6.3 Hz) approximates. PR #7 applied
  both → WM signal R2′ ≈ 16.3 Hz vs shipped 4.5. Fix: WM signal keeps only paramagnetic Dr⁺|χ⁺| as
  `R2p_meso`; the shipped WM r2prime becomes **Dr⁺|χ⁺| + `hc_wm_r2prime`(θ, mwf, TEs)** — the analytic
  mono-exp-equivalent of the pool interference over the acquisition's TE grid (roundtrip-tested:
  exactly what an R2*−R2 pipeline extracts from the noiseless signal).
- **Defect 3 — NaN fibre angles (`41d4f67`).** `generate_theta_from_v1` is NaN where V1=0; ~13k
  seg==8 voxels without fibre direction went NaN in the WM branch and were **silently zeroed** by
  `generate_signal`'s NaN catch (noise-only voxels in every mc phantom). Fix: GRE, SE and r2prime all
  treat WM voxels with non-finite θ as single-compartment, consistently. Generator side: θ downsampled
  by **normalized interpolation** (`_ds_theta`; spline-interpolating NaNs leaks them).
- **Verification (chisep-mc16-v3, 16 echoes 3–48 ms, all fixes):** R2′-consistency **0.90** brain/WM
  (fit mean 7.81 vs GT 6.84 Hz; legacy phantom was 0.24); θ-probe corr **+0.706**, median |err|
  **10.4°** (single-compartment control: −0.03/43°); GT χ± + chimap + localfield **md5-identical** to
  `data/sim/chisep`; multicomp signature **flips non-inert** via the new θ-detector in
  `validate_phantom` (corr(resid, sin²θ)=0.372 vs 0.050 control; script now reports it);
  **null model 37.5% → 98.0%** detrended NRMSE (degeneracy unexplained 0.67 → 0.97) — WM R2′ is no
  longer closed-form Dr·|χ| arithmetic, so the do-nothing attack is dead.
- **Echo train (probe on echo subsets, no extra sims):** 16 echoes → corr 0.706; **8 echoes 3–45 ms
  step 6 → 0.691** (98% of the benefit, half the data/runtime — decompose-qsm runtime scales with
  echoes); 8 early-only (3–24) → 0.599 (the late-TE anchor matters); current-style 4 echoes → 0.62.
  **Recommendation: 8 echoes [3,9,15,21,27,33,39,45] ms.** SE train unchanged (4 × 10–70 ms).
- **Shipping candidate: `data/sim/chisep-mc8`** (8-echo multicompartment, all fixes). Battery: R2′
  consistency 0.87/0.86 (fit 7.81 vs GT 6.65 Hz), θ-probe 0.690 / 10.9° median, null floor 92.2%,
  signature non-inert (0.249). **Local container A/Bs** (old phantom → mc8, avg detr. NRMSE):
  **chisepnet 56.25 → 78.99** (its internal single-kernel Dr=114 R2′ assumption clashes with the
  mechanistic WM R2′ — realistic model error, barely beats the 92% null), **susep-net 56.67 → 58.62**
  (~flat; feeds R2′ raw). The r2prime INPUT changing in WM is the intended physics upgrade; real
  headroom now exists for anisotropy-aware methods (fiber_angle input + the θ-encoded beat).
- **Owner actions when ready:** review + push the commits from `/tmp/qsmf-pr7` to the PR #7 branch
  (`git -C /tmp/qsmf-pr7 push origin feat/chisep-multicompartment-signal`), merge PR #7, then the
  combined OSF re-upload + single CI re-score per the one-cycle plan.

### Step-2b (2026-08-10, cont.) — MWF fix, fiber_angle fix, V1 misregistration verdict, WM-R2′ SCALE BAKE-OFF
Follow-ups from owner review of the mc8 phantom ("mc8 r2prime looks like a failure"; fiber_angle
looks shifted; do veins survive downsampling?). Agents + local runs; PR #7 clone now carries **5
local commits** (`953d395`, `2283825`, `41d4f67` + `3cc5e27` MWF, `e8bb1a8` hc_b0). 66/66 tests.

- **Veins: fine, better than legacy.** Nearest seg preserves vein volume exactly (ratio 1.00); GT χ+
  at veins identical; vein signal contrast at TE=28 INCREASED (13.7% legacy → 28.6% native — the old
  k-space crop smeared the voids). Lost at 1mm-native: supra-voxel dephasing bloom (known PV trade-off).
- **MWF units bug FIXED (`3cc5e27`).** `hc_mwf_from_myelin_content` anchored at −0.10e-6 (SI) while
  callers pass ppm → MWF pegged at 0.25 in every WM voxel. Now ppm + re-anchored (WM-mean χ⁻ −0.038
  ↦ 0.12): in-phantom WM MWF mean 0.119, p5–p95 0.048–0.190. **Restoring texture also improved θ
  recovery: median error 10.9° → 7.3°** (8-echo, SNR 100).
- **`chisep_hc_b0` knob (`e8bb1a8`)**: evaluate hollow-cylinder pool physics at an effective field
  independent of the acquisition B0. Generator: `--b0`, `--hc-b0`, and fiber_angle now written from
  the SAME resize-path θ as the signal (zoom path was ~1 voxel off-grid).
- **V1 IS misregistered** vs the segmentation: **(+5, +1, −6) voxels (+3.2, +0.6, −3.8 mm)**; V1's
  affine header is stale native-DWI garbage (mutually inconsistent — affine resampling is NOT the
  fix); integer translation suffices (no vector reorientation); possible ~3–6° residual rotation not
  demonstrable from masks. Dice vs BrainMask 0.901→0.924. Fix changes WM χ⁻ GT → apply in the
  shipping regen (put the shift in gen_chisep.py as a documented constant; report upstream).
  Report + overlays: `/tmp/v1_reg/`.
- **WM-R2′ scale bake-off** (all: 8-echo mc, MWF-fixed; datasets `data/sim/bake-*`; sheets + scores
  in `/tmp/bakeoff/`; MC study `/tmp/b0_study/`):

  | | θ med err | R2′ cons. (WM) | null floor | chisepnet | susep | WM R2′ look |
  |---|---|---|---|---|---|---|
  | **7t-mech** (pools @7T) | **7.3°** | **0.89** | **92.0%** | 78.9 | 58.6 | hot (lit-band+) |
  | **hcb0-4p5** (pools @4.5T) | 14.5° | 0.66 | 39.3% | 57.3 | 56.5 | ≈ current scale |
  | 3t (whole acq @3T) | 24.8° | 0.39 | 26.9% ⚠ | 53.9 | 56.1 | dark WM |
  | hcb0-1p27 | 41.9° (dead) | 0.16 | 26.9% ⚠ | 53.5 | 55.6 | dark WM |
  | 7t-scaled (Dr @7T) | 16.3° | **0.90** | 134% | **1805** ⚠ | 102 ⚠ | 20 Hz everywhere |

  Key: weak-mechanism variants (1.27/3T) REOPEN the closed-form null degeneracy (null 27% beats all
  methods — the disease the rebuild cured); 7t-scaled is the truest physics but catastrophically OOD
  for existing DL methods; **7t-mech maximises the benchmark's purpose** (θ recoverable, null dead)
  at the cost of WM sitting above the rest of the phantom's 3T-scale calibration; **hcb0-4p5**
  preserves today's visual scale (null 39% ≈ current 37.5%) at half the θ fidelity.

### Step-2c (2026-08-11) — finalist round → ✅ DECISION: 7t-emp (empirical 7T Dr + true-7T pools)
**Corrections from owner image review + fair-attack re-tests:** (a) 7t-mech's WM≫GM ordering is
unphysical at ANY field (7T WM physics inside a 3T-scale map — chimera, downgraded); (b) 7t-scaled's
"null 134%" was an attack-grid artifact — a fair Dr=755 null scores **27.9%** (closed-form again →
dead); (c) weak-mechanism maps "read as χ+ maps" (the diamagnetic term visually vanishes — owner
called it before the numbers did). New knobs: `--dr-fixed`, `--peak-snr` in gen_chisep.

**The key idea (owner):** the phantom's Dr=137 is a *3T* literature calibration; Dr scales linearly
with B0, so the literature-consistent **7T anchor is ≈320 Hz/ppm** = 137·(7/3). Re-anchored there,
the imposed model's WM myelin term (~15 Hz @90°) nearly COINCIDES with the true-7T hollow-cylinder
mechanism (17.3 Hz) — the calibration and mechanistic universes merge without a fudge factor.

**Finalists** (both: 8-echo, MWF-fixed, mc; datasets `data/sim/bake-{7t-emp,4p5-snr250}`):
| | θ med err | R2′ cons. | null (fair) | signature | chisepnet | susep |
|---|---|---|---|---|---|---|
| **7t-emp** (Dr=320, pools@7T, SNR 100) | 10.2° | 0.91/0.89 | **42.8%** | **non-inert (0.39/0.42)** | 77.7 | **46.5** (best ever) |
| 4p5-snr250 (Dr=137, pools@4.5T, SNR 250) | 10.1° | 0.91/0.90 | 39.3% | inert (0.08) | 57.3 | 56.5 |

Both restore DGM≫WM ordering (7t-emp: WM 9.2 / ctx 11.3 / DGM 21.3 Hz — plausible 7T values).
**✅ OWNER DECISION: 7t-emp.** Rationale: field-consistent throughout (7T scan + 7T relaxivity),
standard SNR, physics visible to both detectors, hardest fair null; the chisepnet-vs-susep split
(77.7 vs 46.5) is the benchmark *discriminating* a hard-coded 3T-era Dr=114 assumption from an
adaptable method — informative model error, per the established "reality doesn't care how they were
trained" stance. Caveats to document: Dr=320 is a principled linear-B0 extrapolation of the empirical
3T calibration, not a directly published 7T number (lit check pending); fixed-weight DL methods are
~2.8× off their training assumption.

**Follow-on (2026-08-11):** `data/sim/chisep-ship` BUILT + verified (R2′ 0.91/0.89, θ 10.4°, fair null
43.4%, aniso corr +0.216 w/ registered V1, susep 46.1/chisepnet 78.1). Outreach: story page
`outreach/chisep-phantom-story.html` + slide deck `chisep-phantom-slides.html` (needs visual check;
3T→7T provenance fix applied — Challenge 2.0 subject was 7T MP2RAGEME). **PR #147 OPEN: `chisep-null`**
— the closed-form null as a scored leaderboard baseline (two-kernel exact solve, Dr⁺=137·B0/3,
py-ref image, auto stage routing; scores 30.1/56.7/avg 43.4 on chisep-ship = the floor, exact-zero on
isotropic). Research thread: signal-derived-θ chi-sep algorithm — **hc-chisep BUILT** (`algorithms/hc-chisep/`,
uncommitted): **avg detr NRMSE 24.6** (para 19.6/dia 29.6) vs null 43.4 / susep 46.1 / chisepnet
78.1 — new best; **signal-derived θ (24.6) beats the DTI arm (25.7)**. R2′-anchored fit: θ 8.4°
regularized (corr 0.86), MWF corr 0.81, beat-mask Dice 0.89, 104s runtime, graceful on no-beat
phantom. Discovery: Ridani Dr convention → Dr⁺=0 in WM / Dr⁻=0 outside. Caveat: hyperparams tuned
on this phantom's GT (in `tuned:`) — owner review before submitting as a PR (like #147). Full
report /tmp/hc-chisep-work/REPORT.md.

### Generator defaults now = RIDANI (2026-08-11, owner request)
`gen_chisep.py --dr-model` default flipped `fixed` → **`scaled`** (Ridani's theoretical field-scaled
kernels); with `--multicompartment` off by default, a BARE `gen_chisep.py` run now reproduces the
Ridani model (their 7T protocol TR 50/flip 15/TEs 4-12-20-28 was already the default). Defaults
deliberately kept non-Ridani: V1 registration shift (bug fix; `--no-v1-shift`), matched SE
acquisition (additive; mono-exp unless mc), native-res packaging. ⚠ CONSEQUENCE: a bare run NO
LONGER reproduces `data/sim/chisep`/`chisep-ship` — the canonical shipping command is now explicit
(documented in the docstring): `--multicompartment --dr-model fixed --dr-fixed 320 --tes
3,9,15,21,27,33,39,45`. Also: the chisep_se_pools opt-out commit was added then REVERTED
(superfluous — `chisep_multicompartment` itself is the Ridani-vs-extension toggle); the canonical
qsm-forward clone stays at the 5 commits (`~/repos/qsm/qsmf-pr7-with-fixes`).

### Documentation & provenance ledger (2026-08-11, session close)
- **Artifacts preserved from /tmp → `reports/2026-08-chisep/`** (local-only, untracked): hc-chisep
  REPORT + contact sheet; non-oracle fitter report/figures + `fitter.py` (the algorithm seed);
  B0-scale MC study; V1 registration report/overlays; all bake-off sheets + score JSONs; and
  **format-patches of the 5 qsm-forward fix commits** (`qsmf-pr7-patches/`). The live clone with
  those commits is ALSO copied to `~/repos/qsm/qsmf-pr7-with-fixes` (push from either; /tmp/qsmf-pr7
  remains the original). Volatile-/tmp risk eliminated.
- **Ridani provenance corrections** (from the PUBLISHED paper `~/mrm.70468.epub` — note the paper is
  now MRM, **doi:10.1002/mrm.70468**; repo/docstrings still cite the bioRxiv DOI — update at ship):
  Ridani does NOT use 137 — they use theoretical field-scaled Y&H kernels (Dr⁺=107.83, Dr⁻=0–133.76
  Hz/ppm/**T**; = our `--dr-model scaled`), field-consistent at both their 3T and 7T sims; the 137
  substitution was OURS (§3.2, for method compatibility). **114** = χ-sepnet paper's regression of
  R2′ on COSMOS QSM over 5 DGM nuclei (R²=0.93); 137 = Shin's earlier equivalent (difference =
  QSM reference). **The "null solution" has NO prior paper** — the equations are Shin 2021's; the
  degeneracy observation, name, and scored-baseline use are this project's (WaveSep with its
  regularization off IS the null solve). Failure-1 attribution: the exact degeneracy was OUR
  first-gen isotropic phantom; Ridani's isotropic variant would carry it too in a benchmark
  configuration (their paper never discusses the trivial solution); anisotropy breaks it only
  INSIDE WM.
- **Outreach set** (all local-only, server: `python3 -m http.server 8901` at repo root):
  `chisep-phantom-story.html` (long form), `chisep-phantom-slides.html` (deck; fixed: 7T provenance,
  PSF definition bullet, slide-13 now uses `img/null_iso_vs_ship.png` — isotropic null err exactly
  0.00000 ppm vs ship 0.008–0.010), `chisep-phantom-talk.md` (supervisor summary + Appendix A
  as-built derivations + Appendix B alternatives).

**Shipping build = 7t-emp config + V1 shift (+5,+1,−6) + resize-path fiber_angle** (both already in
the generator) → final regen + full battery + anisotropy re-verification → ship checklist (push
`/tmp/qsmf-pr7` commits → merge PR #7 → qsm-forward release → OSF 38un5 replace → cache clear →
one score.yml dispatch). NB V1 shift not yet implemented in gen_chisep — do at final regen.

### Verification levels the multicompartment model passed (for reference)
1. self-consistency vs Wharton–Bowtell formulas · 2. empirical realism (MWF, myelin T2, freq/R2*-vs-θ) ·
3. recoverability (fit recovers planted θ+MWF; `validate_phantom` multi-comp signature flips non-inert).

### Handy
Repos: `~/repos/qsm/qsmci/qsmci`, `~/repos/qsm/qsm-forward`. Venv (numpy/scipy/nibabel):
`~/repos/qsm/qsm-forward/venv/bin/python`. Local phantom: `data/sim/chisep/{inputs,groundtruth}`
(1 mm/164³). V1: `~/repos/qsm/qsm-forward/data/maps/V1.nii.gz`. Score dispatch: `score.yml`
`scope=chisepnet,susep-net,wavesep,chisep-ilsqr,chisep-medi,decompose-qsm` (apart-qsm ci_skip).

---

## 1. Where things are at (earlier phase, 2026-07-28)

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
