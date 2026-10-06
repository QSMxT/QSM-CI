// Measurement harness for the DIP-UP scoping exercise (QSM.rs #123). Not a CI gate
// (QSM.rs #140) and not committed to QSM.rs -- copy into QSM.rs `examples/` to run:
//   cp dipup_tract_parity.rs <QSM.rs>/examples/ && cargo run --release --example dipup_tract_parity --features ...
// See PROVENANCE.md (DIP-UP) and QSM.rs docs/DIPUP_SCOPING.md.
//!
//!   cargo run --release --example dipup_tract_parity --features onnx -- <dir>
//!
//! <dir> holds {phasenet3d,phunet3d}.onnx and ref_*_{in,out}.bin (f32, NCDHW).

use qsm_core::models::onnx::{OnnxModel, Tensor};

fn read_f32(path: &str) -> Vec<f32> {
    let b = std::fs::read(path).unwrap_or_else(|e| panic!("{path}: {e}"));
    b.chunks_exact(4).map(|c| f32::from_le_bytes([c[0], c[1], c[2], c[3]])).collect()
}

fn main() {
    let dir = std::env::args().nth(1).expect("usage: dipup_tract_parity <dir>");
    for (name, in_ch) in [("phasenet3d", 1usize), ("phunet3d", 2usize)] {
        let bytes = std::fs::read(format!("{dir}/{name}.onnx")).unwrap();
        let t0 = std::time::Instant::now();
        let model = OnnxModel::load(&bytes).expect("tract load");
        let load_s = t0.elapsed().as_secs_f64();

        let x = read_f32(&format!("{dir}/ref_{name}_in.bin"));
        let want = read_f32(&format!("{dir}/ref_{name}_out.bin"));
        let t1 = std::time::Instant::now();
        let out = model
            .run_single(&Tensor::new(vec![1, in_ch, 32, 32, 32], x))
            .expect("tract run");
        let run_s = t1.elapsed().as_secs_f64();
        assert_eq!(out.shape, vec![1, 9, 32, 32, 32], "{name}: output shape");
        assert_eq!(out.data.len(), want.len());

        let max_abs = out.data.iter().zip(&want).map(|(a, b)| (a - b).abs()).fold(0.0f32, f32::max);
        let scale = want.iter().fold(0.0f32, |m, v| m.max(v.abs()));

        // Compare the decoded class (argmax over the 9 wrap classes), which is what the
        // method consumes -- logit drift that never flips an argmax cannot change a wrap count.
        let n_vox = 32 * 32 * 32;
        let argmax = |d: &[f32], i: usize| -> usize {
            (0..9).max_by(|&a, &b| d[a * n_vox + i].partial_cmp(&d[b * n_vox + i]).unwrap()).unwrap()
        };
        let disagree = (0..n_vox).filter(|&i| argmax(&out.data, i) != argmax(&want, i)).count();

        // Pearson correlation over all logits.
        let n = want.len() as f64;
        let (ma, mb) = (
            out.data.iter().map(|&v| v as f64).sum::<f64>() / n,
            want.iter().map(|&v| v as f64).sum::<f64>() / n,
        );
        let (mut sab, mut saa, mut sbb) = (0.0, 0.0, 0.0);
        for (&a, &b) in out.data.iter().zip(&want) {
            let (da, db) = (a as f64 - ma, b as f64 - mb);
            sab += da * db;
            saa += da * da;
            sbb += db * db;
        }
        println!(
            "{name}: tract OK (load {load_s:.1}s, run {run_s:.2}s) | corr {:.8} | \
             max|Δ| {max_abs:.3e} (|logit|max {scale:.1}, rel {:.3e}) | \
             argmax disagreement {disagree}/{n_vox} = {:.5}%",
            sab / (saa.sqrt() * sbb.sqrt()),
            max_abs / scale,
            100.0 * disagree as f64 / n_vox as f64,
        );
    }
}
