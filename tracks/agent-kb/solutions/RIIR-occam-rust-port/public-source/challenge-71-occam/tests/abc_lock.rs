use std::{fs, path::PathBuf};

use serde::Deserialize;
use sha2::{Digest, Sha256};

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct AbcLock {
    schema_version: u32,
    repository: String,
    commit: String,
    archive_url: String,
    archive_sha256: String,
    archive_bytes: usize,
    build: Vec<String>,
}

fn lock_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("tools/abc/LOCK.json")
}

fn validate_lock(lock: &AbcLock) -> Result<(), String> {
    if lock.schema_version != 1 {
        return Err("unsupported schema".into());
    }
    if !lock.repository.starts_with("https://") || !lock.archive_url.starts_with("https://") {
        return Err("ABC URLs must use HTTPS".into());
    }
    if lock.commit.len() != 40
        || !lock
            .commit
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err("ABC commit must be 40 lowercase hexadecimal characters".into());
    }
    if lock.archive_sha256.len() != 64
        || !lock
            .archive_sha256
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err("ABC archive SHA-256 must be lowercase hexadecimal".into());
    }
    if lock.archive_bytes == 0 {
        return Err("ABC archive byte count must be positive".into());
    }
    if lock.build != ["make", "-j2", "ABC_USE_NO_READLINE=1"] {
        return Err("ABC build command is not pinned".into());
    }
    Ok(())
}

fn validate_archive(lock: &AbcLock, bytes: &[u8]) -> Result<(), String> {
    validate_lock(lock)?;
    if bytes.len() != lock.archive_bytes {
        return Err("archive byte count mismatch".into());
    }
    let actual = format!("{:x}", Sha256::digest(bytes));
    if actual != lock.archive_sha256 {
        return Err("archive checksum mismatch".into());
    }
    Ok(())
}

#[test]
fn abc_lock_is_exact_and_well_formed() {
    let source = fs::read_to_string(lock_path()).unwrap();
    let lock: AbcLock = serde_json::from_str(&source).unwrap();
    validate_lock(&lock).unwrap();
    assert_eq!(lock.commit, "e76768b9d34f9dc67cb6608efecd55db271ff849");
    assert_eq!(
        lock.archive_sha256,
        "158a4bf861be010cf899c5cb20c159d1b2e68ae1b461bce7d2c10be348a8e159"
    );
    assert_eq!(lock.archive_bytes, 7_709_448);
}

#[test]
fn tampered_lock_is_rejected_before_archive_use() {
    let bytes = b"archive";
    let mut lock: AbcLock =
        serde_json::from_str(&fs::read_to_string(lock_path()).unwrap()).unwrap();
    lock.archive_bytes = bytes.len();
    lock.archive_sha256 = format!("{:x}", Sha256::digest(bytes));
    validate_archive(&lock, bytes).unwrap();

    lock.archive_sha256.replace_range(0..1, "0");
    if lock.archive_sha256 == format!("{:x}", Sha256::digest(bytes)) {
        lock.archive_sha256.replace_range(0..1, "1");
    }
    assert_eq!(
        validate_archive(&lock, bytes).unwrap_err(),
        "archive checksum mismatch"
    );
}
