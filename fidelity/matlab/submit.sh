#!/usr/bin/env bash
# Submit a MATLAB container fidelity check (or the real-toolbox compile) as Slurm jobs. The login
# node only runs sbatch; all MATLAB, mcc, mex and Apptainer work happens in job.sh on compute nodes.
# See README.md.
#
#   bash fidelity/matlab/submit.sh <slug> [build|trace|setup|runs|compare|all]
#
# Environment:
#   FID_ROOT    work root; each algorithm gets $FID_ROOT/<slug>/ (SIFs are shared in $FID_ROOT/img)
#   FID_CASES   "name=/path/to/inputs ..." contract inputs per case (runs, compare, trace)
#   the source folders the algorithm's fidelity/config.sh lists in FID_SOURCES (build, setup)
#   SBATCH_ACCOUNT, SBATCH_PARTITION (and SBATCH_QOS if the default QOS queues)
# Optional:
#   FID_IMAGE   docker ref by digest (default: image: in the algorithm's algorithm.yml)
#   FID_RUNS    subset of: container real real2 (default: all three)
#   FID_TAG     check another copy of the algorithm folder (FID_ALGO_SRC) and/or other sources, as
#               $FID_ROOT/<slug>/<tag>; its licensed runs are named real-<tag> (setup, runs only)
#   FID_ALGO_SRC  the algorithm folder to copy (default: algorithms/<slug> in this checkout)
#
# `all` = setup, then the runs, then compare. `build` compiles recon against the real toolboxes
# and leaves it at $FID_ROOT/<slug>/build/out/recon for the image build.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
slug=${1:?usage: submit.sh <slug> [build|trace|setup|runs|compare|all]}; what=${2:-all}
ALGO="$REPO/algorithms/$slug"
[ -f "$ALGO/fidelity/config.sh" ] || { echo "no $ALGO/fidelity/config.sh"; exit 2; }
: "${FID_ROOT:?}"
export FID_SLUG=$slug FID_HARNESS="$FID_ROOT/harness" FID_W="$FID_ROOT/$slug"
export FID_TAG=${FID_TAG:-algo}
export FID_IMAGE=${FID_IMAGE:-$(sed -n 's/^image: *\([^ ]*\).*/\1/p' "$ALGO/algorithm.yml")}
mkdir -p "$FID_W/logs" "$FID_HARNESS"
# Snapshot this checkout's harness and algorithm folder, so a run checks exactly this checkout.
rsync -a --delete "$HERE/" "$FID_HARNESS/"
rsync -a --delete --exclude recon --exclude '*.ctf' "${FID_ALGO_SRC:-$ALGO}/" "$FID_W/$FID_TAG/"
# shellcheck source=/dev/null
source "$FID_W/$FID_TAG/fidelity/config.sh"
sub() {  # sub NAME DEPENDENCY [sbatch args...] -> job id
    local name=$1 dep=$2; shift 2
    sbatch --parsable --export=ALL --job-name="fid-$slug-$name" --output="$FID_W/logs/$name-%j.out" \
        ${dep:+--dependency=afterok:$dep} ${FID_SBATCH:-} "$@" "$FID_HARNESS/job.sh"
}
need_sources() { for v in $FID_SOURCES; do : "${!v:?$v is not set (see $slug/fidelity/config.sh)}"; done; }
case $what in
build)
    need_sources
    echo "build $(STEP=build sub build "")" ;;
trace)
    need_sources; : "${FID_CASES:?}"; c=${FID_CASES%% *}
    echo "trace $(STEP=trace FID_CASE=${c%%=*} FID_INPUT=${c#*=} sub trace "")" ;;
setup|runs|compare|all)
    setup=""
    if [[ $what == setup || $what == all ]]; then
        need_sources
        setup=$(STEP=setup sub "setup-$FID_TAG" "" --cpus-per-task=2 --mem=8G --time=01:00:00)
        echo "setup $setup"
    fi
    [[ $what == setup ]] && exit 0
    : "${FID_CASES:?}"
    for c in $FID_CASES; do
        name=${c%%=*}; export FID_CASE=$name FID_INPUT=${c#*=}
        ids=()
        if [[ $what != compare ]]; then
            for m in ${FID_RUNS:-container real real2}; do
                if [[ $m == container ]]; then
                    ids+=("$(STEP=container sub "$name-container" "$setup")")
                else
                    ids+=("$(STEP=recon FID_MODE=$m sub "$name-$m-$FID_TAG" "$setup")")
                fi
            done
        fi
        dep=$(IFS=:; echo "${ids[*]:-}")
        cmp=$(STEP=compare sub "$name-compare" "$dep" --cpus-per-task=2 --mem=32G --time=00:30:00)
        echo "$name: runs ${ids[*]:-} compare $cmp"
    done ;;
*) echo "unknown step $what"; exit 2 ;;
esac
