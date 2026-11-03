# Port parity status

Generated 2026-11-03 by `scripts/parity.py status` from `parity/results.json` and `parity/thresholds.yml`; do not edit by hand. How checks run, the two tracks, and what makes a check stale: [docs/parity.md](../docs/parity.md).

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
| `fit-ppm-complex` | `fit-ppm-complex-cornell` → `fit-ppm-complex-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
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
| `xqsm` | `xqsm` → `xqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `qsmnet` | `qsmnet` → `qsmnet-qsmrs` | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `qsmnet-plus` | `qsmnet-plus` → `qsmnet-plus-qsmrs` | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `lpcnn` | `lpcnn` → `lpcnn-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `qsmgan` | `qsmgan` → `qsmgan-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `modl-qsm` | `modl-qsm` → `modl-qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `ir2qsm` | `ir2qsm` → `ir2qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `autoqsm` | `autoqsm` → `autoqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `nextqsm` | `nextqsm` → `nextqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `bfrnet` | `bfrnet` → `bfrnet-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `chisepnet` | `chisepnet` → `chisepnet-qsmrs` | chisep-mc | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `qsmnetme` | `qsmnetme` → `qsmnetme-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `susep-net` | `susep-net` → `susep-net-qsmrs` | chisep-mc | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `hd-bet` | `hd-bet-qsmci` → `hd-bet-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `mindgrab` | `mindgrab` → `mindgrab-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `r2primenet` | `r2primenet` → `r2primenet-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `iqsm` | `iqsm` → `iqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `iqsm-plus` | `iqsm-plus` → `iqsm-plus-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `iqfm` | `iqfm` → `iqfm-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled (baseline pending) |
|  |  | sim | never | — | — | — | — not enabled (baseline pending) |
| `lsqr` | `lsqr` → `lsqr-qsmrs` | s005001-cbic-prisma-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ❌ fail | 14.58% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ❌ fail | 5.557% | ✅ current |
| `heidi` | `heidi` → `heidi-qsmrs` | s005001-cbic-prisma-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ❌ fail | 33.13% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41579904769) | v0.39.0 `42ab620` | ❌ fail | 30.71% | ✅ current |
| `ndi` | `ndi` → `ndi-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `fansi-nltv` | `fansi-nltv` → `fansi-nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `fansi-nltgv` | `fansi-nltgv` → `fansi-nltgv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `l1qsm` | `l1qsm` → `l1qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `whqsm` | `whqsm` → `whqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `hdqsm` | `hdqsm` → `hdqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `resharp` | `resharp` → `resharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `pdf` | `pdf-cornell` → `pdf-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `lbv` | `lbv-cornell` → `lbv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
| `tfi` | `tfi-cornell` → `tfi-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |
|  |  | sim | never | — | — | — | ⚠️ stale: not run against QSMxT v10.0.0 |

