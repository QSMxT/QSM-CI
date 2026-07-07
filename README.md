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

1. **You submit** a folder under `algorithms/<your-slug>/` via a pull request: a container image, a
   `run.sh`, and a `stage:` declaration. (See [docs/submitting.md](docs/submitting.md).)
2. **QSM-CI runs it** on the challenge data inside your container (`/input` → `/output`), with no
   network and no access to the answer.
3. **QSM-CI scores it** against held-out ground truth with `qsm-eval` (the QSM.rs metrics), both
   **isolated** (fed the true input boundary) and **composed** (chained with other stages).
4. **Results appear** on the leaderboard — per-stage tables and a BFR × inversion combination matrix.

## The contract (v2)

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
| `results/index.json` | Per-run scores; feeds the leaderboard |
| `web/` | Static leaderboard + NiiVue viewer (GitHub Pages) |
| `.github/workflows/` | `evaluate` (per-PR isolated), `combine` (composition matrix), `pages` |

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

The stage model, scorer, composition matrix, and website are working end-to-end on a simulated
phantom. Before opening the challenge: curate the realistic head phantom (so BFR and region metrics
are meaningful — see [data/sim/README.md](data/sim/README.md)), upload held-out ground truth to OSF,
cross-check `qsm-eval` against QSM.rs on that phantom, and wire the ARC runner + `OSF_TOKEN` secrets.
