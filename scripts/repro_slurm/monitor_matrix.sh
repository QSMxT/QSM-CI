#!/bin/bash
# Wait for the repro matrix to launch, confirm it's running, then measure recon-production rate over a
# 15-min window and estimate a total ETA. Writes a report to matrix_monitor_report.txt.
source ~/miniconda3/etc/profile.d/conda.sh && conda activate qsmxt 2>/dev/null
cd /scratch/user/uqaste15/qsmci-repro
R=matrix_monitor_report.txt; : > "$R"
say(){ echo "$@" | tee -a "$R"; }

say "== monitor start $(date '+%F %T') =="

# 1) wait for the watcher to sbatch the matrix (up to ~30 min)
for i in $(seq 1 120); do grep -q LAUNCH_DONE wait_launch.log 2>/dev/null && break; sleep 15; done
say "--- wait_launch.log ---"; tail -10 wait_launch.log | tee -a "$R"
JOB=$(grep -oP "Submitted batch job \K[0-9]+" wait_launch.log | tail -1)
say "matrix job id: ${JOB:-NONE}"
if [ -z "$JOB" ]; then say "!! no matrix job — masks likely failed; aborting monitor"; exit 1; fi

# 2) confirm it's running
say "--- squeue @ start ---"; squeue -j "$JOB" -h -o "%t" | sort | uniq -c | tee -a "$R"
NP=$(ls results 2>/dev/null | grep -- '-cmp-' | sed 's/-cmp-.*//' | sort -u | wc -l)
TARGET=$((NP * 23))
say "distinct composed pipelines (from prior results): $NP  -> target recons ~ $TARGET"

# 3) throughput window: count recons (re)generated during a 15-min window
touch /tmp/win_start
LTS=$(stat -c %Y wait_launch.log); touch -d "@$LTS" /tmp/launch_marker
sleep 900
dt=$(( $(date +%s) - $(stat -c %Y /tmp/win_start) ))
fresh=$(find results -name 'recon.nii.gz' -newer /tmp/win_start 2>/dev/null | wc -l)
done_since_launch=$(find results -name 'recon.nii.gz' -newer /tmp/launch_marker 2>/dev/null | wc -l)
say "--- squeue @ +${dt}s ---"; squeue -j "$JOB" -h -o "%t" | sort | uniq -c | tee -a "$R"
say "recons regenerated in window: $fresh in ${dt}s ; total since launch: $done_since_launch / ~$TARGET"

python - "$fresh" "$dt" "$done_since_launch" "$TARGET" "$LTS" <<'PY' | tee -a "$R"
import sys, time
fresh, dt, done, target, lts = (float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]),
                                 float(sys.argv[4]), float(sys.argv[5]))
rate = fresh / (dt/60.0) if dt else 0      # recons/min
print(f"rate: {rate:.1f} recons/min")
if rate > 0 and target > 0:
    remaining = max(0.0, target - done)
    eta_min = remaining / rate
    elapsed = (time.time() - lts) / 60.0
    total_min = elapsed + eta_min
    fin = time.strftime('%F %H:%M', time.localtime(time.time() + eta_min*60))
    print(f"elapsed since launch: {elapsed:.0f} min ; remaining: {eta_min/60:.1f} h ; total ~{total_min/60:.1f} h")
    print(f"ESTIMATED FINISH: ~{fin}")
else:
    print("insufficient signal for ETA (rate ~0) — recheck")
PY

f=$(ls -t slurm-qsmci-repro-matrix-sb-*.out 2>/dev/null | head -1)
say "--- newest task log ($f) tail ---"; tail -6 "$f" 2>/dev/null | tee -a "$R"
say "== monitor end $(date '+%F %T') =="
