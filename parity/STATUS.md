# Port parity status

Generated 2026-10-27 by `scripts/parity.py status` from `parity/results.json` and `parity/thresholds.yml`; do not edit by hand. How checks run, and what makes one stale: [docs/parity.md](../docs/parity.md).

A check is **stale** when the reference image changed, QSM.rs `main` changed the pair's source files, the pair's limits changed, it is more than 90 days old, or it failed. A **gap** is a pair whose port does not match its original yet: it is not enabled, and has no limits that would pass it.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `star` | `star-sti` → `star-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `medi` | `medi-cornell` → `medi-qsmrs` | — | never | — | — | — | — not enabled (waiting for medi-cornell v4 (MEDI 2024.11.26's own defaults, QSMxT/QSM-CI#309)) |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | never | — | — | — | — not enabled |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `sharp` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |

Refresh every stale pair against QSM.rs `main`:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=qsmart -f dataset=configured -f qsmrs_ref=main
```
