# χ-separation benchmarking in QSM-CI — progress summary

## Background

Quantitative Susceptibility Mapping (QSM) recovers net magnetic susceptibility (χ), but net χ
conflates **paramagnetic** sources (iron → χ+) and **diamagnetic** sources (myelin, calcium → χ−),
which partially cancel. **χ-separation** ("susceptibility source separation") adds a relaxation input
(R2′) to disentangle the two, producing separate χ+ and χ− maps — more biologically specific markers of
iron and myelin. QSM-CI previously benchmarked only net-χ QSM pipelines; this work extends the platform
to χ-separation as a first-class, publicly leaderboard-ranked task.

## What was built

A complete χ-separation benchmarking path in QSM-CI:

- **New "chi-separation" stage** in the platform's stage/artifact registry: consumes the local field,
  R2′, χ_total, multi-echo magnitude and brain mask; **produces two source maps** (χ+ and χ−).
- **Runner / CLI / scorer generalised from single-output to multi-output**, since χ-separation emits two
  maps that are each scored (the existing QSM pipeline produced one map per stage).
- **Ground-truth phantom** generated with `qsm-forward` (our forward-simulation tool), carrying separate
  χ+ / χ− ground truth and a matched R2′ map.
- **Scoring**: each source map is scored (xSIM, NRMSE, correlation) against ground truth and folded into
  a single leaderboard row with χ+ / χ− columns and an average.
- **Web leaderboard**: a QSM ⇄ χ-separation toggle, a sortable per-source metrics table, and a local
  NiiVue viewer for ground-truth vs reconstruction.

## First method, and a key benchmark-design finding

The first method integrated is **χ-separation iLSQR** (SNU-LIST toolbox; Shin et al., NeuroImage 2021).
Producing a meaningful score surfaced an important design point about the R2′ model:

- R2′ relates to susceptibility through a **relaxivity constant, Dr**. Real tissue has *different*
  relaxivities for paramagnetic vs diamagnetic sources (iron dephases more per ppm than myelin), so a
  physically-realistic phantom uses **split relaxivities** (Dr₊ ≈ 114, Dr₋ ≈ 30 Hz/ppm).
- However, **every currently-available χ-separation method** (iLSQR, MEDI-χsep, χ-sepnet) assumes a
  **single effective Dr**. Feeding them a noise-free, perfectly split-Dr R2′ is an internally
  inconsistent constraint that breaks *all* of them catastrophically — iLSQR scored xSIM ≈ 0.03 — and
  far more severely than on real (noisy) data, where R2′ noise and the R2 baseline buffer the mismatch.
- **Decision**: the scored phantom uses a **single effective Dr (137 Hz/ppm**, the value the methods
  assume), so the leaderboard measures *reconstruction quality* rather than a relaxivity-assumption gap.
  This matches how these methods are validated in the literature. The physically-realistic split-Dr
  variant is a candidate *future* robustness evaluation, to be revisited once (a) methods that model
  split relaxivity exist and (b) realistic R2′ noise is added — otherwise it penalises every method
  equally and uninformatively.

The practical upshot: on a consistently-scored single-Dr phantom, a single-Dr method should be only
"a little off" (ordinary reconstruction error), not "way off".

## Status

- Integration complete and unit-tested (96/96 tests pass); running locally.
- iLSQR being finalised on the corrected single-Dr phantom (on the realistic split-Dr phantom it scored
  ~0.03, as expected from the finding above).
- A second method (**χ-separation MEDI**, same toolbox) is scaffolded, and a deep-learning method
  (**χ-sepnet**, which ships ONNX weights) is identified as the next baseline — the point being to check
  whether the scoring meaningfully differentiates method families (iterative vs deep learning).

## Next steps

- Confirm iLSQR recovery on the corrected phantom; add the MEDI and χ-sepnet baselines for a first
  multi-method χ-separation leaderboard.
- Consider a fuller "realism" track (split relaxivities + noise) once split-Dr-aware methods are added.
- Wire the χ-separation container build into CI (currently local-only; the toolbox needs a MATLAB
  licence, like our other MATLAB submissions).
