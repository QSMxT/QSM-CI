# DECOMPOSE-QSM (QSM.rs)

Signal-domain susceptibility source separation (Chen et al., *NeuroImage* 2021), as the Rust
implementation in QSM.rs that QSMxT exposes as `qsmxt separate decompose`. Each voxel's multi-echo
complex GRE signal is modelled as three compartments —

```
S(t) = C+·exp(−( a·χ+ + R2*₀ + i·(2/3)·χ+·γ·B0)·t)
     + C−·exp(−(−a·χ− + R2*₀ + i·(2/3)·χ−·γ·B0)·t)
     + C₀·exp(−R2*₀·t)
```

— and fitted with a three-stage alternating bounded least-squares scheme (amplitudes, then R2*₀,
then [χ+, χ−]), repeated `n_inner` times. χ+ and χ− are then reconstructed from the fitted
parameters as a per-compartment phase accumulation, `−Σ angle(model) / ((2/3)·γ·B0·ΣTE)`.

This is the same algorithm as the compiled-MATLAB entry
[`decompose-qsm`](../decompose-qsm), and it keeps that entry's one adaptation: the reference
re-derives a per-echo QSM from raw phase (STI-Suite unwrap → V-SHARP → STAR-QSM) to build the
signal's phase term. QSM-CI provides that per-echo χ(TE) directly as the optional `chimap-echoes`
input (x,y,z,echo, ppm), from the ground truth like `chimap`: no phase input, no STI dependency,
and DECOMPOSE's separation step is isolated from any upstream QSM error. The echo dependence of
χ(TE) is the information DECOMPOSE fits (Chen et al. 2021, Eq. 4; §4.1), so on a dataset that
doesn't ship `chimap-echoes` the fallback — the one `chimap` at every echo — leaves it little to
separate.

- **Stage:** `chi-separation` — reads `chimap` (χ_total, ppm), `magnitude` (4D multi-echo), `mask`,
  `params` (TE, B0), and `chimap-echoes` (χ(TE), 4D, ppm) when the dataset ships it; writes `chi-para.nii.gz` (χ+ ≥ 0) and `chi-dia.nii.gz` (|χ−|, positive
  magnitude), both ppm. No `localfield` and no `r2prime` — DECOMPOSE is GRE-only.
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs) (Rust) —
  `src/separation/decompose.rs`, whose module header documents the model and the output mapping.
