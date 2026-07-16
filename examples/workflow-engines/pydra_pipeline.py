#!/usr/bin/env python3
"""End-to-end QSM pipeline (phase → χ) built with Pydra and QSM-CI's shipped interfaces.

Chains three methods — field-mapping → background-field removal → dipole inversion — each of which
runs via `qsm-ci run` (so the container is handled for you). Swap any `slug` to mix and match methods.

    pip install "qsm-ci[pydra]"
    python pydra_pipeline.py --phase phase.nii.gz --magnitude mag.nii.gz \
        --mask mask.nii.gz --params params.json --out chimap.nii.gz
"""
import argparse
import os
import shutil

import pydra

from qsm_ci.pydra import BackgroundRemoval, DipoleInversion, FieldMapping


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase", required=True)
    p.add_argument("--magnitude", required=True)
    p.add_argument("--mask", required=True)
    p.add_argument("--params", required=True)
    p.add_argument("--out", default="chimap.nii.gz")
    p.add_argument("--runner", default="docker", help="docker · podman · apptainer · local")
    a = p.parse_args()

    wf = pydra.Workflow(name="qsm", input_spec=["phase", "magnitude", "mask", "params"],
                        phase=a.phase, magnitude=a.magnitude, mask=a.mask, params=a.params)
    wf.add(FieldMapping(name="fm", slug="romeo-fieldmap", phase=wf.lzin.phase,
                        magnitude=wf.lzin.magnitude, mask=wf.lzin.mask, params=wf.lzin.params,
                        runner=a.runner))
    wf.add(BackgroundRemoval(name="bfr", slug="vsharp", totalfield=wf.fm.lzout.totalfield,
                             mask=wf.lzin.mask, params=wf.lzin.params, runner=a.runner))
    wf.add(DipoleInversion(name="dip", slug="rts", localfield=wf.bfr.lzout.localfield,
                           mask=wf.lzin.mask, params=wf.lzin.params, runner=a.runner))
    wf.set_output({"chimap": wf.dip.lzout.chimap})

    with pydra.Submitter(plugin=os.environ.get("PYDRA_PLUGIN", "cf")) as sub:
        sub(wf)
    shutil.copy(str(wf.result().output.chimap), a.out)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
