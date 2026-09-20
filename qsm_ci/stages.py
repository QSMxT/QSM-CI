"""Stage & artifact registry — mirrors ../stages.yml.

Kept as plain Python tables (like scripts/pipeline.py) so the installed CLI carries the registry
with it and never has to locate ../stages.yml on disk — pyyaml is a hard dependency anyway
(runner._parse_manifest reads algorithm.yml with it), so this is about self-containment, not
avoiding YAML. If stages.yml changes, update this too (tests/test_stages_sync.py checks).
"""

from __future__ import annotations

# stage/span -> consumed and produced canonical artifacts
STAGES = {
    "field-mapping": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["totalfield"]},
    "bfr": {"consumes": ["totalfield", "mask", "params"], "produces": ["localfield"]},
    "dipole": {"consumes": ["localfield", "mask", "params"], "produces": ["chimap"]},
    "unwrap+bfr": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["localfield"]},
    "bfr+dipole": {"consumes": ["totalfield", "mask", "params", "magnitude"], "produces": ["chimap"]},
    "end-to-end": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["chimap"]},
    # χ-separation: fed local field, R2′, χ_total and multi-echo magnitude; produces two source maps
    # (χ+ paramagnetic, χ− diamagnetic). Isolated-only — its outputs are neither localfield nor chimap,
    # so the composed field-mapping × bfr × dipole matrix skips it.
    "chi-separation": {"consumes": ["localfield", "r2prime", "chimap", "magnitude", "mask", "params"],
                       "produces": ["chi-para", "chi-dia"]},
    # R2′ generation: estimate R2′ from the multi-echo GRE magnitude alone (the GRE-only condition —
    # no spin-echo R2). Scored vs the phantom's true R2′, and composed with each R2′-consuming
    # χ-separation method on the chisep track (pipeline.run_chisep_composed).
    "r2prime-generation": {"consumes": ["magnitude", "mask", "params"], "produces": ["r2prime"]},
    # Brain extraction: derive a binary brain mask from the multi-echo GRE magnitude alone. Standalone
    # producer of the `mask` artifact (mask is otherwise a provided input to every other stage), used to
    # generate masks for datasets that ship without one. mask is not a scored groundtruth artifact.
    "brain-extraction": {"consumes": ["magnitude", "params"], "produces": ["mask"]},
}

ARTIFACT_FILE = {
    "phase": "phase.nii.gz", "magnitude": "magnitude.nii.gz", "mask": "mask.nii.gz",
    "params": "params.json", "totalfield": "totalfield.nii.gz",
    "localfield": "localfield.nii.gz", "chimap": "chimap.nii.gz",
    "r2prime": "r2prime.nii.gz", "chi-para": "chi-para.nii.gz", "chi-dia": "chi-dia.nii.gz",
}

# how each produced artifact is scored: 'field' (total/local field), 'chi' (susceptibility), or
# 'chisep' (a single χ+/χ− source-separation component). r2prime is a consumed relaxation input.
ARTIFACT_KIND = {"totalfield": "field", "localfield": "field", "chimap": "chi",
                 "r2prime": "relaxation", "chi-para": "chisep", "chi-dia": "chisep"}

# artifacts that come from the ground-truth boundary (vs the public raw inputs) in isolated mode
GT_ARTIFACTS = {"totalfield", "localfield", "chimap", "chi-para", "chi-dia"}


# Stages with no magnitude-free method: the multi-echo magnitude is not a weighting nicety there,
# it IS the measurement. r2prime-generation estimates R2' from the signal decay across echoes;
# chi-separation fits its source model to that decay. brain-extraction derives the mask from it.
# "Optional when it isn't the only image input" is simply the wrong default for these.
MAGNITUDE_REQUIRED_STAGES = {"chi-separation", "r2prime-generation", "brain-extraction"}


def is_optional(stage: str, artifact: str, consumes: "list | None" = None,
                *, explicit: bool = False, opted_out: "set | tuple" = ()) -> bool:
    """Can a method of this stage run without `artifact`? The ONE rule the CLI parser, its help
    text and the workflow-engine wrappers all follow.

    - Anything outside the stage contract is optional by default (a method opted into it via
      `optional_inputs:`, e.g. a χ-separation net taking raw phase) — unless the method named it in
      `inputs:`, which makes it a required extra (MEDI cannot run without its magnitude weight).
    - Everything in the contract other than `magnitude` is required — `phase` included: a
      field-mapping stage cannot run without its phase.
    - `magnitude` is the one negotiable input, and the method decides:
        * required outright on a MAGNITUDE_REQUIRED_STAGES stage;
        * optional when the method names it in `optional_inputs:` (its code guards for the file
          being absent) — the explicit opt-out;
        * required when the method declares an explicit `inputs:` list containing it, because
          listing an input is saying the code reads it;
        * otherwise the legacy default: optional unless it is the only image input.

    `consumes` is the method's actual input list (runner._consumes) when it narrows the contract;
    `explicit` says that list came from a manifest `inputs:` key; `opted_out` is its
    `optional_inputs:`. The bare three-argument call keeps the stage-level answer."""
    base = STAGES[stage]["consumes"]
    if artifact in opted_out:
        return True                       # the method says its code guards for the file being absent
    if explicit and artifact in (consumes or ()):
        return False                      # the method named it in `inputs:` — its code reads it
    if artifact not in base:
        return True                       # opted-in extra, not declared required
    if artifact != "magnitude":
        return False
    if stage in MAGNITUDE_REQUIRED_STAGES:
        return False
    imgs = [a for a in (consumes or base) if a != "params"]
    return imgs != ["magnitude"]


def scorable(stage: str) -> bool:
    """Whether `qsm-ci run --truth` can score this stage's output: every produced artifact has a
    metric set AND the stage consumes the brain mask the scorer needs. brain-extraction fails both
    (its output IS the mask; there is no metric set for one)."""
    return (all(a in ARTIFACT_KIND for a in STAGES[stage]["produces"])
            and "mask" in STAGES[stage]["consumes"])


def input_artifact(stage: str) -> str:
    """The primary artifact a stage reads (used to label starter templates)."""
    return STAGES[stage]["consumes"][0]


def produced_artifact(stage: str) -> str:
    """The primary produced artifact (produces[0]) — for single-output scaffolding/labels.
    Multi-output-aware code (the runner, the scorer) uses produced_artifacts()."""
    return STAGES[stage]["produces"][0]


def produced_artifacts(stage: str) -> list:
    """Every artifact a stage produces — one for the linear QSM stages, two for χ-separation."""
    return list(STAGES[stage]["produces"])
