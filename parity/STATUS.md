# Port parity status

Generated 2026-11-01 by `scripts/parity.py status` from `parity/results.json` and `parity/thresholds.yml`; do not edit by hand. How checks run, the two tracks, and what makes a check stale: [docs/parity.md](../docs/parity.md).

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
| `star` | `star-sti` → `star-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ⚪ not in v10.0.0 | — | ✅ current |
| `medi` | `medi-cornell` → `medi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 81.63% | ✅ current |
|  |  | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ fail | 80.37% | ✅ current |
| `fit-ppm-complex` | `fit-ppm-complex-cornell` → `fit-ppm-complex-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled (intermediates only (ifreq_raw, n_std, r2star); unmeasured until QSMxT/QSMxT#462) |
|  |  | sim | never | — | — | — | — not enabled (intermediates only (ifreq_raw, n_std, r2star); unmeasured until QSMxT/QSMxT#462) |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ✅ pass | 0.4767% | ✅ current |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ error | — | ⚠️ stale: the run against v10.0.0 ended without a result |
| `chisep-ilsqr` | `chisep-ilsqr` → `chisep-ilsqr-qsmrs` | chisep-mc | [2026-11-01](https://github.com/QSMxT/QSM-CI/actions/runs/41283680804) | v0.39.0 `42ab620` | ❌ error | — | ⚠️ stale: the run against v10.0.0 ended without a result |
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
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (QSMxT/QSMxT#465) |
|  |  | sim | never | — | — | — | 🚧 gap (QSMxT/QSMxT#465) |

Run the flagged pairs against v10.0.0:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=decompose,chisep-ilsqr -f dataset=configured -f qsmxt_release=v10.0.0
```

## Development: QSMxT main × QSM.rs main

Tested: QSMxT main `9cfe3f9` with qsm-core at QSM.rs main `15c938f`.

A check is **stale** when the reference image changed, QSM.rs `main` changed the port's source files or `Cargo.lock`, QSMxT `main` changed the step's wiring or `Cargo.lock`, the pair's limits changed, or it failed. There is no age limit. A **gap** is a pair whose port does not match its original yet: it is not enabled, and has no limits that would pass it.

