# Running QSM-CI methods from a workflow engine

Every QSM-CI algorithm is one `qsm-ci run <slug>` away, so any published method drops into a workflow
engine — the container is handled underneath by the CLI. This folder has a **complete end-to-end
pipeline** (phase → χ: field-mapping → background-field removal → dipole inversion, using
`romeo-fieldmap` → `vsharp` → `rts`) for each engine we support. Swap any method slug to mix and match.

| Engine | File | How it's provided |
|---|---|---|
| [nipype](https://nipype.readthedocs.io) | [`nipype_pipeline.py`](nipype_pipeline.py) | shipped interface — `from qsm_ci.nipype import …` |
| [Pydra](https://pydra.readthedocs.io) | [`pydra_pipeline.py`](pydra_pipeline.py) | shipped interface — `from qsm_ci.pydra import …` |
| [CWL](https://www.commonwl.org) | [`pipeline.cwl`](pipeline.cwl) | generated — `qsm-ci interface cwl --pipeline …` |
| [Snakemake](https://snakemake.github.io) | [`Snakefile`](Snakefile) | generated — `qsm-ci interface snakemake --pipeline …` |
| [Nextflow](https://www.nextflow.io) | [`pipeline.nf`](pipeline.nf) | generated — `qsm-ci interface nextflow --pipeline …` |

The two Python engines have ready-to-import interfaces; the three declarative engines are generated
from the stage contract, so they stay in sync. Regenerate the declarative files any time with:

```bash
qsm-ci interface cwl       --pipeline romeo-fieldmap,vsharp,rts -o pipeline.cwl
qsm-ci interface snakemake --pipeline romeo-fieldmap,vsharp,rts -o Snakefile
qsm-ci interface nextflow  --pipeline romeo-fieldmap,vsharp,rts -o pipeline.nf
```

## Running them

You need `qsm-ci` installed (`pip install qsm-ci`) and a container engine (Docker by default). Inputs
are the canonical artifacts a `field-mapping` stage consumes — `phase`, `magnitude`, `mask`, `params`
(generate a test set with `qsm-forward`, or use a packed dataset from `scripts/pack_dataset.py`).

```bash
# nipype
pip install "qsm-ci[nipype]"
python nipype_pipeline.py --phase phase.nii.gz --magnitude magnitude.nii.gz \
    --mask mask.nii.gz --params params.json --out chimap.nii.gz

# Pydra
pip install "qsm-ci[pydra]"
python pydra_pipeline.py  --phase phase.nii.gz --magnitude magnitude.nii.gz \
    --mask mask.nii.gz --params params.json --out chimap.nii.gz

# CWL
cwltool pipeline.cwl --phase phase.nii.gz --magnitude magnitude.nii.gz \
    --mask mask.nii.gz --params params.json

# Snakemake  (put phase/magnitude/mask/params in the working dir first)
snakemake -c1 chimap.nii.gz

# Nextflow
nextflow run pipeline.nf --phase phase.nii.gz --magnitude magnitude.nii.gz \
    --mask mask.nii.gz --params params.json --outdir results
```

## `QSMCI_ALGORITHMS`

CWL and Nextflow run each step in its own **isolated work directory**, so a bare slug like `vsharp`
can't find the `algorithms/` folder by relative path. Point `QSMCI_ALGORITHMS` at it so slugs resolve
anywhere:

```bash
export QSMCI_ALGORITHMS=/path/to/QSM-CI/algorithms
# CWL also needs to forward the variable into the tool:
cwltool --preserve-environment QSMCI_ALGORITHMS pipeline.cwl ...
```

(nipype, Pydra, and Snakemake run in a directory you control, so this is only needed for CWL/Nextflow
— but exporting it is always safe.)

## Verified in CI

`tests/test_pipeline.py` runs all five of these on the real challenge data and checks that they
produce the **identical** χ map and that it matches the ground truth (see `.github/workflows/pipeline.yml`).
