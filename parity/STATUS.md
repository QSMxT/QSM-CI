# Port parity status

Generated 2026-10-31 by `scripts/parity.py status` from `parity/results.json` and `parity/thresholds.yml`; do not edit by hand. How checks run, and what makes one stale: [docs/parity.md](../docs/parity.md).

A check is **stale** when the reference image changed, QSM.rs `main` changed the port's source files or `Cargo.lock`, QSMxT `main` changed the step's wiring or `Cargo.lock`, the pair's limits changed, or it failed. There is no age limit. A **gap** is a pair whose port does not match its original yet: it is not enabled, and has no limits that would pass it.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.7794% | ⚠️ stale: QSM.rs main changed `src/pipeline/config.rs` since the checked 15c938f (2 commits); QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 16.32% | ⚠️ stale: QSM.rs main changed `src/pipeline/config.rs` since the checked 15c938f (2 commits); QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (astewartau/QSM.rs#329) |
|  |  | sim | never | — | — | — | 🚧 gap (astewartau/QSM.rs#329) |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.0002207% | ⚠️ stale: QSM.rs main changed `src/bgremove/vsharp.rs` since the checked 15c938f (2 commits); QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.0009001% | ⚠️ stale: QSM.rs main changed `src/bgremove/vsharp.rs` since the checked 15c938f (2 commits); QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `star` | `star-sti` → `star-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.002147% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.002332% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `medi` | `medi-cornell` → `medi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.02745% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.02896% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `fit-ppm-complex` | `fit-ppm-complex-cornell` → `fit-ppm-complex-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled (intermediates only (ifreq_raw, n_std, r2star); unmeasured until QSMxT/QSMxT#462) |
|  |  | sim | never | — | — | — | — not enabled (intermediates only (ifreq_raw, n_std, r2star); unmeasured until QSMxT/QSMxT#462) |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.4767% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ❌ fail | 143.2% | ⚠️ stale: the last check failed: chi-para correlation 0.4743 (limit >= 0.988); QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `wavesep` | `wavesep` → `wavesep-qsmrs` | chisep-mc | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 6.85e-06% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 8.149e-06% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 1.345e-05% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 1.243e-05% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 2.024e-16% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 9.626e-06% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 2.749e-10% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 5.777e-06% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 3.932e-10% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 2.064e-09% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 6.026e-09% | ⚠️ stale: QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `sharp` | `sharp-sepia` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 1.394e-08% | ⚠️ stale: QSM.rs main changed `src/bgremove/vsharp.rs` since the checked 15c938f (2 commits); QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 1.058e-08% | ⚠️ stale: QSM.rs main changed `src/bgremove/vsharp.rs` since the checked 15c938f (2 commits); QSMxT main changed `Cargo.lock` since the checked 9cfe3f9 (1 commits) |
| `sharp-qsmjl` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (QSMxT/QSMxT#460) |
|  |  | sim | never | — | — | — | 🚧 gap (QSMxT/QSMxT#460) |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (QSMxT/QSMxT#460) |
|  |  | sim | never | — | — | — | 🚧 gap (QSMxT/QSMxT#460) |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 6.398e-10% | ⚠️ stale: QSM.rs main changed `src/pipeline/field_mapping.rs` since the checked 15c938f (2 commits); QSMxT main changed `Cargo.lock`, `src/commands/fieldmap.rs` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 4.767e-14% | ⚠️ stale: QSM.rs main changed `src/pipeline/field_mapping.rs` since the checked 15c938f (2 commits); QSMxT main changed `Cargo.lock`, `src/commands/fieldmap.rs` since the checked 9cfe3f9 (1 commits) |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 1.498% | ⚠️ stale: QSM.rs main changed `src/pipeline/field_mapping.rs` since the checked 15c938f (2 commits); QSMxT main changed `Cargo.lock`, `src/commands/fieldmap.rs` since the checked 9cfe3f9 (1 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 1.639% | ⚠️ stale: QSM.rs main changed `src/pipeline/field_mapping.rs` since the checked 15c938f (2 commits); QSMxT main changed `Cargo.lock`, `src/commands/fieldmap.rs` since the checked 9cfe3f9 (1 commits) |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (QSMxT/QSMxT#465) |
|  |  | sim | never | — | — | — | 🚧 gap (QSMxT/QSMxT#465) |

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
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=qsmart,vsharp,star,medi,amp-pe,decompose,wavesep,tkd,tsvd,tikhonov,tv,nltv,rts,ismv,sharp,laplacian,romeo -f dataset=configured -f qsmrs_ref=main
```
