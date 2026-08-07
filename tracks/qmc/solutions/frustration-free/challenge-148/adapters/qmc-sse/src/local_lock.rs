use crate::secure_fs::canonical_requested_path;
use anyhow::{Context, Result, bail, ensure};
use sha2::{Digest, Sha256};
use std::env;
use std::fs::OpenOptions;
use std::io;
use std::os::fd::{AsRawFd, FromRawFd, OwnedFd};
use std::path::{Path, PathBuf};
use std::thread;
use std::time::{Duration, Instant};

const DEFAULT_TIMEOUT_MS: u64 = 30_000;
const RETRY_INTERVAL_MS: u64 = 25;
const SOCKET_DOMAIN: &[u8] = b"qmc-sse-abstract-lock-v1\0";

pub struct LocalLock {
    _socket: OwnedFd,
}

impl LocalLock {
    pub fn acquire(output: &Path, request_hash: &str) -> Result<Self> {
        let canonical_output = canonical_requested_path(output)?;
        Self::acquire_namespace(&canonical_output, request_hash)
    }

    pub fn acquire_namespace(output_namespace: &str, request_hash: &str) -> Result<Self> {
        // SAFETY: geteuid has no preconditions and cannot fail.
        let uid = unsafe { libc::geteuid() } as u64;
        let mut hasher = Sha256::new();
        hasher.update(SOCKET_DOMAIN);
        hasher.update(uid.to_be_bytes());
        hasher.update([0]);
        hasher.update(output_namespace.as_bytes());
        hasher.update([0]);
        hasher.update(request_hash.as_bytes());
        if let Ok(test_namespace) = env::var("QMC_SSE_TEST_ABSTRACT_LOCK_NAMESPACE") {
            hasher.update([0]);
            hasher.update(b"test-network-namespace\0");
            hasher.update(test_namespace.as_bytes());
        }
        let name = format!("qmc-sse-v1-{:x}", hasher.finalize());
        let timeout_ms = env::var("QMC_SSE_ABSTRACT_LOCK_TIMEOUT_MS")
            .ok()
            .map(|value| {
                value
                    .parse::<u64>()
                    .context("abstract lock timeout must be a positive integer")
            })
            .transpose()?
            .unwrap_or(DEFAULT_TIMEOUT_MS);
        ensure!(timeout_ms > 0, "abstract lock timeout must be positive");
        let started = Instant::now();
        let deadline = started + Duration::from_millis(timeout_ms);
        loop {
            match bind_abstract(&name) {
                Ok(socket) => {
                    publish_acquired_marker()?;
                    hold_for_test()?;
                    return Ok(Self { _socket: socket });
                }
                Err(error) if error.raw_os_error() == Some(libc::EADDRINUSE) => {
                    if Instant::now() >= deadline {
                        bail!(
                            "abstract local lock timeout after {} ms for {name}",
                            started.elapsed().as_millis()
                        );
                    }
                    thread::sleep(Duration::from_millis(RETRY_INTERVAL_MS));
                }
                Err(error) => {
                    return Err(error).context(
                        "Linux abstract AF_UNIX lock setup failed; refusing filesystem access",
                    );
                }
            }
        }
    }
}

fn bind_abstract(name: &str) -> io::Result<OwnedFd> {
    let name = name.as_bytes();
    if name.len() + 1 > 108 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "abstract socket name is too long",
        ));
    }
    // SAFETY: socket has no pointer arguments and returns a new descriptor.
    let raw = unsafe { libc::socket(libc::AF_UNIX, libc::SOCK_STREAM | libc::SOCK_CLOEXEC, 0) };
    if raw < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: socket returned a new owned descriptor.
    let socket = unsafe { OwnedFd::from_raw_fd(raw) };
    // SAFETY: zero is a valid initial representation for sockaddr_un.
    let mut address: libc::sockaddr_un = unsafe { std::mem::zeroed() };
    address.sun_family = libc::AF_UNIX as libc::sa_family_t;
    address.sun_path[0] = 0;
    for (index, byte) in name.iter().enumerate() {
        address.sun_path[index + 1] = *byte as libc::c_char;
    }
    let length =
        (std::mem::offset_of!(libc::sockaddr_un, sun_path) + 1 + name.len()) as libc::socklen_t;
    // SAFETY: address points to an initialized sockaddr_un and `length`
    // includes exactly the family, abstract NUL, and name bytes.
    let result = unsafe {
        libc::bind(
            socket.as_raw_fd(),
            (&raw const address).cast::<libc::sockaddr>(),
            length,
        )
    };
    if result == 0 {
        Ok(socket)
    } else {
        Err(io::Error::last_os_error())
    }
}

fn publish_acquired_marker() -> Result<()> {
    let Ok(path) = env::var("QMC_SSE_TEST_ABSTRACT_LOCK_READY") else {
        return Ok(());
    };
    OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)
        .context("cannot create abstract-lock acquisition marker")?
        .sync_all()
        .context("cannot fsync abstract-lock acquisition marker")
}

fn hold_for_test() -> Result<()> {
    let (Ok(ready), Ok(release)) = (
        env::var("QMC_SSE_TEST_HOLD_ABSTRACT_LOCK_READY"),
        env::var("QMC_SSE_TEST_HOLD_ABSTRACT_LOCK_RELEASE"),
    ) else {
        return Ok(());
    };
    let ready = PathBuf::from(ready);
    let release = PathBuf::from(release);
    OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&ready)
        .context("cannot create held abstract-lock marker")?
        .sync_all()
        .context("cannot fsync held abstract-lock marker")?;
    let deadline = Instant::now() + Duration::from_secs(30);
    while !release.exists() {
        ensure!(
            Instant::now() < deadline,
            "held abstract-lock release timed out"
        );
        thread::sleep(Duration::from_millis(5));
    }
    Ok(())
}
