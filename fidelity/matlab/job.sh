#!/bin/bash -l
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
# One step of a MATLAB container fidelity check, as a Slurm job (submit.sh submits them).
# Every run job uses the same CPU count (8 by default), because the thread count changes rounding.
# Environment (passed with --export=ALL by submit.sh):
#   STEP          build | trace | setup | recon | container | compare
#   FID_SLUG      algorithm slug; FID_W its work dir; FID_HARNESS this folder's snapshot
#   FID_TAG       algorithm copy in $FID_W/<tag> (default algo); other tags use deps-<tag> and
#                 name their licensed runs real-<tag>
#   FID_IMAGE     docker ref, pinned by digest
#   FID_CASE, FID_INPUT   case name and its contract inputs (recon, container, compare, trace)
#   FID_MODE      recon run name: real | real2 (real2 repeats real: the run-to-run floor)
# The algorithm's fidelity/config.sh supplies FID_SIF, FID_SOURCES, FID_MATLAB_PATH, FID_MCC,
# FID_WHICH, fid_assemble and the optional FID_ENV, fid_build_hook and fid_setup_hook.
set -eo pipefail   # not -u: `module load` reads unset variables
W=$FID_W; H=$FID_HARNESS
TAG=${FID_TAG:-algo}; A="$W/$TAG"; SFX=""; [ "$TAG" = algo ] || SFX="-$TAG"
DEPS="$W/deps$SFX"
# shellcheck source=/dev/null
source "$A/fidelity/config.sh"
# Lists may span lines in config.sh; MATLAB gets them on one.
FID_WHICH=$(echo $FID_WHICH); FID_MATLAB_PATH=$(echo $FID_MATLAB_PATH)
ROOT=$(dirname "$W")
export APPTAINER_CACHEDIR="$ROOT/apptainer-cache" APPTAINER_TMPDIR="$ROOT/apptainer-tmp/${SLURM_JOB_ID:-$$}"
mkdir -p "$APPTAINER_CACHEDIR" "$APPTAINER_TMPDIR" "$W/reports" "$ROOT/img"
# One .sif per image digest, so a new image is never confused with an old pull.
dig=$(sed -n 's/.*sha256:\([0-9a-f]\{12\}\).*/\1/p' <<< "$FID_IMAGE")
SIF="$ROOT/img/$FID_SIF-$dig.sif"
mat() { module load matlab/R2023b; matlab -nodisplay -batch "addpath('$H'); $1"; }
# FID_ENV ("K=V K2=V2") applies to every run, licensed and container alike.
envargs=(); for kv in ${FID_ENV:-}; do export "${kv?}"; envargs+=(--env "$kv"); done
echo "STEP=$STEP slug=$FID_SLUG tag=$TAG host=$(hostname) cpus=${SLURM_CPUS_PER_TASK:-?} $(date -Is)"

case "$STEP" in
build)
    # Compile recon.m against the real toolboxes (BUILD.md): no shims, deps as fid_assemble lays
    # them out, the toolbox functions that pcode calls named in recon.m's %#function pragma.
    B="$W/build"; rm -rf "$B"; mkdir -p "$B"
    rsync -a --exclude '*/' --exclude recon "$A/" "$B/"          # recon.m and top-level helpers
    [ ! -e "$B/shims" ] || { echo "shims/ present"; exit 2; }
    fid_assemble "$B/deps" "$A"
    rm -rf "$B/deps/originals"
    cd "$B"
    if declare -F fid_build_hook >/dev/null; then fid_build_hook "$B/deps"; fi
    # FID_MCC_A: folders under deps/ to force-bundle (pcode, mex), or @<path under matlabroot>.
    mcc_a=""; for d in $FID_MCC_A; do
        if [[ $d == @* ]]; then mcc_a+="'-a',fullfile(matlabroot,'${d#@}'),"; else mcc_a+="'-a','deps/$d',"; fi
    done
    mat "fidelity_build('$B', '$FID_MATLAB_PATH', '$FID_WHICH', {${mcc_a%,}})" 2>&1 | tee "$B/mcc.log"
    { echo "# build $(date -Is) on $(hostname)"; grep -E "^(VERSION|WHICH|PRODUCT|TOOLBOXFILE)" "$B/mcc.log"
      echo "## requiredMCRProducts.txt"; cat out/requiredMCRProducts.txt; echo
      echo "## unresolvedSymbols.txt"; cat out/unresolvedSymbols.txt 2>/dev/null; echo
      echo "## mccExcludedFiles.log"; cat out/mccExcludedFiles.log 2>/dev/null; echo
      echo "## warnings"; grep -iE "warning|not deployable|cannot" "$B/mcc.log" | grep -v "Requirements cannot analyze" | sort | uniq -c || true
      echo "## recon"; sha256sum out/recon; } > "$W/reports/build.txt"
    cat "$W/reports/build.txt"
    # Both files hold a header line only when nothing is unresolved or excluded.
    for f in unresolvedSymbols.txt mccExcludedFiles.log; do
        n=$(grep -cvE '^(Path|Excluded Files)' "out/$f" || true)
        [ "$n" -eq 0 ] || { echo "$f lists $n entries"; exit 3; }
    done
    ;;
setup)
    [ -s "$SIF" ] || apptainer pull "$SIF" "docker://$FID_IMAGE"
    fid_assemble "$DEPS" "$A"
    if declare -F fid_setup_hook >/dev/null; then fid_setup_hook "$DEPS"; fi
    mat "fidelity_env('$W/reports/env.json')"
    ;;
trace)
    # Which toolbox functions does the code (pcode included) call? Profile one licensed run.
    out="$W/runs/trace"; rm -rf "$out"; mkdir -p "$out"
    DEPS="$W/deps-trace"; fid_assemble "$DEPS" "$A"
    if declare -F fid_build_hook >/dev/null; then fid_build_hook "$DEPS"; fi
    mat "fidelity_trace('$FID_INPUT', '$out', '$DEPS', '$A', '$FID_MATLAB_PATH', '$W/reports/trace.txt')"
    ;;
recon)
    out="$W/runs/$FID_CASE/$FID_MODE$SFX"; rm -rf "$out"; mkdir -p "$out"
    [ ! -d "$W/bin" ] || export PATH="$W/bin:$PATH"   # e.g. a wrapper for a binary the image ships (qsmart: N4)
    mat "run_recon('$FID_INPUT', '$out', '$DEPS', '$A', '$FID_MATLAB_PATH', '$FID_WHICH')"
    ;;
container)
    out="$W/runs/$FID_CASE/container"; rm -rf "$out"; mkdir -p "$out"
    # As qsm_ci/containers.py runs it under apptainer, plus recon.m's intermediates (images built
    # before the option ignore it and give the final output only).
    /usr/bin/time -v apptainer exec --no-home --cleanenv --env QSMCI_INTERMEDIATES=/output/intermediates \
        "${envargs[@]}" -B "$A:/algo:ro" -B "$FID_INPUT:/input:ro" -B "$out:/output" "$SIF" bash /algo/run.sh
    ;;
compare)
    ref=${FID_REF:-real}; rpt="$W/reports/runs-$FID_CASE.md"; [ "$ref" = real ] || rpt="$W/reports/runs-$FID_CASE-vs-$ref.md"
    mat "compare_runs('$W/runs/$FID_CASE', '$FID_INPUT/mask.nii.gz', '$rpt', '$ref')"
    ;;
*) echo "unknown STEP $STEP"; exit 2 ;;
esac
echo "done $(date -Is)"
