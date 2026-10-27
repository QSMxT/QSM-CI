# ROMEO field mapping (ROMEO.jl)

Combined multi-echo B0 field mapping with the authors' `romeo` command line (ROMEO.jl 08776d4, `ROMEO.unwrapping_main`, with MriResearchTools.jl 771eadf): MCPC-3D-S phase-offset correction, ROMEO unwrapping inside the contract mask, and the phase-SNR weighted B0 (`--compute-B0`), converted from Hz to ppm.

- **Stage:** `field-mapping` (reads `phase`, `magnitude`, `mask`, `params`)
- **Code:** ROMEO.jl at 08776d4 and MriResearchTools.jl at 771eadf, the authors' package, called from `recon.jl` with the package's own
  defaults. [`qsmci_io.jl`](qsmci_io.jl) only reads the inputs, applies `--set` overrides and
  writes the output.
- **Environment:** the shared Julia base image [`algorithms/_julia`](../_julia) (Julia 1.10.11,
  Manifest committed there, packages compiled into a sysimage), pinned by digest in `algorithm.yml`.
- **QSM.rs port:** [`romeo-qsmrs`](../romeo-qsmrs) (same `algorithm: romeo`).
- **Parity only:** the reference of the port's parity pair (`parity/thresholds.yml`, [docs/parity.md](../../docs/parity.md)); not scored and not on the leaderboard.
- **Reference:** Dymerska et al., Magn Reson Med 2021 · doi:[10.1002/mrm.28563](https://doi.org/10.1002/mrm.28563)

## How QSM-CI runs it

```bash
qsm-ci run romeo-romeojl --phase phase.nii.gz --magnitude magnitude.nii.gz --mask mask.nii.gz --params params.json
```

`run.sh` starts Julia with 4 threads (FFTW 4, BLAS 1) and the image's `mritools.so` sysimage.

## Parameters

Defaults are the original's. The *QSM.rs-matched* column is what to `--set` so the pair computes
the same thing as far as the original allows.

| parameter | default | QSM.rs-matched | description |
|---|---|---|---|
| `weights` | romeo | romeo4 | ROMEO weights (`-w`): romeo / romeo2 / romeo3 / romeo4 / romeo6 / bestpath. The command line turns `romeo` into romeo3 (no phase-linearity weight) when a magnitude is given |
| `individual_unwrapping` | false | true | unwrap each echo on its own (`-i`) instead of temporally from the template echo |
| `correct_global` | false | true | remove each echo's global n·2π offset (`-g`) |
| `template` | 1 |  | template echo for temporal unwrapping (`--template`) |
| `temporal_uncertain_unwrapping` | 0 | 0.5 (unused with individual unwrapping) | quality threshold for spatially unwrapping uncertain voxels in temporal mode (EXPERIMENTAL in the CLI) |
| `phase_offset_correction` | on |  | MCPC-3D-S: on (monopolar; the CLI's default with -B) / bipolar / off |
| `phase_offset_sigma_mm` | 7 | 4 (QSMxT's 4 voxels, at 1 mm) | MCPC-3D-S smoothing sigma, mm (one value or three) |
| `b0_weighting` | phase_snr |  | B0 echo weighting (`--B0-phase-weighting`): phase_snr / phase_var / average / TEs / mag / simulated_mag |
| `max_seeds` | 1 |  | maximum seeds (`-s`, EXPERIMENTAL in the CLI) |

## Against the QSM.rs port

- `romeo-qsmrs` runs QSMxT v10.0.0's `qsmxt fieldmap romeo`, which starts from QSMxT's ROMEO settings, not the CLI's: individual unwrapping and global correction on, all four ROMEO weights (`romeo4`; the CLI uses romeo3 when there is a magnitude), MCPC-3D-S with sigma 4 voxels (the CLI: 7 mm), phase-SNR B0. The matched settings give the CLI those values.
- Not configurable in the original, so differences remain: QSM.rs v0.39.0 seeds ROMEO at the mask's centre of mass (ROMEO.jl at the voxel with the best summed edge weights); MCPC-3D-S in MriResearchTools makes its own `robustmask` of the combined magnitude where QSM.rs uses the brain mask.
