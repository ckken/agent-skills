use std::{
    fs,
    path::{Path, PathBuf},
};

use anyhow::{Context, Result, bail};
use clap::{Parser, ValueEnum};
use image::{DynamicImage, imageops::FilterType};
use serde::Serialize;
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

#[derive(Debug, Parser)]
#[command(
    name = "agent-image-opt",
    version,
    about = "Lossless and lossy optimization for AI agent image artifacts"
)]
struct Cli {
    /// Files or directories to process.
    #[arg(required = true)]
    inputs: Vec<PathBuf>,

    /// Walk input directories recursively.
    #[arg(short, long)]
    recursive: bool,

    /// Compression mode. Lossless keeps pixels unchanged; lossy outputs WebP.
    #[arg(short, long, value_enum, default_value_t = Mode::Lossy)]
    mode: Mode,

    /// A quality preset for lossy WebP output.
    #[arg(short, long, value_enum, default_value_t = Preset::Poster)]
    preset: Preset,

    /// Override the preset quality (1-100). Only applies to lossy mode.
    #[arg(short, long, value_parser = clap::value_parser!(u8).range(1..=100))]
    quality: Option<u8>,

    /// In lossless mode, choose the output encoding. Defaults to PNG for PNG input and WebP otherwise.
    #[arg(long, value_enum)]
    format: Option<OutputFormat>,

    /// Resize only when an image is wider than this many pixels. Not available in lossless mode.
    #[arg(long)]
    max_width: Option<u32>,

    /// Skip writing files unless the output is at least this percentage smaller.
    #[arg(long, default_value_t = 8.0)]
    min_savings: f64,

    /// Replace the source only after a successful, smaller optimization.
    #[arg(long, conflicts_with = "dry_run")]
    in_place: bool,

    /// Overwrite an existing .optimized output file.
    #[arg(long)]
    force: bool,

    /// Calculate and report results without writing any image.
    #[arg(long)]
    dry_run: bool,

    /// Write structured results to this JSON file.
    #[arg(long)]
    report: Option<PathBuf>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum)]
enum Mode {
    Lossless,
    Lossy,
}

#[derive(Clone, Copy, Debug, ValueEnum)]
enum Preset {
    Poster,
    Ui,
    Illustration,
    Photo,
}

impl Preset {
    fn quality(self) -> u8 {
        match self {
            Self::Poster => 88,
            Self::Ui => 92,
            Self::Illustration => 86,
            Self::Photo => 82,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum)]
enum OutputFormat {
    Png,
    Webp,
}

impl OutputFormat {
    fn extension(self) -> &'static str {
        match self {
            Self::Png => "png",
            Self::Webp => "webp",
        }
    }
}

#[derive(Debug, Serialize)]
struct Report {
    tool: &'static str,
    version: &'static str,
    mode: String,
    min_savings_percent: f64,
    results: Vec<FileResult>,
}

#[derive(Debug, Serialize)]
struct FileResult {
    source: String,
    output: Option<String>,
    status: Status,
    source_bytes: u64,
    output_bytes: Option<u64>,
    savings_bytes: Option<i64>,
    savings_percent: Option<f64>,
    source_sha256: String,
    width: Option<u32>,
    height: Option<u32>,
    message: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "snake_case")]
enum Status {
    Optimized,
    Skipped,
    DryRun,
    Failed,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    if !(0.0..=100.0).contains(&cli.min_savings) {
        bail!("--min-savings must be between 0 and 100");
    }
    if cli.mode == Mode::Lossless && cli.max_width.is_some() {
        bail!("--max-width is incompatible with --mode lossless because resizing changes pixels");
    }
    if cli.mode == Mode::Lossy && matches!(cli.format, Some(OutputFormat::Png)) {
        bail!("--mode lossy only supports WebP output; remove --format png");
    }

    let paths = collect_paths(&cli.inputs, cli.recursive)?;
    if paths.is_empty() {
        bail!("no supported image files found");
    }

    let mut results = Vec::with_capacity(paths.len());
    for path in paths {
        let result = match optimize_one(&path, &cli) {
            Ok(result) => result,
            Err(error) => FileResult {
                source: path.display().to_string(),
                output: None,
                status: Status::Failed,
                source_bytes: fs::metadata(&path)
                    .map(|metadata| metadata.len())
                    .unwrap_or(0),
                output_bytes: None,
                savings_bytes: None,
                savings_percent: None,
                source_sha256: String::new(),
                width: None,
                height: None,
                message: Some(error.to_string()),
            },
        };
        print_result(&result);
        results.push(result);
    }

