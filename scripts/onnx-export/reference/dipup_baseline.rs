// Measurement harness for the DIP-UP scoping exercise (QSM.rs #123). Not a CI gate
// (QSM.rs #140) and not committed to QSM.rs -- copy into QSM.rs `examples/` to run:
//   cp dipup_baseline.rs <QSM.rs>/examples/ && cargo run --release --example dipup_baseline --features ...
// See PROVENANCE.md (DIP-UP) and QSM.rs docs/DIPUP_SCOPING.md.
//!
//!   cargo run --release --example dipup_baseline --features parallel -- <outdir>

use qsm_core::io::{read_nifti_file, save_nifti_to_file};
use qsm_core::unwrap::{
    laplacian_unwrap, unwrap_bestpath, unwrap_romeo, BestPathParams, RomeoParams,
};
use qsm_core::Grid;
use std::path::Path;
use std::time::Instant;

fn main() {
    let out = std::env::args().nth(1).unwrap_or_else(|| "/tmp/dipup".into());
    std::fs::create_dir_all(&out).unwrap();
    let anat = "bids/sub-1/anat";
    let deriv = "bids/derivatives/qsm-forward/sub-1/anat";

    let m = read_nifti_file(Path::new(&format!("{deriv}/sub-1_mask.nii"))).unwrap();
    let mask: Vec<u8> = m.data.iter().map(|&v| if v > 0.5 { 1 } else { 0 }).collect();
    let (nx, ny, nz) = m.dims;
    let grid = Grid::new(nx, ny, nz, m.voxel_size.0, m.voxel_size.1, m.voxel_size.2);
    eprintln!("volume {nx}x{ny}x{nz}, mask {} voxels", mask.iter().filter(|&&x| x != 0).count());

    for echo in 1..=4 {
        let ph = read_nifti_file(Path::new(&format!(
            "{anat}/sub-1_echo-{echo}_part-phase_MEGRE.nii"
        )))
        .unwrap();
        let mag = read_nifti_file(Path::new(&format!(
            "{anat}/sub-1_echo-{echo}_part-mag_MEGRE.nii"
        )))
        .unwrap();

        for method in ["romeo", "laplacian", "bestpath"] {
            let t = Instant::now();
            let uw = match method {
                "romeo" => unwrap_romeo(
                    &ph.data, &mag.data, None, 0.0, 0.0, &mask, &RomeoParams::default(), &grid,
                ),
                "laplacian" => laplacian_unwrap(&ph.data, &mask, &grid),
                _ => unwrap_bestpath(&ph.data, &mask, &BestPathParams::default(), &grid),
            };
            eprintln!("echo {echo} {method}: {:.1}s", t.elapsed().as_secs_f64());
            save_nifti_to_file(
                Path::new(&format!("{out}/uw_{method}_echo{echo}.nii")),
                &uw, (nx, ny, nz), grid.voxel_size, &m.affine,
            )
            .unwrap();
        }
    }
    eprintln!("wrote baselines to {out}");
}
