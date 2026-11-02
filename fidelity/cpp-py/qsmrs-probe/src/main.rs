//! qsmrs-probe: QSM.rs's ports of the C++/Python originals, called directly (see Cargo.toml).
//!
//!   qsmrs-probe n4       IN OUT [BIAS]
//!   qsmrs-probe bet      IN OUT [--f F] [--subdivisions N]
//!   qsmrs-probe bestpath PHASE MASK OUT
//!   qsmrs-probe gibbs    IN OUT                    (DIPY 2-D mode, slice axis 2; 4-D: each volume)
//!   qsmrs-probe mppca    IN MASK OUT [--patch-radius R]
//!   qsmrs-probe wavesep  CHI R2P MASK OUT_PARA OUT_DIA [--dr DR]
//!   qsmrs-probe prelude  PHASE MASK OUT [--n N] [--slicewise 1]   (3-D or 4-D: each echo alone)
//!   qsmrs-probe morph    MASK OUT_PREFIX [--iterations N] [--radius R]
//!                        (writes _erode, _dilate (6-connected, N iterations), _close (ball R))
//!
//! Defaults are each port's own `Default`. Outputs are float64 NIfTI; WaveSep writes χ− as a
//! positive magnitude, as QSM-CI's chi-separation contract does.
use qsm_core::io::{load_nifti_4d, read_nifti_file, save_nifti_4d_to_file, save_nifti_to_file};
use qsm_core::Grid;
use std::path::Path;

fn arg_after(args: &[String], flag: &str) -> Option<String> {
    args.iter().position(|a| a == flag).and_then(|i| args.get(i + 1).cloned())
}

fn positional(args: &[String]) -> Vec<String> {
    let mut out = vec![];
    let mut skip = false;
    for a in args {
        if skip { skip = false; continue; }
        if a.starts_with("--") { skip = true; continue; }
        out.push(a.clone());
    }
    out
}

fn load4(path: &str) -> (Vec<f64>, (usize, usize, usize), usize, (f64, f64, f64), [f64; 16]) {
    let bytes = std::fs::read(path).expect("read");
    let (data, (nx, ny, nz, nt), vs, aff) = load_nifti_4d(&bytes).expect("nifti");
    (data, (nx, ny, nz), nt.max(1), vs, aff)
}

/// Volume-major (as stored) to voxel-major (what gibbs_unring / mppca_denoise take), and back.
fn interleave(data: &[f64], nvox: usize, nt: usize) -> Vec<f64> {
    let mut out = vec![0.0; nvox * nt];
    for t in 0..nt { for v in 0..nvox { out[v * nt + t] = data[t * nvox + v]; } }
    out
}
fn deinterleave(data: &[f64], nvox: usize, nt: usize) -> Vec<Vec<f64>> {
    (0..nt).map(|t| (0..nvox).map(|v| data[v * nt + t]).collect()).collect()
}

