# QSM-CI

**A challenge platform for Quantitative Susceptibility Mapping (QSM) reconstruction.**

Submit a QSM algorithm — in *any* language — as a container. QSM-CI runs it automatically on
standardized data, scores it the same way the [QSM.rs](https://github.com/astewartau/QSM.rs) CI
does, and publishes the results to an interactive, sortable leaderboard.

QSM is a pipeline — **field-mapping → background field removal (BFR) → dipole inversion** — so
QSM-CI is *stage-aware*: you can submit a single stage, or a span for methods that cross boundaries.
Each stage is scored on its own **and** in combination with others, so you can see both "which
inversion is best" and "which BFR+inversion *pairing* wins."

## How it works

1. **You submit** a folder under `algorithms/<your-slug>/` via a pull request: your code (`run.sh` +
   scripts), a `stage:` declaration, and an *environment* — a base image (`image:`) or a small
   `Dockerfile`. Your code is **mounted**, not baked, and toolboxes are downloaded when the
   environment is built. (See [docs/submitting.md](docs/submitting.md).)
2. **QSM-CI runs it** on the challenge data inside your container (`/input` → `/output`), with no
   network and no access to the answer.
3. **QSM-CI scores it** against held-out ground truth with `qsm-eval` (the QSM.rs metrics), both
   **isolated** (fed the true input boundary) and **composed** (chained with other stages).
4. **Results appear** on the leaderboard — per-stage tables and a BFR × inversion combination matrix.

## The contract

Your container implements one stage and reads/writes canonical artifacts (all fields & χ in **ppm**):

| `stage:` | Consumes (`/input`) | Produces (`/output`) |
|---|---|---|
| `field-mapping` | phase, magnitude, mask, params | `totalfield` |
| `bfr` | totalfield, mask, params | `localfield` |
| `dipole` | localfield, mask, params | `chimap` |
| spans: `unwrap+bfr`, `bfr+dipole`, `end-to-end` | … | … |

Full details in **[CONTRACT.md](CONTRACT.md)** and the machine-readable **[stages.yml](stages.yml)**.
MATLAB is welcome via the license-free MATLAB Runtime — see **[docs/matlab.md](docs/matlab.md)**.

## Repository layout

| Path | What it is |
|------|-----------|
| `CONTRACT.md`, `stages.yml` | The frozen contract; the artifact & stage registry |
| `algorithms/<slug>/` | One submission each (metadata + image + `run.sh` + `stage:`) |
| `eval/` | `qsm-eval` — the Python scorer (metrics ported from QSM.rs) |
| `scripts/pipeline.py` | Isolated + composed evaluation runner (local or containerized) |
| `scripts/pack_dataset.py` | qsm-forward BIDS → QSM-CI artifact layout |
| `data/sim/`, `data/invivo/` | Datasets; ground truth held out on OSF |
| `results/index.json` | Per-run scores + OSF volume URLs; feeds the leaderboard (the only committed result) |
| `web/` | Static leaderboard + NiiVue viewer (GitHub Pages) |
| `.github/workflows/` | `ci` (CLI/runner smoke tests), `evaluate` (per-PR), `score` (change-triggered scoring + OSF), `pages` (deploy), `matlab-compile` |

**Results storage.** NIfTI volumes are **never** committed — they're uploaded to a public OSF
component (`scripts/publish_volumes.py`, secret `OSF_VOLUMES_NODE`) and the viewer loads them by URL.
Only the small `results/index.json` lives in git. The `score` workflow runs on change (a changed
algorithm → its combos; changed scorer/orchestration → everything), never on a weekly timer.

## Local development

```bash
# 1. generate a dev phantom (see data/sim/README.md for the qsm-forward command), then:
python scripts/pack_dataset.py /tmp/BIDS data/sim/dev

# 2. run the full isolated + composed evaluation over all reference submissions
pip install -r eval/requirements.txt
python scripts/pipeline.py --dataset data/sim/dev --mode both

# 3. preview the website (reads results/index.json)
python -m http.server -d web 8000   # → http://localhost:8000
```

## Status

Working end-to-end on a realistic **head phantom** (`data/sim/scoring/`, 7T, 164×205×205): the stage
model, scorer (full region metrics), composition matrix, containerized runner (`--network none`),
and website. Reference submissions include Python (`tkd`, `tikhonov`, `sharp`), the full QSMxT/QSM.rs
engine set (all BFR + dipole methods, HARPERELLA, TGV, QSMART), and a **MATLAB** template compiled to
the free MATLAB Runtime (`matlab-tkd`).

Before opening the challenge: fix the canonical head-phantom `qsm-forward` invocation and upload its
held-out ground truth to OSF; wire the ARC runner + `OSF_TOKEN` secrets; cross-check `qsm-eval`
against QSM.rs on that phantom; add a `field-mapping` reference so the matrix starts from raw phase.
