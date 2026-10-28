# Port parity status

Generated 2026-10-28 by `scripts/parity.py status` from `parity/results.json` and `parity/thresholds.yml`; do not edit by hand. How checks run, and what makes one stale: [docs/parity.md](../docs/parity.md).

A check is **stale** when the reference image changed, QSM.rs `main` changed the pair's source files, the pair's limits changed, it is more than 90 days old, or it failed. A **gap** is a pair whose port does not match its original yet: it is not enabled, and has no limits that would pass it.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (STI Suite port gaps (QSM.rs issue to file; QSMxT/QSM-CI parity/status PR)) |
|  |  | sim | never | — | — | — | 🚧 gap (STI Suite port gaps (QSM.rs issue to file; QSMxT/QSM-CI parity/status PR)) |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (STI Suite port gaps (QSM.rs issue to file; QSMxT/QSM-CI parity/status PR)) |
|  |  | sim | never | — | — | — | 🚧 gap (STI Suite port gaps (QSM.rs issue to file; QSMxT/QSM-CI parity/status PR)) |
| `star` | `star-sti` → `star-qsmrs` | sim | never | — | — | — | ⚠️ stale: never checked |
| `medi` | `medi-cornell` → `medi-qsmrs` | — | never | — | — | — | — not enabled (waiting for medi-cornell v4 (MEDI 2024.11.26's own defaults, QSMxT/QSM-CI#309)) |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | never | — | — | — | — not enabled |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | never | — | — | — | — not enabled |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | — | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `sharp` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
| `vsharp-deconv` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `ilsqr-pad12` | `ilsqr-sti` → `ilsqr-qsmrs` | sim | never | — | — | — | — not enabled |

Refresh every stale pair against QSM.rs `main`:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=qsmart,star,tkd,tsvd,tikhonov,tv,rts,ismv,laplacian -f dataset=configured -f qsmrs_ref=main
```
