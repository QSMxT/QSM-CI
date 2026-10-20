# DECOMPOSE-QSM, complex-signal fit (QSM.rs)

DECOMPOSE (Chen et al., *NeuroImage* 2021) fitted to the **measured** multi-echo complex GRE
signal, as QSMxT's `qsmxt separate decompose-complex` (QSM.rs `separation::decompose_complex`).
Each voxel's signal is modelled as

```
S(t) = [ C+·exp(−( a·χc+ + R2*₀ + i·(2/3)·χc+·γ·B0)·t)
       + C−·exp(−(−a·χc− + R2*₀ + i·(2/3)·χc−·γ·B0)·t)
       + C₀·exp(−R2*₀·t) ] · exp(i·(φ₀ + Δω·t))
```

with all eight parameters fitted jointly (bounded Levenberg–Marquardt, multi-start). The free
phase offset φ₀ and frequency Δω take up the transmit/receive phase and every field not produced
inside the voxel, so the method needs no χ_total, no local field and no background removal.
The sources written are the voxel averages χ+ = C+/ΣC·χc+ and χ− = C−/ΣC·χc−.

The sibling [`decompose-qsmrs`](../decompose-qsmrs) instead rebuilds the phase as linear in TE from
the provided χ_total, which the three-pool model cannot produce; this entry fits the phase the
pools actually create.

- **Stage:** `chi-separation`, declaring `inputs: [magnitude, phase, mask, params]`. `phase` is
  outside the stage contract, so it is a declared extra (mounted from the dataset's
  `inputs/phase.nii.gz`). The chisep phantoms ship it 4D, wrapped to (−π, π], whole-head with the
  background field: none of that needs handling here — the fit compares complex signals, so wraps
  do not enter it, and the background field is part of Δω. Phase sign convention: +γ·ΔB·TE
  (qsm-forward's).
- **Outputs:** `chi-para.nii.gz` (χ+ ≥ 0) and `chi-dia.nii.gz` (|χ−|), ppm.
- **Image:** placeholder. `algorithm.yml` points at the shared QSMxT image (v10.0.0), which does
  **not** have `separate decompose-complex` yet; the entry runs once a QSMxT release with it is
  built and pinned.

```bash
qsmxt separate decompose-complex --magnitude magnitude.nii.gz --phase phase.nii.gz \
  --echo-times <t1,t2,…> -m mask.nii.gz -o $WORK/dcx \
  --field-strength <B0> --b0-direction <B0_dir> [--chi-bound PPM] [--r2-bound HZ] [--max-lm-iter N]
```

| parameter | default | description |
|---|---|---|
| `chi_bound` | 0.5 | upper bound on the pool susceptibilities \|χc±\|, ppm |
| `r2_bound` | 100 | upper bound on R2*₀, Hz |
| `max_lm_iter` | 100 | Levenberg–Marquardt iterations per start |

Defaults are qsm-core's `DecomposeComplexParams::default()`.
