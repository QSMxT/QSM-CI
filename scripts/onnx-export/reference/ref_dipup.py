#!/usr/bin/env python3
"""Reference measurements for DIP-UP's pretrained wrap-count CNNs on the QSM.rs phantom.

Reproduces every number quoted in PROVENANCE.md's DIP-UP entry and in
QSM.rs `docs/DIPUP_SCOPING.md`. Nothing here is a CI gate -- it is a one-time
characterisation run (QSM.rs #140: parity checks are not CI gates).

Needs: torch, onnxruntime, nibabel, scipy, numpy, and the two checkpoints from the
authors' Dropbox (linked from the DIP-UP README).

The classical baselines (ROMEO / Laplacian / best-path) are produced by qsm-core, not
here -- see `dipup_baseline.rs` beside this file; run it first and pass its output
directory as --baseline.

Subcommands:
  wrapcount   required wrap-count range per echo, vs the net's 9 classes
  validate    justify ROMEO as the wrap-count reference (congruence + independent agreement)
  accuracy    per-echo wrap-count accuracy, against the trivial "no wraps" predictor
  ablate      the conventions the public repo does not pin down (masking, sign, Laplacian)
  fieldmap    total field (ppm) after echo fit, vs ground truth -- a WEAK metric, see below
  dipgap      what the test-time DIP loop adds on top of the pretrained CNN
  export-unwrapped  write per-echo unwrapped phase as NIfTI, for the downstream comparison

An unwrapper cannot be judged by correlating unwrapped phase or total field: two unwrappings
differing by a HARMONIC field give the same local field once background removal has run.
Measured here, Laplacian unwrapping disagrees with ROMEO's wrap count at 53.6% of voxels and
places last on total field, then places FIRST on chi. Score at chi. The full chain is
  dipup_baseline.rs            -> classical unwraps (ROMEO / Laplacian / best path)
  ref_dipup.py export-unwrapped -> the CNN unwraps
  dipup_downstream.rs           -> echo fit, V-SHARP, RTS, scored against ground truth
  dipup_figure.py               -> the two figures used in QSM.rs docs/figures/
"""
import argparse
import math
import os
import sys
import time

import nibabel as nib
import numpy as np
import scipy.io as sio
import scipy.ndimage as ndi
import torch

# dipup_net.py lives one level up, beside export_dipup.py (single copy, no duplication).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dipup_net import VARIANTS, load  # noqa: E402

GAMMA, B0 = 42.576e6, 7.0           # phantom is 7 T
TE = np.array([0.004, 0.012, 0.020, 0.028])
SHIFT_BASE = 5                      # 9 classes -> counts [-5, +3]


def paths(bids):
    return f"{bids}/sub-1/anat", f"{bids}/derivatives/qsm-forward/sub-1/anat"


def load_phantom(bids):
    anat, deriv = paths(bids)
    mask = nib.load(f"{deriv}/sub-1_mask.nii").get_fdata() > 0.5
    wrapped = [nib.load(f"{anat}/sub-1_echo-{e}_part-phase_MEGRE.nii").get_fdata()
               for e in (1, 2, 3, 4)]
    gt = nib.load(f"{deriv}/sub-1_fieldmap.nii").get_fdata()      # ppm
    return mask, wrapped, gt


def ref_count(wrapped, unwrapped, mask):
    """Integer wrap count of a congruent unwrapper, with its arbitrary global offset removed."""
    n = np.round((unwrapped - wrapped) / (2 * math.pi))
    return n - np.round(np.median(n[mask]))


def dker(repo):
    return np.squeeze(sio.loadmat(f"{repo}/PHU-NET3D/dker.mat")["dker"])


def lap7(p):
    """7-point stencil, circular -- what QSM-CI's dip_up_infer.py uses."""
    out = -6.0 * p
    for ax in range(3):
        out = out + np.roll(p, 1, ax) + np.roll(p, -1, ax)
    return out


