"""Auto-generate workflow-engine wrappers from the QSM-CI stage contract.

Every QSM-CI algorithm is invoked the same way — ``qsm-ci run <slug> --<artifact> … -o <produced>`` —
and the artifacts each stage consumes/produces are declared once in :mod:`qsm_ci.stages` (mirroring
``stages.yml``). So a wrapper for any workflow engine is just a template over that contract; this
module generates them, which keeps them in lock-step with the contract instead of hand-maintained.

Supported engines (``qsm-ci interface <engine>``):

- ``cwl``       — a CommandLineTool per stage (``$graph`` when several)
- ``snakemake`` — a rule per stage
- ``nextflow``  — a DSL2 process per stage

The container runs underneath the CLI (docker/podman/apptainer/local), so none of the wrappers need
the engine's own container support. The two Python engines ship as ready-to-import modules instead:
:mod:`qsm_ci.nipype` and :mod:`qsm_ci.pydra`.
"""

from __future__ import annotations

from .stages import ARTIFACT_FILE, STAGES, is_optional, produced_artifact, produced_artifacts


def _optional(stage: str, artifact: str) -> bool:
    """Consumed artifacts a stage can run without: the CLI's own rule (stages.is_optional — magnitude
    when it isn't the sole image input) plus params, which a caller may replace with acquisition
    flags. Same rule as `qsm-ci run`, so a wrapper never marks required what the CLI would reject."""
    return artifact == "params" or is_optional(stage, artifact)

CORE_STAGES = ["field-mapping", "bfr", "dipole"]
ENGINES = ("cwl", "snakemake", "nextflow")

STAGE_DESC = {
    "field-mapping": "phase → total field",
    "bfr": "total field → local field",
    "dipole": "local field → susceptibility (χ)",
    "unwrap+bfr": "phase → local field",
    "bfr+dipole": "total field → susceptibility (χ)",
    "end-to-end": "phase → susceptibility (χ)",
}


def _ident(stage: str) -> str:
    """A safe identifier for a stage/span name (``bfr+dipole`` -> ``bfr_dipole``)."""
    return stage.replace("+", "_").replace("-", "_")


def _consumes(stage: str) -> list:
    return STAGES[stage]["consumes"]


# --- CWL --------------------------------------------------------------------------------------

def _cwl_tool(stage: str, indent: str = "") -> str:
    prods = produced_artifacts(stage)
    multi = len(prods) > 1  # χ-separation writes two source maps into an output directory
    lines = [
        "class: CommandLineTool",
        f"label: QSM-CI {stage} stage ({STAGE_DESC.get(stage, stage)})",
        "baseCommand: [qsm-ci, run]",
        "inputs:",
        "  slug: { type: string, inputBinding: { position: 1 } }",
    ]
    for art in _consumes(stage):
        # quote the optional type — bare `File?` is ambiguous in YAML flow style. position:2 keeps
        # every flag after the positional slug (position:1), else unpositioned flags sort before it.
        t = '"File?"' if _optional(stage, art) else "File"
        lines.append(f"  {art}: {{ type: {t}, inputBinding: {{ prefix: --{art}, position: 2 }} }}")
    default_out = "out" if multi else ARTIFACT_FILE[prods[0]]
    lines.append(
        f"  out: {{ type: string, default: {default_out}, "
        f"inputBinding: {{ prefix: -o, position: 2 }} }}")
    lines.append("outputs:")
    for art in prods:  # single-output: glob the -o path; multi (dir): glob each file inside it
        glob = f"$(inputs.out)/{ARTIFACT_FILE[art]}" if multi else "$(inputs.out)"
        lines.append(f"  {art}: {{ type: File, outputBinding: {{ glob: {glob} }} }}")
    return "\n".join(indent + ln for ln in lines) if indent else "\n".join(lines)


def _cwl(stages: list) -> str:
    if len(stages) == 1:
        return "cwlVersion: v1.2\n" + _cwl_tool(stages[0]) + "\n"
    out = ["cwlVersion: v1.2", "$graph:"]
    for s in stages:
        out.append(f"  - id: {_ident(s)}")
        out.append(_cwl_tool(s, indent="    "))
    return "\n".join(out) + "\n"


# --- Snakemake --------------------------------------------------------------------------------

