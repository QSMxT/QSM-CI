import nibabel, numpy as np, glob, os, subprocess, time
from collections import Counter

os.chdir("/scratch/user/uqaste15/qsmci-repro")
LAUNCH = time.mktime(time.strptime("2026-09-01 14:24", "%Y-%m-%d %H:%M"))
now = time.time()
TARGET = 15732

# A. matrix job state
sq = subprocess.run(["squeue","-j","27844946","-h","-o","%t"], capture_output=True, text=True).stdout.split()
print("squeue states:", dict(Counter(sq)) or "none (job may be done)")
sacct = subprocess.run(["sacct","-j","27844946","--format=State","-X","-n"], capture_output=True, text=True).stdout
print("sacct task states:", dict(Counter(w.strip() for w in sacct.splitlines() if w.strip())))

# B. throughput / ETA from recons regenerated since launch (overwrite -> mtime>launch)
recs = glob.glob("results/*-cmp-*/recon.nii.gz")
fresh = [f for f in recs if os.path.getmtime(f) > LAUNCH]
elapsed_min = (now - LAUNCH) / 60
rate = len(fresh) / elapsed_min if elapsed_min else 0
print(f"\nrecons regenerated: {len(fresh)}/{TARGET} in {elapsed_min:.0f} min = {rate:.1f}/min")
if rate > 0:
    rem_h = (TARGET - len(fresh)) / rate / 60
    print(f"  remaining ~{rem_h:.1f} h ; est finish ~{time.strftime('%m-%d %H:%M', time.localtime(now + rem_h*3600))}")

# C. AMP-PE garbage rate: new (HD-BET) vs old (SynthStrip), by mtime
def std(f):
    try: return float(np.nanstd(nibabel.load(f).get_fdata()))
    except Exception: return None
amp = glob.glob("results/*amp-pe*cmp*/recon.nii.gz")
def rate_of(fs):
    ss = [s for s in (std(f) for f in fs) if s is not None]
    bad = sum(1 for s in ss if (not np.isfinite(s)) or s > 1.0)
    return bad, len(ss)
new_amp = [f for f in amp if os.path.getmtime(f) > LAUNCH]
old_amp = [f for f in amp if os.path.getmtime(f) <= LAUNCH]
nb, nt = rate_of(new_amp); ob, ot = rate_of(old_amp)
print(f"\nAMP-PE garbage (std>1 or NaN):")
print(f"  NEW (HD-BET):     {nb}/{nt}" + (f"  = {100*nb//nt}%" if nt else "  (none regenerated yet)"))
print(f"  OLD (SynthStrip): {ob}/{ot}" + (f"  = {100*ob//ot}%" if ot else ""))

# D. mask sizes: HD-BET vs SynthStrip
print("\n=== mask voxels: HD-BET vs SynthStrip ===")
hd_tot = ss_tot = n = smaller = 0
for d in sorted(glob.glob("data/harmonization/*/inputs")):
    acq = d.split("/")[-2]
    if acq == "_align": continue
    hm, sm = os.path.join(d,"mask.nii.gz"), os.path.join(d,"mask_synthstrip.nii.gz")
    if not (os.path.exists(hm) and os.path.exists(sm)): continue
    hv = int((np.asanyarray(nibabel.load(hm).dataobj) > 0).sum())
    sv = int((np.asanyarray(nibabel.load(sm).dataobj) > 0).sum())
    hd_tot += hv; ss_tot += sv; n += 1; smaller += (hv < sv)
    print(f"  {acq:34s} HD-BET={hv:>9d}  SynthStrip={sv:>9d}  HD/SS={hv/sv:.2f}")
if n:
    print(f"\nmean: HD-BET={hd_tot//n}  SynthStrip={ss_tot//n}  | HD-BET smaller in {smaller}/{n} acqs | overall HD/SS={hd_tot/ss_tot:.2f}")
