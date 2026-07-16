#!/usr/bin/env python3
"""End-to-end QSM pipeline (phase → χ) built with nipype and QSM-CI's shipped interfaces.

Chains three methods — field-mapping → background-field removal → dipole inversion — each of which
runs via `qsm-ci run` (so the container is handled for you). Swap any `slug` to mix and match methods.

    pip install "qsm-ci[nipype]"
    python nipype_pipeline.py --phase phase.nii.gz --magnitude mag.nii.gz \
        --mask mask.nii.gz --params params.json --out chimap.nii.gz
"""
import argparse

from nipype import Node, Workflow

from qsm_ci.nipype import BackgroundRemoval, DipoleInversion, FieldMapping


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase", required=True)
    p.add_argument("--magnitude", required=True)
    p.add_argument("--mask", required=True)
    p.add_argument("--params", required=True)
    p.add_argument("--out", default="chimap.nii.gz")
    p.add_argument("--runner", default="docker", help="docker · podman · apptainer · local")
    a = p.parse_args()

    fm = Node(FieldMapping(slug="romeo-fieldmap", phase=a.phase, magnitude=a.magnitude,
                           mask=a.mask, params=a.params, runner=a.runner), name="fm")
    bfr = Node(BackgroundRemoval(slug="vsharp", mask=a.mask, params=a.params, runner=a.runner), name="bfr")
    dip = Node(DipoleInversion(slug="rts", mask=a.mask, params=a.params, runner=a.runner,
                               out=a.out), name="dip")

    wf = Workflow(name="qsm")
    wf.connect([(fm, bfr, [("out_file", "totalfield")]),
                (bfr, dip, [("out_file", "localfield")])])
    wf.run()
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