Run the flagged pairs against v10.0.0:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=xqsm,qsmnet,qsmnet-plus,lpcnn,qsmgan,modl-qsm,ir2qsm,autoqsm,nextqsm,bfrnet,chisepnet,qsmnetme,susep-net,hd-bet,mindgrab,r2primenet,iqsm,iqsm-plus,ndi,fansi-nltv,fansi-nltgv,l1qsm,whqsm,hdqsm,resharp,pdf,lbv,tfi -f dataset=configured -f qsmxt_release=v10.0.0
```

## Development: QSMxT main × QSM.rs main

Tested: QSMxT main `632fed9` with qsm-core at QSM.rs main `cc4ae49`.

A check is **stale** when the reference image changed, QSM.rs `main` changed the port's source files or `Cargo.lock`, QSMxT `main` changed the step's wiring or `Cargo.lock`, the pair's limits changed, or it failed. There is no age limit. A **gap** is a pair whose port does not match its original yet: it is not enabled, and has no limits that would pass it.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.7794% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.3834% | ✅ current |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.01666% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.002378% | ✅ current |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0002207% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0009001% | ✅ current |
| `iharperella` | `iharperella-sti` → `iharperella-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 3.898e-05% | ✅ current |
| `star` | `star-sti` → `star-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.002147% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.002332% | ✅ current |
| `medi` | `medi-cornell` → `medi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.02745% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.02896% | ✅ current |
| `fit-ppm-complex` | `fit-ppm-complex-cornell` → `fit-ppm-complex-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 2.559e-06% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 2.601e-06% | ✅ current |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.4767% | ✅ current |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 4.89% | ✅ current |
| `chisep-ilsqr` | `chisep-ilsqr` → `chisep-ilsqr-qsmrs` | chisep-mc | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 8.808e-09% | ✅ current |
| `chisep-medi` | `chisep-medi` → `chisep-medi-qsmrs` | chisep-mc | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.5787% | ✅ current |
| `wavesep` | `wavesep` → `wavesep-qsmrs` | chisep-mc | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 2.138e-07% | ✅ current |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 2.664e-14% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0% | ✅ current |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 1.297e-16% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0% | ✅ current |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0% | ✅ current |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 2.024e-16% | ✅ current |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 2.749e-10% | ✅ current |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 9.29e-09% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 3.932e-10% | ✅ current |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 2.064e-09% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 6.026e-09% | ✅ current |
| `sharp` | `sharp-sepia` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 1.394e-08% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 1.058e-08% | ✅ current |
| `sharp-qsmjl` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 6.322e-12% | ✅ current |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 1.133e-11% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 5.205e-12% | ✅ current |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 4.62e-06% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 4.767e-14% | ✅ current |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 1.498% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 1.639% | ✅ current |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0007664% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0003827% | ✅ current |
| `xqsm` | `xqsm` → `xqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.001409% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ❌ fail | 0.001641% | ⚠️ stale: the pair's settings or limits for this dataset changed since; the last check failed: chimap max_abs 1.496e-05 ppm (limit <= 9e-06 ppm) |
| `qsmnet` | `qsmnet` → `qsmnet-qsmrs` | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0001346% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
| `qsmnet-plus` | `qsmnet-plus` → `qsmnet-plus-qsmrs` | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0002059% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
| `lpcnn` | `lpcnn` → `lpcnn-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.007654% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 3.537e-05% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
| `qsmgan` | `qsmgan` → `qsmgan-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 9.92e-05% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.005643% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
| `modl-qsm` | `modl-qsm` → `modl-qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 5.912e-05% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.01412% | ✅ current |
| `ir2qsm` | `ir2qsm` → `ir2qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.001054% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0005049% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
| `autoqsm` | `autoqsm` → `autoqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0001121% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0001416% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
| `nextqsm` | `nextqsm` → `nextqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.1436% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0163% | ✅ current |
| `bfrnet` | `bfrnet` → `bfrnet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0001557% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0002169% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
| `chisepnet` | `chisepnet` → `chisepnet-qsmrs` | chisep-mc | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 4.001e-05% | ✅ current |
| `qsmnetme` | `qsmnetme` → `qsmnetme-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 9.434e-05% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 6.011e-05% | ✅ current |
| `susep-net` | `susep-net` → `susep-net-qsmrs` | chisep-mc | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 3.103e-05% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
| `hd-bet` | `hd-bet-qsmci` → `hd-bet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | — | ✅ current |
| `mindgrab` | `mindgrab` → `mindgrab-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | — | ✅ current |
| `r2primenet` | `r2primenet` → `r2primenet-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 2.033e-05% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 2.047e-05% | ✅ current |
| `iqsm` | `iqsm` → `iqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0002244% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0002708% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
| `iqsm-plus` | `iqsm-plus` → `iqsm-plus-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0001157% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0001549% | ⚠️ stale: the pair's settings or limits for this dataset changed since |
| `iqfm` | `iqfm` → `iqfm-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled (baseline pending) |
|  |  | sim | never | — | — | — | — not enabled (baseline pending) |
| `lsqr` | `lsqr` → `lsqr-qsmrs` | s005001-cbic-prisma-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0002515% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0003931% | ✅ current |
| `heidi` | `heidi` → `heidi-qsmrs` | s005001-cbic-prisma-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0003489% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0004536% | ✅ current |
| `ndi` | `ndi` → `ndi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 8.885e-05% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.001103% | ✅ current |
| `fansi-nltv` | `fansi-nltv` → `fansi-nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.003004% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.006892% | ✅ current |
| `fansi-nltgv` | `fansi-nltgv` → `fansi-nltgv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.003897% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.006343% | ✅ current |
| `l1qsm` | `l1qsm` → `l1qsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.002593% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.002205% | ✅ current |
| `whqsm` | `whqsm` → `whqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.003822% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.001817% | ✅ current |
| `hdqsm` | `hdqsm` → `hdqsm-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0008603% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.001482% | ✅ current |
| `resharp` | `resharp` → `resharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 7.731e-09% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 1.49e-08% | ✅ current |
| `pdf` | `pdf-cornell` → `pdf-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 2.107e-05% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.01461% | ✅ current |
| `lbv` | `lbv-cornell` → `lbv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.001839% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 0.0007665% | ✅ current |
| `tfi` | `tfi-cornell` → `tfi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 1.256% | ✅ current |
|  |  | sim | [2026-11-03](https://github.com/QSMxT/QSM-CI/actions/runs/41625523205) | `cc4ae49` | ✅ pass | 3.606% | ✅ current |

Refresh every stale pair against QSM.rs `main`:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=xqsm,qsmnet,qsmnet-plus,lpcnn,qsmgan,modl-qsm,ir2qsm,autoqsm,bfrnet,susep-net,iqsm,iqsm-plus -f dataset=configured -f qsmrs_ref=main
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
| `chisep-ilsqr` | not in v10.0.0 |
| `chisep-medi` | not in v10.0.0 |
| `decompose` | failing · v10.0.0 · no unwrap_phase |
| `fit-ppm-complex` | not in v10.0.0 |
| `heidi` | failing · v10.0.0 · no denoise_reference_itk |
| `iharperella` | failing · v10.0.0 |
| `ilsqr` | failing · v10.0.0 |
| `ismv` | failing · v10.0.0 · no variant |
| `laplacian` | < 0.001 % · v10.0.0 |
| `lsqr` | failing · v10.0.0 |
| `medi` | failing · v10.0.0 |
| `nltv` | failing · v10.0.0 |
| `qsmart` | failing · v10.0.0 · no reliability, no offset_grid |
| `romeo` | failing · v10.0.0 |
| `rts` | failing · v10.0.0 |
| `sharp` | failing · v10.0.0 |
| `sharp-qsmjl` | failing · v10.0.0 · no variant |
| `star` | not in v10.0.0 |
| `tgv` | failing · v10.0.0 · no reference_divergence, no reference_edge_erosion, no reference_output_box |
| `tikhonov` | failing · v10.0.0 |
| `tkd` | failing · v10.0.0 |
| `tsvd` | failing · v10.0.0 |
| `tv` | failing · v10.0.0 |
| `vsharp` | failing · v10.0.0 |
| `vsharp-qsmjl` | failing · v10.0.0 · no ball, no radius_step |
| `wavesep` | failing · v10.0.0 |
