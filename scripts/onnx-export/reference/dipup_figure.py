"""The two figures in QSM.rs docs/figures/ (issue #123, PR #155).

Run from a directory holding `uw/` (dipup_baseline.rs + ref_dipup.py export-unwrapped)
and `stages/` (dipup_downstream.rs). Writes the filenames the QSM.rs docs reference.
"""
import numpy as np, nibabel as nib, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
B="/home/ashley/repos/qsm/QSM.rs/.claude/worktrees/hungry-vaughan-6787e2/bids"
D=f"{B}/derivatives/qsm-forward/sub-1/anat"; A=f"{B}/sub-1/anat"
L=lambda p: nib.load(p).get_fdata()
mask=L(f"{D}/sub-1_mask.nii")>0.5; Z=mask.shape[2]//2
sl=lambda v: np.rot90(v[:,:,Z])
vm=L("stages/localfield_romeo.nii")!=0
gt_lf=L(f"{D}/sub-1_fieldmap-local.nii"); gt_chi=L(f"{D}/sub-1_Chimap.nii")
NICE={"romeo":"ROMEO","bestpath":"best path","laplacian":"Laplacian",
      "phasenet3d":"PhaseNet3D","phunet3d":"PHU-NET3D"}
def wrapcount(m):
    ref=L("uw/uw_romeo_echo4.nii")
    d=np.round((L(f"uw/uw_{m}_echo4.nii")-ref)/(2*np.pi))*mask
    return d-np.round(np.median(d[mask]))

# ---------- Figure A: the whole chain ----------
METH=["romeo","bestpath","laplacian","phasenet3d","phunet3d"]
fig,ax=plt.subplots(3,6,figsize=(20,10.5))
for a in ax.ravel(): a.axis("off")
wr=L(f"{A}/sub-1_echo-4_part-phase_MEGRE.nii")*mask
ax[0,0].imshow(sl(wr),cmap="twilight"); ax[0,0].set_title("wrapped phase, echo 4\n(the input)",fontsize=11,weight="bold")
for i,m in enumerate(METH):
    uw=L(f"uw/uw_{m}_echo4.nii")*mask; v=np.percentile(np.abs(uw[mask]),99)
    ax[0,i+1].imshow(sl(uw),cmap="twilight",vmin=-v,vmax=v)
    ax[0,i+1].set_title(f"unwrapped — {NICE[m]}",fontsize=11)
for row,(stage,truth,lbl,lim) in enumerate(
        [("localfield",gt_lf,"local field (V-SHARP)",0.05),("chi",gt_chi,"$\\chi$ (RTS)",0.10)],1):
    ax[row,0].imshow(sl(truth*vm),cmap="gray",vmin=-lim,vmax=lim)
    ax[row,0].set_title(f"GROUND TRUTH\n{lbl}",fontsize=11,weight="bold")
    for i,m in enumerate(METH):
        v=L(f"stages/{stage}_{m}.nii"); r=np.corrcoef(v[vm],truth[vm])[0,1]
        ax[row,i+1].imshow(sl(v),cmap="gray",vmin=-lim,vmax=lim)
        ax[row,i+1].set_title(f"{NICE[m]} — corr {r:.3f}",fontsize=11,
                              color=("firebrick" if r<0.1 else "black"))
fig.suptitle("Each unwrapper carried through the full chain (7 T phantom, same window per row)",
             fontsize=14,weight="bold")
plt.tight_layout(rect=[0,0,1,0.96]); plt.savefig("dipup_chain.png",dpi=92,bbox_inches="tight")

# ---------- Figure B: why phase-domain scoring misleads ----------
# Show the UNROUNDED difference from ROMEO, in units of 2*pi. Rounding it to integers would
# make Laplacian's genuinely smooth difference look blocky. Measured mean |fractional part|:
# Laplacian 0.2505 (a smooth continuous field), the CNNs 0.0000 (exact 2*pi steps).
def contdiff(m):
    return ((L(f"uw/uw_{m}_echo4.nii") - L("uw/uw_romeo_echo4.nii")) / (2*np.pi)) * mask

fig = plt.figure(figsize=(13, 9.6))
gs = fig.add_gridspec(2, 3, left=.03, right=.88, top=.78, bottom=.03, hspace=.14, wspace=.06)
ax = np.array([[fig.add_subplot(gs[r, c]) for c in range(3)] for r in range(2)])
for a in ax.ravel(): a.axis("off")
for col,(m,caption) in enumerate([
    ("laplacian","Laplacian\n53.6% of wrap counts differ from ROMEO,\nbut as a SMOOTH field (mean frac. part 0.25)"),
    ("phasenet3d","PhaseNet3D\n33.0% differ, as exact 2$\\pi$ STEPS\n(mean frac. part 0.0000)"),
    ("phunet3d","PHU-NET3D\n36.2% differ, as exact 2$\\pi$ steps")]):
    d=contdiff(m)
    im=ax[0,col].imshow(sl(d),cmap="RdBu_r",vmin=-4,vmax=4)
    ax[0,col].set_title(caption,fontsize=11,pad=9)
    chi=L(f"stages/chi_{m}.nii"); r=np.corrcoef(chi[vm],gt_chi[vm])[0,1]
    ax[1,col].imshow(sl(chi),cmap="gray",vmin=-0.10,vmax=0.10)
    ax[1,col].set_title(f"resulting $\\chi$ — corr {r:.3f}",fontsize=13,pad=7,
                        weight="bold",color=("firebrick" if r<0.1 else "darkgreen"))
cax = fig.add_axes([.90, .10, .018, .60])
cb = fig.colorbar(im, cax=cax); cb.set_label("difference from ROMEO, in units of 2$\\pi$", fontsize=10)
fig.text(.455,.945,"Disagreeing with ROMEO is not the same as being wrong",
         ha="center",fontsize=15,weight="bold")
fig.text(.455,.862,"Laplacian disagrees the most, and scores BEST on $\\chi$ (0.498, vs ROMEO's 0.445). Its difference is a smooth\n"
                 "harmonic field, which background-field removal deletes. The CNNs differ by hard 2$\\pi$ steps, which survive\n"
                 "BFR and are then amplified by the dipole inversion.",
         ha="center",fontsize=11,linespacing=1.6)
plt.savefig("dipup_error_character.png",dpi=92,bbox_inches="tight")
print("wrote dipup_chain.png dipup_error_character.png")
