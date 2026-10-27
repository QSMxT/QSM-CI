# Port parity

Some algorithms have two implementations here: the authors' original and the QSM.rs port (same
`algorithm:` in `algorithm.yml`, e.g. `qsmart-matlab` and `qsmart-qsmrs`). The `parity` workflow
runs both on the same dataset and checks that they still agree as well as they did when the limits
were set.

## Running it

Actions → **parity** → *Run workflow*, or:

```bash
gh workflow run parity.yml -f algorithm=qsmart -f dataset=sim
gh workflow run parity.yml -f algorithm=enabled -f dataset=configured   # every enabled pair and dataset
```

Each job runs the reference and then the candidate through `qsm-ci run` with the images pinned in
`algorithm.yml`, compares them inside the dataset mask, and writes a report to the job summary and
the `parity-<algorithm>-<dataset>` artifact (with both outputs). The job fails when a limit is
exceeded. Locally, with Docker and the dataset fetched:

```bash
python scripts/parity.py pairs                       # pairs algorithm.yml defines, and their state
python scripts/parity.py run     --algorithm qsmart --dataset data/sim/scoring --work .parity
python scripts/parity.py compare --algorithm qsmart --dataset data/sim/scoring --work .parity
```

## What is compared

- **The final artifact** (χ): NRMSE (‖candidate − reference‖ / ‖reference‖, %), correlation, and the
  maximum and 99th-percentile |Δ| (ppm), inside the mask.
- **Intermediates**, for every name both sides write (CONTRACT.md, "Intermediates"). Binary maps
  are compared by Dice. An intermediate with no limits is reported but does not fail the job; one
  that only one side writes is listed.

## Limits

`parity/thresholds.yml` holds the pairs, which side is the reference, and the limits per dataset.
They are the agreement measured when the pair was set up, plus a margin. To set or reset them,
dispatch with `baseline=true`: the report then prints limits derived from what it measured, ready to
paste. Re-baseline whenever an image digest of either side changes on purpose, or when `feed:` or a
`*_prefix:` changes what is measured.

A dataset entry can make the comparison closer to like-for-like:

- `feed: {totalfield: totalfield}` gives the candidate the reference's own `totalfield` intermediate
  in place of the dataset's, so both start from the same field.
- `candidate_prefix: [laplacian-qsmrs]` runs a field-mapping step first, for datasets with no
  ground-truth total field (the in-vivo acquisitions).
