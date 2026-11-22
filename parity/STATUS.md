# Port parity status

Generated 2026-11-22 by `scripts/parity.py status` from `parity/results.json` and `parity/thresholds.yml`; do not edit by hand. How checks run, the two tracks, and what makes a check stale: [docs/parity.md](../docs/parity.md).

## Released: QSMxT v12.2.0

Tested: QSMxT **v12.2.0** (the binary the release ships) with QSM.rs `dff62e2`.

The latest QSMxT release against each verified original. A release does not change, so it is rerun only for a new release, or when a pair's reference image or settings change. A failure here is that release's result; **not in** means the release has no such command or option yet.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.7947% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.3834% | ✅ current |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.02599% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.002378% | ✅ current |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0002207% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0009001% | ✅ current |
| `iharperella` | `iharperella-sti` → `iharperella-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 3.898e-05% | ✅ current |
| `star` | `star-sti` → `star-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.002085% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.002332% | ✅ current |
| `medi` | `medi-cornell` → `medi-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.003049% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.003712% | ✅ current |
| `toolbox-pipeline-medi-cornell` | `toolbox-pipeline-medi-cornell` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.02439% | ✅ current |
| `toolbox-pipeline-chisep-ilsqr` | `toolbox-pipeline-chisep` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.003285% | ✅ current |
| `toolbox-pipeline-chisep-medi` | `toolbox-pipeline-chisep` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.003285% | ✅ current |
| `toolbox-pipeline-decompose` | `toolbox-pipeline-decompose-qsmci` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 8.144% | ✅ current |
| `toolbox-pipeline-qsmart` | `toolbox-pipeline-qsmart` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 8.579% | ✅ current |
| `toolbox-pipeline-sti` | `toolbox-pipeline-sti` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.298% | ✅ current |
| `toolbox-pipeline-ukb` | `toolbox-pipeline-ukb` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.002657% | ✅ current |
| `fit-ppm-complex` | `fit-ppm-complex-cornell` → `fit-ppm-complex-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0% | ✅ current |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.4767% | ✅ current |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 4.89% | ✅ current |
| `chisep-ilsqr` | `chisep-ilsqr` → `chisep-ilsqr-qsmrs` | chisep-mc | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 7.442e-08% | ✅ current |
| `chisep-medi` | `chisep-medi` → `chisep-medi-qsmrs` | chisep-mc | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.6334% | ✅ current |
| `wavesep` | `wavesep` → `wavesep-qsmrs` | chisep-mc | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 2.138e-07% | ✅ current |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0% | ✅ current |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0% | ✅ current |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0% | ✅ current |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 2.024e-16% | ✅ current |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 1.798e-15% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 1.944e-10% | ✅ current |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 7.812e-10% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 3.932e-10% | ✅ current |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 2.064e-09% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 6.026e-09% | ✅ current |
| `sharp` | `sharp-sepia` → `sharp-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 1.394e-08% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 1.058e-08% | ✅ current |
| `sharp-qsmjl` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 6.322e-12% | ✅ current |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 1.133e-11% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 5.205e-12% | ✅ current |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 4.62e-06% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 4.767e-14% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 1.498% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 1.645% | ✅ current |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0006844% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0003367% | ✅ current |
| `xqsm` | `xqsm` → `xqsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.001784% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0008659% | ✅ current |
| `qsmnet` | `qsmnet` → `qsmnet-qsmrs` | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0001349% | ✅ current |
| `qsmnet-plus` | `qsmnet-plus` → `qsmnet-plus-qsmrs` | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0002079% | ✅ current |
| `lpcnn` | `lpcnn` → `lpcnn-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.009191% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 3.711e-05% | ✅ current |
| `qsmgan` | `qsmgan` → `qsmgan-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0001076% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.005643% | ✅ current |
| `modl-qsm` | `modl-qsm` → `modl-qsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | unknown | ❌ error | — | ⚠️ stale: the run against v12.2.0 ended without a result |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.01412% | ✅ current |
| `ir2qsm` | `ir2qsm` → `ir2qsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.001523% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0005049% | ✅ current |
| `autoqsm` | `autoqsm` → `autoqsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0001121% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0001443% | ✅ current |
| `nextqsm` | `nextqsm` → `nextqsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.1025% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.01823% | ✅ current |
| `bfrnet` | `bfrnet` → `bfrnet-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0001557% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0002169% | ✅ current |
| `chisepnet` | `chisepnet` → `chisepnet-qsmrs` | chisep-mc | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 4.001e-05% | ✅ current |
| `qsmnetme` | `qsmnetme` → `qsmnetme-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 9.916e-05% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 6.011e-05% | ✅ current |
| `susep-net` | `susep-net` → `susep-net-qsmrs` | chisep-mc | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 3.103e-05% | ✅ current |
| `hd-bet` | `hd-bet-qsmci` → `hd-bet-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | — | ✅ current |
| `mindgrab` | `mindgrab` → `mindgrab-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | — | ✅ current |
| `r2primenet` | `r2primenet` → `r2primenet-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 2.033e-05% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 2.047e-05% | ✅ current |
| `iqsm` | `iqsm` → `iqsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0002228% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0002708% | ✅ current |
| `iqsm-plus` | `iqsm-plus` → `iqsm-plus-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0001157% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0001549% | ✅ current |
| `iqfm` | `iqfm` → `iqfm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0001829% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.000216% | ✅ current |
| `lsqr` | `lsqr` → `lsqr-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0004323% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0003931% | ✅ current |
| `heidi` | `heidi` → `heidi-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0006515% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.1622% | ✅ current |
| `ndi` | `ndi` → `ndi-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 9.525e-05% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.001103% | ✅ current |
| `fansi-nltv` | `fansi-nltv` → `fansi-nltv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.003387% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.006892% | ✅ current |
| `fansi-nltgv` | `fansi-nltgv` → `fansi-nltgv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.003419% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.006343% | ✅ current |
| `l1qsm` | `l1qsm` → `l1qsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.002988% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.002205% | ✅ current |
| `whqsm` | `whqsm` → `whqsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.00337% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.001819% | ✅ current |
| `hdqsm` | `hdqsm` → `hdqsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0008346% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.001482% | ✅ current |
| `resharp` | `resharp` → `resharp-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 3.861e-09% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 1.49e-08% | ✅ current |
| `pdf` | `pdf-cornell` → `pdf-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 2.107e-05% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.01461% | ✅ current |
| `lbv` | `lbv-cornell` → `lbv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.001839% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 0.0007665% | ✅ current |
| `tfi` | `tfi-cornell` → `tfi-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 2.485% | ✅ current |
|  |  | sim | [2026-11-22](https://github.com/QSMxT/QSM-CI/actions/runs/44986395967) | `dff62e2` | ✅ pass | 3.606% | ✅ current |

Run the flagged pairs against v12.2.0:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=laplacian,modl-qsm -f dataset=configured -f qsmxt_release=v12.2.0
```

## Development: QSMxT main × QSM.rs main

Tested: QSMxT main `7473f09` with qsm-core at QSM.rs main `dff62e2` (1 older build(s) for pairs not rerun since).

A check is **stale** when the reference image changed, QSM.rs `main` changed the port's source files or `Cargo.lock`, QSMxT `main` changed the step's wiring or `Cargo.lock`, the pair's limits changed, or it failed. There is no age limit. A **gap** is a pair whose port does not match its original yet: it is not enabled, and has no limits that would pass it.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.7794% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.3834% | ✅ current |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.02599% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.002378% | ✅ current |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0002207% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0009001% | ✅ current |
| `iharperella` | `iharperella-sti` → `iharperella-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 3.898e-05% | ✅ current |
| `star` | `star-sti` → `star-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.002085% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.002332% | ✅ current |
| `medi` | `medi-cornell` → `medi-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.02066% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.02896% | ✅ current |
| `toolbox-pipeline-medi-cornell` | `toolbox-pipeline-medi-cornell` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
| `toolbox-pipeline-chisep-ilsqr` | `toolbox-pipeline-chisep` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
| `toolbox-pipeline-chisep-medi` | `toolbox-pipeline-chisep` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
| `toolbox-pipeline-decompose` | `toolbox-pipeline-decompose-qsmci` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
| `toolbox-pipeline-qsmart` | `toolbox-pipeline-qsmart` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-20](https://github.com/QSMxT/QSM-CI/actions/runs/44816285676) | `dff62e2` | ✅ pass | 8.579% | ✅ current |
| `toolbox-pipeline-sti` | `toolbox-pipeline-sti` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-20](https://github.com/QSMxT/QSM-CI/actions/runs/44816285676) | `dff62e2` | ✅ pass | 0.298% | ✅ current |
| `toolbox-pipeline-ukb` | `toolbox-pipeline-ukb` → `toolbox-pipeline-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-20](https://github.com/QSMxT/QSM-CI/actions/runs/44816285676) | `dff62e2` | ✅ pass | 0.002657% | ✅ current |
| `fit-ppm-complex` | `fit-ppm-complex-cornell` → `fit-ppm-complex-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0% | ✅ current |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.4767% | ✅ current |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 4.89% | ✅ current |
| `chisep-ilsqr` | `chisep-ilsqr` → `chisep-ilsqr-qsmrs` | chisep-mc | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 7.442e-08% | ✅ current |
| `chisep-medi` | `chisep-medi` → `chisep-medi-qsmrs` | chisep-mc | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.5787% | ✅ current |
| `wavesep` | `wavesep` → `wavesep-qsmrs` | chisep-mc | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 2.138e-07% | ✅ current |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0% | ✅ current |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0% | ✅ current |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0% | ✅ current |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 2.024e-16% | ✅ current |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 1.798e-15% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 1.944e-10% | ✅ current |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 7.812e-10% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 3.932e-10% | ✅ current |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 2.064e-09% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 6.026e-09% | ✅ current |
| `sharp` | `sharp-sepia` → `sharp-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 1.394e-08% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 1.058e-08% | ✅ current |
| `sharp-qsmjl` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 6.322e-12% | ✅ current |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 1.133e-11% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 5.205e-12% | ✅ current |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-20](https://github.com/QSMxT/QSM-CI/actions/runs/44816285676) | `dff62e2` | ✅ pass | 4.62e-06% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
|  |  | sim | [2026-11-20](https://github.com/QSMxT/QSM-CI/actions/runs/44816285676) | `dff62e2` | ✅ pass | 4.767e-14% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 1.498% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 1.645% | ✅ current |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0006844% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0003367% | ✅ current |
| `xqsm` | `xqsm` → `xqsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.001784% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0008659% | ✅ current |
| `qsmnet` | `qsmnet` → `qsmnet-qsmrs` | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0001346% | ✅ current |
| `qsmnet-plus` | `qsmnet-plus` → `qsmnet-plus-qsmrs` | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0002079% | ✅ current |
| `lpcnn` | `lpcnn` → `lpcnn-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.009192% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 3.537e-05% | ✅ current |
| `qsmgan` | `qsmgan` → `qsmgan-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0001132% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.004818% | ✅ current |
| `modl-qsm` | `modl-qsm` → `modl-qsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ❌ error | — | ⚠️ stale: the last check ended without a result |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.01412% | ✅ current |
| `ir2qsm` | `ir2qsm` → `ir2qsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.001523% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0005049% | ✅ current |
| `autoqsm` | `autoqsm` → `autoqsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0001101% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0001443% | ✅ current |
| `nextqsm` | `nextqsm` → `nextqsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.1019% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.01711% | ✅ current |
| `bfrnet` | `bfrnet` → `bfrnet-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0001557% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0002169% | ✅ current |
| `chisepnet` | `chisepnet` → `chisepnet-qsmrs` | chisep-mc | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 4.001e-05% | ✅ current |
| `qsmnetme` | `qsmnetme` → `qsmnetme-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 9.916e-05% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 6.011e-05% | ✅ current |
| `susep-net` | `susep-net` → `susep-net-qsmrs` | chisep-mc | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 2.434e-05% | ✅ current |
| `hd-bet` | `hd-bet-qsmci` → `hd-bet-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | — | ✅ current |
| `mindgrab` | `mindgrab` → `mindgrab-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | — | ✅ current |
| `r2primenet` | `r2primenet` → `r2primenet-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 2.033e-05% | ⚠️ stale: QSM.rs main changed `src/models/memory_calibration.rs`, `src/models/mod.rs`, `src/models/registry.rs`, `src/utils/r2star.rs` since the checked 8a655f4 (50 commits); QSMxT main changed `Cargo.lock` since the checked dc94cf4 (99 commits) |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 2.047e-05% | ⚠️ stale: QSM.rs main changed `src/models/memory_calibration.rs`, `src/models/mod.rs`, `src/models/registry.rs`, `src/utils/r2star.rs` since the checked 8a655f4 (50 commits); QSMxT main changed `Cargo.lock` since the checked dc94cf4 (99 commits) |
| `iqsm` | `iqsm` → `iqsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0002228% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0002708% | ✅ current |
| `iqsm-plus` | `iqsm-plus` → `iqsm-plus-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0001157% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0001695% | ✅ current |
| `iqfm` | `iqfm` → `iqfm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0001829% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.000216% | ✅ current |
| `lsqr` | `lsqr` → `lsqr-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0004323% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0003931% | ✅ current |
| `heidi` | `heidi` → `heidi-qsmrs` | s005001-site5-prisma-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0006515% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.1622% | ✅ current |
| `ndi` | `ndi` → `ndi-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 9.525e-05% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.001103% | ✅ current |
| `fansi-nltv` | `fansi-nltv` → `fansi-nltv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.003387% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.006892% | ✅ current |
| `fansi-nltgv` | `fansi-nltgv` → `fansi-nltgv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.003419% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.006343% | ✅ current |
| `l1qsm` | `l1qsm` → `l1qsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.002988% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.002205% | ✅ current |
| `whqsm` | `whqsm` → `whqsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.00337% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.001819% | ✅ current |
| `hdqsm` | `hdqsm` → `hdqsm-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0008346% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.001482% | ✅ current |
| `resharp` | `resharp` → `resharp-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 3.861e-09% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 1.49e-08% | ✅ current |
| `pdf` | `pdf-cornell` → `pdf-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 2.107e-05% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.01461% | ✅ current |
| `lbv` | `lbv-cornell` → `lbv-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.001839% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 0.0007665% | ✅ current |
| `tfi` | `tfi-cornell` → `tfi-qsmrs` | s002001-site1-achieva-bridge-run1 | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 1.256% | ✅ current |
|  |  | sim | [2026-11-21](https://github.com/QSMxT/QSM-CI/actions/runs/44816299994) | `dff62e2` | ✅ pass | 3.56% | ✅ current |

Refresh every stale pair against QSM.rs `main`:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=toolbox-pipeline-medi-cornell,toolbox-pipeline-chisep-ilsqr,toolbox-pipeline-chisep-medi,toolbox-pipeline-decompose,laplacian,modl-qsm,r2primenet -f dataset=configured -f qsmrs_ref=main
```

## No original

No original code to check against (QSMxT/QSM-CI#302; tested against ground truth in QSM.rs instead):

| Method | Covers | Note |
|---|---|---|
| `cosmos` | COSMOS (`cosmos`, `cosmos_weighted`) |  |
| `harperella` | HARPERELLA (`harperella`) | not in STI Suite 3.0 (paper-based); iHARPERELLA is paired with STI Suite's |
| `slicewise-unwrap` | slice-wise (2D) unwrapping (`unwrap_slicewise`, `unwrap_slicewise_multi_echo`) | QSM.rs's own wrapper (any unwrapper per slice, plus an inter-echo 2π pass) |
| `robust-fit` | robust echo combination (`multi_echo_robust_fit`) | QSM.rs's own IRLS fit (Tukey/Huber loss, one robust scale over the mask) |
| `motion-correction` | motion correction (`motion`) | QSM.rs's own rigid registration (NCC, Powell, pyramid) and complex-domain resampling |
| `morphology` | erosion / dilation, closing (`erode_mask`, `dilate_mask`, `morphological_close`) | set definitions, no authored algorithm; identical to scipy.ndimage |

## Release history

| Pair | v12.2.0 | v12.1.0 | v12.0.0 | v11.0.0 | v10.0.0 |
|---|---|---|---|---|---|
| `amp-pe` | 0.48 % · v12.2.0 | 0.48 % · v12.1.0 | 0.48 % · v12.0.0 | 0.48 % · v11.0.0 | 0.48 % · v10.0.0 |
| `autoqsm` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `bfrnet` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | < 0.001 % · v10.0.0 |
| `chisep-ilsqr` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `chisep-medi` | 0.63 % · v12.2.0 | 0.58 % · v12.1.0 | 0.58 % · v12.0.0 | 0.58 % · v11.0.0 | not in v10.0.0 |
| `chisepnet` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `decompose` | 4.9 % · v12.2.0 | 4.9 % · v12.1.0 | 4.9 % · v12.0.0 | 4.9 % · v11.0.0 | failing · v10.0.0 · no unwrap_phase |
| `fansi-nltgv` | 0.0063 % · v12.2.0 | 0.0063 % · v12.1.0 | 0.0063 % · v12.0.0 | 0.0063 % · v11.0.0 | failing · v10.0.0 |
| `fansi-nltv` | 0.0069 % · v12.2.0 | 0.0069 % · v12.1.0 | 0.0069 % · v12.0.0 | 0.0069 % · v11.0.0 | failing · v10.0.0 |
| `fit-ppm-complex` | identical · v12.2.0 | identical · v12.1.0 | identical · v12.0.0 | identical · v11.0.0 | not in v10.0.0 |
| `hd-bet` | pass · v12.2.0 | pass · v12.1.0 | pass · v12.0.0 | pass · v11.0.0 | pass · v10.0.0 |
| `hdqsm` | 0.0015 % · v12.2.0 | 0.0015 % · v12.1.0 | 0.0015 % · v12.0.0 | 0.0015 % · v11.0.0 | failing · v10.0.0 |
| `heidi` | 0.16 % · v12.2.0 | 0.11 % · v12.1.0 | 0.16 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 · no denoise_reference_itk |
| `iharperella` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | not in v11.0.0 | failing · v10.0.0 |
| `ilsqr` | 0.026 % · v12.2.0 | 0.026 % · v12.1.0 | 0.026 % · v12.0.0 | 0.017 % · v11.0.0 | failing · v10.0.0 |
| `iqfm` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `iqsm` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `iqsm-plus` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `ir2qsm` | 0.0015 % · v12.2.0 | 0.0012 % · v12.1.0 | 0.0012 % · v12.0.0 | 0.0011 % · v11.0.0 | 0.0014 % · v10.0.0 |
| `ismv` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 · no variant |
| `l1qsm` | 0.003 % · v12.2.0 | 0.003 % · v12.1.0 | 0.003 % · v12.0.0 | 0.0026 % · v11.0.0 | failing · v10.0.0 |
| `laplacian` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | < 0.001 % · v10.0.0 |
| `lbv` | 0.0018 % · v12.2.0 | 0.0018 % · v12.1.0 | 0.0018 % · v12.0.0 | 0.0018 % · v11.0.0 | failing · v10.0.0 |
| `lpcnn` | 0.0092 % · v12.2.0 | 0.0092 % · v12.1.0 | 0.0092 % · v12.0.0 | 0.0077 % · v11.0.0 | 0.0078 % · v10.0.0 |
| `lsqr` | < 0.001 % · v12.2.0 | 0.089 % · v12.1.0 | 0.089 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `medi` | 0.0037 % · v12.2.0 | 0.029 % · v12.1.0 | 0.029 % · v12.0.0 | 0.029 % · v11.0.0 | failing · v10.0.0 |
| `mindgrab` | pass · v12.2.0 | pass · v12.1.0 | pass · v12.0.0 | pass · v11.0.0 | not in v10.0.0 |
| `modl-qsm` | failing · v12.2.0 | 0.014 % · v12.1.0 | 0.014 % · v12.0.0 | 0.014 % · v11.0.0 | 0.014 % · v10.0.0 |
| `ndi` | 0.0011 % · v12.2.0 | 0.0011 % · v12.1.0 | 0.0011 % · v12.0.0 | 0.0011 % · v11.0.0 | failing · v10.0.0 |
| `nextqsm` | 0.1 % · v12.2.0 | 0.1 % · v12.1.0 | 0.1 % · v12.0.0 | 0.1 % · v11.0.0 | failing · v10.0.0 |
| `nltv` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `pdf` | 0.015 % · v12.2.0 | 0.015 % · v12.1.0 | 0.015 % · v12.0.0 | 0.015 % · v11.0.0 | failing · v10.0.0 |
| `qsmart` | 0.79 % · v12.2.0 | 0.79 % · v12.1.0 | 0.78 % · v12.0.0 | 0.78 % · v11.0.0 | failing · v10.0.0 · no reliability, no offset_grid |
| `qsmgan` | 0.0056 % · v12.2.0 | 0.0048 % · v12.1.0 | 0.0056 % · v12.0.0 | 0.0056 % · v11.0.0 | 0.0056 % · v10.0.0 |
| `qsmnet` | < 0.001 % · v12.2.0 | failing · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | < 0.001 % · v10.0.0 |
| `qsmnet-plus` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | < 0.001 % · v10.0.0 |
| `qsmnetme` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `r2primenet` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `resharp` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `romeo` | 1.6 % · v12.2.0 | 1.6 % · v12.1.0 | 1.6 % · v12.0.0 | 1.6 % · v11.0.0 | failing · v10.0.0 |
| `rts` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `sharp` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `sharp-qsmjl` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 · no variant |
| `star` | 0.0023 % · v12.2.0 | 0.0023 % · v12.1.0 | 0.0023 % · v12.0.0 | 0.0023 % · v11.0.0 | not in v10.0.0 |
| `susep-net` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | < 0.001 % · v10.0.0 |
| `tfi` | 3.6 % · v12.2.0 | 3.6 % · v12.1.0 | 3.6 % · v12.0.0 | 3.6 % · v11.0.0 | failing · v10.0.0 |
| `tgv` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 · no reference_divergence, no reference_edge_erosion, no reference_output_box |
| `tikhonov` | identical · v12.2.0 | identical · v12.1.0 | identical · v12.0.0 | identical · v11.0.0 | failing · v10.0.0 |
| `tkd` | identical · v12.2.0 | identical · v12.1.0 | identical · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `toolbox-pipeline-chisep-ilsqr` | 0.0033 % · v12.2.0 | 0.0033 % · v12.1.0 | 0.0033 % · v12.0.0 | — | — |
| `toolbox-pipeline-chisep-medi` | 0.0033 % · v12.2.0 | 0.0033 % · v12.1.0 | 0.0033 % · v12.0.0 | — | — |
| `toolbox-pipeline-decompose` | 8.1 % · v12.2.0 | 8.1 % · v12.1.0 | 8.2 % · v12.0.0 | — | — |
| `toolbox-pipeline-medi-cornell` | 0.024 % · v12.2.0 | 0.024 % · v12.1.0 | 0.024 % · v12.0.0 | — | — |
| `toolbox-pipeline-qsmart` | 8.6 % · v12.2.0 | 8.6 % · v12.1.0 | 8.6 % · v12.0.0 | — | — |
| `toolbox-pipeline-sti` | 0.3 % · v12.2.0 | 0.3 % · v12.1.0 | 0.3 % · v12.0.0 | — | — |
| `toolbox-pipeline-ukb` | 0.0027 % · v12.2.0 | 0.0027 % · v12.1.0 | 0.0027 % · v12.0.0 | — | — |
| `tsvd` | identical · v12.2.0 | identical · v12.1.0 | identical · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `tv` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `vsharp` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `vsharp-qsmjl` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 · no ball, no radius_step |
| `wavesep` | < 0.001 % · v12.2.0 | < 0.001 % · v12.1.0 | < 0.001 % · v12.0.0 | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `whqsm` | 0.0034 % · v12.2.0 | 0.0034 % · v12.1.0 | 0.0034 % · v12.0.0 | 0.0038 % · v11.0.0 | failing · v10.0.0 |
| `xqsm` | 0.0018 % · v12.2.0 | 0.0018 % · v12.1.0 | 0.0018 % · v12.0.0 | 0.0014 % · v11.0.0 | 0.0016 % · v10.0.0 |
