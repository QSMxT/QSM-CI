#!/bin/bash -l
#SBATCH --job-name=qsmart-fidelity
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
# One step of the qsmart-matlab fidelity check, as a Slurm job (submit.sh submits them all).
# Environment (passed with --export=ALL):
#   STEP       setup | recon | container | compare
#   FID_WORK   work dir: deps/ img/ bin/ algo/ runs/<case>/<run>/ reports/
#   FID_CASE   case name (recon, container, compare); FID_INPUT its contract inputs folder
#   FID_MODE   recon mode: real | real2 (a second real run: the run-to-run floor)
#   FID_TAG    algorithm copy to use, $FID_WORK/<tag> (default algo); non-default tags get
#              their own runs/<case>/<mode>-<tag> and reports/*-<tag>
#   setup only: FID_QSMART FID_SUN FID_STI (sources) and FID_IMAGE (docker ref, by digest)
set -eo pipefail   # not -u: `module load` reads unset variables
W=$FID_WORK
TAG=${FID_TAG:-algo}; A="$W/$TAG"; SFX=""; [ "$TAG" = algo ] || SFX="-$TAG"
FID="$A/fidelity"
export APPTAINER_CACHEDIR="$W/apptainer-cache" APPTAINER_TMPDIR="$W/apptainer-tmp"
mkdir -p "$APPTAINER_CACHEDIR" "$APPTAINER_TMPDIR" "$W/reports"
# One .sif per image digest, so a new image is never confused with an old pull.
SIF="$W/img/matlab-qsmart-$(sed -n 's/.*sha256:\([0-9a-f]\{12\}\).*/\1/p' <<< "$FID_IMAGE").sif"
[ "$SIF" != "$W/img/matlab-qsmart-.sif" ] || { echo "FID_IMAGE must be pinned by digest"; exit 2; }
mat() { module load matlab/R2023b; matlab -nodisplay -batch "$1"; }
echo "STEP=$STEP host=$(hostname) cpus=${SLURM_CPUS_PER_TASK:-?} $(date -Is)"

case "$STEP" in
setup)
    mkdir -p "$W/img" "$W/bin"
    [ -s "$SIF" ] || apptainer pull "$SIF" "docker://$FID_IMAGE"
    bash "$FID/assemble_deps.sh" "$FID_QSMART" "$FID_SUN" "$FID_STI" "$W/deps"
    mat "cd('$W/deps/frangi'); mex eig3volume.c; fidelity_dir='$FID'; addpath(fidelity_dir); fidelity_env('$W/reports/env.json')"
    # N4 for licensed MATLAB: the image's own N4BiasFieldCorrection, so all runs share one binary.
    cat > "$W/bin/N4BiasFieldCorrection" <<EOF
#!/bin/bash
unset LD_LIBRARY_PATH
exec apptainer exec --no-home --cleanenv -B "\$PWD" --pwd "\$PWD" "$SIF" N4BiasFieldCorrection "\$@"
EOF
    chmod +x "$W/bin/N4BiasFieldCorrection"
    apptainer exec --cleanenv "$SIF" bash -c 'command -v N4BiasFieldCorrection; N4BiasFieldCorrection --version' | tee "$W/reports/n4-version.txt" || true
    { for f in calculate_curvature vasculature_mask FrangiFilter3D; do
          case $f in
              vasculature_mask) new="$W/algo/vasculature_mask_qsmci.m" ;;
              FrangiFilter3D) new="$W/deps/frangi/FrangiFilter3D.m" ;;
              *) new="$W/deps/qsmart/$f.m" ;;
          esac
          diff -u --strip-trailing-cr "$W/deps/originals/$f.m" "$new" || true
      done; } > "$W/reports/deviations.diff"
    ;;
recon)
    mode=$FID_MODE; [ "$mode" = real2 ] && mode=real
    out="$W/runs/$FID_CASE/$FID_MODE$SFX"; rm -rf "$out"; mkdir -p "$out"
    export PATH="$W/bin:$PATH"
    mat "addpath('$FID'); run_recon('$mode', '$FID_INPUT', '$out', '$W/deps', '$A')"
    ;;
container)
    out="$W/runs/$FID_CASE/container"; rm -rf "$out"; mkdir -p "$out"
    # As qsm_ci/containers.py runs it under apptainer, plus recon.m's intermediates (images
    # built before the option ignore it and give the final chi only).
    /usr/bin/time -v apptainer exec --no-home --cleanenv --env QSMCI_INTERMEDIATES=/output/intermediates \
        -B "$W/algo:/algo:ro" \
        -B "$FID_INPUT:/input:ro" -B "$out:/output" "$SIF" bash /algo/run.sh
    ;;
compare)
    mat "addpath('$FID'); compare_runs('$W/runs/$FID_CASE', '$FID_INPUT/mask.nii.gz', '$W/deps', '$W/reports/runs-$FID_CASE.md')"
    ;;
*) echo "unknown STEP $STEP"; exit 2 ;;
esac
echo "done $(date -Is)"
