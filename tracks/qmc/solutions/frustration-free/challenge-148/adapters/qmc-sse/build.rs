use sha2::{Digest, Sha256};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

const QMC_REVISION: &str = "35f100af856f3273cc67d31962f3e67f801b0c37";

fn collect_files(root: &Path, path: &Path, files: &mut Vec<PathBuf>) {
    let mut entries = fs::read_dir(path)
        .unwrap_or_else(|error| panic!("cannot read {}: {error}", path.display()))
        .map(|entry| entry.expect("cannot read adapter source entry").path())
        .collect::<Vec<_>>();
    entries.sort();
    for entry in entries {
        if entry.is_dir() {
            collect_files(root, &entry, files);
        } else {
            files.push(
                entry
                    .strip_prefix(root)
                    .expect("source path under root")
                    .to_path_buf(),
            );
        }
    }
}

fn hash_file(hasher: &mut Sha256, root: &Path, relative: &Path) {
    println!("cargo:rerun-if-changed={}", relative.display());
    hasher.update(relative.to_string_lossy().as_bytes());
    hasher.update([0]);
    hasher.update(
        fs::read(root.join(relative))
            .unwrap_or_else(|error| panic!("cannot read {}: {error}", relative.display())),
    );
    hasher.update([0]);
}

fn normalized_encoded_rustflags() -> String {
    env::var("CARGO_ENCODED_RUSTFLAGS")
        .unwrap_or_default()
        .split('\u{1f}')
        .map(str::trim)
        .filter(|flag| !flag.is_empty())
        .collect::<Vec<_>>()
        .join("\u{1f}")
}

fn main() {
    let root = PathBuf::from(env::var_os("CARGO_MANIFEST_DIR").expect("manifest directory"));
    let mut tracked = vec![
        PathBuf::from("Cargo.toml"),
        PathBuf::from("Cargo.lock"),
        PathBuf::from("README.md"),
        PathBuf::from("build.rs"),
    ];
    collect_files(&root, &root.join("src"), &mut tracked);
    tracked.sort();

    let compiler = Command::new(env::var_os("RUSTC").unwrap_or_else(|| "rustc".into()))
        .arg("--version")
        .output()
        .expect("run rustc --version");
    assert!(compiler.status.success(), "rustc --version failed");
    let compiler = String::from_utf8(compiler.stdout)
        .expect("rustc version is UTF-8")
        .trim()
        .to_owned();
    let profile = env::var("PROFILE").expect("Cargo profile");
    let target = env::var("TARGET").expect("Cargo target");
    let encoded_rustflags = normalized_encoded_rustflags();
    let mut behavior_environment = env::vars()
        .filter(|(name, _)| {
            name == "CARGO_ENCODED_RUSTFLAGS"
                || name == "PROFILE"
                || name == "OPT_LEVEL"
                || name == "DEBUG"
                || name == "HOST"
                || name == "TARGET"
                || name == "RUSTC"
                || name.starts_with("CARGO_CFG_")
                || name.starts_with("CARGO_FEATURE_")
                || name.starts_with("CARGO_PROFILE_")
        })
        .collect::<Vec<_>>();
    behavior_environment.sort();
    let features = behavior_environment
        .iter()
        .filter_map(|(name, _)| name.strip_prefix("CARGO_FEATURE_"))
        .collect::<Vec<_>>()
        .join(",");
    let panic = env::var("CARGO_CFG_PANIC").unwrap_or_else(|_| "unknown".to_owned());
    let lto = env::var(format!(
        "CARGO_PROFILE_{}_LTO",
        profile.to_ascii_uppercase()
    ))
    .unwrap_or_else(|_| {
        if profile == "release" {
            "true"
        } else {
            "false"
        }
        .to_owned()
    });
    let codegen_units = env::var(format!(
        "CARGO_PROFILE_{}_CODEGEN_UNITS",
        profile.to_ascii_uppercase()
    ))
    .unwrap_or_else(|_| if profile == "release" { "1" } else { "default" }.to_owned());

    let source_hash = format!("{:x}", Sha256::digest(format!("QMC_SSE:{QMC_REVISION}")));
    let mut build = Sha256::new();
    build.update(b"qmc-sse-build-v1\0");
    build.update(QMC_REVISION.as_bytes());
    build.update([0]);
    build.update(compiler.as_bytes());
    build.update([0]);
    build.update(profile.as_bytes());
    build.update([0]);
    build.update(target.as_bytes());
    build.update([0]);
    for (name, value) in &behavior_environment {
        println!("cargo:rerun-if-env-changed={name}");
        build.update(name.as_bytes());
        build.update(b"=");
        if name == "CARGO_ENCODED_RUSTFLAGS" {
            build.update(encoded_rustflags.as_bytes());
        } else {
            build.update(value.as_bytes());
        }
        build.update([0]);
    }
    for relative in tracked {
        hash_file(&mut build, &root, &relative);
    }
    let build_hash = format!("{:x}", build.finalize());

    println!("cargo:rustc-env=QMC_SSE_BUILD_HASH={build_hash}");
    println!("cargo:rustc-env=QMC_SSE_SOURCE_HASH={source_hash}");
    println!("cargo:rustc-env=QMC_SSE_COMPILER={compiler}");
    println!("cargo:rustc-env=QMC_SSE_PROFILE={profile}");
    println!("cargo:rustc-env=QMC_SSE_TARGET={target}");
    println!("cargo:rustc-env=QMC_SSE_ENCODED_RUSTFLAGS={encoded_rustflags}");
    println!("cargo:rustc-env=QMC_SSE_FEATURES={features}");
    println!("cargo:rustc-env=QMC_SSE_PANIC={panic}");
    println!("cargo:rustc-env=QMC_SSE_LTO={lto}");
    println!("cargo:rustc-env=QMC_SSE_CODEGEN_UNITS={codegen_units}");
    println!("cargo:rustc-env=QMC_SSE_QMC_REVISION={QMC_REVISION}");
}