- **Reference:** Chen J., Gong N.-J., Chaim K.T., Otaduy M.C.G., Liu C., *NeuroImage*
  2021;242:118477 · doi:[10.1016/j.neuroimage.2021.118477](https://doi.org/10.1016/j.neuroimage.2021.118477).
  (Note: the sibling `decompose-qsm` manifest carries `10.1016/j.neuroimage.2021.118735`, which
  Crossref resolves to a different NeuroImage paper; 118477 is this article.)
- **Image:** `ghcr.io/astewartau/qsm-ci/qsmxt:v10.0.0` — the shared QSMxT engine image
  ([`algorithms/_qsmxt`](../_qsmxt)), already used by the other QSM.rs ports. No new image and no
  Dockerfile: `run.sh` is mounted at run time.
- **Runner:** the default hosted tier (see *Runtime* below).

## How QSM-CI runs it

`run.sh` reads `B0`, `B0_dir` and `TE` from `params.json` with `jq`, forwards any
`n_inner` / `chi_bound` / `max_lm_iter` overrides from `config.json` (the `qsm-ci run --set` path),
passes `chimap-echoes.nii.gz` as `--qsm-per-echo` (or `chimap.nii.gz` once per echo when the dataset
has no `chimap-echoes`; a qsmxt without that flag, such as the pinned v10.0.0, takes `--qsm` alone),
calls the CLI into a scratch prefix, and gzips the two artifacts into `/output`:

```bash
qsmxt separate decompose --qsm chimap.nii.gz -m mask.nii.gz -o $WORK/dec \
  --magnitude magnitude.nii.gz --echo-times <t1,t2,…> --qsm-per-echo chimap-echoes.nii.gz \
  --field-strength <B0> --b0-direction <B0_dir> [--n-inner N] [--chi-bound PPM] [--max-lm-iter N]
```

`-o` is a *prefix*: the CLI writes `{prefix}_desc-paramagnetic_Chimap.nii`,
`{prefix}_desc-diamagnetic_Chimap.nii` and `{prefix}_desc-total_Chimap.nii` (the pipeline's BIDS
names, since qsmxt v10.0.0; earlier releases wrote `{prefix}_paramagnetic.nii` etc.). The diamagnetic map already comes out as the positive magnitude |χ−|
(qsmxt negates qsm-core's signed χ− in `commands/separate.rs::save_result`), which is what
[`CONTRACT.md`](../../CONTRACT.md) asks for, so publishing is a straight gzip with no sign flip;
the total map is not a stage artifact and is dropped.

Locally:

```bash
qsm-ci run decompose-qsmrs --chimap chimap.nii.gz --magnitude magnitude.nii.gz \
  --mask mask.nii.gz --params params.json [--chimap-echoes chimap-echoes.nii.gz] -o out/
qsm-ci run decompose-qsmrs … --set n_inner=4
```

## Parameters

| parameter | default | description |
|---|---|---|
| `n_inner` | 10 | alternating three-stage fit passes per voxel (the reference's inner-iteration count) |
| `chi_bound` | 0.5 | upper bound on \|χ\| in the per-voxel fit, ppm |
| `max_lm_iter` | 30 | max Levenberg–Marquardt iterations per fit stage |

Defaults are qsm-core's `DecomposeParams::default()`; no tuned values are declared.

**At 7 T** (B0 ≥ 6.5 T) the entry also unwraps the phase along the echoes and bounds |χ| at the
echo-spacing limit, π / ((2/3)·γ·B0·ΔTE_max). These are what QSMxT suggests at 7 T (its rules
`decompose.unwrap-7t` and `decompose.chi-bound-7t`, QSM.rs#345), and a QSMxT user gets them by
accepting the suggestion. QSM-CI scores the method as QSMxT runs it. At 3 T the entry runs the
defaults above, the authors' settings. A `--set chi_bound=…` still overrides the bound.

## Output mapping — where this differs from the MATLAB entry

The two DECOMPOSE entries deliberately use **opposite** paramagnetic/diamagnetic output mappings,
so their maps may disagree; scoring both is a purpose of this submission.

Both reconstruct each source from the same fitted parameters, through a paramagnetic sub-model
(`pscModel`) and a diamagnetic one (`dscModel`). The MATLAB reference's demo writes DSC→"XPSC" and
PSC→"XDSC", and [`decompose-qsm/recon.m`](../decompose-qsm/recon.m) follows that swap
(χ+ = |DSC|). The Rust port does not replicate it: its module header records that on the
qsm-forward phantom the swapped mapping anti-correlates with ground truth while the
physically-consistent mapping (χ+ = |PSC|) correlates strongly, so it emits χ+ = |PSC| and
χ− = −|DSC|. On the independent synthetic case used to validate this submission — a phantom
generated from the paper's own three-compartment signal model, with known χ+ and χ− — this port's
χ+ correlated **+1.000** with the true χ+ and −0.03 with the true χ−, and its χ− the other way
round. That is evidence for the non-swapped mapping, not proof for the QSM-CI phantoms: the MATLAB
entry's published chisep-mc scores are positively correlated too (χ+ r = 0.44, χ− r = 0.71), so the
leaderboard comparison is the real test.

## Runtime and tier

Measured with this `run.sh` on a 14-core desktop (Intel Core Ultra 7 155U), image
`qsmxt:v9.16.0`, on a synthetic 6-echo case at `n_inner=10`:

| threads | 12,568 voxels | rate |
|---|---|---|
| 1 (P-core) | 7.7–8.7 s | ~1,500 voxels/s |
| 1 (E-core, pinned) | 10.9 s | 1,150 voxels/s |
| 2 (2 P-cores) | 15.3 s | 820 voxels/s |
| 4 (4 E-cores) | 27.3 s | 460 voxels/s |
| 8 (8 E-cores) | 37.6 s | 334 voxels/s |
| 14 (all, the engine default) | 87.7–97.4 s | ~140 voxels/s |

That table is from before QSM.rs#93: the decompose loop then allocated per voxel, the static musl
allocator serialised those allocations, and more threads was slower. `run.sh` pinned one thread
for it. The loop has been allocation-free since, and scales with the cores at bit-identical
outputs (QSMxT v9.16.0 vs the current loop, 3,200 voxels on a 6-core i5-11500: 2.2 s → 6.3 s from
1 → 8 threads before, 6.9 s → 1.2 s now), so `run.sh` no longer pins it.

At ~1,500 voxels/s on one core, the scored phantoms come out at:

| phantom | mask voxels | echoes | this port (serial, est.) | `decompose-qsm` (measured) |
|---|---|---|---|---|
| chisep-mc | 1,310,432 | | ~15–20 min | 14,818 s (4.1 h) |
| ridani-3t-aniso | 4,994,325 | 6 | ~55–75 min | 36,995 s (10.3 h) |
| ridani-3t-iso | 4,996,381 | 6 | ~55–75 min | DNF (never finished in 12 h) |
| ridani-7t-aniso | 4,996,510 | 4 | ~40–50 min | 28,651 s (8.0 h) |

Even at the conservative end that is ≥5× inside the 360-minute hosted cap on a single core, and
each phantom is scheduled as its own focus task, so this submission declares **no `runner:` and no
`timeout_minutes:`** — the default hosted tier — and no `manual_phantoms:`. `smoke_box: 32` keeps
the per-PR smoke gate at ~30 s (the full scoring run is unaffected).
