use std::{
    fs,
    path::{Path, PathBuf},
    process,
};

use anyhow::{Context, Result, bail};
use clap::{Args, Parser, Subcommand, ValueEnum};
use image::{DynamicImage, imageops::FilterType};
use serde::Serialize;
use serde_json::json;
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

#[derive(Debug, Parser)]
#[command(
    name = "agent-image-opt",
    version,
    about = "Lossless and lossy optimization for AI agent image artifacts"
)]
struct Cli {
    /// Emit a stable JSON result to stdout.
    #[arg(long, global = true)]
    json: bool,

    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Verify the local, offline image optimization runtime.
    Doctor,
    /// Read image metadata and return recommended optimization presets.
    Inspect(InspectArgs),
    /// Optimize one or more images. Writes new files unless --in-place is explicit.
    Optimize(OptimizeArgs),
    /// Low-level conversion to WebP or PNG using explicit encoding options.
    Transcode(TranscodeArgs),
}

#[derive(Debug, Args)]
struct InspectArgs {
    /// Files or directories to inspect.
    #[arg(required = true)]
    inputs: Vec<PathBuf>,

    /// Walk input directories recursively.
    #[arg(short, long)]
    recursive: bool,
}

#[derive(Debug, Args)]
struct OptimizeArgs {
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

#[derive(Debug, Args)]
struct TranscodeArgs {
    /// The source image to convert.
    input: PathBuf,

    /// Target encoding.
    #[arg(long, value_enum, default_value = "webp")]
    format: OutputFormat,

    /// Use a lossless encoder. PNG output requires PNG input.
    #[arg(long)]
    lossless: bool,

    /// WebP quality in lossy mode (1-100).
    #[arg(short, long, default_value_t = 88, value_parser = clap::value_parser!(u8).range(1..=100))]
    quality: u8,

    /// Resize only when the image is wider than this many pixels.
    #[arg(long)]
    max_width: Option<u32>,

    /// Replace the source only after a successful, smaller optimization.
    #[arg(long, conflicts_with = "dry_run")]
    in_place: bool,

    /// Overwrite an existing .optimized output file.
    #[arg(long)]
    force: bool,

