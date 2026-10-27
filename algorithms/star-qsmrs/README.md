# STAR-QSM

STAR-QSM (streaking artifact reduction) dipole inversion: the QSM.rs port of STI Suite's
`QSM_star`. The original is [`star-sti`](../star-sti).

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Wei et al., NMR Biomed 2015 (doi:10.1002/nbm.3383)

## How QSM-CI runs it

```bash
qsmxt invert star /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz \
  --b0-direction <B0 dir> --field-strength <B0> --echo-times <TEs>
```

`qsmxt invert star` is not in a QSMxT release yet (v10.0.0 lacks it), so the entry is skipped by
CI until `image:` is repinned to one that has it.

## Parameters

| parameter | default | description |
|---|---|---|
| `te` | sum | echo time the field is converted to phase at: first, last, spacing, sum, or ms |
