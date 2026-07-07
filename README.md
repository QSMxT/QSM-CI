# QSM-CI

**A challenge platform for Quantitative Susceptibility Mapping (QSM) reconstruction.**

Submit a QSM algorithm — in *any* language — as a container. QSM-CI runs it automatically
on standardized data, scores the output the same way the [QSM.rs](https://github.com/astewartau/QSM.rs)
CI does, and publishes the results to an interactive, sortable leaderboard.

## How it works

1. **You submit** a small folder under `algorithms/<your-slug>/` via a pull request: a container
   image reference plus a `run.sh`. That's it — no need to package your code any particular way.
2. **QSM-CI runs it** on the challenge data inside your container (`/input` → `/output`).
3. **QSM-CI scores it** against held-out ground truth using `qsm-eval` (the QSM.rs metrics).
4. **Results appear** on the leaderboard, with an interactive 3D viewer of your reconstruction.

Your algorithm never sees the ground truth, and runs with no network access — so scores are honest.

## The contract

Your container reads inputs from `/input` and writes one file to `/output`:

```
/input/     (read-only)   phase.nii.gz, magnitude.nii.gz, mask.nii.gz, params.json
/output/                  chimap.nii.gz   ← your susceptibility map, in ppm, within the mask
```

See **[CONTRACT.md](CONTRACT.md)** for the exact `params.json` schema and units. It is frozen as
`contract: v1`.

## Submitting

See **[docs/submitting.md](docs/submitting.md)** for a step-by-step guide, and
**[docs/matlab.md](docs/matlab.md)** for a MATLAB-specific template (via the Neurodesk MATLAB
Runtime image — no license needed).

The reference submission in **[`algorithms/example-tkd/`](algorithms/example-tkd/)** is a working
example you can copy.

## Tracks

- **`sim`** — simulated phantom with perfect, known ground truth. Enables the full metric suite
  (region-specific NRMSE, deep-gray-matter linearity, calcification, streaking). *Live.*
- **`invivo`** — in-vivo data scored against a reference reconstruction. *Scaffolded, coming soon.*

## Repository layout

| Path | What it is |
|------|-----------|
| `CONTRACT.md` | The frozen `/input`→`/output` contract |
| `algorithms/<slug>/` | One submission each (metadata + image ref + `run.sh`) |
| `eval/` | `qsm-eval` — the Python scorer (metrics ported from QSM.rs) |
| `data/sim/`, `data/invivo/` | Public challenge inputs (ground truth is held out on OSF) |
| `results/` | Per-run scores as JSON; `index.json` feeds the leaderboard |
| `web/` | The static leaderboard + NiiVue viewer (GitHub Pages) |
| `.github/workflows/` | `evaluate.yml` (the CI that runs + scores submissions) |

## Local development

```bash
# Score a reconstruction locally (see eval/README.md)
pip install -r eval/requirements.txt
python eval/qsm_eval.py --recon out/chimap.nii.gz --track sim \
  --truth gt/chimap.nii.gz --seg gt/dseg.nii.gz --mask data/sim/public/mask.nii.gz \
  --out metrics.json --figures figures/

# Preview the website
python -m http.server -d web 8000   # → http://localhost:8000
```
