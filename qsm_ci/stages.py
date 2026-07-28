"""Stage & artifact registry — mirrors ../stages.yml.

Kept as plain Python (like scripts/pipeline.py) so the CLI needs no YAML dependency and works
standalone once installed. If stages.yml changes, update this too.
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
