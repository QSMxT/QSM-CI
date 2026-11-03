# FSL PRELUDE (original of QSM.rs's PRELUDE): local only

FSL's own `prelude` binary, from FSL's official conda channel: `fsl-fugue` 2603.0 (build
`he1a3b45_0`; the binary reports "Part of FSL (ID: 2412.6-dirty)", "prelude Version 2.0"), with the
exact package set in `fsl-explicit.lock` (MD5-checked on install). Nothing is compiled.
**Build it locally; do not publish the image** (see Licence).

| | |
|---|---|
| `/opt/fsl/bin/prelude` | sha256 `4210078495b97723e813de553e0b18e768842bf51a32684d7f0e96f8aa1d0dc8` |
| base | `mambaorg/micromamba:2.0.5@sha256:c6c6daf6…cdb9bb` |
| local image (podman, 2026-11-02) | `fedfdd12ce67…` (567 MB) |

## The port and what it may read

QSM.rs's `unwrap_prelude` is a clean-room implementation written from Jenkinson's technical report
(TR01MJ1) alone: FSL's source was not read, and must not be, since the FSL licence reaches "any
derivative" (QSM.rs `THIRD_PARTY_NOTICES.md`). So this image is used as a **black box**: the binary
is run and its outputs and help text are compared. Nobody working on `prelude.rs` should open FSL's
`prelude` source, here or anywhere.

## Licence

FSL is under the FSL licence (University of Oxford): non-commercial use only; it may be passed on
without the University's permission only "without financial return", with "the conditions of this
Licence ... imposed upon the receiver" and "all original and amended source code ... included".
As for [`_bet2`](../_bet2/README.md), a public registry image cannot impose those conditions on
whoever pulls it, so the image stays local and the PRELUDE check is a fixture run
([`fidelity/cpp-py`](../../fidelity/cpp-py/README.md)), not a QSM-CI entry that CI would pull.

## Use

```bash
podman build -t localhost/qsm-ci/fsl-prelude:2603.0 algorithms/_fsl-prelude
# in the image: unwraps every volume of PHASE on its own
bash algorithms/_fsl-prelude/prelude.sh PHASE MAG MASK OUT -f -n 6
```

`prelude`'s modes, from its help text and its `-v` output: by default it uses 8 phase partitions
and labels its initial regions slice by slice, then merges them in 3-D (the default and
`--labelslices` start from the same region count and give the same output); `-f` labels in full
3-D, which is the report's algorithm and what QSM.rs implements; `-s` does everything slice by
slice. It writes 0 outside the mask (QSM.rs keeps the wrapped input there), so compare inside it.
