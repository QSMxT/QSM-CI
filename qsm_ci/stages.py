"""Stage & artifact registry — mirrors ../stages.yml.

Kept as plain Python (like scripts/pipeline.py) so the CLI needs no YAML dependency and works
standalone once installed. If stages.yml changes, update this too.
"""

from __future__ import annotations

# stage/span -> consumed and produced canonical artifacts
STAGES = {
    "field-mapping": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["totalfield"]},
    "bfr": {"consumes": ["totalfield", "mask", "params"], "produces": ["localfield"]},
    "dipole": {"consumes": ["localfield", "mask", "params", "magnitude"], "produces": ["chimap"]},
    "unwrap+bfr": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["localfield"]},
    "bfr+dipole": {"consumes": ["totalfield", "mask", "params"], "produces": ["chimap"]},
    "end-to-end": {"consumes": ["phase", "magnitude", "mask", "params"], "produces": ["chimap"]},
}

ARTIFACT_FILE = {
    "phase": "phase.nii.gz", "magnitude": "magnitude.nii.gz", "mask": "mask.nii.gz",
    "params": "params.json", "totalfield": "totalfield.nii.gz",
    "localfield": "localfield.nii.gz", "chimap": "chimap.nii.gz",
}

# how each produced artifact is scored: 'field' (total/local field) or 'chi' (susceptibility)
ARTIFACT_KIND = {"totalfield": "field", "localfield": "field", "chimap": "chi"}

# artifacts that come from the ground-truth boundary (vs the public raw inputs) in isolated mode
GT_ARTIFACTS = {"totalfield", "localfield", "chimap"}


def input_artifact(stage: str) -> str:
    """The primary artifact a stage reads (used to label starter templates)."""
    return STAGES[stage]["consumes"][0]


def produced_artifact(stage: str) -> str:
    return STAGES[stage]["produces"][0]
