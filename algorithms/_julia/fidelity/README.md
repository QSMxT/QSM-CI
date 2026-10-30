# Julia-original fidelity check

The Julia submissions run the authors' own packages, so there is no port to check against an
original here: the container *is* the original, in its own pinned environment. Fidelity
(QSMxT/QSM-CI#299) therefore means three things, and [`harness.py`](harness.py) checks the last two
by running each submission exactly as QSM-CI does (`qsm-ci run`):

1. **Pinned versions.** Julia 1.10.11 (official image, by digest) and the committed
   [`../env/Manifest.toml`](../env/Manifest.toml), with the five authors' packages at the git
   revisions QSM.rs cites. The image is pinned by digest in each `algorithm.yml`.
2. **Deterministic output.** The image run twice on the same inputs gives bit-identical output,
   at the fixed thread count `run.sh` sets (4 Julia threads, FFTW 4, BLAS 1).
3. **Same outside the container.** `run.sh` run on the host (`--runner local`) with a host Julia
   1.10.11 and the same Manifest, without the image's sysimage, gives the same output.

The latest results are in [`REPORT.md`](REPORT.md). When a check passes, the image digest is
recorded in each submission's `algorithm.yml` under `fidelity:`.

## Running it

From the repository root, with `pip install .` (the `qsm-ci` CLI), `nibabel` and `pyyaml`:

```bash
# A case is a directory holding the artifacts the stages read: phase, magnitude, mask,
# params.json, and the totalfield / localfield the bfr and dipole stages take.
python algorithms/_julia/fidelity/harness.py determinism --runner podman \
    --case invivo=path/to/case --case sim=path/to/sim-case

# Also run outside the container: a host Julia 1.10.11 and the Manifest instantiated in a depot.
mkdir -p ~/.local/share/qsmci-julia/env
cp algorithms/_julia/env/*.toml ~/.local/share/qsmci-julia/env/
JULIA_DEPOT_PATH=~/.local/share/qsmci-julia/depot JULIA_PROJECT=~/.local/share/qsmci-julia/env \
    /path/to/julia-1.10.11/bin/julia -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
python algorithms/_julia/fidelity/harness.py determinism --runner podman --case invivo=path/to/case \
    --local /path/to/julia-1.10.11/bin --local-project ~/.local/share/qsmci-julia/env \
    --local-depot ~/.local/share/qsmci-julia/depot

# First look against the QSM.rs ports, at the original's defaults and at the QSM.rs-matched
# settings (each submission's README table).
python algorithms/_julia/fidelity/harness.py pair --runner podman --case invivo=path/to/case
```

Results go to `fidelity-out/` (`determinism.json/.md`, `pair.json/.md`). The `julia-originals`
workflow runs `determinism` and `pair` on the in-silico phantom for every Julia submission on a
pull request that touches them, one hosted job per method, and puts the tables in the job summary.

## Pass rule

Every output of every submission is bit-identical across the two image runs and between the image
and the host Julia, on every case. Floating-point output can depend on the CPU (FFTW and the SIMD
packages pick kernels by CPU features, and code compiled at run time is native), so the record
names the host the check ran on; the Actions job reruns the image-twice check on hosted runners.
