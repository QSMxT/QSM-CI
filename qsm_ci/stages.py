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


def is_optional(stage: str, artifact: str, consumes: "list | None" = None) -> bool:
    """Can a method of this stage run without `artifact`? The ONE rule the CLI parser, its help
    text and the workflow-engine wrappers all follow.

    - Anything outside the stage contract (a method opted into it via `optional_inputs:`, e.g. a
      χ-separation net taking raw phase) is optional by definition.
    - `magnitude` is optional when it is one of several image inputs (MEDI weights with it, plain
      TKD ignores it) and required when it is the ONLY image input (brain-extraction,
      r2prime-generation read nothing else).
    - Everything else in the contract is required — `phase` included: a field-mapping stage cannot
      run without its phase.
    `consumes` is the method's actual input list (runner._consumes) when it narrows the contract."""
    base = STAGES[stage]["consumes"]
    if artifact not in base:
        return True
    if artifact == "magnitude":
        imgs = [a for a in (consumes or base) if a != "params"]
        return imgs != ["magnitude"]
    return False


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
