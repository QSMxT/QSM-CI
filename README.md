# QSM-CI

**An open challenge and leaderboard for Quantitative Susceptibility Mapping (QSM) reconstruction.**

Submit a QSM algorithm — in any language, as a container — and QSM-CI runs it on standardized data,
scores it against held-out ground truth, and publishes the result to an interactive leaderboard.
Every published algorithm gets a citable Zenodo DOI and can be run by anyone with one command.

## → https://qsmxt.github.io/QSM-CI

- **[Leaderboard](https://qsmxt.github.io/QSM-CI/leaderboard.html)** — per-stage tables and the
  background-removal × dipole-inversion combination matrix, with an interactive volume viewer.
- **[Run an algorithm](https://qsmxt.github.io/QSM-CI/running.html)** — locally or from a workflow
  engine (nipype, Pydra, CWL, Snakemake, Nextflow).
- **[Submit yours](https://qsmxt.github.io/QSM-CI/submit.html)** — open a pull request adding a folder
  under `algorithms/`.

## Run an algorithm

```bash
pip install qsm-ci
qsm-ci list                                   # the published algorithms you can run
qsm-ci run sharp --totalfield tf.nii.gz --mask mask.nii.gz
```

Algorithms are fetched from Zenodo and run in their pinned container, so results are reproducible.
See the [running guide](https://qsmxt.github.io/QSM-CI/running.html) for details.

## Submit an algorithm

A submission is a folder under `algorithms/<slug>/` — your `run.sh`, a `stage:` declaration, and a
container environment — reading and writing canonical artifacts (all fields and χ in **ppm**). Your
code is mounted, not baked. QSM is scored stage-aware (field-mapping → background removal → dipole
inversion, plus combined spans), both isolated and composed with other stages.

Start from the **[Submit guide](https://qsmxt.github.io/QSM-CI/submit.html)**; the full rules are in
**[CONTRACT.md](CONTRACT.md)** and the machine-readable **[stages.yml](stages.yml)**. MATLAB is
welcome via the license-free MATLAB Runtime.

## Repository layout

| Path | What it is |
|------|------------|
| `algorithms/<slug>/` | One submission each |
| `qsm_ci/` | The `qsm-ci` CLI (published to PyPI) |
| `eval/` | `qsm-eval` — the Python scorer (metrics ported from QSM.rs) |
| `scripts/pipeline.py` | Isolated + composed evaluation runner |
| `web/`, `results/index.json` | The leaderboard site and the scores that feed it |
| `CONTRACT.md`, `stages.yml` | The submission contract and stage registry |
