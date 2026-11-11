# Building toolbox-pipeline-decompose-qsmci (compiled MATLAB → MATLAB Runtime)

DECOMPOSE-QSM as its paper describes it (Chen et al. 2021, §2.2 and §3.6), from the echoes to χ+ and
χ−: the reference side of pipeline parity for QSMxT's `decompose` pipeline (QSMxT/QSM-CI#421). The
paper ships no code, so `recon.m` is QSM-CI's MATLAB of it: STI Suite 3.0 for unwrapping, V-SHARP
and STAR-QSM per echo, FSL BET on the first echo's magnitude (MEDI's bet2 mex, which is FSL's bet2
code; x reversed around it for a neurological header, as FSL's `bet` does), then the paper's fit with MATLAB's `lsqlin` (interior-point) and `lsqnonlin`
(trust-region-reflective). The model functions in `decompose_utils/` are a copy of
`decompose-qsm`'s (Tim Ho's). It also serves as the `lsqlin` cross-check of QSM.rs's exact stage
5.1/5.2 solves (astewartau/QSM.rs#449): its fitted parameters are written as intermediates.

Needs the **Optimization Toolbox** (lsqlin, lsqnonlin) at compile time.

`kiwi/` and `sparsa/` are STI Suite's `Support_Functions/qsm_kiwi_1` and SpaRSA's solver code
(no demos): `QSM_star` calls them and `Core_Functions_P` lacks them (as `star-sti`).

## Compile
```bash
matlab -batch "addpath('../../fidelity/matlab'); mex_bet2('medi/bet2')"; rm medi/bet2/runmex.m   # runmex with C++98 (FSL code)
matlab -batch "addpath('sti','kiwi','sparsa','medi/bet2','decompose_utils','nifti'); \
  mcc('-m','recon.m','-a','sti','-a','kiwi','-a','sparsa','-a','medi/bet2/bet2.mexa64','-o','recon','-d','.')"
```
On Bunya: `fidelity/matlab/submit.sh toolbox-pipeline-decompose-qsmci build`. The image contains
FSL's bet2 code: it carries bet2's sources and licence (README.md, *Licence*).

## 3. Bake the image and push
The image carries the bet2 sources and FSL's licence text (README.md, *Licence*): copy them next
to `recon` first, without the binaries.
```bash
mkdir -p fsl-bet2 && cp -r medi/bet2/. fsl-bet2/ && rm -f fsl-bet2/*.mex* fsl-bet2/runmex.m
podman build -t ghcr.io/astewartau/qsm-ci/decompose-pipeline:v1 .
podman push  ghcr.io/astewartau/qsm-ci/decompose-pipeline:v1
```
Pin `image:` in `algorithm.yml` by the pushed digest and run the fidelity check
([`fidelity/REPORT.md`](fidelity/REPORT.md)).
