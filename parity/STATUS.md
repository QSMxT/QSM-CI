# Port parity status

Generated 2026-10-30 by `scripts/parity.py status` from `parity/results.json` and `parity/thresholds.yml`; do not edit by hand. How checks run, and what makes one stale: [docs/parity.md](../docs/parity.md).

A check is **stale** when the reference image changed, QSM.rs `main` changed the port's source files or `Cargo.lock`, QSMxT `main` changed the step's wiring or `Cargo.lock`, the pair's limits changed, or it failed. There is no age limit. A **gap** is a pair whose port does not match its original yet: it is not enabled, and has no limits that would pass it.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-30](https://github.com/QSMxT/QSM-CI/actions/runs/41002894810) | `df84af4` | ❌ error | — | ⚠️ stale: QSM.rs main changed `src/utils/bias_correction.rs` since the checked df84af4 (7 commits); the last check ended without a result |
|  |  | sim | [2026-10-30](https://github.com/QSMxT/QSM-CI/actions/runs/41002894810) | `df84af4` | ✅ pass | 16.71% | ⚠️ stale: QSM.rs main changed `src/utils/bias_correction.rs` since the checked df84af4 (7 commits) |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (QSMxT/QSM-CI#311) |
|  |  | sim | never | — | — | — | 🚧 gap (QSMxT/QSM-CI#311) |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (QSMxT/QSM-CI#311) |
|  |  | sim | never | — | — | — | 🚧 gap (QSMxT/QSM-CI#311) |
| `star` | `star-sti` → `star-qsmrs` | sim | [2026-10-30](https://github.com/QSMxT/QSM-CI/actions/runs/41002894810) | `df84af4` | ✅ pass | 0.3256% | ✅ current |
| `medi` | `medi-cornell` → `medi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-30](https://github.com/QSMxT/QSM-CI/actions/runs/41002894810) | `df84af4` | ❌ fail | 0.02745% | ⚠️ stale: QSM.rs main changed `src/utils/bias_correction.rs`, `src/utils/multi_echo.rs` since the checked df84af4 (7 commits); the last check failed: chimap max_abs 0.001274 ppm (limit <= 0.000214 ppm) |
|  |  | sim | [2026-10-30](https://github.com/QSMxT/QSM-CI/actions/runs/41002894810) | `df84af4` | ✅ pass | 0.02896% | ⚠️ stale: QSM.rs main changed `src/utils/bias_correction.rs`, `src/utils/multi_echo.rs` since the checked df84af4 (7 commits) |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | [2026-10-30](https://github.com/QSMxT/QSM-CI/actions/runs/41002894810) | `df84af4` | ✅ pass | 0.4767% | ⚠️ stale: QSM.rs main changed `src/inversion/amp_pe.rs`, `src/utils/wavelet.rs` since the checked df84af4 (7 commits) |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | [2026-10-30](https://github.com/QSMxT/QSM-CI/actions/runs/41002894810) | `df84af4` | ✅ pass | 4.89% | ✅ current |
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
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-30](https://github.com/QSMxT/QSM-CI/actions/runs/41002894810) | `df84af4` | ✅ pass | 6.398e-10% | ⚠️ stale: QSM.rs main changed `src/utils/bias_correction.rs`, `src/utils/multi_echo.rs` since the checked df84af4 (7 commits) |
|  |  | sim | [2026-10-30](https://github.com/QSMxT/QSM-CI/actions/runs/41002894810) | `df84af4` | ✅ pass | 4.767e-14% | ⚠️ stale: QSM.rs main changed `src/utils/bias_correction.rs`, `src/utils/multi_echo.rs` since the checked df84af4 (7 commits) |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#325) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#325) |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#324) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#324) |

No original code to check against (QSMxT/QSM-CI#302; tested against ground truth in QSM.rs instead):

| Method | Covers | Note |
|---|---|---|
| `cosmos` | COSMOS (`cosmos`, `cosmos_weighted`) |  |
| `harperella` | HARPERELLA (`harperella`) |  |
| `prelude` | PRELUDE (`unwrap_prelude`) | clean-room by design |
| `slicewise-unwrap` | slice-wise (2D) unwrapping (`unwrap_slicewise`, `unwrap_slicewise_multi_echo`) |  |
| `robust-fit` | robust echo combination (`multi_echo_robust_fit`) |  |
| `motion-correction` | motion correction (`motion`) |  |
| `morphology` | erosion / dilation, closing (`erode_mask`, `dilate_mask`, `morphological_close`) |  |

Refresh every stale pair against QSM.rs `main`:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=qsmart,medi,amp-pe,laplacian -f dataset=configured -f qsmrs_ref=main
```
