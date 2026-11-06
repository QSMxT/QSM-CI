# Port parity status

Generated 2026-11-06 by `scripts/parity.py status` from `parity/results.json` and `parity/thresholds.yml`; do not edit by hand. How checks run, the two tracks, and what makes a check stale: [docs/parity.md](../docs/parity.md).

## Released: QSMxT v11.0.0

Tested: QSMxT **v11.0.0** (the binary the release ships) with QSM.rs v0.41.0 `8a655f4`.

The latest QSMxT release against each verified original. A release does not change, so it is rerun only for a new release, or when a pair's reference image or settings change. A failure here is that release's result; **not in** means the release has no such command or option yet.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.7794% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.3588% | ✅ current |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.01666% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.002378% | ✅ current |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0002207% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0009001% | ✅ current |
| `iharperella` | `iharperella-sti` → `iharperella-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 3.898e-05% | ✅ current |
| `star` | `star-sti` → `star-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.002147% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.002332% | ✅ current |
| `medi` | `medi-cornell` → `medi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.02745% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.02896% | ✅ current |
| `fit-ppm-complex` | `fit-ppm-complex-cornell` → `fit-ppm-complex-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0% | ✅ current |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.4767% | ✅ current |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 4.89% | ✅ current |
| `chisep-ilsqr` | `chisep-ilsqr` → `chisep-ilsqr-qsmrs` | chisep-mc | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 7.442e-08% | ✅ current |
| `chisep-medi` | `chisep-medi` → `chisep-medi-qsmrs` | chisep-mc | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.5787% | ✅ current |
| `wavesep` | `wavesep` → `wavesep-qsmrs` | chisep-mc | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 2.138e-07% | ✅ current |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 2.664e-14% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0% | ✅ current |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 1.297e-16% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0% | ✅ current |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0% | ✅ current |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 2.024e-16% | ✅ current |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 2.749e-10% | ✅ current |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 9.29e-09% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 3.932e-10% | ✅ current |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 2.064e-09% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 6.026e-09% | ✅ current |
| `sharp` | `sharp-sepia` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 1.394e-08% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 1.058e-08% | ✅ current |
| `sharp-qsmjl` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 6.322e-12% | ✅ current |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 1.133e-11% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 5.205e-12% | ✅ current |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 4.62e-06% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 4.767e-14% | ✅ current |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 1.498% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 1.645% | ✅ current |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0007664% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0003827% | ✅ current |
| `xqsm` | `xqsm` → `xqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.001409% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0008659% | ✅ current |
| `qsmnet` | `qsmnet` → `qsmnet-qsmrs` | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0001346% | ✅ current |
| `qsmnet-plus` | `qsmnet-plus` → `qsmnet-plus-qsmrs` | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0002086% | ✅ current |
| `lpcnn` | `lpcnn` → `lpcnn-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.007654% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 3.711e-05% | ✅ current |
| `qsmgan` | `qsmgan` → `qsmgan-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 9.417e-05% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.005643% | ✅ current |
| `modl-qsm` | `modl-qsm` → `modl-qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 5.912e-05% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.01412% | ✅ current |
| `ir2qsm` | `ir2qsm` → `ir2qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.001054% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0007882% | ✅ current |
| `autoqsm` | `autoqsm` → `autoqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0001121% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0001416% | ✅ current |
| `nextqsm` | `nextqsm` → `nextqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.1019% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0163% | ✅ current |
| `bfrnet` | `bfrnet` → `bfrnet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0001557% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0002169% | ✅ current |
| `chisepnet` | `chisepnet` → `chisepnet-qsmrs` | chisep-mc | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 4.001e-05% | ✅ current |
| `qsmnetme` | `qsmnetme` → `qsmnetme-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 9.434e-05% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 6.011e-05% | ✅ current |
| `susep-net` | `susep-net` → `susep-net-qsmrs` | chisep-mc | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 3.103e-05% | ✅ current |
| `hd-bet` | `hd-bet-qsmci` → `hd-bet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | — | ✅ current |
| `mindgrab` | `mindgrab` → `mindgrab-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | — | ✅ current |
| `r2primenet` | `r2primenet` → `r2primenet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 2.033e-05% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 2.047e-05% | ✅ current |
| `iqsm` | `iqsm` → `iqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0002228% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0002708% | ✅ current |
| `iqsm-plus` | `iqsm-plus` → `iqsm-plus-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0001166% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0001491% | ✅ current |
| `iqfm` | `iqfm` → `iqfm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0001829% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.000216% | ✅ current |
| `lsqr` | `lsqr` → `lsqr-qsmrs` | s005001-cbic-prisma-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0002515% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0003931% | ✅ current |
| `heidi` | `heidi` → `heidi-qsmrs` | s005001-cbic-prisma-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ❌ fail | 0.05137% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0004536% | ✅ current |
| `ndi` | `ndi` → `ndi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 8.885e-05% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.001103% | ✅ current |
| `fansi-nltv` | `fansi-nltv` → `fansi-nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.003004% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.006892% | ✅ current |
| `fansi-nltgv` | `fansi-nltgv` → `fansi-nltgv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.003897% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.006343% | ✅ current |
| `l1qsm` | `l1qsm` → `l1qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.002593% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.002205% | ✅ current |
| `whqsm` | `whqsm` → `whqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.003822% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.001817% | ✅ current |
| `hdqsm` | `hdqsm` → `hdqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0008603% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.001482% | ✅ current |
| `resharp` | `resharp` → `resharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 7.731e-09% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 1.49e-08% | ✅ current |
| `pdf` | `pdf-cornell` → `pdf-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 2.107e-05% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.01461% | ✅ current |
| `lbv` | `lbv-cornell` → `lbv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.001839% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 0.0007665% | ✅ current |
| `tfi` | `tfi-cornell` → `tfi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 1.256% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/42171553924) | v0.41.0 `8a655f4` | ✅ pass | 3.56% | ✅ current |

## Development: QSMxT main × QSM.rs main

Tested: QSMxT main `dc94cf4` with qsm-core at QSM.rs main `8a655f4`.

A check is **stale** when the reference image changed, QSM.rs `main` changed the port's source files or `Cargo.lock`, QSMxT `main` changed the step's wiring or `Cargo.lock`, the pair's limits changed, or it failed. There is no age limit. A **gap** is a pair whose port does not match its original yet: it is not enabled, and has no limits that would pass it.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.7794% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.3834% | ✅ current |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.01666% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.002378% | ✅ current |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0002207% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0009001% | ✅ current |
| `iharperella` | `iharperella-sti` → `iharperella-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 3.898e-05% | ✅ current |
| `star` | `star-sti` → `star-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.002147% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.002332% | ✅ current |
| `medi` | `medi-cornell` → `medi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.02745% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.02896% | ✅ current |
| `fit-ppm-complex` | `fit-ppm-complex-cornell` → `fit-ppm-complex-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41811450319) | `8a655f4` | ✅ pass (reviewed) | 0% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41811450319) | `8a655f4` | ✅ pass (reviewed) | 0% | ✅ current |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.4767% | ✅ current |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 4.89% | ✅ current |
| `chisep-ilsqr` | `chisep-ilsqr` → `chisep-ilsqr-qsmrs` | chisep-mc | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 7.442e-08% | ✅ current |
| `chisep-medi` | `chisep-medi` → `chisep-medi-qsmrs` | chisep-mc | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.5787% | ✅ current |
| `wavesep` | `wavesep` → `wavesep-qsmrs` | chisep-mc | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 2.138e-07% | ✅ current |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 2.664e-14% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0% | ✅ current |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 1.297e-16% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0% | ✅ current |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0% | ✅ current |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 2.024e-16% | ✅ current |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 2.749e-10% | ✅ current |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 9.29e-09% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 3.932e-10% | ✅ current |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 2.064e-09% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 6.026e-09% | ✅ current |
| `sharp` | `sharp-sepia` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 1.394e-08% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 1.058e-08% | ✅ current |
| `sharp-qsmjl` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 6.322e-12% | ✅ current |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 1.133e-11% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 5.205e-12% | ✅ current |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41811450319) | `8a655f4` | ✅ pass (reviewed) | 4.62e-06% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41811450319) | `8a655f4` | ✅ pass (reviewed) | 4.767e-14% | ✅ current |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41949669792) | `8a655f4` | ✅ pass (reviewed) | 1.498% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41949669792) | `8a655f4` | ✅ pass (reviewed) | 1.645% | ✅ current |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0007664% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0003827% | ✅ current |
| `xqsm` | `xqsm` → `xqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.001409% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.001641% | ✅ current |
| `qsmnet` | `qsmnet` → `qsmnet-qsmrs` | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0001346% | ✅ current |
| `qsmnet-plus` | `qsmnet-plus` → `qsmnet-plus-qsmrs` | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0002079% | ✅ current |
| `lpcnn` | `lpcnn` → `lpcnn-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.007654% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 3.92e-05% | ✅ current |
| `qsmgan` | `qsmgan` → `qsmgan-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 9.418e-05% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.005643% | ✅ current |
| `modl-qsm` | `modl-qsm` → `modl-qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 5.912e-05% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.01412% | ✅ current |
| `ir2qsm` | `ir2qsm` → `ir2qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.001054% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0007882% | ✅ current |
| `autoqsm` | `autoqsm` → `autoqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0001101% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0001416% | ✅ current |
| `nextqsm` | `nextqsm` → `nextqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.1436% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.01823% | ✅ current |
| `bfrnet` | `bfrnet` → `bfrnet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0001557% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0002169% | ✅ current |
| `chisepnet` | `chisepnet` → `chisepnet-qsmrs` | chisep-mc | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 4.001e-05% | ✅ current |
| `qsmnetme` | `qsmnetme` → `qsmnetme-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 9.434e-05% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 6.011e-05% | ✅ current |
| `susep-net` | `susep-net` → `susep-net-qsmrs` | chisep-mc | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 3.103e-05% | ✅ current |
| `hd-bet` | `hd-bet-qsmci` → `hd-bet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | — | ✅ current |
| `mindgrab` | `mindgrab` → `mindgrab-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | — | ✅ current |
| `r2primenet` | `r2primenet` → `r2primenet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 2.033e-05% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 2.047e-05% | ✅ current |
| `iqsm` | `iqsm` → `iqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0002228% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0002789% | ✅ current |
| `iqsm-plus` | `iqsm-plus` → `iqsm-plus-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.00012% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0001549% | ✅ current |
| `iqfm` | `iqfm` → `iqfm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0001829% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.000216% | ✅ current |
| `lsqr` | `lsqr` → `lsqr-qsmrs` | s005001-cbic-prisma-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0002515% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0003931% | ✅ current |
| `heidi` | `heidi` → `heidi-qsmrs` | s005001-cbic-prisma-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0003489% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0004536% | ✅ current |
| `ndi` | `ndi` → `ndi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 8.885e-05% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.001103% | ✅ current |
| `fansi-nltv` | `fansi-nltv` → `fansi-nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.003004% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.006892% | ✅ current |
| `fansi-nltgv` | `fansi-nltgv` → `fansi-nltgv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.003897% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.006343% | ✅ current |
| `l1qsm` | `l1qsm` → `l1qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.002593% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.002205% | ✅ current |
| `whqsm` | `whqsm` → `whqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.003822% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.001817% | ✅ current |
| `hdqsm` | `hdqsm` → `hdqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0008603% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.001482% | ✅ current |
| `resharp` | `resharp` → `resharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 7.731e-09% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 1.595e-08% | ✅ current |
| `pdf` | `pdf-cornell` → `pdf-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 2.107e-05% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.01461% | ✅ current |
| `lbv` | `lbv-cornell` → `lbv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.001839% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 0.0007665% | ✅ current |
| `tfi` | `tfi-cornell` → `tfi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 1.256% | ✅ current |
|  |  | sim | [2026-11-06](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `8a655f4` | ✅ pass (reviewed) | 3.56% | ✅ current |

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

| Pair | v11.0.0 | v10.0.0 |
|---|---|---|
| `amp-pe` | 0.48 % · v11.0.0 | 0.48 % · v10.0.0 |
| `autoqsm` | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `bfrnet` | < 0.001 % · v11.0.0 | < 0.001 % · v10.0.0 |
| `chisep-ilsqr` | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `chisep-medi` | 0.58 % · v11.0.0 | not in v10.0.0 |
| `chisepnet` | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `decompose` | 4.9 % · v11.0.0 | failing · v10.0.0 · no unwrap_phase |
| `fansi-nltgv` | 0.0063 % · v11.0.0 | failing · v10.0.0 |
| `fansi-nltv` | 0.0069 % · v11.0.0 | failing · v10.0.0 |
| `fit-ppm-complex` | identical · v11.0.0 | not in v10.0.0 |
| `hd-bet` | pass · v11.0.0 | pass · v10.0.0 |
| `hdqsm` | 0.0015 % · v11.0.0 | failing · v10.0.0 |
| `heidi` | failing · v11.0.0 | failing · v10.0.0 · no denoise_reference_itk |
| `iharperella` | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `ilsqr` | 0.017 % · v11.0.0 | failing · v10.0.0 |
| `iqfm` | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `iqsm` | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `iqsm-plus` | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `ir2qsm` | 0.0011 % · v11.0.0 | 0.0014 % · v10.0.0 |
| `ismv` | < 0.001 % · v11.0.0 | failing · v10.0.0 · no variant |
| `l1qsm` | 0.0026 % · v11.0.0 | failing · v10.0.0 |
| `laplacian` | < 0.001 % · v11.0.0 | < 0.001 % · v10.0.0 |
| `lbv` | 0.0018 % · v11.0.0 | failing · v10.0.0 |
| `lpcnn` | 0.0077 % · v11.0.0 | 0.0078 % · v10.0.0 |
| `lsqr` | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `medi` | 0.029 % · v11.0.0 | failing · v10.0.0 |
| `mindgrab` | pass · v11.0.0 | not in v10.0.0 |
| `modl-qsm` | 0.014 % · v11.0.0 | 0.014 % · v10.0.0 |
| `ndi` | 0.0011 % · v11.0.0 | failing · v10.0.0 |
| `nextqsm` | 0.1 % · v11.0.0 | failing · v10.0.0 |
| `nltv` | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `pdf` | 0.015 % · v11.0.0 | failing · v10.0.0 |
| `qsmart` | 0.78 % · v11.0.0 | failing · v10.0.0 · no reliability, no offset_grid |
| `qsmgan` | 0.0056 % · v11.0.0 | 0.0056 % · v10.0.0 |
| `qsmnet` | < 0.001 % · v11.0.0 | < 0.001 % · v10.0.0 |
| `qsmnet-plus` | < 0.001 % · v11.0.0 | < 0.001 % · v10.0.0 |
| `qsmnetme` | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `r2primenet` | < 0.001 % · v11.0.0 | not in v10.0.0 |
| `resharp` | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `romeo` | 1.6 % · v11.0.0 | failing · v10.0.0 |
| `rts` | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `sharp` | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `sharp-qsmjl` | < 0.001 % · v11.0.0 | failing · v10.0.0 · no variant |
| `star` | 0.0023 % · v11.0.0 | not in v10.0.0 |
| `susep-net` | < 0.001 % · v11.0.0 | < 0.001 % · v10.0.0 |
| `tfi` | 3.6 % · v11.0.0 | failing · v10.0.0 |
| `tgv` | < 0.001 % · v11.0.0 | failing · v10.0.0 · no reference_divergence, no reference_edge_erosion, no reference_output_box |
| `tikhonov` | identical · v11.0.0 | failing · v10.0.0 |
| `tkd` | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `tsvd` | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `tv` | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `vsharp` | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `vsharp-qsmjl` | < 0.001 % · v11.0.0 | failing · v10.0.0 · no ball, no radius_step |
| `wavesep` | < 0.001 % · v11.0.0 | failing · v10.0.0 |
| `whqsm` | 0.0038 % · v11.0.0 | failing · v10.0.0 |
| `xqsm` | 0.0014 % · v11.0.0 | 0.0016 % · v10.0.0 |
