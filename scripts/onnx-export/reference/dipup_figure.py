import numpy as np, nibabel as nib, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
B="/home/ashley/repos/qsm/QSM.rs/.claude/worktrees/hungry-vaughan-6787e2/bids"
D=f"{B}/derivatives/qsm-forward/sub-1/anat"; A=f"{B}/sub-1/anat"
L=lambda p: nib.load(p).get_fdata()
mask=L(f"{D}/sub-1_mask.nii")>0.5
Z=mask.shape[2]//2                       # axial slice through the middle
sl=lambda v: np.rot90(v[:,:,Z])
METH=["romeo","bestpath","laplacian","phasenet3d","phunet3d"]
NICE={"romeo":"ROMEO","bestpath":"best path","laplacian":"Laplacian",
      "phasenet3d":"PhaseNet3D","phunet3d":"PHU-NET3D"}

fig,ax=plt.subplots(4,6,figsize=(21,15))
for a in ax.ravel(): a.axis("off")

# --- row 0: unwrapped phase, echo 4 (the hardest echo) ---
wr=L(f"{A}/sub-1_echo-4_part-phase_MEGRE.nii")*mask
ax[0,0].imshow(sl(wr),cmap="twilight"); ax[0,0].set_title("wrapped phase, echo 4\n(input)",fontsize=11)
for i,m in enumerate(METH):
    uw=L(f"uw/uw_{m}_echo4.nii")*mask
    v=np.percentile(np.abs(uw[mask]),99)
    ax[0,i+1].imshow(sl(uw),cmap="twilight",vmin=-v,vmax=v)
    ax[0,i+1].set_title(f"unwrapped: {NICE[m]}",fontsize=11)

# --- row 1: wrap-count difference vs ROMEO ---
ax[1,0].text(.5,.5,"wrap-count error\nvs ROMEO, echo 4\n\n(each unit = a 2$\\pi$ step;\nscattered = not harmonic,\nso BFR cannot remove it)",
             ha="center",va="center",fontsize=11,transform=ax[1,0].transAxes)
for i,m in enumerate(METH):
    if m in ("phasenet3d","phunet3d"):
        d=L(f"uw/dn_{m}_echo4.nii")*mask
    else:
        ref=L("uw/uw_romeo_echo4.nii"); d=np.round((L(f"uw/uw_{m}_echo4.nii")-ref)/(2*np.pi))*mask
        d-=np.round(np.median(d[mask]))
    im=ax[1,i+1].imshow(sl(d),cmap="RdBu_r",vmin=-4,vmax=4)
    ax[1,i+1].set_title(f"{NICE[m]}: {np.mean(d[mask]!=0)*100:.1f}% wrong",fontsize=11)
plt.colorbar(im,ax=ax[1,5],fraction=.046)

# --- rows 2,3: local field after V-SHARP, and chi after RTS, vs ground truth ---
for row,(stage,truth,lbl,lim) in enumerate(
        [("localfield",L(f"{D}/sub-1_fieldmap-local.nii"),"local field (V-SHARP), ppm",0.05),
         ("chi",       L(f"{D}/sub-1_Chimap.nii"),        "$\\chi$ (RTS), ppm",        0.10)],2):
    vm=L(f"stages/localfield_romeo.nii")!=0        # V-SHARP eroded mask
    ax[row,0].imshow(sl(truth*vm),cmap="gray",vmin=-lim,vmax=lim)
    ax[row,0].set_title(f"GROUND TRUTH\n{lbl}",fontsize=11)
    for i,m in enumerate(METH):
        v=L(f"stages/{stage}_{m}.nii")
        ax[row,i+1].imshow(sl(v),cmap="gray",vmin=-lim,vmax=lim)
        r=np.corrcoef(v[vm],truth[vm])[0,1]
        ax[row,i+1].set_title(f"{NICE[m]}  corr {r:.3f}",fontsize=11)

fig.suptitle("DIP-UP pretrained CNNs vs classical unwrappers: the whole chain, 7 T phantom "
             "(same window per row)",fontsize=14)
plt.tight_layout(rect=[0,0,1,0.97]); plt.savefig("dipup_figure.png",dpi=95,bbox_inches="tight")
print("wrote dipup_figure.png")
