# Port parity status

Generated 2026-10-28 by `scripts/parity.py status` from `parity/results.json` and `parity/thresholds.yml`; do not edit by hand. How checks run, and what makes one stale: [docs/parity.md](../docs/parity.md).

A check is **stale** when the reference image changed, QSM.rs `main` changed the pair's source files, the pair's limits changed, it is more than 90 days old, or it failed. A **gap** is a pair whose port does not match its original yet: it is not enabled, and has no limits that would pass it.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (QSMxT/QSM-CI#311) |
|  |  | sim | never | — | — | — | 🚧 gap (QSMxT/QSM-CI#311) |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (QSMxT/QSM-CI#311) |
|  |  | sim | never | — | — | — | 🚧 gap (QSMxT/QSM-CI#311) |
| `star` | `star-sti` → `star-qsmrs` | sim | never | — | — | — | ⚠️ stale: never checked |
| `medi` | `medi-cornell` → `medi-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | never | — | — | — | ⚠️ stale: never checked |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | never | — | — | — | 🚧 gap (QSMxT/QSM-CI#311) |
| `wavesep` | `wavesep` → `wavesep-qsmrs` | chisep-mc | never | — | — | — | 🚧 gap (QSMxT/QSM-CI#312) |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#323) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#323) |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#323) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#323) |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#323) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#323) |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#323) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#323) |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | — | never | — | — | — | 🚧 gap (astewartau/QSM.rs#323) |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#323) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#323) |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#322) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#322) |
| `sharp` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#321) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#321) |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#321) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#321) |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#325) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#325) |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#324) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#324) |

Refresh every stale pair against QSM.rs `main`:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=qsmart,star,medi,amp-pe,laplacian -f dataset=configured -f qsmrs_ref=main
```
