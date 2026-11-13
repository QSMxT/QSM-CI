// Measurement harness for the DIP-UP scoping exercise (QSM.rs #123). Not a CI gate
// (QSM.rs #140) and not committed to QSM.rs -- copy into QSM.rs `examples/` to run:
//   cargo run --release --example dipup_downstream --features parallel -- <uwdir> <outdir>
//! Correlating unwrapped phase against a reference is a weak test: two unwrappings can differ
//! by a harmonic field that background-field removal deletes, leaving the local field — and so
//! the susceptibility — identical. So this walks the whole chain for each unwrapper and scores
//! against the phantom ground truth at every stage:
//!
//!   per-echo unwrapped phase  ->  linear fit over TE  ->  total field (ppm)
//!                             ->  V-SHARP            ->  local field (ppm)   vs fieldmap-local
//!                             ->  RTS                ->  chi (ppm)           vs Chimap
//!
//! Run:
//!   cargo run --release --example dipup_downstream --features parallel -- <uwdir> <outdir>
//!
//! <uwdir> holds uw_<method>_echo{1..4}.nii for the CNN variants (written by
//! ref_dipup.py export-unwrapped); the classical ones come from dipup_baseline.rs output,
//! which is expected in the same directory.

use qsm_core::bgremove::{vsharp, VsharpParams};
use qsm_core::inversion::{rts, RtsParams};
use qsm_core::io::{read_nifti_file, save_nifti_to_file};
use qsm_core::Grid;
use std::path::Path;

const TES: [f64; 4] = [0.004, 0.012, 0.020, 0.028];
const GAMMA: f64 = 42.576e6;
const B0: f64 = 7.0;

/// Pearson correlation, NRMSE normalized by the reference std, over masked voxels.
fn score(out: &[f64], truth: &[f64], mask: &[u8]) -> (f64, f64) {
    let idx: Vec<usize> = (0..truth.len()).filter(|&i| mask[i] != 0).collect();
    let n = idx.len() as f64;
    let (mt, mo) = (
        idx.iter().map(|&i| truth[i]).sum::<f64>() / n,
        idx.iter().map(|&i| out[i]).sum::<f64>() / n,
    );
    let (mut sto, mut stt, mut soo, mut sse) = (0.0, 0.0, 0.0, 0.0);
    for &i in &idx {
        let (dt, dv) = (truth[i] - mt, out[i] - mo);
        sto += dt * dv;
        stt += dt * dt;
        soo += dv * dv;
        sse += (truth[i] - out[i]).powi(2);
    }
    (sto / (stt.sqrt() * soo.sqrt()), (sse / n).sqrt() / (stt / n).sqrt())
}

/// Per-voxel linear fit of unwrapped phase over TE -> total field in ppm.
fn echo_fit(uw: &[Vec<f64>], mask: &[u8], n: usize) -> Vec<f64> {
    let te_mean = TES.iter().sum::<f64>() / TES.len() as f64;
    let dt: Vec<f64> = TES.iter().map(|t| t - te_mean).collect();
    let sdt2: f64 = dt.iter().map(|d| d * d).sum();
    let mut field = vec![0.0; n];
    for i in 0..n {
        if mask[i] == 0 {
            continue;
        }
        let pbar = uw.iter().map(|e| e[i]).sum::<f64>() / uw.len() as f64;
        let slope: f64 = uw.iter().zip(&dt).map(|(e, d)| d * (e[i] - pbar)).sum::<f64>() / sdt2;
        // rad/s -> Hz -> ppm
        field[i] = slope / (2.0 * std::f64::consts::PI) * 1e6 / (GAMMA * B0);
    }
    field
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let uwdir = args.get(1).expect("usage: dipup_downstream <uwdir> <outdir>");
    let outdir = args.get(2).expect("usage: dipup_downstream <uwdir> <outdir>");
    std::fs::create_dir_all(outdir).unwrap();
    let deriv = "bids/derivatives/qsm-forward/sub-1/anat";

    let m = read_nifti_file(Path::new(&format!("{deriv}/sub-1_mask.nii"))).unwrap();
    let mask: Vec<u8> = m.data.iter().map(|&v| if v > 0.5 { 1 } else { 0 }).collect();
    let (nx, ny, nz) = m.dims;
    let n = nx * ny * nz;
    let grid = Grid::new(nx, ny, nz, m.voxel_size.0, m.voxel_size.1, m.voxel_size.2);
    let truth_lf = read_nifti_file(Path::new(&format!("{deriv}/sub-1_fieldmap-local.nii"))).unwrap();
    let truth_chi = read_nifti_file(Path::new(&format!("{deriv}/sub-1_Chimap.nii"))).unwrap();
    let truth_tf = read_nifti_file(Path::new(&format!("{deriv}/sub-1_fieldmap.nii"))).unwrap();

    println!(
        "{:<14} {:>18} {:>18} {:>18}",
        "unwrapper", "total field", "local field (VSHARP)", "chi (RTS)"
    );
    println!("{:<14} {:>18} {:>18} {:>18}", "", "corr / NRMSE", "corr / NRMSE", "corr / NRMSE");

    for meth in ["romeo", "bestpath", "laplacian", "phasenet3d", "phunet3d"] {
        let uw: Vec<Vec<f64>> = (1..=4)
            .map(|e| {
                let p = format!("{uwdir}/uw_{meth}_echo{e}.nii");
                read_nifti_file(Path::new(&p)).unwrap_or_else(|e| panic!("{p}: {e}")).data
            })
            .collect();

        let tf = echo_fit(&uw, &mask, n);
        let (r_tf, e_tf) = score(&tf, &truth_tf.data, &mask);

        // V-SHARP returns an eroded mask; score the local field and chi on that mask, which is
        // what a real pipeline would carry forward.
        let (lf, vmask) = vsharp(&tf, &mask, &grid, &VsharpParams::default(), |_, _| {});
        let (r_lf, e_lf) = score(&lf, &truth_lf.data, &vmask);

        let chi = rts(&lf, &vmask, &grid, (0.0, 0.0, 1.0), &RtsParams::default(), |_, _| {});
        let (r_chi, e_chi) = score(&chi, &truth_chi.data, &vmask);

        println!(
            "{meth:<14} {:>8.4} /{:>7.4} {:>8.4} /{:>7.4} {:>8.4} /{:>7.4}",
            r_tf, e_tf, r_lf, e_lf, r_chi, e_chi
        );

        for (name, data, msk) in [
            ("totalfield", &tf, &mask),
            ("localfield", &lf, &vmask),
            ("chi", &chi, &vmask),
        ] {
            let masked: Vec<f64> =
                (0..n).map(|i| if msk[i] != 0 { data[i] } else { 0.0 }).collect();
            save_nifti_to_file(
                Path::new(&format!("{outdir}/{name}_{meth}.nii")),
                &masked,
                (nx, ny, nz),
                grid.voxel_size,
                &m.affine,
            )
            .unwrap();
        }
    }
    println!("\nwrote per-stage volumes to {outdir}");
}
