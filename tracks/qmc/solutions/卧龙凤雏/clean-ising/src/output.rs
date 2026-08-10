use anyhow::{bail, Context, Result};
use serde::de::DeserializeOwned;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::fs::{self, File};
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::{Path, PathBuf};

pub fn write_jsonl<T: Serialize>(path: &Path, records: &[T]) -> Result<()> {
    ensure_parent(path)?;
    let file = File::create(path)
        .with_context(|| format!("failed to create JSONL output {}", path.display()))?;
    let mut writer = BufWriter::new(file);
    for record in records {
        serde_json::to_writer(&mut writer, record)
            .with_context(|| format!("failed to serialize JSONL record for {}", path.display()))?;
        writer.write_all(b"\n")?;
        writer.flush()?;
    }
    writer.get_ref().sync_all()?;
    Ok(())
}

pub fn read_jsonl_prefix<T: DeserializeOwned>(path: &Path) -> Result<(Vec<T>, bool)> {
    let file = File::open(path)
        .with_context(|| format!("failed to open JSONL input {}", path.display()))?;
    let ends_with_newline = fs::read(path)?.last().copied() == Some(b'\n');
    let mut records = Vec::new();
    let mut lines = BufReader::new(file).lines().peekable();
    while let Some(line_result) = lines.next() {
        let line = line_result?;
        if line.trim().is_empty() {
            continue;
        }
        match serde_json::from_str(&line) {
            Ok(record) => records.push(record),
            Err(_error) if lines.peek().is_none() && !ends_with_newline => {
                return Ok((records, false));
            }
            Err(error) => {
                bail!(
                    "invalid complete JSONL record in {}: {error}",
                    path.display()
                );
            }
        }
    }
    Ok((records, true))
}

pub fn write_json_atomic<T: Serialize>(path: &Path, value: &T) -> Result<()> {
    ensure_parent(path)?;
    let temporary = temporary_path(path);
    {
        let file = File::create(&temporary)
            .with_context(|| format!("failed to create {}", temporary.display()))?;
        let mut writer = BufWriter::new(file);
        serde_json::to_writer_pretty(&mut writer, value)?;
        writer.write_all(b"\n")?;
        writer.flush()?;
        writer.get_ref().sync_all()?;
    }
    fs::rename(&temporary, path).with_context(|| {
        format!(
            "failed to atomically rename {} to {}",
            temporary.display(),
            path.display()
        )
    })?;
    Ok(())
}

pub fn read_json<T: DeserializeOwned>(path: &Path) -> Result<T> {
    let file = File::open(path)
        .with_context(|| format!("failed to open JSON input {}", path.display()))?;
    serde_json::from_reader(BufReader::new(file))
        .with_context(|| format!("failed to parse JSON input {}", path.display()))
}

pub fn sha256_file(path: &Path) -> Result<String> {
    let bytes = fs::read(path).with_context(|| format!("failed to read {}", path.display()))?;
    let digest = Sha256::digest(bytes);
    Ok(format!("{digest:x}"))
}

fn ensure_parent(path: &Path) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("failed to create output directory {}", parent.display()))?;
    }
    Ok(())
}

fn temporary_path(path: &Path) -> PathBuf {
    let name = path
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or("manifest.json");
    path.with_file_name(format!(".{name}.tmp-{}", std::process::id()))
}
