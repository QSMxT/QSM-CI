# Building toolbox-pipeline-decompose-qsmci (compiled MATLAB → MATLAB Runtime)

DECOMPOSE-QSM as its paper describes it (Chen et al. 2021, §2.2 and §3.6), from the echoes to χ+ and
χ−: the reference side of pipeline parity for QSMxT's `decompose` pipeline (QSMxT/QSM-CI#421). The
paper ships no code, so `recon.m` is QSM-CI's MATLAB of it: STI Suite 3.0 for unwrapping, V-SHARP
and STAR-QSM per echo, FSL BET on the first echo's magnitude (MEDI's bet2 mex, which is FSL's bet2
code), then the paper's fit with MATLAB's `lsqlin` (interior-point) and `lsqnonlin`
(trust-region-reflective). The model functions in `decompose_utils/` are a copy of
`decompose-qsm`'s (Tim Ho's). It also serves as the `lsqlin` cross-check of QSM.rs's exact stage
5.1/5.2 solves (astewartau/QSM.rs#449): its fitted parameters are written as intermediates.

Needs the **Optimization Toolbox** (lsqlin, lsqnonlin) at compile time.

## Compile
```bash
matlab -batch "cd medi/bet2; runmex"; rm medi/bet2/runmex.m
matlab -batch "addpath('sti','medi/bet2','decompose_utils','nifti'); \
  mcc('-m','recon.m','-a','sti','-a','medi/bet2/bet2.mexa64','-o','recon','-d','.')"
```
On Bunya: `fidelity/matlab/submit.sh toolbox-pipeline-decompose-qsmci build`. The image contains
FSL's bet2 code, so it is built locally and not published (`../_bet2/README.md`).
