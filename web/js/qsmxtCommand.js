// The equivalent `qsmxt run` command for a QSM-CI pipeline, or null when there is none.
//
// QSM-CI reproduces the scored artifact; QSMxT runs the same method(s) end-to-end from BIDS. A
// pipeline gets a command only when every step runs on the QSM.rs engine (each algorithm's
// self-described `engine` contains "QSM.rs") and each step's stage has a faithful `qsmxt run` flag.
// The flag value is the method's `algorithm` (from web/algorithms.json), never its QSM-CI slug;
// `qsmxt_value` in algorithm.yml overrides it where QSMxT names the method differently, and
// `qsmxt_args` adds any flags QSMxT needs to run it the way QSM-CI does.
//
// Pure (no DOM), so tests/test_web_qsmxt_command.py can run it under node.

// Stage -> `qsmxt run` flag. Stages missing here have no faithful equivalent:
// - unwrap+bfr (HARPERELLA, iHARPERELLA): `qsmxt run` always unwraps and fits the field first and
//   runs `--bf-algorithm harperella` on that unwrapped total field, while QSM-CI runs it on the
//   wrapped first-echo phase, so the command would describe a different pipeline.
// - brain-extraction, chi-separation, r2prime-generation: not `qsmxt run` reconstruction stages.
// bfr+dipole (TGV, TFI, QSMART) and end-to-end inversions are a single `--qsm-algorithm`: QSMxT skips
// its own background-removal stage for them.
const QSMXT_FLAG = {
  "field-mapping": "--unwrapping-algorithm",
  bfr: "--bf-algorithm",
  dipole: "--qsm-algorithm",
  "bfr+dipole": "--qsm-algorithm",
  "end-to-end": "--qsm-algorithm",
};

export function qsmxtCommand(steps, bySlug) {
  if (!steps.length) return null;
  const parts = ["qsmxt run /path/to/bids /path/to/output"];
  for (const s of steps) {
    const a = bySlug[s];
    if (!a || !a.engine || !a.engine.includes("QSM.rs")) return null;  // every step on the QSM.rs engine
    const flag = QSMXT_FLAG[a.stage];
    const value = a.qsmxt_value || a.algorithm;
    if (!flag || !value) return null;  // no faithful qsmxt run equivalent -> no command
    parts.push([flag, value, ...(a.qsmxt_args || [])].join(" "));
  }
  return parts.join(" \\\n  ");
}
