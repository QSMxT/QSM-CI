# Port parity status

Generated 2026-11-04 by `scripts/parity.py status` from `parity/results.json` and `parity/thresholds.yml`; do not edit by hand. How checks run, the two tracks, and what makes a check stale: [docs/parity.md](../docs/parity.md).

## Released: QSMxT v10.0.0

Tested: QSMxT **v10.0.0** (the binary the release ships) with QSM.rs v0.39.0 `42ab620`.

The latest QSMxT release against each verified original. A release does not change, so it is rerun only for a new release, or when a pair's reference image or settings change. A failure here is that release's result; **not in** means the release has no such command or option yet.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 133.8% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 66.26% | ✅ current |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 9.223% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 6.039% | ✅ current |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 13.37% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 10.86% | ✅ current |
| `iharperella` | `iharperella-sti` → `iharperella-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ❌ fail | 90.2% | ✅ current |
| `star` | `star-sti` → `star-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
| `medi` | `medi-cornell` → `medi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 81.63% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 80.37% | ✅ current |
| `fit-ppm-complex` | `fit-ppm-complex-cornell` → `fit-ppm-complex-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ✅ pass | 0.4767% | ✅ current |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | [2026-11-02](https://github.com/QSMxT/QSM-CI/actions/runs/41371103875) | v0.39.0 `42ab620` | ❌ fail | 144% | ✅ current |
| `chisep-ilsqr` | `chisep-ilsqr` → `chisep-ilsqr-qsmrs` | chisep-mc | [2026-11-02](https://github.com/QSMxT/QSM-CI/actions/runs/41371086692) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
| `chisep-medi` | `chisep-medi` → `chisep-medi-qsmrs` | chisep-mc | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
| `wavesep` | `wavesep` → `wavesep-qsmrs` | chisep-mc | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 17.65% | ✅ current |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 0.6929% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 1.302% | ✅ current |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 0.5905% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 2.741% | ✅ current |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 0.522% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 0.3246% | ✅ current |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 55.29% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 38.68% | ✅ current |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 208.6% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 59.14% | ✅ current |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 24.59% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 20.25% | ✅ current |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 223.2% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 48.04% | ✅ current |
| `sharp` | `sharp-sepia` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 33.49% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 26.76% | ✅ current |
| `sharp-qsmjl` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 98.51% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 98.3% | ✅ current |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 22% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 9.378% | ✅ current |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ✅ pass | 4.62e-06% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ✅ pass | 4.767e-14% | ✅ current |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 2.058% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 2.566% | ✅ current |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ❌ fail | 72.64% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ❌ fail | 50.55% | ✅ current |
| `xqsm` | `xqsm` → `xqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 0.001571% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 0.0008659% | ✅ current |
| `qsmnet` | `qsmnet` → `qsmnet-qsmrs` | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 0.0001346% | ✅ current |
| `qsmnet-plus` | `qsmnet-plus` → `qsmnet-plus-qsmrs` | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 0.0002086% | ✅ current |
| `lpcnn` | `lpcnn` → `lpcnn-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 0.007791% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 3.92e-05% | ✅ current |
| `qsmgan` | `qsmgan` → `qsmgan-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 9.337e-05% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 0.005643% | ✅ current |
| `modl-qsm` | `modl-qsm` → `modl-qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 5.855e-05% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 0.01412% | ✅ current |
| `ir2qsm` | `ir2qsm` → `ir2qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 0.001434% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 0.0005049% | ✅ current |
| `autoqsm` | `autoqsm` → `autoqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 184.5% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 182.2% | ✅ current |
| `nextqsm` | `nextqsm` → `nextqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 0.1025% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 30.74% | ✅ current |
| `bfrnet` | `bfrnet` → `bfrnet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 0.0001557% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 0.0002169% | ✅ current |
| `chisepnet` | `chisepnet` → `chisepnet-qsmrs` | chisep-mc | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
| `qsmnetme` | `qsmnetme` → `qsmnetme-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
| `susep-net` | `susep-net` → `susep-net-qsmrs` | chisep-mc | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | 3.103e-05% | ✅ current |
| `hd-bet` | `hd-bet-qsmci` → `hd-bet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ✅ pass | — | ✅ current |
| `mindgrab` | `mindgrab` → `mindgrab-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
| `r2primenet` | `r2primenet` → `r2primenet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
| `iqsm` | `iqsm` → `iqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
| `iqsm-plus` | `iqsm-plus` → `iqsm-plus-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
| `iqfm` | `iqfm` → `iqfm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
| `lsqr` | `lsqr` → `lsqr-qsmrs` | s005001-cbic-prisma-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ❌ fail | 14.58% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ❌ fail | 5.557% | ✅ current |
| `heidi` | `heidi` → `heidi-qsmrs` | s005001-cbic-prisma-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ❌ fail | 33.13% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ❌ fail | 30.71% | ✅ current |
| `ndi` | `ndi` → `ndi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 84.92% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 48.63% | ✅ current |
| `fansi-nltv` | `fansi-nltv` → `fansi-nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 26.74% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 44.63% | ✅ current |
| `fansi-nltgv` | `fansi-nltgv` → `fansi-nltgv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 31.03% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 43.41% | ✅ current |
| `l1qsm` | `l1qsm` → `l1qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 116.4% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 51.78% | ✅ current |
| `whqsm` | `whqsm` → `whqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 58.08% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 37.49% | ✅ current |
| `hdqsm` | `hdqsm` → `hdqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 65.88% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 25.29% | ✅ current |
| `resharp` | `resharp` → `resharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 39.03% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 27.81% | ✅ current |
| `pdf` | `pdf-cornell` → `pdf-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 48.43% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 72.31% | ✅ current |
| `lbv` | `lbv-cornell` → `lbv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 24% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 7.724% | ✅ current |
| `tfi` | `tfi-cornell` → `tfi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 35.37% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41775085523) | v0.39.0 `42ab620` | ❌ fail | 84.67% | ✅ current |

## Development: QSMxT main × QSM.rs main

Tested: QSMxT main `67c7342` with qsm-core at QSM.rs main `008b829` (1 older build(s) for pairs not rerun since).

A check is **stale** when the reference image changed, QSM.rs `main` changed the port's source files or `Cargo.lock`, QSMxT `main` changed the step's wiring or `Cargo.lock`, the pair's limits changed, or it failed. There is no age limit. A **gap** is a pair whose port does not match its original yet: it is not enabled, and has no limits that would pass it.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.7794% | ⚠️ stale: QSM.rs main changed `src/pipeline/config.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs`, `src/pipeline/config.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.3834% | ⚠️ stale: QSM.rs main changed `src/pipeline/config.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs`, `src/pipeline/config.rs` since the checked f5a8ac6 (5 commits) |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.01666% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.002378% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0002207% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0009001% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `iharperella` | `iharperella-sti` → `iharperella-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 3.898e-05% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `star` | `star-sti` → `star-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.002147% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.002332% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `medi` | `medi-cornell` → `medi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.02745% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs`, `src/utils/multi_echo.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.02896% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs`, `src/utils/multi_echo.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `fit-ppm-complex` | `fit-ppm-complex-cornell` → `fit-ppm-complex-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41811450319) | `008b829` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41811450319) | `008b829` | ✅ pass | 0% | ✅ current |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.4767% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 4.89% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `chisep-ilsqr` | `chisep-ilsqr` → `chisep-ilsqr-qsmrs` | chisep-mc | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 7.442e-08% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `chisep-medi` | `chisep-medi` → `chisep-medi-qsmrs` | chisep-mc | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.5787% | ⚠️ stale: QSM.rs main changed `src/utils/multi_echo.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `wavesep` | `wavesep` → `wavesep-qsmrs` | chisep-mc | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 2.138e-07% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 2.664e-14% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 1.297e-16% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 2.024e-16% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 2.749e-10% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 9.29e-09% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 3.932e-10% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 2.064e-09% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 6.026e-09% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `sharp` | `sharp-sepia` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 1.394e-08% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 1.058e-08% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `sharp-qsmjl` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 6.322e-12% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 1.133e-11% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 5.205e-12% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41811450319) | `008b829` | ✅ pass | 4.62e-06% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41811450319) | `008b829` | ✅ pass | 4.767e-14% | ✅ current |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41811450319) | `008b829` | ✅ pass | 1.498% | ✅ current |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41811450319) | `008b829` | ❌ fail | 1.684% | ⚠️ stale: the last check failed: totalfield max_abs 0.2823 ppm (limit <= 0.205 ppm) |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0007664% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0003827% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `xqsm` | `xqsm` → `xqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.001409% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.001641% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `qsmnet` | `qsmnet` → `qsmnet-qsmrs` | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0001346% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `qsmnet-plus` | `qsmnet-plus` → `qsmnet-plus-qsmrs` | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0002079% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `lpcnn` | `lpcnn` → `lpcnn-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.007654% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 3.92e-05% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `qsmgan` | `qsmgan` → `qsmgan-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 9.418e-05% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.005643% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `modl-qsm` | `modl-qsm` → `modl-qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 5.912e-05% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.01412% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `ir2qsm` | `ir2qsm` → `ir2qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.001054% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0007882% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `autoqsm` | `autoqsm` → `autoqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0001101% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0001416% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `nextqsm` | `nextqsm` → `nextqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.1436% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.01823% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `bfrnet` | `bfrnet` → `bfrnet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0001557% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0002169% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `chisepnet` | `chisepnet` → `chisepnet-qsmrs` | chisep-mc | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 4.001e-05% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `qsmnetme` | `qsmnetme` → `qsmnetme-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 9.434e-05% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 6.011e-05% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `susep-net` | `susep-net` → `susep-net-qsmrs` | chisep-mc | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 3.103e-05% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `hd-bet` | `hd-bet-qsmci` → `hd-bet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | — | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/mask.rs` since the checked f5a8ac6 (5 commits) |
| `mindgrab` | `mindgrab` → `mindgrab-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | — | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/mask.rs` since the checked f5a8ac6 (5 commits) |
| `r2primenet` | `r2primenet` → `r2primenet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 2.033e-05% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 2.047e-05% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `iqsm` | `iqsm` → `iqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0002228% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0002789% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `iqsm-plus` | `iqsm-plus` → `iqsm-plus-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.00012% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0001549% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `iqfm` | `iqfm` → `iqfm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0001829% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.000216% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `lsqr` | `lsqr` → `lsqr-qsmrs` | s005001-cbic-prisma-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0002515% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0003931% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `heidi` | `heidi` → `heidi-qsmrs` | s005001-cbic-prisma-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0003489% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0004536% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `ndi` | `ndi` → `ndi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 8.885e-05% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.001103% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `fansi-nltv` | `fansi-nltv` → `fansi-nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.003004% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.006892% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `fansi-nltgv` | `fansi-nltgv` → `fansi-nltgv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.003897% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.006343% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `l1qsm` | `l1qsm` → `l1qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.002593% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.002205% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `whqsm` | `whqsm` → `whqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.003822% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.001817% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `hdqsm` | `hdqsm` → `hdqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0008603% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.001482% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/mask.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `resharp` | `resharp` → `resharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 7.731e-09% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 1.595e-08% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `pdf` | `pdf-cornell` → `pdf-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 2.107e-05% | ⚠️ stale: QSM.rs main changed `src/utils/multi_echo.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.01461% | ⚠️ stale: QSM.rs main changed `src/utils/multi_echo.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `lbv` | `lbv-cornell` → `lbv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.001839% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 0.0007665% | ⚠️ stale: QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
| `tfi` | `tfi-cornell` → `tfi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 1.256% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/multi_echo.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |
|  |  | sim | [2026-11-04](https://github.com/QSMxT/QSM-CI/actions/runs/41757738719) | `de9231e` | ✅ pass | 3.56% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/utils/multi_echo.rs` since the checked de9231e (1 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs` since the checked f5a8ac6 (5 commits) |

Refresh every stale pair against QSM.rs `main`:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=qsmart,ilsqr,vsharp,iharperella,star,medi,amp-pe,decompose,chisep-ilsqr,chisep-medi,wavesep,tkd,tsvd,tikhonov,tv,nltv,rts,ismv,sharp,sharp-qsmjl,vsharp-qsmjl,romeo,tgv,xqsm,qsmnet,qsmnet-plus,lpcnn,qsmgan,modl-qsm,ir2qsm,autoqsm,nextqsm,bfrnet,chisepnet,qsmnetme,susep-net,hd-bet,mindgrab,r2primenet,iqsm,iqsm-plus,iqfm,lsqr,heidi,ndi,fansi-nltv,fansi-nltgv,l1qsm,whqsm,hdqsm,resharp,pdf,lbv,tfi -f dataset=configured -f qsmrs_ref=main
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

| Pair | v10.0.0 |
|---|---|
| `amp-pe` | 0.48 % · v10.0.0 |
| `autoqsm` | failing · v10.0.0 |
| `bfrnet` | < 0.001 % · v10.0.0 |
| `chisep-ilsqr` | not in v10.0.0 |
| `chisep-medi` | not in v10.0.0 |
| `chisepnet` | not in v10.0.0 |
| `decompose` | failing · v10.0.0 · no unwrap_phase |
| `fansi-nltgv` | failing · v10.0.0 |
| `fansi-nltv` | failing · v10.0.0 |
| `fit-ppm-complex` | not in v10.0.0 |
| `hd-bet` | pass · v10.0.0 |
| `hdqsm` | failing · v10.0.0 |
| `heidi` | failing · v10.0.0 · no denoise_reference_itk |
| `iharperella` | failing · v10.0.0 |
| `ilsqr` | failing · v10.0.0 |
| `iqfm` | not in v10.0.0 |
| `iqsm` | not in v10.0.0 |
| `iqsm-plus` | not in v10.0.0 |
| `ir2qsm` | 0.0014 % · v10.0.0 |
| `ismv` | failing · v10.0.0 · no variant |
| `l1qsm` | failing · v10.0.0 |
| `laplacian` | < 0.001 % · v10.0.0 |
| `lbv` | failing · v10.0.0 |
| `lpcnn` | 0.0078 % · v10.0.0 |
| `lsqr` | failing · v10.0.0 |
| `medi` | failing · v10.0.0 |
| `mindgrab` | not in v10.0.0 |
| `modl-qsm` | 0.014 % · v10.0.0 |
| `ndi` | failing · v10.0.0 |
| `nextqsm` | failing · v10.0.0 |
| `nltv` | failing · v10.0.0 |
| `pdf` | failing · v10.0.0 |
| `qsmart` | failing · v10.0.0 · no reliability, no offset_grid |
| `qsmgan` | 0.0056 % · v10.0.0 |
| `qsmnet` | < 0.001 % · v10.0.0 |
| `qsmnet-plus` | < 0.001 % · v10.0.0 |
| `qsmnetme` | not in v10.0.0 |
| `r2primenet` | not in v10.0.0 |
| `resharp` | failing · v10.0.0 |
| `romeo` | failing · v10.0.0 |
| `rts` | failing · v10.0.0 |
| `sharp` | failing · v10.0.0 |
| `sharp-qsmjl` | failing · v10.0.0 · no variant |
| `star` | not in v10.0.0 |
| `susep-net` | < 0.001 % · v10.0.0 |
| `tfi` | failing · v10.0.0 |
| `tgv` | failing · v10.0.0 · no reference_divergence, no reference_edge_erosion, no reference_output_box |
| `tikhonov` | failing · v10.0.0 |
| `tkd` | failing · v10.0.0 |
| `tsvd` | failing · v10.0.0 |
| `tv` | failing · v10.0.0 |
| `vsharp` | failing · v10.0.0 |
| `vsharp-qsmjl` | failing · v10.0.0 · no ball, no radius_step |
| `wavesep` | failing · v10.0.0 |
| `whqsm` | failing · v10.0.0 |
| `xqsm` | 0.0016 % · v10.0.0 |