    let report = Report {
        tool: "agent-image-opt",
        version: env!("CARGO_PKG_VERSION"),
        mode: format!("{:?}", cli.mode).to_lowercase(),
        min_savings_percent: cli.min_savings,
        results,
    };
    if let Some(report_path) = &cli.report {
        let json = serde_json::to_vec_pretty(&report)?;
        fs::write(report_path, json)
            .with_context(|| format!("failed to write report {}", report_path.display()))?;
    }

    if report
        .results
        .iter()
        .any(|result| matches!(result.status, Status::Failed))
    {
        bail!("one or more files failed; see the result lines or JSON report")
    }
    Ok(())
}

fn collect_paths(inputs: &[PathBuf], recursive: bool) -> Result<Vec<PathBuf>> {
    let mut paths = Vec::new();
    for input in inputs {
        if input.is_file() {
            if is_supported(input) && !is_optimized_name(input) {
                paths.push(input.to_owned());
            }
        } else if input.is_dir() {
            let depth = if recursive { usize::MAX } else { 1 };
            for entry in WalkDir::new(input).min_depth(1).max_depth(depth) {
                let entry = entry.with_context(|| format!("failed to read {}", input.display()))?;
                let path = entry.path();
                if path.is_file() && is_supported(path) && !is_optimized_name(path) {
                    paths.push(path.to_owned());
                }
            }
        } else {
            bail!("input does not exist: {}", input.display());
        }
    }
    paths.sort();
    paths.dedup();
    Ok(paths)
}

fn is_supported(path: &Path) -> bool {
    matches!(
        extension(path).as_deref(),
        Some("png" | "jpg" | "jpeg" | "webp")
    )
}

fn is_optimized_name(path: &Path) -> bool {
    path.file_stem()
        .and_then(|stem| stem.to_str())
        .is_some_and(|stem| stem.ends_with(".optimized"))
}

fn extension(path: &Path) -> Option<String> {
    path.extension()
        .and_then(|extension| extension.to_str())
        .map(|extension| extension.to_ascii_lowercase())
}

fn choose_format(path: &Path, cli: &Cli) -> OutputFormat {
    match (cli.mode, cli.format) {
        (_, Some(format)) => format,
        (Mode::Lossy, None) => OutputFormat::Webp,
        (Mode::Lossless, None) if extension(path).as_deref() == Some("png") => OutputFormat::Png,
        (Mode::Lossless, None) => OutputFormat::Webp,
    }
}

fn optimize_one(path: &Path, cli: &Cli) -> Result<FileResult> {
    let source = fs::read(path).with_context(|| format!("failed to read {}", path.display()))?;
    let source_bytes = source.len() as u64;
    let source_sha256 = sha256(&source);
    let output_format = choose_format(path, cli);
    let (encoded, width, height) = encode(&source, path, cli, output_format)?;
    let output_bytes = encoded.len() as u64;
    let savings_bytes = source_bytes as i64 - output_bytes as i64;
    let savings_percent = percentage(savings_bytes, source_bytes);
    let output_path = output_path(path, output_format, cli.in_place);

    if savings_percent < cli.min_savings {
        return Ok(FileResult {
            source: path.display().to_string(),
            output: None,
            status: Status::Skipped,
            source_bytes,
            output_bytes: Some(output_bytes),
            savings_bytes: Some(savings_bytes),
            savings_percent: Some(savings_percent),
            source_sha256,
            width: Some(width),
            height: Some(height),
            message: Some(format!(
                "saving {savings_percent:.1}% is below the configured {:.1}% threshold",
                cli.min_savings
            )),
        });
    }

    if cli.dry_run {
        return Ok(FileResult {
            source: path.display().to_string(),
            output: Some(output_path.display().to_string()),
            status: Status::DryRun,
            source_bytes,
            output_bytes: Some(output_bytes),
            savings_bytes: Some(savings_bytes),
            savings_percent: Some(savings_percent),
            source_sha256,
            width: Some(width),
            height: Some(height),
            message: None,
        });
    }

    if output_path.exists() && output_path != path && !cli.force {
        return Ok(FileResult {
            source: path.display().to_string(),
            output: Some(output_path.display().to_string()),
            status: Status::Skipped,
            source_bytes,
            output_bytes: Some(output_bytes),
            savings_bytes: Some(savings_bytes),
            savings_percent: Some(savings_percent),
            source_sha256,
            width: Some(width),
            height: Some(height),
            message: Some("output already exists; pass --force to overwrite it".to_string()),
        });
    }

    if cli.in_place {
        let temporary = path.with_extension(format!("{}.tmp", output_format.extension()));
        fs::write(&temporary, encoded)
            .with_context(|| format!("failed to write {}", temporary.display()))?;
        if output_path != path && path.exists() {
            fs::remove_file(path)
                .with_context(|| format!("failed to replace {}", path.display()))?;
        }
        fs::rename(&temporary, &output_path)
            .with_context(|| format!("failed to finalize {}", output_path.display()))?;
    } else {
        fs::write(&output_path, encoded)
            .with_context(|| format!("failed to write {}", output_path.display()))?;
    }

    Ok(FileResult {
        source: path.display().to_string(),
        output: Some(output_path.display().to_string()),
        status: Status::Optimized,
        source_bytes,
        output_bytes: Some(output_bytes),
        savings_bytes: Some(savings_bytes),
        savings_percent: Some(savings_percent),
        source_sha256,
        width: Some(width),
        height: Some(height),
        message: None,
    })
}