SNAKEMAKE_OPTIONAL_HELPER = '''import os

def optional(**artifacts):
    """`--flag path` for each optional artifact that is actually present.

    The stage contract names these (so the rule works with any method slug), but they are not
    required: `magnitude` only some methods weight with, and `params.json` a caller may replace
    with acquisition flags. Listing them under `input:` would make Snakemake refuse to run the
    rule until the files exist.
    """
    return " ".join(f"--{flag} {path}" for flag, path in artifacts.items() if os.path.exists(path))
'''


def _snakemake_rule(stage: str, slug: str) -> str:
    prods = produced_artifacts(stage)
    multi = len(prods) > 1  # χ-separation writes two files into an output directory
    required = [a for a in _consumes(stage) if not _optional(stage, a)]
    opt = [a for a in _consumes(stage) if _optional(stage, a)]
    inputs = "\n".join(f'        {a}="{ARTIFACT_FILE[a]}",' for a in required)
    flags = " ".join(f"--{a} {{input.{a}}}" for a in required)
    if opt:  # resolved when the rule runs: passed only for the files that are there
        flags += " {params.optional}"
    outputs = "\n".join(f'        {_ident(a)}="{ARTIFACT_FILE[a]}",' for a in prods)
    params = [f'        slug="{slug}",']
    if opt:
        # a lambda, so the existence check happens when the job is scheduled — after any earlier
        # rule that produces one of these files has run, not at Snakefile parse time.
        params.append("        optional=lambda wildcards: optional("
                      + ", ".join(f'{a}="{ARTIFACT_FILE[a]}"' for a in opt) + "),")
    # -o is a file for single-output stages, a directory for χ-separation (writes both maps into it).
    out_ref = "." if multi else f"{{output.{_ident(prods[0])}}}"
    return (
        f"rule {_ident(stage)}:\n"
        f"    input:\n{inputs}\n"
        f"    output:\n{outputs}\n"
        f'    params:\n' + "\n".join(params) + "\n"
        f'    shell:\n        "qsm-ci run {{params.slug}} {flags} -o {out_ref}"'
    )


def _snakemake_head(comment: str, stages: list) -> str:
    """The generated Snakefile's preamble: the comment, plus the `optional()` helper whenever any
    rule in the file calls it. Both Snakemake generators go through here — emitting the helper in
    one and not the other left `optional()` undefined at parse time, and snakemake exited 1 before
    running a thing."""
    if any(_optional(s, a) for s in stages for a in _consumes(s)):
        return comment + SNAKEMAKE_OPTIONAL_HELPER + "\n"
    return comment


def _snakemake(stages: list, slug: str) -> str:
    head = _snakemake_head(
        "# QSM-CI Snakemake rules — auto-generated by `qsm-ci interface snakemake`.\n"
        "# Set params.slug to pick which method runs each stage.\n\n", stages)
    return head + "\n\n".join(_snakemake_rule(s, slug) for s in stages) + "\n"


# --- Nextflow (DSL2) --------------------------------------------------------------------------

# `params` is Nextflow's own global (the pipeline's command-line parameters), so an input channel
# of that name shadows it inside the process body. Every artifact gets a safe variable name here.
NF_VAR = {"params": "params_json"}
# Sentinel for an optional input that wasn't supplied: Nextflow has no optional `path` input, so the
# caller stages a placeholder file and the script drops the flag. Same idiom nf-core uses.
NF_ABSENT = "NO_FILE"


def _nf_var(artifact: str) -> str:
    return NF_VAR.get(artifact, artifact)