    /// Calculate and report results without writing any image.
    #[arg(long)]
    dry_run: bool,
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
    ok: bool,
    operation: &'static str,
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

#[derive(Serialize)]
struct DoctorReport {
    ok: bool,
    operation: &'static str,
    tool: &'static str,
    version: &'static str,
    offline: bool,
    auth_required: bool,
    encoders: Vec<&'static str>,
    binary: Option<String>,
}

#[derive(Serialize)]
struct InspectReport {
    ok: bool,
    operation: &'static str,
    results: Vec<InspectResult>,
}

#[derive(Serialize)]
struct InspectResult {
    path: String,
    format: String,
    bytes: u64,
    width: u32,
    height: u32,
    has_alpha: bool,
    recommended_preset: &'static str,
}

fn main() {
    let cli = Cli::parse();
    let json = cli.json;
    if let Err(error) = run(cli) {
        if json {
            println!(
                "{}",
                json!({
                    "ok": false,
                    "error": { "code": "command_failed", "message": error.to_string() }
                })
            );
        } else {
            eprintln!("error: {error:#}");
        }
        process::exit(1);
    }
}

fn run(cli: Cli) -> Result<()> {
    match cli.command {
        Command::Doctor => run_doctor(cli.json),
        Command::Inspect(args) => run_inspect(args, cli.json),
        Command::Optimize(args) => run_optimize(args, cli.json),
        Command::Transcode(args) => run_transcode(args, cli.json),
    }
}

fn run_doctor(json_output: bool) -> Result<()> {
    let report = DoctorReport {
        ok: true,
        operation: "doctor",
        tool: "agent-image-opt",
        version: env!("CARGO_PKG_VERSION"),
        offline: true,
        auth_required: false,
        encoders: vec!["oxipng (lossless PNG)", "libwebp (lossless and lossy WebP)"],
        binary: std::env::current_exe()
            .ok()
            .map(|path| path.display().to_string()),
    };
    if json_output {
        println!("{}", serde_json::to_string(&report)?);
    } else {
        println!("agent-image-opt {}", report.version);
        println!("offline: yes; auth required: no");
        for encoder in &report.encoders {
            println!("encoder: {encoder}");
        }
    }
    Ok(())
}

fn run_inspect(args: InspectArgs, json_output: bool) -> Result<()> {
    let paths = collect_paths(&args.inputs, args.recursive)?;
    if paths.is_empty() {
        bail!("no supported image files found");
    }
    let mut results = Vec::with_capacity(paths.len());
    for path in paths {
        let bytes =
            fs::read(&path).with_context(|| format!("failed to read {}", path.display()))?;
        let image = image::load_from_memory(&bytes)
            .with_context(|| format!("unsupported or invalid image {}", path.display()))?;
        let recommended_preset = recommendation(&image);
        results.push(InspectResult {
            path: path.display().to_string(),
            format: extension(&path).unwrap_or_else(|| "unknown".to_string()),
            bytes: bytes.len() as u64,
            width: image.width(),
            height: image.height(),
            has_alpha: image.color().has_alpha(),
            recommended_preset,
        });
    }
    let report = InspectReport {
        ok: true,
        operation: "inspect",
        results,
    };
    if json_output {
        println!("{}", serde_json::to_string(&report)?);
    } else {
        for result in &report.results {
            println!(
                "{} — {}×{}, {} B, preset={}",
                result.path, result.width, result.height, result.bytes, result.recommended_preset
            );
        }
    }
    Ok(())
}

fn run_transcode(args: TranscodeArgs, json_output: bool) -> Result<()> {
    if args.lossless && args.max_width.is_some() {
        bail!("--max-width is incompatible with --lossless because resizing changes pixels");
    }
    let optimize = OptimizeArgs {
        inputs: vec![args.input],
        recursive: false,
        mode: if args.lossless {
            Mode::Lossless
        } else {
            Mode::Lossy
        },
        preset: Preset::Poster,
        quality: Some(args.quality),
        format: Some(args.format),
        max_width: args.max_width,
        min_savings: 0.0,
        in_place: args.in_place,
        force: args.force,
        dry_run: args.dry_run,
        report: None,
    };
    run_optimize_with_operation(optimize, json_output, "transcode")
}

fn run_optimize(args: OptimizeArgs, json_output: bool) -> Result<()> {
    run_optimize_with_operation(args, json_output, "optimize")
}

fn run_optimize_with_operation(
    args: OptimizeArgs,
    json_output: bool,
    operation: &'static str,
) -> Result<()> {
    validate_optimize_args(&args)?;
    let paths = collect_paths(&args.inputs, args.recursive)?;
    if paths.is_empty() {
        bail!("no supported image files found");
    }

    let mut results = Vec::with_capacity(paths.len());
    for path in paths {
        let result = match optimize_one(&path, &args) {
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
        if !json_output {
            print_result(&result);
        }
        results.push(result);
    }

    let report = Report {
        ok: true,
        operation,
        tool: "agent-image-opt",
        version: env!("CARGO_PKG_VERSION"),
        mode: format!("{:?}", args.mode).to_lowercase(),
        min_savings_percent: args.min_savings,
        results,
    };
    if let Some(report_path) = &args.report {
        let report_json = serde_json::to_vec_pretty(&report)?;
        fs::write(report_path, report_json)
            .with_context(|| format!("failed to write report {}", report_path.display()))?;
    }
    if report
        .results
        .iter()
        .any(|result| matches!(result.status, Status::Failed))
    {
        bail!("one or more files failed; pass --report to retain the detailed report");
    }
    if json_output {
        println!("{}", serde_json::to_string(&report)?);
    }
    Ok(())
}

fn validate_optimize_args(args: &OptimizeArgs) -> Result<()> {
    if !(0.0..=100.0).contains(&args.min_savings) {
        bail!("--min-savings must be between 0 and 100");
    }
    if args.mode == Mode::Lossless && args.max_width.is_some() {
        bail!("--max-width is incompatible with --mode lossless because resizing changes pixels");
    }
    if args.mode == Mode::Lossy && matches!(args.format, Some(OutputFormat::Png)) {
        bail!("--mode lossy only supports WebP output; remove --format png");
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

fn recommendation(image: &DynamicImage) -> &'static str {
    if image.width() > 1200 || image.height() > 1200 {
        "poster"
    } else if image.color().has_alpha() {
        "illustration"
    } else {
        "photo"
    }
}

fn choose_format(path: &Path, args: &OptimizeArgs) -> OutputFormat {
    match (args.mode, args.format) {
        (_, Some(format)) => format,
        (Mode::Lossy, None) => OutputFormat::Webp,
        (Mode::Lossless, None) if extension(path).as_deref() == Some("png") => OutputFormat::Png,
        (Mode::Lossless, None) => OutputFormat::Webp,
    }
}

fn optimize_one(path: &Path, args: &OptimizeArgs) -> Result<FileResult> {
    let source = fs::read(path).with_context(|| format!("failed to read {}", path.display()))?;
    let source_bytes = source.len() as u64;
    let source_sha256 = sha256(&source);
    let output_format = choose_format(path, args);
    let (encoded, width, height) = encode(&source, path, args, output_format)?;
    let output_bytes = encoded.len() as u64;
    let savings_bytes = source_bytes as i64 - output_bytes as i64;
    let savings_percent = percentage(savings_bytes, source_bytes);
    let output_path = output_path(path, output_format, args.in_place);

    if savings_percent < args.min_savings {
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
                args.min_savings
            )),
        });
    }

    if args.dry_run {
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

    if output_path.exists() && output_path != path && !args.force {
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

    if args.in_place {
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
    args: &OptimizeArgs,
    output_format: OutputFormat,
) -> Result<(Vec<u8>, u32, u32)> {
    if args.mode == Mode::Lossless && output_format == OutputFormat::Png {
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
    let image = resize_if_needed(image, args.max_width);
    let width = image.width();
    let height = image.height();
    let rgba = image.to_rgba8();
    let encoder = webp::Encoder::from_rgba(rgba.as_raw(), width, height);
    let encoded = match args.mode {
        Mode::Lossless => encoder.encode_lossless().to_vec(),
        Mode::Lossy => encoder
            .encode(f32::from(
                args.quality.unwrap_or_else(|| args.preset.quality()),
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