fn encode(
    source: &[u8],
    path: &Path,
    cli: &Cli,
    output_format: OutputFormat,
) -> Result<(Vec<u8>, u32, u32)> {
    if cli.mode == Mode::Lossless && output_format == OutputFormat::Png {
        if extension(path).as_deref() != Some("png") {
            bail!("lossless PNG output requires PNG input: {}", path.display());
        }
        let options = oxipng::Options::from_preset(4);
        let encoded = oxipng::optimize_from_memory(source, &options)
            .with_context(|| format!("failed to optimize PNG {}", path.display()))?;
        let image = image::load_from_memory(source)
            .with_context(|| format!("failed to read PNG dimensions from {}", path.display()))?;
        return Ok((encoded, image.width(), image.height()));
    }

    let image = image::load_from_memory(source)
        .with_context(|| format!("unsupported or invalid image {}", path.display()))?;
    let image = resize_if_needed(image, cli.max_width);
    let width = image.width();
    let height = image.height();
    let rgba = image.to_rgba8();
    let encoder = webp::Encoder::from_rgba(rgba.as_raw(), width, height);
    let encoded = match cli.mode {
        Mode::Lossless => encoder.encode_lossless().to_vec(),
        Mode::Lossy => encoder
            .encode(f32::from(
                cli.quality.unwrap_or_else(|| cli.preset.quality()),
            ))
            .to_vec(),
    };
    Ok((encoded, width, height))
}

fn resize_if_needed(image: DynamicImage, max_width: Option<u32>) -> DynamicImage {
    match max_width {
        Some(max_width) if image.width() > max_width => {
            image.resize(max_width, u32::MAX, FilterType::Lanczos3)
        }
        _ => image,
    }
}

fn output_path(path: &Path, format: OutputFormat, in_place: bool) -> PathBuf {
    if in_place {
        return path.with_extension(format.extension());
    }
    let stem = path
        .file_stem()
        .and_then(|stem| stem.to_str())
        .unwrap_or("image");
    path.with_file_name(format!("{stem}.optimized.{}", format.extension()))
}

fn sha256(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    format!("{digest:x}")
}

fn percentage(delta: i64, original: u64) -> f64 {
    if original == 0 {
        return 0.0;
    }
    delta as f64 / original as f64 * 100.0
}

fn print_result(result: &FileResult) {
    let status = match result.status {
        Status::Optimized => "optimized",
        Status::Skipped => "skipped",
        Status::DryRun => "dry-run",
        Status::Failed => "failed",
    };
    let details = match (result.output_bytes, result.savings_percent) {
        (Some(bytes), Some(percent)) => format!(
            "{} B -> {} B ({percent:.1}% saved)",
            result.source_bytes, bytes
        ),
        _ => format!("{} B", result.source_bytes),
    };
    println!("[{status}] {} — {details}", result.source);
    if let Some(message) = &result.message {
        println!("  {message}");
    }
}
