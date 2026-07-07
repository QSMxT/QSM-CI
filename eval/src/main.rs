//! qsm-eval — the QSM-CI scorer.
//!
//! Loads a reconstruction and the (held-out) ground truth, computes the challenge metrics via the
//! QSM.rs `qsm_core::metrics` module, and writes a `metrics.json` the platform records and the
//! website renders. Optionally emits center-slice figures (recon | truth | error).
//!
//! This is the *only* place ground truth is read, keeping it out of submitters' containers.

use std::path::PathBuf;

use clap::Parser;
use qsm_core::io::{read_nifti_file, NiftiData};
use qsm_core::metrics::{correlation, xsim, ChallengeMetrics};
use serde::Serialize;

#[derive(Parser, Debug)]
#[command(about = "Score a QSM reconstruction against ground truth (QSM-CI).")]
struct Args {
    /// Reconstruction to score (chimap.nii.gz, ppm).
    #[arg(long)]
    recon: PathBuf,
    /// Ground-truth susceptibility map (ppm).
    #[arg(long)]
    truth: PathBuf,
    /// Tissue segmentation (labels). Required for the `sim` track's region metrics.
    #[arg(long)]
    seg: Option<PathBuf>,
    /// Brain mask.
    #[arg(long)]
    mask: PathBuf,
    /// Track: `sim` (full metric suite) or `invivo` (correlation + XSIM only).
    #[arg(long, default_value = "sim")]
    track: String,
    /// Display name for the run.
    #[arg(long, default_value = "submission")]
    name: String,
    /// Submitter image reference (recorded in the output).
    #[arg(long)]
    image: Option<String>,
    /// Wall-clock runtime of the algorithm, seconds (recorded in the output).
    #[arg(long)]
    runtime: Option<f64>,
    /// Where to write metrics.json.
    #[arg(long)]
    out: PathBuf,
    /// Optional directory to write center-slice PNG figures.
    #[arg(long)]
    figures: Option<PathBuf>,
}

/// The scored result written to disk. Track-specific metrics are `null` when not applicable.
#[derive(Serialize)]
struct Output {
    contract: &'static str,
    name: String,
    track: String,
    image: Option<String>,
    runtime_s: Option<f64>,
    metrics: Metrics,
}

#[derive(Serialize, Default)]
struct Metrics {
    #[serde(skip_serializing_if = "Option::is_none")]
    nrmse: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    nrmse_detrend: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    nrmse_tissue: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    nrmse_blood: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    nrmse_dgm: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    dgm_linearity: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    calc_moment_dev: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    calc_streak: Option<f64>,
    correlation: f64,
    xsim: f64,
}

fn to_u8_mask(nd: &NiftiData) -> Vec<u8> {
    nd.data.iter().map(|&v| if v > 0.5 { 1 } else { 0 }).collect()
}

fn to_labels(nd: &NiftiData) -> Vec<u8> {
    nd.data.iter().map(|&v| v.round().clamp(0.0, 255.0) as u8).collect()
}

fn check_dims(a: &NiftiData, b: &NiftiData, what: &str) -> Result<(), String> {
    if a.dims != b.dims {
        return Err(format!("{what}: dimension mismatch {:?} vs {:?}", a.dims, b.dims));
    }
    Ok(())
}

fn main() -> Result<(), String> {
    let args = Args::parse();

    let recon = read_nifti_file(&args.recon)?;
    let truth = read_nifti_file(&args.truth)?;
    let mask_nd = read_nifti_file(&args.mask)?;
    check_dims(&recon, &truth, "recon vs truth")?;
    check_dims(&recon, &mask_nd, "recon vs mask")?;

    let dims = recon.dims;
    let mask = to_u8_mask(&mask_nd);

    let metrics = match args.track.as_str() {
        "sim" => {
            let seg_nd = read_nifti_file(
                args.seg.as_ref().ok_or("--seg is required for the sim track")?,
            )?;
            check_dims(&recon, &seg_nd, "recon vs seg")?;
            let seg = to_labels(&seg_nd);
            let c = ChallengeMetrics::compute(&args.name, &recon.data, &truth.data, &mask, &seg, dims);
            Metrics {
                nrmse: Some(c.nrmse),
                nrmse_detrend: Some(c.nrmse_detrend),
                nrmse_tissue: Some(c.nrmse_tissue),
                nrmse_blood: Some(c.nrmse_blood),
                nrmse_dgm: Some(c.nrmse_dgm),
                dgm_linearity: Some(c.dgm_linearity),
                calc_moment_dev: Some(c.calc_moment_dev),
                calc_streak: Some(c.calc_streak),
                correlation: c.correlation,
                xsim: c.xsim,
            }
        }
        "invivo" => Metrics {
            correlation: correlation(&recon.data, &truth.data, &mask),
            xsim: xsim(&recon.data, &truth.data, &mask, dims),
            ..Default::default()
        },
        other => return Err(format!("unknown track: {other}")),
    };

    let output = Output {
        contract: "v1",
        name: args.name.clone(),
        track: args.track.clone(),
        image: args.image.clone(),
        runtime_s: args.runtime,
        metrics,
    };

    let json = serde_json::to_string_pretty(&output).map_err(|e| e.to_string())?;
    std::fs::write(&args.out, json + "\n").map_err(|e| e.to_string())?;
    println!("[qsm-eval] wrote {}", args.out.display());

    if let Some(dir) = args.figures.as_ref() {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
        figures::write_triptych(dir, &recon, &truth)?;
        println!("[qsm-eval] wrote figures to {}", dir.display());
    }

    Ok(())
}

/// Minimal center-slice figure writer (axial center slice: recon | truth | |error|).
mod figures {
    use super::NiftiData;
    use std::path::Path;

    fn window(v: f64, lo: f64, hi: f64) -> u8 {
        (((v - lo) / (hi - lo)).clamp(0.0, 1.0) * 255.0) as u8
    }

    pub fn write_triptych(dir: &Path, recon: &NiftiData, truth: &NiftiData) -> Result<(), String> {
        let (nx, ny, nz) = recon.dims;
        let z = nz / 2;
        let (lo, hi) = (-0.1_f64, 0.1_f64); // ppm display window
        let w = nx * 3 + 4; // three panels + separators
        let mut img = image::GrayImage::new(w as u32, ny as u32);
        for y in 0..ny {
            for x in 0..nx {
                let i = z * nx * ny + y * nx + x;
                let r = window(recon.data[i], lo, hi);
                let t = window(truth.data[i], lo, hi);
                let e = window((recon.data[i] - truth.data[i]).abs(), 0.0, hi);
                img.put_pixel(x as u32, y as u32, image::Luma([r]));
                img.put_pixel((nx + 2 + x) as u32, y as u32, image::Luma([t]));
                img.put_pixel((2 * nx + 4 + x) as u32, y as u32, image::Luma([e]));
            }
        }
        img.save(dir.join("slices.png")).map_err(|e| e.to_string())
    }
}
