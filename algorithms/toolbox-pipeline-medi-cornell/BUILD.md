# Building toolbox-pipeline-medi-cornell (compiled MATLAB → MATLAB Runtime)

The MEDI toolbox 2024.11.26's own pipeline (`README.m`), from the echoes to χ: the reference side of
pipeline parity for QSMxT's `medi-toolbox` pipeline (QSMxT/QSM-CI#421). The recipe follows
[`../medi-cornell/BUILD.md`](../medi-cornell/BUILD.md) (licensed R2023b + MATLAB Compiler, R2023b
Runtime), with the whole chain in `recon.m` and two mex files.

Stage: `pipeline`. It consumes `phase`, `magnitude` and `params` and produces `chimap` (ppm). The
chain: `Fit_ppm_complex` → `unwrapPhase` → `BET` → `PDF` → `arlo`/`extract_CSF` →
`MEDI_L1('lambda',1000,'lambda_CSF',100,'merit','smv',5)`. CF is `params.json`'s `ImagingFrequency`
when present, as README.m reads it from the DICOM header.

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122                        algorithms/toolbox-pipeline-medi-cornell/nifti
cp -r /path/to/MEDI_toolbox-2024.11.26/functions     algorithms/toolbox-pipeline-medi-cornell/medi
printf 'function store_CG_results(varargin)\nend\n' > algorithms/toolbox-pipeline-medi-cornell/medi/store_CG_results.m
rm -f algorithms/toolbox-pipeline-medi-cornell/medi/{mexUnwrap.mexa64,bet2/bet2.mexa64}
```

## 2. Compile the mex files and recon
`unwrapPhase` calls `mexUnwrap` and `BET` calls `bet2`. Both are rebuilt from the shipped sources
(`mexUnwrap.c`, and `bet2/runmex.m` over FSL's bet2 sources), as `fit-ppm-complex-cornell` does for
`mexUnwrap`, so the binaries match the MATLAB that compiles `recon`:
```bash
cd algorithms/toolbox-pipeline-medi-cornell
matlab -batch "cd medi; mex mexUnwrap.c; cd bet2; runmex"
matlab -batch "addpath('nifti'); addpath(genpath('medi')); mcc('-m','recon.m','-a','medi/mexUnwrap.mexa64','-a','medi/bet2/bet2.mexa64','-o','recon','-d','.')"
```
On Bunya the harness does this as a Slurm job (`fidelity/matlab/submit.sh toolbox-pipeline-medi-cornell build`).

## 3. Bake the image (local only)
MEDI's `bet2` mex is FSL's bet2 code, whose licence does not clearly allow publishing it
(`../_bet2/README.md`), so the image is built where it runs and never pushed:
```bash
podman build -t localhost/qsm-ci/medi-pipeline:v1 .   # or apptainer build from it on Bunya
```
Run the fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)) and the parity pair on that
host.
