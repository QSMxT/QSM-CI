#!/usr/bin/env bash
# Submit the qsmart-matlab fidelity check as Slurm jobs (login node: sbatch only; all MATLAB,
# Apptainer and mex work happens in job.sh on compute nodes). See README.md.
#
#   FID_WORK=/path/to/work FID_QSMART=... FID_SUN=... FID_STI=... \
#   FID_CASES="sim=/path/sim/inputs invivo=/path/acq/inputs" \
#   SBATCH_ACCOUNT=... SBATCH_PARTITION=... bash submit.sh [setup|runs|compare|all]
#
# FID_RUNS limits `runs` to some of: container real real2 (default: all).
# FID_ALGO_SRC checks another copy of the algorithm folder (e.g. a proposed change) into
# $FID_WORK/<FID_TAG>; FID_TAG (default algo) also names its runs/ and reports/ entries.
#
# Copies this algorithm folder to $FID_WORK/algo first, so a run checks exactly this checkout.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ALGO="$(dirname "$HERE")"
: "${FID_WORK:?}" "${FID_CASES:?}"
what=${1:-all}
export FID_IMAGE=${FID_IMAGE:-$(sed -n 's/^image: *\([^ ]*\).*/\1/p' "$ALGO/algorithm.yml")}
mkdir -p "$FID_WORK/logs"
export FID_TAG=${FID_TAG:-algo}
rsync -a --delete --exclude recon --exclude '*.ctf' "${FID_ALGO_SRC:-$ALGO}/" "$FID_WORK/$FID_TAG/"
sub() {  # sub NAME DEPENDENCY [sbatch args...] -> job id
    local name=$1 dep=$2; shift 2
    sbatch --parsable --export=ALL --job-name="qf-$name" --output="$FID_WORK/logs/$name-%j.out" \
        ${dep:+--dependency=afterok:$dep} "$@" "$HERE/job.sh"
}
setup=""
if [[ $what == setup || $what == all ]]; then
    : "${FID_QSMART:?}" "${FID_SUN:?}" "${FID_STI:?}"
    setup=$(STEP=setup sub setup "")
    echo "setup $setup"
fi
if [[ $what == runs || $what == all || $what == compare ]]; then
    for c in $FID_CASES; do
        name=${c%%=*}; export FID_CASE=$name FID_INPUT=${c#*=}
        ids=()
        if [[ $what != compare ]]; then
            [[ " ${FID_RUNS:-container} " == *" container "* ]] && ids+=("$(STEP=container sub "$name-container" "$setup")")
            for m in ${FID_RUNS:-real real2}; do
                [[ $m == container ]] && continue
                ids+=("$(STEP=recon FID_MODE=$m sub "$name-$m" "$setup")")
            done
        fi
        dep=$(IFS=:; echo "${ids[*]:-}")
        cmp=$(STEP=compare sub "$name-compare" "$dep" --cpus-per-task=2 --mem=16G --time=00:30:00)
        echo "$name: runs ${ids[*]:-} compare $cmp"
    done
fi