def _nextflow_process(stage: str, slug: str) -> str:
    prods = produced_artifacts(stage)
    multi = len(prods) > 1  # χ-separation emits two files (into the task dir via -o .)
    consumes = _consumes(stage)
    opt = [a for a in consumes if _optional(stage, a)]
    ins = "\n".join(
        ["    val slug"]
        + [f"    path {_nf_var(a)}" + (f"      // optional: pass file('{NF_ABSENT}') to skip"
                                       if a in opt else "")
           for a in consumes])
    flags = " ".join(f"--{a} ${{{_nf_var(a)}}}" for a in consumes if a not in opt)
    outs = "\n".join(f"    path '{ARTIFACT_FILE[a]}'" for a in prods)
    out_ref = "." if multi else ARTIFACT_FILE[prods[0]]
    # An optional artifact contributes its flag only when a real file was staged — the stage
    # contract names it so the process works with any method slug, but not every method needs it.
    opt_defs = "".join(
        f"    def {_nf_var(a)}_flag = {_nf_var(a)}.name == '{NF_ABSENT}' ? '' : "
        f'"--{a} ${{{_nf_var(a)}}}"\n' for a in opt)
    opt_refs = "".join(f" ${{{_nf_var(a)}_flag}}" for a in opt)
    return (
        f"process {_ident(stage)} {{\n"
        f"    input:\n{ins}\n\n"
        f"    output:\n{outs}\n\n"
        f"    script:\n{opt_defs}"
        f'    """\n'
        f"    qsm-ci run ${{slug}} {flags}{opt_refs} -o {out_ref}\n"
        f'    """\n'
        f"}}"
    )


def _nextflow(stages: list, slug: str) -> str:
    head = "// QSM-CI Nextflow processes — auto-generated by `qsm-ci interface nextflow`.\n" \
           "// The `slug` input picks which method runs each stage.\n" \
           f"// Optional inputs: Nextflow has no optional `path`, so pass file('{NF_ABSENT}') — an\n" \
           f"// empty placeholder you create once (`touch {NF_ABSENT}`) — and the flag is dropped.\n" \
           "nextflow.enable.dsl = 2\n\n"
    return head + "\n\n".join(_nextflow_process(s, slug) for s in stages) + "\n"


# --- end-to-end pipeline (a method per stage, chained phase -> chi) ----------------------------

PIPELINE = ["field-mapping", "bfr", "dipole"]  # the canonical phase -> chi chain


def _pipeline_io(stages: list) -> tuple:
    """(produced, top) — produced maps an artifact to the index of the stage that makes it; top is
    the ordered list of artifacts consumed but never produced upstream (the pipeline's own inputs)."""
    produced = {produced_artifact(s): i for i, (s, _) in enumerate(stages)}
    top: list = []
    for s, _ in stages:
        for a in STAGES[s]["consumes"]:
            if a not in produced and a not in top:
                top.append(a)
    return produced, top


def _stages(slugs: list) -> list:
    if len(slugs) != len(PIPELINE):
        raise ValueError(f"pipeline needs {len(PIPELINE)} slugs (field-mapping, bfr, dipole), got {len(slugs)}")
    return list(zip(PIPELINE, slugs))


def _cwl_pipeline(stages: list) -> str:
    produced, top = _pipeline_io(stages)
    final = stages[-1][0]
    fprod = produced_artifact(final)
    out = ["cwlVersion: v1.2", "class: Workflow",
           "# run:  cwltool pipeline.cwl --phase p.nii.gz --magnitude m.nii.gz --mask mask.nii.gz",
           "#       (--magnitude/--params are optional — only some methods read them)",
           "inputs:"]
    # Optional for the workflow when every stage that consumes it can run without it — otherwise
    # cwltool would demand a params.json for a pipeline of methods that read none.
    consumers = {a: [s for s, _ in stages if a in STAGES[s]["consumes"]] for a in top}
    out += [f'  {a}: {"File?" if all(_optional(s, a) for s in consumers[a]) else "File"}'
            for a in top]
    out += ["outputs:", f"  {fprod}:", "    type: File", f"    outputSource: {_ident(final)}/{fprod}",
            "steps:"]
    for stage, slug in stages:
        sid, prod = _ident(stage), produced_artifact(stage)
        out.append(f"  {sid}:")
        out.append("    run:")
        out.append("      class: CommandLineTool")
        out.append("      baseCommand: [qsm-ci, run]")
        out.append("      inputs:")
        out.append(f"        slug: {{ type: string, default: {slug}, inputBinding: {{ position: 1 }} }}")
        for a in STAGES[stage]["consumes"]:
            t = '"File?"' if _optional(stage, a) else "File"
            out.append(f"        {a}: {{ type: {t}, inputBinding: {{ prefix: --{a}, position: 2 }} }}")
        out.append(f"        out: {{ type: string, default: {ARTIFACT_FILE[prod]}, inputBinding: {{ prefix: -o, position: 2 }} }}")
        out.append("      outputs:")
        out.append(f"        {prod}: {{ type: File, outputBinding: {{ glob: {ARTIFACT_FILE[prod]} }} }}")
        out.append("    in:")
        for a in STAGES[stage]["consumes"]:
            src = f"{_ident(stages[produced[a]][0])}/{a}" if a in produced else a
            out.append(f"      {a}: {src}")
        out.append(f"    out: [{prod}]")
    return "\n".join(out) + "\n"