| Pair | Original → port | Dataset | Last check | QSM.rs | Result | NRMSE | Status |
|---|---|---|---|---|---|---|---|
| `qsmart` | `qsmart-matlab` → `qsmart-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.7794% | ⚠️ stale: reference image changed: checked sha256:e0e8bc6957c5, algorithm.yml pins sha256:01f36e868bca; QSM.rs main changed `src/pipeline/config.rs`, `src/pipeline/qsmart.rs`, `src/pipeline/rules.rs`, `src/utils/n4.rs` … since the checked 15c938f (13 commits); the pair's settings or limits for this dataset changed since; QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/bridge.rs`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` … since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 16.32% | ⚠️ stale: reference image changed: checked sha256:e0e8bc6957c5, algorithm.yml pins sha256:01f36e868bca; QSM.rs main changed `src/pipeline/config.rs`, `src/pipeline/qsmart.rs`, `src/pipeline/rules.rs`, `src/utils/n4.rs` … since the checked 15c938f (13 commits); the pair's settings or limits for this dataset changed since; QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/bridge.rs`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` … since the checked 9cfe3f9 (7 commits) |
| `ilsqr` | `ilsqr-sti` → `ilsqr-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `vsharp` | `vsharp-sti` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.0002207% | ⚠️ stale: QSM.rs main changed `src/bgremove/vsharp.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs`, `src/commands/bgremove.rs` since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.0009001% | ⚠️ stale: QSM.rs main changed `src/bgremove/vsharp.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs`, `src/commands/bgremove.rs` since the checked 9cfe3f9 (7 commits) |
| `star` | `star-sti` → `star-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.002147% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.002332% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
| `medi` | `medi-cornell` → `medi-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.02745% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.02896% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
| `fit-ppm-complex` | `fit-ppm-complex-cornell` → `fit-ppm-complex-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | — not enabled (intermediates only (ifreq_raw, n_std, r2star); unmeasured until QSMxT/QSMxT#462) |
|  |  | sim | never | — | — | — | — not enabled (intermediates only (ifreq_raw, n_std, r2star); unmeasured until QSMxT/QSMxT#462) |
| `amp-pe` | `amp-pe` → `amp-pe-qsmrs` | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0.4767% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
| `decompose` | `decompose-qsm` → `decompose-qsmrs` | chisep-mc | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ❌ fail | 143.2% | ⚠️ stale: QSM.rs main changed `src/pipeline/rules.rs` since the checked 15c938f (13 commits); the pair's settings or limits for this dataset changed since; the last check failed: chi-para correlation 0.4743 (limit >= 0.988); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/bridge.rs`, `src/cli.rs`, `src/commands/separate.rs` since the checked 9cfe3f9 (7 commits) |
| `chisep-ilsqr` | `chisep-ilsqr` → `chisep-ilsqr-qsmrs` | chisep-mc | never | — | — | — | ⚠️ stale: never checked |
| `chisep-medi` | `chisep-medi` → `chisep-medi-qsmrs` | chisep-mc | never | — | — | — | ⚠️ stale: never checked |
| `wavesep` | `wavesep` → `wavesep-qsmrs` | chisep-mc | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0% | ⚠️ stale: QSM.rs main changed `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/bridge.rs`, `src/cli.rs`, `src/commands/separate.rs` since the checked 9cfe3f9 (7 commits) |
| `tkd` | `tkd-qsmjl` → `tkd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 6.85e-06% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
| `tsvd` | `tsvd-qsmjl` → `tsvd-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 8.149e-06% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
| `tikhonov` | `tikhonov-qsmjl` → `tikhonov-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 1.345e-05% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 0% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
| `tv` | `tv-qsmjl` → `tv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 1.243e-05% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 2.024e-16% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
| `nltv` | `nltv-qsmjl` → `nltv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 9.626e-06% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 2.749e-10% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
| `rts` | `rts-qsmjl` → `rts-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 5.777e-06% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 3.932e-10% | ⚠️ stale: QSM.rs main changed `src/pipeline/inversion.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/invert.rs` since the checked 9cfe3f9 (7 commits) |
| `ismv` | `ismv-qsmjl` → `ismv-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 2.064e-09% | ⚠️ stale: QSM.rs main changed `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/bgremove.rs` since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 6.026e-09% | ⚠️ stale: QSM.rs main changed `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/bgremove.rs` since the checked 9cfe3f9 (7 commits) |
| `sharp` | `sharp-sepia` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 1.394e-08% | ⚠️ stale: QSM.rs main changed `src/bgremove/vsharp.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/bgremove.rs` since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 1.058e-08% | ⚠️ stale: QSM.rs main changed `src/bgremove/vsharp.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `src/cli.rs`, `src/commands/bgremove.rs` since the checked 9cfe3f9 (7 commits) |
| `sharp-qsmjl` | `sharp-qsmjl` → `sharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `vsharp-qsmjl` | `vsharp-qsmjl` → `vsharp-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | ⚠️ stale: never checked |
|  |  | sim | never | — | — | — | ⚠️ stale: never checked |
| `laplacian` | `laplacian-qsmjl` → `laplacian-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 6.398e-10% | ⚠️ stale: QSM.rs main changed `src/pipeline/field_mapping.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/bridge.rs`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` … since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 4.767e-14% | ⚠️ stale: QSM.rs main changed `src/pipeline/field_mapping.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/bridge.rs`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` … since the checked 9cfe3f9 (7 commits) |
| `romeo` | `romeo-romeojl` → `romeo-qsmrs` | s002001-kki-achieva-bridge-run1 | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 1.498% | ⚠️ stale: QSM.rs main changed `src/pipeline/field_mapping.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/bridge.rs`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` … since the checked 9cfe3f9 (7 commits) |
|  |  | sim | [2026-10-31](https://github.com/QSMxT/QSM-CI/actions/runs/41189442934) | `15c938f` | ✅ pass | 1.639% | ⚠️ stale: QSM.rs main changed `src/pipeline/field_mapping.rs`, `src/pipeline/rules.rs` since the checked 15c938f (13 commits); QSMxT main changed `Cargo.lock`, `crates/qsmxt-engine/src/bridge.rs`, `crates/qsmxt-engine/src/config.rs`, `src/cli.rs` … since the checked 9cfe3f9 (7 commits) |
| `tgv` | `tgv-tgvjl` → `tgv-qsmrs` | s002001-kki-achieva-bridge-run1 | never | — | — | — | 🚧 gap (QSMxT/QSMxT#465) |
|  |  | sim | never | — | — | — | 🚧 gap (QSMxT/QSMxT#465) |

Refresh every stale pair against QSM.rs `main`:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=qsmart,ilsqr,vsharp,star,medi,amp-pe,decompose,chisep-ilsqr,chisep-medi,wavesep,tkd,tsvd,tikhonov,tv,nltv,rts,ismv,sharp,sharp-qsmjl,vsharp-qsmjl,laplacian,romeo -f dataset=configured -f qsmrs_ref=main
```

## No original

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

## Release history

| Pair | v10.0.0 |
|---|---|
| `amp-pe` | 0.48 % · v10.0.0 |
| `chisep-ilsqr` | failing · v10.0.0 |
| `chisep-medi` | not in v10.0.0 |
| `decompose` | failing · v10.0.0 |
| `ilsqr` | failing · v10.0.0 |
| `ismv` | failing · v10.0.0 · no variant |
| `laplacian` | < 0.001 % · v10.0.0 |
| `medi` | failing · v10.0.0 |
| `nltv` | failing · v10.0.0 |
| `qsmart` | failing · v10.0.0 · no reliability, no offset_grid |
| `romeo` | failing · v10.0.0 |
| `rts` | failing · v10.0.0 |
| `sharp` | failing · v10.0.0 |
| `sharp-qsmjl` | failing · v10.0.0 · no variant |
| `star` | not in v10.0.0 |
| `tikhonov` | failing · v10.0.0 |
| `tkd` | failing · v10.0.0 |
| `tsvd` | failing · v10.0.0 |
| `tv` | failing · v10.0.0 |
| `vsharp` | failing · v10.0.0 |
| `vsharp-qsmjl` | failing · v10.0.0 · no ball, no radius_step |
| `wavesep` | failing · v10.0.0 |