fn save4(path: &str, vols: &[Vec<f64>], dims: (usize, usize, usize), vs: (f64, f64, f64), aff: &[f64; 16]) {
    if vols.len() == 1 {
        save_nifti_to_file(Path::new(path), &vols[0], dims, vs, aff).expect("save");
    } else {
        let refs: Vec<&[f64]> = vols.iter().map(|v| v.as_slice()).collect();
        save_nifti_4d_to_file(Path::new(path), &refs, dims, vs, aff).expect("save");
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let cmd = args.first().cloned().unwrap_or_default();
    let rest = &args[1.min(args.len())..];
    let pos = positional(rest);
    match cmd.as_str() {
        "n4" => {
            let img = read_nifti_file(Path::new(&pos[0])).expect("read");
            let g = Grid::new(img.dims.0, img.dims.1, img.dims.2, img.voxel_size.0, img.voxel_size.1, img.voxel_size.2);
            let p = qsm_core::utils::n4::N4Params::default();
            let out = qsm_core::utils::n4::n4_bias_correction(&img.data, None, &g,
                &qsm_core::utils::itk_geometry::ItkGeometry::axis_aligned([img.voxel_size.0, img.voxel_size.1, img.voxel_size.2]), &p, |_, _| {}).expect("n4");
            save_nifti_to_file(Path::new(&pos[1]), &out.corrected, img.dims, img.voxel_size, &img.affine).expect("save");
            if let Some(b) = pos.get(2) {
                save_nifti_to_file(Path::new(b), &out.bias_field, img.dims, img.voxel_size, &img.affine).expect("save");
            }
        }
        "bet" => {
            let img = read_nifti_file(Path::new(&pos[0])).expect("read");
            let g = Grid::new(img.dims.0, img.dims.1, img.dims.2, img.voxel_size.0, img.voxel_size.1, img.voxel_size.2);
            let mut p = qsm_core::bet::BetParams::default();
            if let Some(f) = arg_after(rest, "--f") { p.fractional_intensity = f.parse().unwrap(); }
            if let Some(s) = arg_after(rest, "--subdivisions") { p.subdivisions = s.parse().unwrap(); }
            let m = qsm_core::bet::run_bet(&img.data, &g, &p,
                qsm_core::bet::FslLeftRightOrder::from_affine(Some(&img.affine)), |_, _| {});
            let mf: Vec<f64> = m.iter().map(|&v| v as f64).collect();
            save_nifti_to_file(Path::new(&pos[1]), &mf, img.dims, img.voxel_size, &img.affine).expect("save");
        }
        "bestpath" => {
            let img = read_nifti_file(Path::new(&pos[0])).expect("read");
            let mask = read_nifti_file(Path::new(&pos[1])).expect("read");
            let m: Vec<u8> = mask.data.iter().map(|&v| (v > 0.0) as u8).collect();
            let g = Grid::new(img.dims.0, img.dims.1, img.dims.2, img.voxel_size.0, img.voxel_size.1, img.voxel_size.2);
            let p = qsm_core::unwrap::BestPathParams::default();
            let out = qsm_core::unwrap::unwrap_bestpath(&img.data, &m, &p, &g);
            save_nifti_to_file(Path::new(&pos[2]), &out, img.dims, img.voxel_size, &img.affine).expect("save");
        }
        "prelude" => {
            let (data, dims, nt, vs, aff) = load4(&pos[0]);
            let mask = read_nifti_file(Path::new(&pos[1])).expect("read");
            let m: Vec<u8> = mask.data.iter().map(|&v| (v > 0.0) as u8).collect();
            let g = Grid::new(dims.0, dims.1, dims.2, vs.0, vs.1, vs.2);
            let nvox = dims.0 * dims.1 * dims.2;
            let mut p = qsm_core::unwrap::PreludeParams::default();
            if let Some(n) = arg_after(rest, "--n") { p.num_phase_partitions = n.parse().unwrap(); }
            let slicewise = arg_after(rest, "--slicewise").is_some_and(|v| v == "1");
            let vols: Vec<Vec<f64>> = (0..nt).map(|t| {
                let ph = &data[t * nvox..(t + 1) * nvox];
                if slicewise {
                    let sp = qsm_core::unwrap::SliceWiseParams { prelude: p, ..Default::default() };
                    qsm_core::unwrap::unwrap_slicewise(ph, &[], &m, qsm_core::unwrap::UnwrapMethod::Prelude, &sp, &g)
                } else {
                    qsm_core::unwrap::unwrap_prelude(ph, &m, &g, &p)
                }
            }).collect();
            save4(&pos[2], &vols, dims, vs, &aff);
        }
        "morph" => {
            let img = read_nifti_file(Path::new(&pos[0])).expect("read");
            let m: Vec<u8> = img.data.iter().map(|&v| (v > 0.0) as u8).collect();
            let g = Grid::new(img.dims.0, img.dims.1, img.dims.2, img.voxel_size.0, img.voxel_size.1, img.voxel_size.2);
            let it: usize = arg_after(rest, "--iterations").map_or(2, |v| v.parse().unwrap());
            let r: i32 = arg_after(rest, "--radius").map_or(3, |v| v.parse().unwrap());
            let f = |v: Vec<u8>| -> Vec<f64> { v.iter().map(|&x| x as f64).collect() };
            use qsm_core::utils::morphology::{dilate_mask, erode_mask, morphological_close};
            for (name, out) in [("erode", f(erode_mask(&m, &g, it))), ("dilate", f(dilate_mask(&m, &g, it))),
                                ("close", f(morphological_close(&m, &g, r)))] {
                let path = format!("{}_{}.nii.gz", pos[1], name);
                save_nifti_to_file(Path::new(&path), &out, img.dims, img.voxel_size, &img.affine).expect("save");
            }
        }
        "gibbs" => {
            let (data, dims, nt, vs, aff) = load4(&pos[0]);
            let nvox = dims.0 * dims.1 * dims.2;
            let out = qsm_core::unring::gibbs_unring(&interleave(&data, nvox, nt), dims, nt,
                qsm_core::unring::GibbsMode::Dipy2d { slice_axis: 2 });
            save4(&pos[1], &deinterleave(&out, nvox, nt), dims, vs, &aff);
        }
        "mppca" => {
            let (data, dims, nt, vs, aff) = load4(&pos[0]);
            let nvox = dims.0 * dims.1 * dims.2;
            let mask = read_nifti_file(Path::new(&pos[1])).expect("read");
            let m: Vec<u8> = mask.data.iter().map(|&v| (v > 0.0) as u8).collect();
            let r: usize = arg_after(rest, "--patch-radius").map(|s| s.parse().unwrap()).unwrap_or(2);
            let out = qsm_core::denoise::mppca_denoise(&interleave(&data, nvox, nt), dims, nt, r, Some(&m));
            save4(&pos[2], &deinterleave(&out, nvox, nt), dims, vs, &aff);
        }
        "wavesep" => {
            let chi = read_nifti_file(Path::new(&pos[0])).expect("read");
            let r2p = read_nifti_file(Path::new(&pos[1])).expect("read");
            let mask = read_nifti_file(Path::new(&pos[2])).expect("read");
            let m: Vec<u8> = mask.data.iter().map(|&v| (v > 0.5) as u8).collect();
            let g = Grid::new(chi.dims.0, chi.dims.1, chi.dims.2, chi.voxel_size.0, chi.voxel_size.1, chi.voxel_size.2);
            let mut p = qsm_core::separation::WaveSepParams::default();
            if let Some(d) = arg_after(rest, "--dr") { p.dr_pos = d.parse().unwrap(); p.dr_neg = p.dr_pos; }
            let (pos_map, neg_map, _) = qsm_core::separation::wavesep(&chi.data, &r2p.data, &m, &g, &p, |_, _| {}).expect("wavesep");
            let dia: Vec<f64> = neg_map.iter().map(|v| -v).collect();
            save_nifti_to_file(Path::new(&pos[3]), &pos_map, chi.dims, chi.voxel_size, &chi.affine).expect("save");
            save_nifti_to_file(Path::new(&pos[4]), &dia, chi.dims, chi.voxel_size, &chi.affine).expect("save");
        }
        _ => {
            eprintln!("usage: qsmrs-probe n4|bet|bestpath|prelude|morph|gibbs|mppca|wavesep ... (see src/main.rs)");
            std::process::exit(2);
        }
    }
}
