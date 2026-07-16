"""Pydra interfaces for QSM-CI algorithms.

Thin ``ShellCommandTask`` wrappers around the ``qsm-ci run <slug>`` CLI — one per stage — so any
published method drops into a `pydra <https://pydra.readthedocs.io>`_ workflow. The CLI does the
container orchestration (docker / podman / apptainer, or ``--runner local``), so these tasks don't
need pydra's own container support. Every QSM-CI algorithm is one ``qsm-ci run`` away, so any method
(by its ``slug``) works with the task for its stage.

Install the extra::

    pip install "qsm-ci[pydra]"

Example — an end-to-end phase → χ pipeline mixing three methods::

    import pydra
    from qsm_ci.pydra import FieldMapping, BackgroundRemoval, DipoleInversion

    wf = pydra.Workflow(name="qsm", input_spec=["phase", "magnitude", "mask", "params"])
    wf.add(FieldMapping(name="fm", slug="romeo-fieldmap", phase=wf.lzin.phase,
                        magnitude=wf.lzin.magnitude, mask=wf.lzin.mask, params=wf.lzin.params))
    wf.add(BackgroundRemoval(name="bfr", slug="sharp", totalfield=wf.fm.lzout.totalfield,
                             mask=wf.lzin.mask, params=wf.lzin.params))
    wf.add(DipoleInversion(name="dip", slug="rts", localfield=wf.bfr.lzout.localfield,
                           mask=wf.lzin.mask, params=wf.lzin.params))
    wf.set_output({"chimap": wf.dip.lzout.chimap})

The ``slug`` picks which method runs each stage; the stage fixes the inputs and output.
"""

from __future__ import annotations

try:
    from pydra import ShellCommandTask
    from pydra.engine.specs import File, ShellOutSpec, ShellSpec, SpecInfo
except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
    raise ImportError(
        "qsm_ci.pydra requires pydra. Install it with:  pip install 'qsm-ci[pydra]'"
    ) from exc


_SLUG = ("slug", str, {"help_string": "algorithm slug to run for this stage",
                       "argstr": "", "position": 1, "mandatory": True})


def _trailing(produced_file: str) -> list:
    """Fields shared by every stage: mask, params, output, acquisition, scoring, runner."""
    return [
        ("mask", File, {"help_string": "brain mask NIfTI", "argstr": "--mask", "mandatory": True}),
        ("params", File, {"help_string": "params.json or a BIDS MEGRE sidecar", "argstr": "--params"}),
        ("out", str, produced_file, {"help_string": "path to write the produced artifact",
                                     "argstr": "-o"}),
        ("te", list, {"help_string": "echo times in seconds (field-mapping stages)",
                      "argstr": "--te", "sep": " "}),
        ("field_strength", float, {"help_string": "B0 field strength in tesla",
                                   "argstr": "--field-strength"}),
        ("b0_dir", list, {"help_string": "unit B0 direction (default 0 0 1)",
                          "argstr": "--b0-dir", "sep": " "}),
        ("voxel_size", list, {"help_string": "voxel size in mm (default: from the header)",
                              "argstr": "--voxel-size", "sep": " "}),
        ("truth", File, {"help_string": "ground-truth artifact to score against", "argstr": "--truth"}),
        ("seg", File, {"help_string": "segmentation for full χ-region metrics", "argstr": "--seg"}),
        ("runner", str, {"help_string": "container engine (docker/podman/apptainer/local)",
                         "argstr": "--runner"}),
    ]


def _input(name: str, primary_fields: list) -> "SpecInfo":
    return SpecInfo(name=name, bases=(ShellSpec,), fields=[_SLUG, *primary_fields])


def _output(name: str, produced: str, help_: str) -> "SpecInfo":
    return SpecInfo(name=name, bases=(ShellOutSpec,),
                    fields=[(produced, File, {"help_string": help_, "output_file_template": "{out}"})])


# --- field-mapping: phase (+magnitude) -> totalfield ------------------------------------------

_field_mapping_in = _input("FieldMappingIn", [
    ("phase", File, {"help_string": "wrapped phase NIfTI", "argstr": "--phase", "mandatory": True}),
    ("magnitude", File, {"help_string": "magnitude NIfTI", "argstr": "--magnitude"}),
    *_trailing("totalfield.nii.gz"),
])
_field_mapping_out = _output("FieldMappingOut", "totalfield", "total field (ppm)")


def FieldMapping(name: str = "field_mapping", **kwargs) -> "ShellCommandTask":
    """QSM-CI field-mapping stage — phase (+ magnitude) → total field (ppm)."""
    return ShellCommandTask(name=name, executable=["qsm-ci", "run"],
                            input_spec=_field_mapping_in, output_spec=_field_mapping_out, **kwargs)


# --- bfr: totalfield -> localfield ------------------------------------------------------------

_bfr_in = _input("BackgroundRemovalIn", [
    ("totalfield", File, {"help_string": "total field NIfTI (ppm)",
                          "argstr": "--totalfield", "mandatory": True}),
    *_trailing("localfield.nii.gz"),
])
_bfr_out = _output("BackgroundRemovalOut", "localfield", "local field (ppm)")


def BackgroundRemoval(name: str = "bfr", **kwargs) -> "ShellCommandTask":
    """QSM-CI background field removal stage — total field → local field (ppm)."""
    return ShellCommandTask(name=name, executable=["qsm-ci", "run"],
                            input_spec=_bfr_in, output_spec=_bfr_out, **kwargs)


# --- dipole: localfield (+magnitude) -> chimap ------------------------------------------------

_dipole_in = _input("DipoleInversionIn", [
    ("localfield", File, {"help_string": "local field NIfTI (ppm)",
                          "argstr": "--localfield", "mandatory": True}),
    ("magnitude", File, {"help_string": "magnitude NIfTI (some methods use it)",
                         "argstr": "--magnitude"}),
    *_trailing("chimap.nii.gz"),
])
_dipole_out = _output("DipoleInversionOut", "chimap", "susceptibility χ map (ppm)")


def DipoleInversion(name: str = "dipole", **kwargs) -> "ShellCommandTask":
    """QSM-CI dipole inversion stage — local field → susceptibility χ map (ppm)."""
    return ShellCommandTask(name=name, executable=["qsm-ci", "run"],
                            input_spec=_dipole_in, output_spec=_dipole_out, **kwargs)


__all__ = ["FieldMapping", "BackgroundRemoval", "DipoleInversion"]
