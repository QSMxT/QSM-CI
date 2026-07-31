# In-vivo track data — 2016 QSM Reconstruction Challenge (dipole inversion)

The **in-vivo** track scores dipole inversion on real acquired brain data from the
[2016 QSM Reconstruction Challenge](https://qsm.neuroimaging.at). Because there is no true χ in vivo,
scoring uses two **reference** reconstructions and the subset of metrics that are meaningful without a
known χ map (NRMSE, detrended NRMSE, HFEN, correlation, XSIM). Phantom-only region metrics
(tissue/blood/DGM NRMSE, DGM linearity, calcification) are **not** reported — the shipped `dseg`
follows a different label scheme (0–11) than the sim phantom, so those metrics would be meaningless.

## References

Each method is scored against **both** references by running the same dipole recon through the scorer
twice (no second recon):

- **COSMOS** (primary) — the multi-orientation reconstruction, the challenge pseudo-ground-truth.
  Its metrics carry the unsuffixed keys (`nrmse`, `xsim`, …).
- **STI χ33** (secondary) — the single-orientation susceptibility-tensor χ33 map. Its metrics are
  merged into the same run under a `_sti` suffix (`nrmse_sti`, `xsim_sti`, …).

## Scope — dipole stage only

The dataset ships only the local tissue field (the isolated-dipole input) and the two χ references, so
**only the `dipole` stage is scorable** (ppm local field → ppm χ). There is no field-mapping or BFR
ground truth, so the in-vivo track runs isolated-only (no composed matrix) and every non-dipole /
phantom-only metric is absent. Dipole is ppm-in / ppm-out, so no TE/B0 conversion is involved
anywhere; the `B0`/`TE` in `params.json` are display-only and do not affect scores.

## Dataset layout

The scoring dataset is the flattened `inputs/ + groundtruth/` layout (like sim/chisep), but it ships
**pre-flattened** as a single zip rather than a qsm-forward BIDS tree. `fetch_dataset.sh invivo` just
downloads and unzips it straight into the dataset dir (no BIDS-find, no `pack_dataset.py` step).

```
inputs/
  mask.nii.gz          brain mask (BET, eroded)
  magnitude.nii.gz     single-echo magnitude (viewer underlay)
  params.json          TE/B0/B0_dir=[0,0,1]/voxel_size (display-only for dipole)
groundtruth/
  localfield.nii.gz    LOCAL tissue field, ppm — the isolated-dipole input
  chimap.nii.gz        COSMOS reference χ, ppm (primary)
  chimap-sti.nii.gz    STI χ33 reference χ, ppm (secondary)
  dseg.nii.gz          challenge evaluation label map (0–11; NOT used — different scheme from sim)
```

## Provenance

The zip is built by [`scripts/make_invivo_zip.py`](../../scripts/make_invivo_zip.py) from the challenge
release niftis (`phs_tissue` → `localfield`, `chi_cosmos` → `chimap`, `chi_33` → `chimap-sti`,
`msk`/`magn`/`evaluation_mask`), with a unit sanity check that everything is ppm-scale. It is uploaded
to OSF and fetched in CI via the `OSF_FILE_INVIVO` secret (cache key `.osfcache/invivo.zip`).

Langkammer C, Schweser F, Shmueli K, et al. *Quantitative susceptibility mapping: Report from the 2016
reconstruction challenge.* Magnetic Resonance in Medicine. 2018;79(3):1661–1673.
[doi:10.1002/mrm.26830](https://doi.org/10.1002/mrm.26830)