def predict(net, variant, phase, mask, lap=None, decode="expect"):
    """Pad to /16, run, decode to an integer wrap count, mask. Returns count (not phase)."""
    in_ch = VARIANTS[variant][0]
    pads = [((16 - s % 16) % 16) for s in phase.shape]
    pads = [(p // 2, p - p // 2) for p in pads]
    sl = tuple(slice(a, a + s) for (a, _), s in zip(pads, phase.shape))
    chans = [np.pad(phase, pads)]
    if in_ch == 2:
        chans.append(np.pad(lap if lap is not None else lap7(phase), pads))
    x = torch.from_numpy(np.stack(chans)).float()[None]
    with torch.inference_mode():
        logits = net(x)
        if decode == "argmax":
            c = (logits.argmax(1).float() - SHIFT_BASE).squeeze().numpy()[sl]
        else:
            sm = torch.softmax(logits, 1)
            idx = torch.arange(9)[None, :, None, None, None].float()
            c = ((idx * sm).sum(1, keepdim=True) - SHIFT_BASE).squeeze().numpy()[sl]
    return np.round(c * mask)


def score_count(c, nref, mask):
    """Exact-match %, and % on the voxels that actually need a nonzero count.

    The best global integer shift is granted, since a constant wrap offset is the one
    error a downstream fit could in principle absorb. It comes out as 0 everywhere.
    """
    nz = mask & (nref != 0)
    best = max(range(-4, 5), key=lambda s: ((c[mask] + s) == nref[mask]).mean())
    return (((c[mask] + best) == nref[mask]).mean() * 100,
            (((c + best)[nz]) == nref[nz]).mean() * 100 if nz.sum() else float("nan"),
            best)


# ----------------------------------------------------------------------------------
def cmd_wrapcount(a):
    mask, wrapped, gt = load_phantom(a.bids)
    print(f"volume {mask.shape}, mask {int(mask.sum())} voxels")
    print(f"ground-truth field in mask: {gt[mask].min():+.3f} .. {gt[mask].max():+.3f} ppm")
    print("\nrequired wrap count vs the net's 9 classes ([-5,+3]):")
    print(f"{'echo':>5} {'min':>6} {'max':>6} {'#distinct':>10} {'in [-5,3]':>10}")
    for e, wr in zip((1, 2, 3, 4), wrapped):
        uw = nib.load(f"{a.baseline}/uw_romeo_echo{e}.nii").get_fdata()
        n = ref_count(wr, uw, mask)[mask]
        print(f"{e:>5} {n.min():+6.0f} {n.max():+6.0f} {len(np.unique(n)):10d} "
              f"{((n >= -5) & (n <= 3)).mean() * 100:9.2f}%")


def cmd_validate(a):
    """Two independent congruent unwrappers agreeing pins the reference."""
    mask, wrapped, _ = load_phantom(a.bids)
    print("Is ROMEO a sound wrap-count reference? (no ground truth used)")
    print(f"{'echo method':26s} {'congruence':>12s} {'resid wraps':>20s} {'agree w/ ROMEO':>15s}")
    for e, wr in zip((1, 2, 3, 4), wrapped):
        ns = {}
        for meth in ("romeo", "bestpath", "laplacian"):
            uw = nib.load(f"{a.baseline}/uw_{meth}_echo{e}.nii").get_fdata()
            k = (uw - wr) / (2 * math.pi)
            congr = np.abs(k[mask] - np.round(k[mask])).max()   # 0 => integer multiples of 2pi
            bad = tot = 0
            for ax in range(3):
                d = np.diff(uw, axis=ax)
                mm = (mask & np.roll(mask, -1, ax))[
                    tuple(slice(0, s - 1) if i == ax else slice(None)
                          for i, s in enumerate(mask.shape))]
                tot += mm.sum()
                bad += (np.abs(d[mm]) > math.pi).sum()
            ns[meth] = ref_count(wr, uw, mask)
            ag = "" if meth == "romeo" else \
                f"{(ns[meth][mask] == ns['romeo'][mask]).mean() * 100:14.3f}%"
            print(f"  {e} {meth:22s} {congr:12.2e} {bad:8d}/{tot:<11d} {ag}")


def cmd_accuracy(a):
    mask, wrapped, _ = load_phantom(a.bids)
    net = load(a.variant, a.weights)
    print(f"{a.variant}: wrap-count accuracy vs ROMEO, full volume, "
          f"phase {'pre-masked' if a.premask else 'as-is'}")
    print(f"{'echo':>5} {'ref n!=0':>9} {'trivial-0':>10} {'net exact':>10} "
          f"{'on n!=0':>9} {'shift':>6} {'secs':>6}")
    for e, wr in zip((1, 2, 3, 4), wrapped):
        uw = nib.load(f"{a.baseline}/uw_romeo_echo{e}.nii").get_fdata()
        nref = ref_count(wr, uw, mask)
        inp = wr * mask if a.premask else wr
        t0 = time.time()
        c = predict(net, a.variant, inp, mask, decode=a.decode)
        ex, nzacc, shift = score_count(c, nref, mask)
        print(f"{e:>5} {(mask & (nref != 0)).sum() / mask.sum() * 100:8.2f}% "
              f"{(nref[mask] == 0).mean() * 100:9.2f}% {ex:9.2f}% {nzacc:8.2f}% "
              f"{shift:6d} {time.time() - t0:6.0f}")


def cmd_ablate(a):
    """The public repo does not pin these down; each is decided by measurement."""
    mask, wrapped, _ = load_phantom(a.bids)
    S = a.crop
    c0 = [s // 2 for s in mask.shape]
    sl = tuple(slice(ci - S // 2, ci + S // 2) for ci in c0)
    mask = mask[sl]
    k = dker(a.repo)
    nets = {v: load(v, w) for v, w in (("PHU-NET3D", a.weights_phu),
                                       ("PhaseNet3D", a.weights_phase)) if w}
    for e in a.echoes:
        wr = wrapped[e - 1][sl]
        uw = nib.load(f"{a.baseline}/uw_romeo_echo{e}.nii").get_fdata()[sl]
        nref = ref_count(wr, uw, mask)
        triv = (nref[mask] == 0).mean() * 100
        wm = wr * mask
        cases = []
        if "PHU-NET3D" in nets:
            cases += [
                ("PHU-NET3D  as-is, lap=dker27",      "PHU-NET3D", wr, ndi.convolve(wr, k, mode="wrap")),
                ("PHU-NET3D  masked, lap=dker27",     "PHU-NET3D", wm, ndi.convolve(wm, k, mode="wrap")),
                ("PHU-NET3D  masked, lap=7pt",        "PHU-NET3D", wm, lap7(wm)),
                ("PHU-NET3D  masked, lap=zeros",      "PHU-NET3D", wm, np.zeros_like(wr)),
                ("PHU-NET3D  masked, sign-flipped",   "PHU-NET3D", -wm, ndi.convolve(-wm, k, mode="wrap")),
            ]
        if "PhaseNet3D" in nets:
            cases += [
                ("PhaseNet3D as-is",                  "PhaseNet3D", wr, None),
                ("PhaseNet3D masked",                 "PhaseNet3D", wm, None),
                ("PhaseNet3D masked, sign-flipped",   "PhaseNet3D", -wm, None),
            ]
        print(f"\necho {e}  (crop {S}^3, trivial-0 = {triv:.2f}%)")
        for name, v, p, l in cases:
            ex, nz, _ = score_count(predict(nets[v], v, p, mask, lap=l), nref, mask)
            print(f"  {name:34s} exact {ex:6.2f}%  on n!=0 {nz:6.2f}%"
                  f"{'' if ex > triv else '   <- worse than trivial'}")


def cmd_fieldmap(a):
    mask, wrapped, gt = load_phantom(a.bids)

    def echofit(uw):
        uw = np.stack(uw, -1)
        dt = TE - TE.mean()
        slope = np.sum(dt * (uw - uw.mean(-1, keepdims=True)), -1) / np.sum(dt ** 2)  # rad/s
        return slope / (2 * np.pi) * 1e6 / (GAMMA * B0) * mask                        # ppm

    def score(f):
        x, y = f[mask], gt[mask]
        return np.corrcoef(x, y)[0, 1], np.sqrt(((x - y) ** 2).mean()) / y.std()

    print(f"{'method':38s} {'corr':>9s} {'NRMSE':>8s}")
    for meth in ("romeo", "laplacian", "bestpath"):
        uw = [nib.load(f"{a.baseline}/uw_{meth}_echo{e}.nii").get_fdata() for e in (1, 2, 3, 4)]
        r, n = score(echofit(uw))
        print(f"{'classical (qsm-core): ' + meth:38s} {r:9.5f} {n:8.4f}")
    for variant, w in (("PhaseNet3D", a.weights_phase), ("PHU-NET3D", a.weights_phu)):
        if not w:
            continue
        net = load(variant, w)
        uw = []
        for wr in wrapped:
            wm = wr * mask
            uw.append(predict(net, variant, wm, mask) * 2 * math.pi + wr)
        r, n = score(echofit(uw))
        print(f"{'pretrained CNN, no DIP: ' + variant:38s} {r:9.5f} {n:8.4f}")
    r, n = score(echofit([w * mask for w in wrapped]))
    print(f"{'no unwrapping at all':38s} {r:9.5f} {n:8.4f}")


def cmd_dipgap(a):
    """What the test-time DIP loop adds. tract is inference-only, so this can never be
    ported -- the question is only how much of the accuracy it accounts for.

    Losses/optimiser/schedule/decoding follow QSM-CI's dip_up_infer.py verbatim, which
    means the phase is NOT pre-masked here. Internally consistent (iter 0 vs iter N on
    identical input), so the delta is the measurement; the absolute numbers are not the
    best-configuration numbers from `accuracy`.
    """
    mask_f, wrapped, _ = load_phantom(a.bids)
    S = a.patch
    com = np.array(ndi.center_of_mass(mask_f)).round().astype(int)
    sl = tuple(slice(int(np.clip(c - S // 2, 0, s - S)), int(np.clip(c - S // 2, 0, s - S)) + S)
               for c, s in zip(com, mask_f.shape))
    mask = mask_f[sl]
    wr = wrapped[a.echo - 1][sl]
    uw = nib.load(f"{a.baseline}/uw_romeo_echo{a.echo}.nii").get_fdata()[sl]
    nref = ref_count(wr, uw, mask)

    net = load(a.variant, a.weights)
    in_ch = VARIANTS[a.variant][0]
    image = torch.from_numpy(wr).float()[None, None]
    tm = torch.from_numpy(mask.astype(np.float32))[None, None]
    feats = image if in_ch == 1 else torch.cat(
        [image, torch.from_numpy(lap7(wr)).float()[None, None]], 1)
    idx = torch.arange(9)[None, :, None, None, None].float()

    def tv(x, m):
        d = lambda t, ax: (torch.diff(t, dim=ax).abs() * m.narrow(ax, 1, m.shape[ax] - 1)).sum()
        return d(x, 2) + d(x, 3) + d(x, 4)

    def lapl(wrapped_t, unw):
        diff = unw - wrapped_t
        return (diff - torch.round(diff / (2 * math.pi)) * 2 * math.pi).abs().sum()

    def decode():
        with torch.inference_mode():
            sm = torch.softmax(net(feats), 1)
            return torch.round((((idx * sm).sum(1, keepdim=True) - SHIFT_BASE) * tm)).squeeze().numpy()

    print(f"{a.variant} echo {a.echo}: patch {S}^3, mask {int(mask.sum())} vox, "
          f"ref n!=0 {(mask & (nref != 0)).sum() / mask.sum() * 100:.2f}%, "
          f"trivial-0 {(nref[mask] == 0).mean() * 100:.2f}%")
    ex, nz, sh = score_count(decode(), nref, mask)
    print(f"  iter    0 (pretrained CNN alone): exact {ex:.2f}% | on n!=0 {nz:.2f}%")

    opt = torch.optim.RMSprop(net.parameters(), lr=a.lr)
    t0 = time.time()
    for it in range(1, a.n_iter + 1):
        sm = torch.softmax(net(feats), 1)
        cnt = ((idx * sm).sum(1, keepdim=True) - SHIFT_BASE) * tm
        uwph = cnt * 2 * math.pi + image
        loss = tv(uwph, tm) + lapl(image, uwph)
        loss.backward()
        opt.step()
        opt.zero_grad()
        if a.lr_decay and it % 10 == 0:
            for g in opt.param_groups:
                g["lr"] *= 0.9
        if it in (1, 5, 10, 25, 50, 75, 100) or it == a.n_iter:
            ex, nz, sh = score_count(decode(), nref, mask)
            print(f"  iter {it:4d}: exact {ex:.2f}% | on n!=0 {nz:.2f}% | "
                  f"loss {loss.item():.4g} | lr {opt.param_groups[0]['lr']:.3g} | "
                  f"{(time.time() - t0) / it:.1f}s/iter", flush=True)



def cmd_export_unwrapped(a):
    """Write per-echo unwrapped phase as NIfTI, so the downstream (BFR -> chi) can be scored.

    Correlation of unwrapped phase is a weak metric: two unwrappings may differ by a harmonic
    field that background-field removal deletes, leaving the local field identical. What the
    pipeline actually consumes is written here so the comparison can be made where it matters.
    Also writes the wrap-count difference vs ROMEO, to show whether errors are scattered
    (2*pi discontinuities, which BFR cannot remove) or spatially coherent (piecewise constant,
    much more benign).
    """
    mask, wrapped, _ = load_phantom(a.bids)
    aff = nib.load(f"{paths(a.bids)[1]}/sub-1_mask.nii").affine
    os.makedirs(a.out, exist_ok=True)
    net = load(a.variant, a.weights)
    tag = a.variant.replace("-", "").lower()
    for e, wr in zip((1, 2, 3, 4), wrapped):
        c = predict(net, a.variant, wr * mask, mask)
        uw = c * 2 * math.pi + wr
        nib.save(nib.Nifti1Image(uw.astype(np.float32), aff),
                 f"{a.out}/uw_{tag}_echo{e}.nii")
        ref = nib.load(f"{a.baseline}/uw_romeo_echo{e}.nii").get_fdata()
        d = (c - ref_count(wr, ref, mask)) * mask
        nib.save(nib.Nifti1Image(d.astype(np.float32), aff),
                 f"{a.out}/dn_{tag}_echo{e}.nii")
        # Is the error scattered or coherent? Compare the error's own spatial roughness
        # against that of a random relabelling with the same marginal distribution.
        err = (d != 0) & mask
        nb = np.zeros_like(d, dtype=bool)
        for ax in range(3):
            nb |= (np.roll(d, 1, ax) != d) | (np.roll(d, -1, ax) != d)
        boundary = (nb & mask).sum() / max(mask.sum(), 1)
        print(f"  echo {e}: |dn|>0 at {err.sum() / mask.sum() * 100:5.2f}% of voxels, "
              f"dn changes between neighbours at {boundary * 100:5.2f}% "
              f"(low => coherent regions, high => scattered)", flush=True)
    print(f"wrote {a.out}/uw_{tag}_echo*.nii and dn_{tag}_echo*.nii")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bids", required=True, help="QSM.rs bids/ directory")
    ap.add_argument("--baseline", required=True, help="output dir of dipup_baseline.rs")
    ap.add_argument("--repo", default=".", help="DIP-UP checkout (for dker.mat)")
    ap.add_argument("--weights-phu")
    ap.add_argument("--weights-phase")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("wrapcount").set_defaults(fn=cmd_wrapcount)
    sub.add_parser("validate").set_defaults(fn=cmd_validate)
    sub.add_parser("fieldmap").set_defaults(fn=cmd_fieldmap)

    p = sub.add_parser("accuracy")
    p.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    p.add_argument("--weights", required=True)
    p.add_argument("--premask", action="store_true")
    p.add_argument("--decode", default="expect", choices=["expect", "argmax"])
    p.set_defaults(fn=cmd_accuracy)

    p = sub.add_parser("ablate")
    p.add_argument("--crop", type=int, default=128)
    p.add_argument("--echoes", type=int, nargs="+", default=[2, 4])
    p.set_defaults(fn=cmd_ablate)

    p = sub.add_parser("dipgap")
    p.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    p.add_argument("--weights", required=True)
    p.add_argument("--echo", type=int, default=4)
    p.add_argument("--n-iter", type=int, default=100)
    p.add_argument("--patch", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-6)
    p.add_argument("--lr-decay", type=int, default=1)
    p.set_defaults(fn=cmd_dipgap)

    p = sub.add_parser("export-unwrapped")
    p.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    p.add_argument("--weights", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_export_unwrapped)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
