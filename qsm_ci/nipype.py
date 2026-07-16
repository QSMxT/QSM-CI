"""Nipype interfaces for QSM-CI algorithms.

Each interface is a thin wrapper around the ``qsm-ci run <slug>`` CLI, so it drops straight into a
nipype ``Workflow``. The CLI does all the container orchestration (docker / podman / apptainer, or
``--runner local``), so these interfaces do **not** depend on nipype's own container support — the
container happens underneath. Every QSM-CI algorithm is one ``qsm-ci run`` away, so any published
method (by its ``slug``) works with the interface for its stage.

Install the extra::

    pip install "qsm-ci[nipype]"

Example — a background-removal → dipole-inversion pipeline mixing two methods::

    from nipype import Workflow, Node
    from qsm_ci.nipype import BackgroundRemoval, DipoleInversion

    bfr = Node(BackgroundRemoval(slug="sharp", totalfield="totalfield.nii.gz",
                                 mask="mask.nii.gz", params="params.json"), name="bfr")
    dip = Node(DipoleInversion(slug="rts", mask="mask.nii.gz", params="params.json"), name="dip")

    wf = Workflow(name="qsm")
    wf.connect(bfr, "out_file", dip, "localfield")
    wf.run()

The ``stage`` each interface targets is fixed; the ``slug`` picks which method runs that stage.
"""

from __future__ import annotations

import os

try:
    from nipype.interfaces.base import (
        CommandLine,
        CommandLineInputSpec,
        File,
        TraitedSpec,
        traits,
    )
except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
    raise ImportError(
        "qsm_ci.nipype requires nipype. Install it with:  pip install 'qsm-ci[nipype]'"
    ) from exc


class _RunInputSpec(CommandLineInputSpec):
    """Flags common to every ``qsm-ci run`` invocation (see `qsm-ci run <slug> --help`)."""

    slug = traits.Str(argstr="%s", position=0, mandatory=True,
                      desc="algorithm slug to run for this stage (e.g. 'sharp', 'rts')")
    mask = File(exists=True, argstr="--mask %s", mandatory=True, desc="brain mask NIfTI")
    params = File(exists=True, argstr="--params %s",
                  desc="params.json or a BIDS MEGRE sidecar (alternative to --te/--field-strength)")
    out = File(argstr="-o %s", usedefault=True, desc="path to write the produced artifact")
    # acquisition parameters (alternative to a --params file)
    te = traits.List(traits.Float, argstr="--te %s", sep=" ",
                     desc="echo times in seconds (field-mapping stages)")
    field_strength = traits.Float(argstr="--field-strength %g",
                                  desc="B0 field strength in tesla (field-mapping stages)")
    b0_dir = traits.List(traits.Float, minlen=3, maxlen=3, argstr="--b0-dir %s", sep=" ",
                         desc="unit B0 direction (default 0 0 1)")
    voxel_size = traits.List(traits.Float, minlen=3, maxlen=3, argstr="--voxel-size %s", sep=" ",
                             desc="voxel size in mm (default: from the input header)")
    # scoring (optional)
    truth = File(exists=True, argstr="--truth %s", desc="ground-truth artifact to score against")
    seg = File(exists=True, argstr="--seg %s", desc="segmentation for full χ-region metrics")
    # execution
    runner = traits.Enum("docker", "podman", "apptainer", "local", argstr="--runner %s",
                         desc="container engine (default docker); 'local' runs run.sh on the host")
    overrides = traits.List(traits.Str, argstr="--set %s...",
                            desc="method parameter overrides, each 'NAME=VALUE'")


class _RunOutputSpec(TraitedSpec):
    out_file = File(desc="the produced artifact (totalfield / localfield / chimap)")


class _QsmCiRun(CommandLine):
    """Base for the per-stage interfaces — never used directly (has no primary input)."""

    _cmd = "qsm-ci run"
    input_spec = _RunInputSpec
    output_spec = _RunOutputSpec
    _produced = "output.nii.gz"  # overridden per stage

    def _format_arg(self, name, spec, value):
        if name == "out" and not value:
            value = self._produced
        return super()._format_arg(name, spec, value)

    def _list_outputs(self):
        outputs = self.output_spec().get()
        out = self.inputs.out if self.inputs.out else self._produced
        outputs["out_file"] = os.path.abspath(out)
        return outputs


# --- field-mapping: phase (+magnitude) -> totalfield ------------------------------------------

class FieldMappingInputSpec(_RunInputSpec):
    phase = File(exists=True, argstr="--phase %s", mandatory=True, desc="wrapped phase NIfTI")
    magnitude = File(exists=True, argstr="--magnitude %s", desc="magnitude NIfTI")
    out = File("totalfield.nii.gz", argstr="-o %s", usedefault=True,
               desc="path to write the total field (ppm)")


class FieldMapping(_QsmCiRun):
    """QSM-CI *field-mapping* stage — phase (+ magnitude) → total field (ppm)."""

    input_spec = FieldMappingInputSpec
    _produced = "totalfield.nii.gz"


# --- bfr: totalfield -> localfield ------------------------------------------------------------

class BackgroundRemovalInputSpec(_RunInputSpec):
    totalfield = File(exists=True, argstr="--totalfield %s", mandatory=True,
                      desc="total field NIfTI (ppm)")
    out = File("localfield.nii.gz", argstr="-o %s", usedefault=True,
               desc="path to write the local field (ppm)")


class BackgroundRemoval(_QsmCiRun):
    """QSM-CI *background field removal* stage — total field → local field (ppm)."""

    input_spec = BackgroundRemovalInputSpec
    _produced = "localfield.nii.gz"


# --- dipole: localfield (+magnitude) -> chimap ------------------------------------------------

class DipoleInversionInputSpec(_RunInputSpec):
    localfield = File(exists=True, argstr="--localfield %s", mandatory=True,
                      desc="local field NIfTI (ppm)")
    magnitude = File(exists=True, argstr="--magnitude %s",
                     desc="magnitude NIfTI (data-fidelity weighting; some methods use it)")
    out = File("chimap.nii.gz", argstr="-o %s", usedefault=True,
               desc="path to write the susceptibility map (ppm)")


class DipoleInversion(_QsmCiRun):
    """QSM-CI *dipole inversion* stage — local field → susceptibility χ map (ppm)."""

    input_spec = DipoleInversionInputSpec
    _produced = "chimap.nii.gz"


__all__ = ["FieldMapping", "BackgroundRemoval", "DipoleInversion"]
