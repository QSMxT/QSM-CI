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

The data fitted are built from the magnitude and a QSM reconstructed at each echo, χ(t)
(the paper's Eq. 4):

```
y(t) = M(t)·exp(−i·(2/3)·χ(t)·γ·B0·t)
```

The paper is explicit that the TE-dependent QSM is required: sub-voxel compartments make the
apparent susceptibility drift with TE, and that drift is what the fit separates. The reference
implementation computes χ(t) with STI Suite per echo (Laplacian unwrapping → V-SHARP → STAR-QSM).
Here it is the phantom's `chimap-echoes.nii.gz` (4D, one χ map per echo, same echo order as the
magnitude). A phantom without it falls back to `chimap.nii.gz` (χ_total) for every echo, which
runs but gives every echo the same apparent χ, so the method loses the echo dependence it relies
on; `run.sh` logs which input it used.

This is the same algorithm as the compiled-MATLAB entry [`decompose-qsm`](../decompose-qsm).

- **Stage:** `chi-separation` — reads `chimap-echoes` (4D per-echo QSM, ppm; optional, falls back
  to `chimap`, χ_total), `magnitude` (4D multi-echo), `mask`, `params` (TE, B0); writes `chi-para.nii.gz` (χ+ ≥ 0) and `chi-dia.nii.gz` (|χ−|, positive
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
calls the CLI into a scratch prefix, and gzips the two artifacts into `/output`:

```bash
qsmxt separate decompose --qsm chimap-echoes.nii.gz -m mask.nii.gz -o $WORK/dec \
  --magnitude magnitude.nii.gz --echo-times <t1,t2,…> \
  --field-strength <B0> --b0-direction <B0_dir> [--n-inner N] [--chi-bound PPM] [--max-lm-iter N]
```

`--qsm` is `chimap-echoes.nii.gz` when the phantom ships it and the image's `qsmxt` accepts a 4D
`--qsm` (checked from `qsmxt separate decompose --help`), else `chimap.nii.gz`. The pinned
`qsmxt:v10.0.0` image predates per-echo input, so until it is bumped to a QSMxT release that has
it, the fallback is what runs.

`-o` is a *prefix*: the CLI writes `{prefix}_desc-paramagnetic_Chimap.nii`,
`{prefix}_desc-diamagnetic_Chimap.nii` and `{prefix}_desc-total_Chimap.nii` (the pipeline's BIDS
names, since qsmxt v10.0.0; earlier releases wrote `{prefix}_paramagnetic.nii` etc.). The diamagnetic map already comes out as the positive magnitude |χ−|
(qsmxt negates qsm-core's signed χ− in `commands/separate.rs::save_result`), which is what
[`CONTRACT.md`](../../CONTRACT.md) asks for, so publishing is a straight gzip with no sign flip;
the total map is not a stage artifact and is dropped.

Locally:

```bash
qsm-ci run decompose-qsmrs --chimap chimap.nii.gz --chimap-echoes chimap-echoes.nii.gz \
  --magnitude magnitude.nii.gz --mask mask.nii.gz --params params.json -o out/
qsm-ci run decompose-qsmrs … --set n_inner=4
```

## Parameters

| parameter | default | description |
|---|---|---|
| `n_inner` | 10 | alternating three-stage fit passes per voxel (the reference's inner-iteration count) |
| `chi_bound` | 0.5 | upper bound on \|χ\| in the per-voxel fit, ppm |
| `max_lm_iter` | 30 | max Levenberg–Marquardt iterations per fit stage |

Defaults are qsm-core's `DecomposeParams::default()`; no tuned values are declared.

## Output mapping

The paper defines the paramagnetic component as the PCS, reconstructed from the paramagnetic-pool
sub-model (Eq. 6), and the diamagnetic one as the DCS (Eq. 7). This port returns χ+ = |PCS| and
χ− = −|DCS| (written as |χ−|). The MATLAB reference demo writes DSC to the file `XPSC` and PSC to
`XDSC`, a filename swap; neither this entry nor [`decompose-qsm/recon.m`](../decompose-qsm/recon.m)
follows it.

Note that PCS and DCS are voxel-level components: on voxels planted from the paper's own
three-pool model they track the pool fraction times the pool susceptibility (C+·χ+, C−·χ−), not
the pool susceptibility itself.

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

More threads is **slower** — measured again at 42,168 voxels (1 thread 37.1 s vs 8 threads
205.9 s), with core clocks constant at 3.35 GHz in both, bit-identical outputs at every thread
count, and a control (`qsmxt separate hc-chisep`, same image) scaling normally 3.6 s → 1.4 s from
1 → 8 threads. So this is an upstream scaling bug in qsm-core's decompose loop, not the
environment; `run.sh` pins `RAYON_NUM_THREADS=1` (overridable) until it is fixed, which is also the
fastest setting measured.

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
