cwlVersion: v1.2
class: Workflow
# run:  cwltool pipeline.cwl --phase p.nii.gz --magnitude m.nii.gz --mask mask.nii.gz --params p.json
inputs:
  phase: File
  magnitude: File
  mask: File
  params: File
outputs:
  chimap:
    type: File
    outputSource: dipole/chimap
steps:
  field_mapping:
    run:
      class: CommandLineTool
      baseCommand: [qsm-ci, run]
      inputs:
        slug: { type: string, default: romeo-fieldmap, inputBinding: { position: 1 } }
        phase: { type: File, inputBinding: { prefix: --phase, position: 2 } }
        magnitude: { type: "File?", inputBinding: { prefix: --magnitude, position: 2 } }
        mask: { type: File, inputBinding: { prefix: --mask, position: 2 } }
        params: { type: "File?", inputBinding: { prefix: --params, position: 2 } }
        out: { type: string, default: totalfield.nii.gz, inputBinding: { prefix: -o, position: 2 } }
      outputs:
        totalfield: { type: File, outputBinding: { glob: totalfield.nii.gz } }
    in:
      phase: phase
      magnitude: magnitude
      mask: mask
      params: params
    out: [totalfield]
  bfr:
    run:
      class: CommandLineTool
      baseCommand: [qsm-ci, run]
      inputs:
        slug: { type: string, default: vsharp, inputBinding: { position: 1 } }
        totalfield: { type: File, inputBinding: { prefix: --totalfield, position: 2 } }
        mask: { type: File, inputBinding: { prefix: --mask, position: 2 } }
        params: { type: "File?", inputBinding: { prefix: --params, position: 2 } }
        out: { type: string, default: localfield.nii.gz, inputBinding: { prefix: -o, position: 2 } }
      outputs:
        localfield: { type: File, outputBinding: { glob: localfield.nii.gz } }
    in:
      totalfield: field_mapping/totalfield
      mask: mask
      params: params
    out: [localfield]
  dipole:
    run:
      class: CommandLineTool
      baseCommand: [qsm-ci, run]
      inputs:
        slug: { type: string, default: rts, inputBinding: { position: 1 } }
        localfield: { type: File, inputBinding: { prefix: --localfield, position: 2 } }
        mask: { type: File, inputBinding: { prefix: --mask, position: 2 } }
        params: { type: "File?", inputBinding: { prefix: --params, position: 2 } }
        out: { type: string, default: chimap.nii.gz, inputBinding: { prefix: -o, position: 2 } }
      outputs:
        chimap: { type: File, outputBinding: { glob: chimap.nii.gz } }
    in:
      localfield: bfr/localfield
      mask: mask
      params: params
    out: [chimap]