def _snakemake_pipeline(stages: list) -> str:
    head = _snakemake_head(
        "# QSM-CI end-to-end pipeline — auto-generated by `qsm-ci interface snakemake --pipeline`.\n"
        "# Put phase/mask in the working dir (magnitude/params too if your methods read them),\n"
        "# then:  snakemake -c1 chimap.nii.gz\n"
        "# The rules chain by filename (totalfield -> localfield -> chimap).\n\n",
        [stage for stage, _ in stages])
    return head + "\n\n".join(_snakemake_rule(stage, slug) for stage, slug in stages) + "\n"


def _nextflow_pipeline(stages: list) -> str:
    produced, top = _pipeline_io(stages)
    parts = ["// QSM-CI end-to-end pipeline — auto-generated by `qsm-ci interface nextflow --pipeline`.",
             "// run:  nextflow run qsm.nf --phase p.nii.gz --magnitude m.nii.gz --mask mask.nii.gz \\",
             "//         --params p.json --outdir results",
             "// --magnitude/--params are optional; omit either and the sentinel "
             f"file('{NF_ABSENT}') is staged",
             f"// instead (create it once with `touch {NF_ABSENT}`) and the flag is dropped.",
             "nextflow.enable.dsl = 2", ""]
    parts += [_nextflow_process(stage, slug) + "\n" for stage, slug in stages]
    wf = ["workflow {"]
    for stage, slug in stages:
        sid = _ident(stage)
        args = [f"'{slug}'"]
        for a in STAGES[stage]["consumes"]:
            if a in produced:
                args.append(f"{_ident(stages[produced[a]][0])}_out")
            elif _optional(stage, a):  # not given on the command line → stage the sentinel
                args.append(f"(params.{a} ? file(params.{a}) : file('{NF_ABSENT}'))")
            else:
                args.append(f"file(params.{a})")
        wf.append(f"    {sid}_out = {sid}({', '.join(args)})")
    fprod = produced_artifact(stages[-1][0])
    wf.append(f"    {_ident(stages[-1][0])}_out.collectFile(name: '{ARTIFACT_FILE[fprod]}', "
              "storeDir: params.outdir ?: '.')")
    wf.append("}")
    parts.append("\n".join(wf))
    return "\n".join(parts) + "\n"


_PIPELINE_GENERATORS = {"cwl": _cwl_pipeline, "snakemake": _snakemake_pipeline, "nextflow": _nextflow_pipeline}


def generate_pipeline(engine: str, slugs: list) -> str:
    """Return an end-to-end (phase → χ) pipeline wrapper: field-mapping → bfr → dipole, one method
    (slug) per stage, chained. Only the declarative engines — nipype/pydra compose in Python."""
    if engine not in _PIPELINE_GENERATORS:
        raise ValueError(f"no pipeline generator for '{engine}'; choose from {', '.join(_PIPELINE_GENERATORS)}")
    return _PIPELINE_GENERATORS[engine](_stages(slugs))


# --- entry point ------------------------------------------------------------------------------

_GENERATORS = {
    "cwl": lambda stages, slug: _cwl(stages),
    "snakemake": _snakemake,
    "nextflow": _nextflow,
}


def generate(engine: str, stage: str | None = None, slug: str = "SLUG") -> str:
    """Return the wrapper text for ``engine``. ``stage`` defaults to the three core stages."""
    if engine not in _GENERATORS:
        raise ValueError(f"unknown engine '{engine}'; choose from {', '.join(ENGINES)}")
    if stage is not None and stage not in STAGES:
        raise ValueError(f"unknown stage '{stage}'; choose from {', '.join(STAGES)}")
    stages = [stage] if stage else list(CORE_STAGES)
    return _GENERATORS[engine](stages, slug)
