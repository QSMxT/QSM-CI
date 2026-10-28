# Port parity status

Generated 2026-10-28 by `scripts/parity.py status` from `parity/results.json` and `parity/thresholds.yml`; do not edit by hand. How checks run, and what makes one stale: [docs/parity.md](../docs/parity.md).

A check is **stale** when the reference image changed, QSM.rs `main` changed the pair's source files, the pair's limits changed, it is more than 90 days old, or it failed. A **gap** is a pair whose port does not match its original yet: it is not enabled, and has no limits that would pass it.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 4.618% | ✅ current |
|  |  | sim | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 16.71% | ✅ current |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (STI Suite port gaps (QSM.rs issue to file; QSMxT/QSM-CI parity/status PR)) |
|  |  | sim | never | — | — | — | 🚧 gap (STI Suite port gaps (QSM.rs issue to file; QSMxT/QSM-CI parity/status PR)) |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (STI Suite port gaps (QSM.rs issue to file; QSMxT/QSM-CI parity/status PR)) |
|  |  | sim | never | — | — | — | 🚧 gap (STI Suite port gaps (QSM.rs issue to file; QSMxT/QSM-CI parity/status PR)) |
| `star` | `star-sti` → `star-qsmrs` | sim | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 0.3256% | ✅ current |
| `medi` | `medi-cornell` → `medi-qsmrs` | — | never | — | — | — | — not enabled (waiting for medi-cornell v4 (MEDI 2024.11.26's own defaults, QSMxT/QSM-CI#309)) |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | never | — | — | — | — not enabled |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | never | — | — | — | — not enabled |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 0.6894% | ✅ current |
|  |  | sim | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 0% | ✅ current |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 0.5703% | ✅ current |
|  |  | sim | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 0% | ✅ current |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 0.5189% | ✅ current |
|  |  | sim | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 0% | ✅ current |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 0.1674% | ✅ current |
|  |  | sim | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 0% | ✅ current |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | — | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 1.192% | ✅ current |
|  |  | sim | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 0% | ✅ current |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 9.812e-09% | ✅ current |
|  |  | sim | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 4.491e-10% | ✅ current |
| `sharp` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 6.398e-10% | ✅ current |
|  |  | sim | [2026-10-28](https://github.com/QSMxT/QSM-CI/actions/runs/40610484483) | `da928e0` | ✅ pass | 4.767e-14% | ✅ current |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#319) |
| `vsharp-deconv` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled |
|  |  | sim | never | — | — | — | — not enabled |
| `ilsqr-pad12` | `ilsqr-sti` → `ilsqr-qsmrs` | sim | never | — | — | — | — not enabled |
