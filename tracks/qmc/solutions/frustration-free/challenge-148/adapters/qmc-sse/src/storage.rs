use crate::graph::Graph;
use crate::local_lock::LocalLock;
use crate::request::{Request, canonical_bytes, is_sha256, sha256};
use crate::secure_fs::{
    AnchoredDir, Dir, canonical_requested_path, file_identity, open_or_create_anchored_dir,
    read_regular_file,
};
use crate::simulation::{Bin, generate_bins};
use anyhow::{Context, Result, bail, ensure};
use fs2::FileExt;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::os::unix::fs::FileExt as UnixFileExt;
use std::path::{Path, PathBuf};
use std::thread;
use std::time::{Duration, Instant};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Generation {
    schema_version: String,
    anchor_sha256: String,
    request_sha256: String,
    adapter: String,
    source_hash: String,
    build_hash: String,
    seed: u64,
    completed_bin_count: u64,
    bin_object_hashes: Vec<String>,
    previous_generation_sha256: Option<String>,
    replay_update_count: u64,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Pointer {
    schema_version: String,
    anchor_sha256: String,
    generation_sha256: String,
    path: String,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct LockIdentity {
    schema_version: String,
    state_device: u64,
    state_inode: u64,
    lock_device: u64,
    lock_inode: u64,
    identity_device: u64,
    identity_inode: u64,
    request_sha256: String,
}

#[derive(Debug, Serialize)]
struct LockStateBinding<'a> {
    schema_version: &'static str,
    state_device: u64,
    state_inode: u64,
    lock_device: u64,
    lock_inode: u64,
    identity_device: u64,
    identity_inode: u64,
    output_namespace: &'a str,
    request_sha256: &'a str,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct RunLockAnchor {
    schema_version: String,
    state_device: u64,
    state_inode: u64,
    lock_device: u64,
    lock_inode: u64,
    identity_device: u64,
    identity_inode: u64,
    lock_state_identity_sha256: String,
    output_namespace: String,
    request_sha256: String,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct AnchorSelection {
    schema_version: String,
    anchor_sha256: String,
    anchor_device: u64,
    anchor_inode: u64,
    path: String,
}

struct RetainedSelection {
    value: AnchorSelection,
    file: File,
    identity: (u64, u64),
    bytes: Vec<u8>,
}

struct RetainedAnchor {
    value: RunLockAnchor,
    file: File,
    identity: (u64, u64),
    bytes: Vec<u8>,
}

const LOCK_STATE_NAME: &str = ".qmc-sse-lock-state";
const LOCK_FILE_NAME: &str = ".qmc-sse.lock";
const LOCK_IDENTITY_NAME: &str = "identity.json";
const LOCK_ANCHOR_NAME: &str = "run-lock-anchor.json";
const LOCK_ANCHORS_NAME: &str = "run-lock-anchors";
const LOCK_ANCHOR_PIN_SUFFIX: &str = ".pin";

struct InitializedLock {
    anchors: Dir,
    selection: File,
    selection_identity: (u64, u64),
    selection_bytes: Vec<u8>,
    anchor: File,
    anchor_identity: (u64, u64),
    anchor_bytes: Vec<u8>,
    anchor_sha256: String,
    anchor_value: RunLockAnchor,
    state: Dir,
    lock: File,
    identity_identity: (u64, u64),
    identity_bytes: Vec<u8>,
    losing_stages: Vec<String>,
}

struct LockStateCandidate {
    name: String,
    state: Dir,
    lock: File,
    identity_identity: (u64, u64),
    identity_bytes: Vec<u8>,
}

struct Replay<'a> {
    bin_hashes: &'a [String],
    bin_bytes: &'a [Vec<u8>],
    bins: &'a [Bin],
    request: &'a Request,
    graph: &'a Graph,
}

struct Faults {
    failpoint: Option<String>,
    failpoint_occurrence: u64,
    failpoint_seen: u64,
    crashpoint: Option<String>,
    crashpoint_occurrence: u64,
    crashpoint_seen: u64,
    fail_fsync_at: Option<u64>,
    fsync_seen: u64,
}

impl Faults {
    fn from_environment() -> Result<Self> {
        let parse = |name: &str| -> Result<Option<u64>> {
            env::var(name)
                .ok()
                .map(|value| {
                    value
                        .parse::<u64>()
                        .with_context(|| format!("{name} must be a positive integer"))
                })
                .transpose()
        };
        let failpoint_occurrence = parse("QMC_SSE_FAILPOINT_OCCURRENCE")?.unwrap_or(1);
        let crashpoint_occurrence = parse("QMC_SSE_CRASHPOINT_OCCURRENCE")?.unwrap_or(1);
        ensure!(
            failpoint_occurrence > 0 && crashpoint_occurrence > 0,
            "fault occurrence must be positive"
        );
        let fail_fsync_at = parse("QMC_SSE_FAIL_FSYNC_AT")?;
        if let Some(value) = fail_fsync_at {
            ensure!(value > 0, "fsync failure index must be positive");
        }
        Ok(Self {
            failpoint: env::var("QMC_SSE_FAILPOINT").ok(),
            failpoint_occurrence,
            failpoint_seen: 0,
            crashpoint: env::var("QMC_SSE_CRASHPOINT").ok(),
            crashpoint_occurrence,
            crashpoint_seen: 0,
            fail_fsync_at,
            fsync_seen: 0,
        })
    }

    fn boundary(&mut self, name: &str) -> Result<()> {
        self.test_pause(name)?;
        if self.failpoint.as_deref() == Some(name) {
            self.failpoint_seen += 1;
            if self.failpoint_seen == self.failpoint_occurrence {
                bail!("injected failure at {name}");
            }
        }
        if self.crashpoint.as_deref() == Some(name) {
            self.crashpoint_seen += 1;
            if self.crashpoint_seen == self.crashpoint_occurrence {
                // SAFETY: this is an explicit abrupt-crash test hook. `_exit`
                // intentionally skips destructors and buffered I/O.
                unsafe { libc::_exit(86) };
            }
        }
        Ok(())
    }

    fn fsync_file(&mut self, file: &File, label: &str, boundary: &str) -> Result<()> {
        self.fsync_seen += 1;
        if self.fail_fsync_at == Some(self.fsync_seen) {
            bail!("injected fsync failure #{}, at {label}", self.fsync_seen);
        }
        file.sync_all()
            .with_context(|| format!("fsync failed at {label}"))?;
        self.boundary(boundary)
    }

    fn fsync_dir(&mut self, directory: &Dir, label: &str, boundary: &str) -> Result<()> {
        self.fsync_seen += 1;
        if self.fail_fsync_at == Some(self.fsync_seen) {
            bail!("injected fsync failure #{}, at {label}", self.fsync_seen);
        }
        directory
            .sync()
            .with_context(|| format!("fsync failed at {label}"))?;
        self.boundary(boundary)
    }

    fn test_pause(&self, name: &str) -> Result<()> {
        if env::var("QMC_SSE_TEST_PAUSE_AT").ok().as_deref() != Some(name) {
            return Ok(());
        }
        let ready = PathBuf::from(
            env::var("QMC_SSE_TEST_READY").context("pause hook requires ready path")?,
        );
        let release = PathBuf::from(
            env::var("QMC_SSE_TEST_RELEASE").context("pause hook requires release path")?,
        );
        OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&ready)
            .context("cannot publish test pause marker")?
            .sync_all()
            .context("cannot fsync test pause marker")?;
        let deadline = Instant::now() + Duration::from_secs(30);
        while !release.exists() {
            ensure!(Instant::now() < deadline, "test pause release timed out");
            thread::sleep(Duration::from_millis(5));
        }
        Ok(())
    }
}

fn json_line<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    let mut bytes = canonical_bytes(value)?;
    bytes.push(b'\n');
    Ok(bytes)
}

fn lock_state_identity_sha256(
    state_identity: (u64, u64),
    lock_identity: (u64, u64),
    identity_identity: (u64, u64),
    request_hash: &str,
    output_namespace: &str,
) -> Result<String> {
    Ok(sha256(&canonical_bytes(&LockStateBinding {
        schema_version: "qmc-sse-lock-state-binding-v2",
        state_device: state_identity.0,
        state_inode: state_identity.1,
        lock_device: lock_identity.0,
        lock_inode: lock_identity.1,
        identity_device: identity_identity.0,
        identity_inode: identity_identity.1,
        output_namespace,
        request_sha256: request_hash,
    })?))
}

fn read_retained(file: &File, label: &str) -> Result<Vec<u8>> {
    let length = file
        .metadata()
        .with_context(|| format!("cannot stat retained {label} descriptor"))?
        .len();
    let length = usize::try_from(length).context("retained control object is too large")?;
    let mut bytes = vec![0; length];
    file.read_exact_at(&mut bytes, 0)
        .with_context(|| format!("cannot read retained {label} descriptor"))?;
    ensure!(
        file.metadata()
            .with_context(|| format!("cannot restat retained {label} descriptor"))?
            .len()
            == length as u64,
        "retained {label} size changed while reading"
    );
    Ok(bytes)
}

fn write_fsynced(
    directory: &Dir,
    name: &str,
    bytes: &[u8],
    faults: &mut Faults,
    label: &str,
    boundary: &str,
) -> Result<(u64, u64)> {
    let mut file = directory.create_file(name)?;
    file.write_all(bytes)
        .with_context(|| format!("cannot write {label}"))?;
    file.flush()
        .with_context(|| format!("cannot flush {label}"))?;
    faults.fsync_file(&file, label, boundary)?;
    file_identity(&file)
}

fn archive_entry(
    source: &Dir,
    archive: &Dir,
    name: &str,
    reason: &str,
    faults: &mut Faults,
) -> Result<String> {
    let base = format!("{name}.{reason}");
    for index in 0_u64.. {
        let destination = if index == 0 {
            base.clone()
        } else {
            format!("{base}-{index}")
        };
        if source.rename_noreplace(name, archive, &destination)? {
            faults.fsync_dir(
                source,
                "archive source directory",
                "after-archive-source-fsync",
            )?;
            faults.fsync_dir(
                archive,
                "archive directory",
                "after-archive-directory-fsync",
            )?;
            return Ok(destination);
        }
    }
    unreachable!("archive suffix space exhausted")
}

fn initialize_lock_state(
    anchored_root: &AnchoredDir,
    request_hash: &str,
    output_namespace: &str,
    faults: &mut Faults,
) -> Result<InitializedLock> {
    let mut losing_stages = Vec::new();
    ensure!(
        anchored_root
            .directory
            .open_file_optional(LOCK_FILE_NAME)?
            .is_none(),
        "legacy unbound run lock exists; refusing unsafe lock migration"
    );
    let selection_existed = anchored_root
        .directory
        .open_file_optional(LOCK_ANCHOR_NAME)?
        .is_some();
    if !selection_existed {
        ensure!(
            anchored_root
                .directory
                .open_dir_optional(LOCK_STATE_NAME)?
                .is_none(),
            "unbound run lock-state exists; refusing unsafe anchor migration"
        );
    }
    let anchors = if selection_existed {
        anchored_root.directory.open_dir(LOCK_ANCHORS_NAME)?
    } else {
        anchored_root
            .directory
            .open_or_create_dir(LOCK_ANCHORS_NAME)?
    };
    if !selection_existed {
        let stage_name = unique_stage_name(&anchored_root.directory, ".tmp-lock-state")?;
        anchored_root.verify()?;
        let stage = anchored_root.directory.create_dir(&stage_name)?;
        anchored_root.verify()?;
        ensure!(
            anchored_root.directory.same_entry(&stage_name, &stage)?,
            "staged lock-state directory was replaced"
        );
        let lock = stage.create_file(LOCK_FILE_NAME)?;
        faults.fsync_file(&lock, "new run lock", "after-lock-file-fsync")?;
        let state_identity = stage.identity()?;
        let lock_identity = file_identity(&lock)?;
        anchored_root.verify()?;
        ensure!(
            anchored_root.directory.same_entry(&stage_name, &stage)?,
            "staged lock-state directory was replaced"
        );
        let mut identity_file = stage.create_file(LOCK_IDENTITY_NAME)?;
        let identity_identity = file_identity(&identity_file)?;
        let identity = LockIdentity {
            schema_version: "qmc-sse-lock-identity-v1".to_owned(),
            state_device: state_identity.0,
            state_inode: state_identity.1,
            lock_device: lock_identity.0,
            lock_inode: lock_identity.1,
            identity_device: identity_identity.0,
            identity_inode: identity_identity.1,
            request_sha256: request_hash.to_owned(),
        };
        let identity_bytes = json_line(&identity)?;
        identity_file
            .write_all(&identity_bytes)
            .context("cannot write lock identity")?;
        identity_file
            .flush()
            .context("cannot flush lock identity")?;
        faults.fsync_file(&identity_file, "lock identity", "after-lock-identity-fsync")?;
        faults.fsync_dir(
            &stage,
            "staged lock-state directory",
            "after-lock-state-directory-fsync",
        )?;
        faults.fsync_dir(
            &anchored_root.directory,
            "run directory containing staged lock state",
            "after-lock-stage-parent-fsync",
        )?;
        anchored_root.verify()?;
        ensure!(
            anchored_root.directory.same_entry(&stage_name, &stage)?,
            "staged lock-state directory was replaced"
        );
        let anchor_stage_name = unique_stage_name(&anchored_root.directory, ".tmp-lock-anchor")?;
        let mut anchor_file = anchored_root.directory.create_file(&anchor_stage_name)?;
        let anchor_identity = file_identity(&anchor_file)?;
        let anchor = RunLockAnchor {
            schema_version: "qmc-sse-run-lock-anchor-v2".to_owned(),
            state_device: state_identity.0,
            state_inode: state_identity.1,
            lock_device: lock_identity.0,
            lock_inode: lock_identity.1,
            identity_device: identity_identity.0,
            identity_inode: identity_identity.1,
            lock_state_identity_sha256: lock_state_identity_sha256(
                state_identity,
                lock_identity,
                identity_identity,
                request_hash,
                output_namespace,
            )?,
            output_namespace: output_namespace.to_owned(),
            request_sha256: request_hash.to_owned(),
        };
        let anchor_bytes = json_line(&anchor)?;
        anchor_file
            .write_all(&anchor_bytes)
            .context("cannot write run lock anchor")?;
        anchor_file
            .flush()
            .context("cannot flush run lock anchor")?;
        faults.fsync_file(
            &anchor_file,
            "staged run lock anchor",
            "after-lock-anchor-file-fsync",
        )?;
        let anchor_sha256 = sha256(&anchor_bytes);
        let selection = AnchorSelection {
            schema_version: "qmc-sse-run-lock-anchor-selection-v1".to_owned(),
            anchor_sha256: anchor_sha256.clone(),
            anchor_device: anchor_identity.0,
            anchor_inode: anchor_identity.1,
            path: format!("{LOCK_ANCHORS_NAME}/{anchor_sha256}.json"),
        };
        let selection_bytes = json_line(&selection)?;
        let selection_stage_name =
            unique_stage_name(&anchored_root.directory, ".tmp-lock-selection")?;
        write_fsynced(
            &anchored_root.directory,
            &selection_stage_name,
            &selection_bytes,
            faults,
            "staged run lock anchor selection",
            "after-lock-anchor-selection-fsync",
        )?;
        faults.boundary("before-lock-anchor-rename")?;
        anchored_root.verify()?;
        if anchored_root.directory.rename_noreplace(
            &selection_stage_name,
            &anchored_root.directory,
            LOCK_ANCHOR_NAME,
        )? {
            faults.boundary("after-lock-anchor-rename")?;
            faults.fsync_dir(
                &anchored_root.directory,
                "run directory after lock-anchor publication",
                "after-lock-anchor-directory-fsync",
            )?;
        } else {
            losing_stages.push(stage_name);
            losing_stages.push(anchor_stage_name);
            losing_stages.push(selection_stage_name);
        }
    }

    anchored_root.verify()?;
    ensure!(
        anchored_root
            .directory
            .same_entry(LOCK_ANCHORS_NAME, &anchors)?,
        "run lock anchors directory was replaced"
    );
    let selection = read_and_validate_anchor_selection(anchored_root)?;
    let anchor_name = format!("{}.json", selection.value.anchor_sha256);
    let pin_name = format!("{}{LOCK_ANCHOR_PIN_SUFFIX}", selection.value.anchor_sha256);
    if anchors.open_file_optional(&anchor_name)?.is_none() {
        let anchor_entries = anchors.entries()?;
        ensure!(
            anchor_entries.is_empty() || anchor_entries == [pin_name.clone()],
            "selected canonical run lock anchor is missing with unexpected anchor entries"
        );
        faults.boundary("after-selected-canonical-anchor-absent")?;
        let matching = anchored_root
            .directory
            .entries()?
            .into_iter()
            .filter(|name| name.starts_with(".tmp-lock-anchor-"))
            .filter_map(|name| {
                let file = anchored_root.directory.open_file_optional(&name).ok()??;
                let identity = file_identity(&file).ok()?;
                let bytes = read_regular_file(file, "staged run lock anchor").ok()?;
                (identity == (selection.value.anchor_device, selection.value.anchor_inode)
                    && sha256(&bytes) == selection.value.anchor_sha256)
                    .then_some(name)
            })
            .collect::<Vec<_>>();
        if anchors.open_file_optional(&pin_name)?.is_none() {
            ensure!(
                matching.len() == 1,
                "selected canonical run lock anchor has {} matching staged objects",
                matching.len()
            );
            anchored_root.verify()?;
            if anchored_root
                .directory
                .link_noreplace(&matching[0], &anchors, &pin_name)?
            {
                faults.fsync_dir(
                    &anchors,
                    "pinned run lock anchors directory",
                    "after-lock-anchor-pin-directory-fsync",
                )?;
            }
        }
        validate_anchor_pin(&anchors, &pin_name, &selection.value)?;
        if anchors.open_file_optional(&anchor_name)?.is_none() {
            ensure!(
                matching.len() == 1,
                "selected canonical run lock anchor is missing without its staged recovery object"
            );
            faults.boundary("before-canonical-lock-anchor-rename")?;
            let renamed =
                match anchored_root
                    .directory
                    .rename_noreplace(&matching[0], &anchors, &anchor_name)
                {
                    Ok(value) => value,
                    Err(_error) if anchors.open_file_optional(&anchor_name)?.is_some() => false,
                    Err(error) => return Err(error),
                };
            if renamed {
                faults.fsync_dir(
                    &anchors,
                    "canonical run lock anchors directory",
                    "after-canonical-lock-anchor-directory-fsync",
                )?;
            }
        }
    }
    let anchor = read_and_validate_anchor(
        anchored_root,
        &anchors,
        &selection.value,
        request_hash,
        output_namespace,
    )?;
    let candidate = find_anchored_lock_state(anchored_root, request_hash, &anchor.value)?;
    let candidate_name = candidate.name;
    let mut state = candidate.state;
    let lock = candidate.lock;
    let mut identity_identity = candidate.identity_identity;
    let mut identity_bytes = candidate.identity_bytes;
    validate_lock_binding(
        anchored_root,
        &anchors,
        &selection.file,
        selection.identity,
        &selection.bytes,
        &anchor.file,
        anchor.identity,
        &anchor.bytes,
        &selection.value.anchor_sha256,
        &anchor.value,
        &state,
        &lock,
        identity_identity,
        &identity_bytes,
        request_hash,
        output_namespace,
        false,
    )?;
    lock.lock_exclusive()
        .context("cannot acquire exclusive anchored run lock")?;
    validate_lock_binding(
        anchored_root,
        &anchors,
        &selection.file,
        selection.identity,
        &selection.bytes,
        &anchor.file,
        anchor.identity,
        &anchor.bytes,
        &selection.value.anchor_sha256,
        &anchor.value,
        &state,
        &lock,
        identity_identity,
        &identity_bytes,
        request_hash,
        output_namespace,
        false,
    )?;

    if let Some(published) = anchored_root.directory.open_dir_optional(LOCK_STATE_NAME)? {
        let opened = read_and_validate_lock_state(&published, request_hash)?;
        ensure!(
            published.identity()? == (anchor.value.state_device, anchor.value.state_inode)
                && file_identity(&opened.0)? == (anchor.value.lock_device, anchor.value.lock_inode)
                && opened.1 == (anchor.value.identity_device, anchor.value.identity_inode),
            "published run lock-state does not match durable anchor"
        );
        state = published;
        identity_identity = opened.1;
        identity_bytes = opened.2;
    } else {
        ensure!(
            candidate_name != LOCK_STATE_NAME,
            "anchored run lock-state disappeared"
        );
        faults.boundary("before-lock-state-rename")?;
        anchored_root.verify()?;
        ensure!(
            anchored_root
                .directory
                .same_entry(&candidate_name, &state)?,
            "anchored staged lock-state directory was replaced"
        );
        ensure!(
            anchored_root.directory.rename_noreplace(
                &candidate_name,
                &anchored_root.directory,
                LOCK_STATE_NAME,
            )?,
            "unexpected competing lock-state publication"
        );
        faults.boundary("after-lock-state-rename")?;
        faults.fsync_dir(
            &anchored_root.directory,
            "run directory after anchored lock-state publication",
            "after-lock-directory-fsync",
        )?;
        state = anchored_root.directory.open_dir(LOCK_STATE_NAME)?;
        let opened = read_and_validate_lock_state(&state, request_hash)?;
        ensure!(
            state.identity()? == (anchor.value.state_device, anchor.value.state_inode)
                && file_identity(&opened.0)? == (anchor.value.lock_device, anchor.value.lock_inode)
                && opened.1 == (anchor.value.identity_device, anchor.value.identity_inode),
            "published run lock descriptor does not match durable anchor"
        );
        identity_identity = opened.1;
        identity_bytes = opened.2;
    }
    validate_lock_binding(
        anchored_root,
        &anchors,
        &selection.file,
        selection.identity,
        &selection.bytes,
        &anchor.file,
        anchor.identity,
        &anchor.bytes,
        &selection.value.anchor_sha256,
        &anchor.value,
        &state,
        &lock,
        identity_identity,
        &identity_bytes,
        request_hash,
        output_namespace,
        true,
    )?;
    if selection_existed {
        faults.fsync_dir(
            &anchored_root.directory,
            "run directory after adopted anchored lock-state validation",
            "after-adopted-lock-state-fsync",
        )?;
    }
    Ok(InitializedLock {
        anchors,
        selection: selection.file,
        selection_identity: selection.identity,
        selection_bytes: selection.bytes,
        anchor: anchor.file,
        anchor_identity: anchor.identity,
        anchor_bytes: anchor.bytes,
        anchor_sha256: selection.value.anchor_sha256,
        anchor_value: anchor.value,
        state,
        lock,
        identity_identity,
        identity_bytes,
        losing_stages,
    })
}

fn unique_stage_name(directory: &Dir, prefix: &str) -> Result<String> {
    let entries = directory.entries()?;
    for suffix in 0_u64.. {
        let name = format!("{prefix}-{}-{suffix}", std::process::id());
        if !entries.contains(&name) {
            return Ok(name);
        }
    }
    unreachable!("temporary lock stage suffix space exhausted")
}

fn read_and_validate_anchor_selection(anchored_root: &AnchoredDir) -> Result<RetainedSelection> {
    anchored_root.verify()?;
    let file = anchored_root.directory.open_file(LOCK_ANCHOR_NAME)?;
    let identity = file_identity(&file)?;
    let bytes = read_retained(&file, "run lock anchor selection")?;
    let selection: AnchorSelection =
        serde_json::from_slice(&bytes).context("malformed run lock anchor selection")?;
    ensure!(
        bytes == json_line(&selection)?,
        "run lock anchor selection is not canonical"
    );
    ensure!(
        selection.schema_version == "qmc-sse-run-lock-anchor-selection-v1",
        "run lock anchor selection schema mismatch"
    );
    ensure!(
        is_sha256(&selection.anchor_sha256)
            && selection.path == format!("{LOCK_ANCHORS_NAME}/{}.json", selection.anchor_sha256),
        "run lock anchor selection hash/path mismatch"
    );
    ensure!(
        selection.anchor_device != 0 && selection.anchor_inode != 0,
        "run lock anchor selection identity is invalid"
    );
    Ok(RetainedSelection {
        value: selection,
        file,
        identity,
        bytes,
    })
}

fn validate_anchor_pin(anchors: &Dir, pin_name: &str, selection: &AnchorSelection) -> Result<()> {
    let pin = anchors.open_file(pin_name)?;
    ensure!(
        file_identity(&pin)? == (selection.anchor_device, selection.anchor_inode),
        "canonical run lock anchor pin identity mismatch"
    );
    ensure!(
        sha256(&read_retained(&pin, "canonical run lock anchor pin")?) == selection.anchor_sha256,
        "canonical run lock anchor pin hash mismatch"
    );
    Ok(())
}

fn read_and_validate_anchor(
    anchored_root: &AnchoredDir,
    anchors: &Dir,
    selection: &AnchorSelection,
    request_hash: &str,
    output_namespace: &str,
) -> Result<RetainedAnchor> {
    anchored_root.verify()?;
    ensure!(
        anchored_root
            .directory
            .same_entry(LOCK_ANCHORS_NAME, anchors)?,
        "run lock anchors directory was replaced"
    );
    let anchor_name = format!("{}.json", selection.anchor_sha256);
    let pin_name = format!("{}{LOCK_ANCHOR_PIN_SUFFIX}", selection.anchor_sha256);
    let names = anchors.entries()?;
    ensure!(
        names == [anchor_name.clone(), pin_name.clone()],
        "exactly one selected canonical run lock anchor and its inode pin are required"
    );
    let file = anchors.open_file(&anchor_name)?;
    let anchor_identity = file_identity(&file)?;
    let bytes = read_retained(&file, "canonical run lock anchor")?;
    ensure!(
        anchor_identity == (selection.anchor_device, selection.anchor_inode),
        "canonical run lock anchor pathname was substituted"
    );
    validate_anchor_pin(anchors, &pin_name, selection)?;
    ensure!(
        sha256(&bytes) == selection.anchor_sha256,
        "canonical run lock anchor hash mismatch"
    );
    let anchor: RunLockAnchor =
        serde_json::from_slice(&bytes).context("malformed canonical run lock anchor")?;
    ensure!(
        bytes == json_line(&anchor)?,
        "canonical run lock anchor is not canonical"
    );
    ensure!(
        anchor.schema_version == "qmc-sse-run-lock-anchor-v2",
        "run lock anchor schema mismatch"
    );
    ensure!(
        anchor.request_sha256 == request_hash,
        "run lock anchor request namespace mismatch"
    );
    ensure!(
        anchor.output_namespace == output_namespace,
        "run lock anchor output namespace mismatch"
    );
    ensure!(
        is_sha256(&anchor.lock_state_identity_sha256)
            && anchor.lock_state_identity_sha256
                == lock_state_identity_sha256(
                    (anchor.state_device, anchor.state_inode),
                    (anchor.lock_device, anchor.lock_inode),
                    (anchor.identity_device, anchor.identity_inode),
                    request_hash,
                    output_namespace,
                )?,
        "run lock anchor lock-state identity hash mismatch"
    );
    Ok(RetainedAnchor {
        value: anchor,
        file,
        identity: anchor_identity,
        bytes,
    })
}

fn read_and_validate_lock_state(
    state: &Dir,
    request_hash: &str,
) -> Result<(File, (u64, u64), Vec<u8>)> {
    ensure!(
        state.entries()? == [LOCK_FILE_NAME, LOCK_IDENTITY_NAME],
        "run lock-state directory shape changed"
    );
    let lock = state.open_file(LOCK_FILE_NAME)?;
    let lock_identity = file_identity(&lock)?;
    let identity_file = state.open_file(LOCK_IDENTITY_NAME)?;
    let identity_identity = file_identity(&identity_file)?;
    let identity_bytes = read_regular_file(identity_file, "lock identity")?;
    let identity: LockIdentity =
        serde_json::from_slice(&identity_bytes).context("malformed run lock identity")?;
    ensure!(
        identity_bytes == json_line(&identity)?,
        "run lock identity is not canonical"
    );
    ensure!(
        identity.schema_version == "qmc-sse-lock-identity-v1",
        "run lock identity schema mismatch"
    );
    ensure!(
        (identity.state_device, identity.state_inode) == state.identity()?,
        "run lock-state descriptor identity mismatch"
    );
    ensure!(
        (identity.lock_device, identity.lock_inode) == lock_identity,
        "run lock descriptor identity mismatch"
    );
    ensure!(
        (identity.identity_device, identity.identity_inode) == identity_identity,
        "run lock identity descriptor mismatch"
    );
    ensure!(
        identity.request_sha256 == request_hash,
        "run lock request namespace mismatch"
    );
    Ok((lock, identity_identity, identity_bytes))
}

fn find_anchored_lock_state(
    anchored_root: &AnchoredDir,
    request_hash: &str,
    anchor: &RunLockAnchor,
) -> Result<LockStateCandidate> {
    if let Some(state) = anchored_root.directory.open_dir_optional(LOCK_STATE_NAME)? {
        let opened = read_and_validate_lock_state(&state, request_hash)?;
        ensure!(
            state.identity()? == (anchor.state_device, anchor.state_inode)
                && file_identity(&opened.0)? == (anchor.lock_device, anchor.lock_inode)
                && opened.1 == (anchor.identity_device, anchor.identity_inode),
            "published run lock-state does not match durable anchor"
        );
        return Ok(LockStateCandidate {
            name: LOCK_STATE_NAME.to_owned(),
            state,
            lock: opened.0,
            identity_identity: opened.1,
            identity_bytes: opened.2,
        });
    }
    let mut matches = Vec::new();
    for name in anchored_root
        .directory
        .entries()?
        .into_iter()
        .filter(|name| name.starts_with(".tmp-lock-state-"))
    {
        let Some(state) = anchored_root.directory.open_dir_optional(&name)? else {
            continue;
        };
        if let Ok(opened) = read_and_validate_lock_state(&state, request_hash)
            && state.identity()? == (anchor.state_device, anchor.state_inode)
            && file_identity(&opened.0)? == (anchor.lock_device, anchor.lock_inode)
            && opened.1 == (anchor.identity_device, anchor.identity_inode)
        {
            matches.push(LockStateCandidate {
                name,
                state,
                lock: opened.0,
                identity_identity: opened.1,
                identity_bytes: opened.2,
            });
        }
    }
    if matches.is_empty()
        && let Some(state) = anchored_root.directory.open_dir_optional(LOCK_STATE_NAME)?
    {
        let opened = read_and_validate_lock_state(&state, request_hash)?;
        ensure!(
            state.identity()? == (anchor.state_device, anchor.state_inode)
                && file_identity(&opened.0)? == (anchor.lock_device, anchor.lock_inode)
                && opened.1 == (anchor.identity_device, anchor.identity_inode),
            "published run lock-state does not match durable anchor"
        );
        return Ok(LockStateCandidate {
            name: LOCK_STATE_NAME.to_owned(),
            state,
            lock: opened.0,
            identity_identity: opened.1,
            identity_bytes: opened.2,
        });
    }
    ensure!(
        matches.len() == 1,
        "durable run lock anchor has {} matching staged lock states",
        matches.len()
    );
    Ok(matches.pop().expect("exactly one matching lock state"))
}

#[allow(clippy::too_many_arguments)]
fn validate_lock_binding(
    anchored_root: &AnchoredDir,
    anchors: &Dir,
    selection_file: &File,
    selection_identity: (u64, u64),
    expected_selection_bytes: &[u8],
    anchor_file: &File,
    anchor_identity: (u64, u64),
    expected_anchor_bytes: &[u8],
    anchor_sha256: &str,
    anchor: &RunLockAnchor,
    state: &Dir,
    lock: &File,
    identity_identity: (u64, u64),
    expected_identity_bytes: &[u8],
    request_hash: &str,
    output_namespace: &str,
    require_published_state: bool,
) -> Result<()> {
    anchored_root.verify()?;
    ensure!(
        anchored_root
            .directory
            .same_entry(LOCK_ANCHORS_NAME, anchors)?,
        "run lock anchors directory was replaced"
    );
    let path_selection = anchored_root.directory.open_file(LOCK_ANCHOR_NAME)?;
    ensure!(
        file_identity(&path_selection)? == selection_identity
            && file_identity(selection_file)? == selection_identity,
        "run lock anchor selection pathname was replaced"
    );
    let selection_bytes = read_retained(&path_selection, "run lock anchor selection")?;
    ensure!(
        selection_bytes == expected_selection_bytes
            && read_retained(selection_file, "retained run lock anchor selection")?
                == expected_selection_bytes,
        "run lock anchor selection content changed"
    );
    let selection: AnchorSelection = serde_json::from_slice(&selection_bytes)
        .context("malformed retained run lock anchor selection")?;
    ensure!(
        selection.anchor_sha256 == anchor_sha256
            && selection.path == format!("{LOCK_ANCHORS_NAME}/{anchor_sha256}.json")
            && (selection.anchor_device, selection.anchor_inode) == anchor_identity,
        "run lock anchor selection binding changed"
    );
    let anchor_name = format!("{anchor_sha256}.json");
    let pin_name = format!("{anchor_sha256}{LOCK_ANCHOR_PIN_SUFFIX}");
    ensure!(
        anchors.entries()? == [anchor_name.clone(), pin_name.clone()],
        "exactly one selected canonical run lock anchor and its inode pin are required"
    );
    let path_anchor = anchors.open_file(&anchor_name)?;
    let path_pin = anchors.open_file(&pin_name)?;
    ensure!(
        file_identity(&path_anchor)? == anchor_identity
            && file_identity(anchor_file)? == anchor_identity
            && file_identity(&path_pin)? == anchor_identity,
        "canonical run lock anchor pathname was substituted"
    );
    let anchor_bytes = read_retained(&path_anchor, "canonical run lock anchor")?;
    ensure!(
        anchor_bytes == expected_anchor_bytes
            && read_retained(anchor_file, "retained canonical run lock anchor")?
                == expected_anchor_bytes
            && read_retained(&path_pin, "canonical run lock anchor pin")? == expected_anchor_bytes
            && sha256(&anchor_bytes) == anchor_sha256,
        "canonical run lock anchor bytes/hash changed"
    );
    let parsed_anchor: RunLockAnchor =
        serde_json::from_slice(&anchor_bytes).context("malformed retained run lock anchor")?;
    ensure!(
        parsed_anchor.schema_version == anchor.schema_version
            && parsed_anchor.state_device == anchor.state_device
            && parsed_anchor.state_inode == anchor.state_inode
            && parsed_anchor.lock_device == anchor.lock_device
            && parsed_anchor.lock_inode == anchor.lock_inode
            && parsed_anchor.identity_device == anchor.identity_device
            && parsed_anchor.identity_inode == anchor.identity_inode
            && parsed_anchor.lock_state_identity_sha256 == anchor.lock_state_identity_sha256
            && parsed_anchor.output_namespace == output_namespace
            && parsed_anchor.request_sha256 == request_hash,
        "canonical run lock anchor binding changed"
    );
    if require_published_state {
        ensure!(
            anchored_root.directory.same_entry(LOCK_STATE_NAME, state)?,
            "run lock-state directory was replaced"
        );
    }
    ensure!(
        state.identity()? == (anchor.state_device, anchor.state_inode),
        "run lock-state descriptor identity does not match durable anchor"
    );
    ensure!(
        state.entries()? == [LOCK_FILE_NAME, LOCK_IDENTITY_NAME],
        "run lock-state directory shape changed"
    );
    let path_lock = state.open_file(LOCK_FILE_NAME)?;
    ensure!(
        file_identity(&path_lock)? == (anchor.lock_device, anchor.lock_inode)
            && file_identity(lock)? == (anchor.lock_device, anchor.lock_inode),
        "run lock pathname does not match immutable identity"
    );
    let identity_file = state.open_file(LOCK_IDENTITY_NAME)?;
    ensure!(
        file_identity(&identity_file)? == identity_identity
            && identity_identity == (anchor.identity_device, anchor.identity_inode),
        "run lock identity pathname was replaced"
    );
    let bytes = read_regular_file(identity_file, "lock identity")?;
    ensure!(
        bytes == expected_identity_bytes,
        "run lock identity content changed"
    );
    read_and_validate_lock_state(state, request_hash)?;
    ensure!(
        anchor.lock_state_identity_sha256
            == lock_state_identity_sha256(
                state.identity()?,
                file_identity(lock)?,
                identity_identity,
                request_hash,
                output_namespace,
            )?,
        "run lock-state identity hash changed"
    );
    Ok(())
}

struct Storage {
    anchored_root: AnchoredDir,
    anchors: Dir,
    selection: File,
    selection_identity: (u64, u64),
    selection_bytes: Vec<u8>,
    anchor: File,
    anchor_identity: (u64, u64),
    anchor_bytes: Vec<u8>,
    anchor_sha256: String,
    anchor_value: RunLockAnchor,
    lock_state: Dir,
    bins: Dir,
    generations: Dir,
    archive: Dir,
    lock: File,
    identity_identity: (u64, u64),
    identity_bytes: Vec<u8>,
    request_hash: String,
    output_namespace: String,
    faults: Faults,
}

impl Storage {
    fn open(root: &Path, request_hash: &str) -> Result<Self> {
        let output_namespace = canonical_requested_path(root)?;
        let anchored_root = open_or_create_anchored_dir(root)
            .with_context(|| format!("cannot securely open output directory {}", root.display()))?;
        Self::open_anchored(anchored_root, output_namespace, request_hash)
    }

    fn open_anchored(
        anchored_root: AnchoredDir,
        output_namespace: String,
        request_hash: &str,
    ) -> Result<Self> {
        let mut faults = Faults::from_environment()?;
        let initialized =
            initialize_lock_state(&anchored_root, request_hash, &output_namespace, &mut faults)?;
        let InitializedLock {
            anchors,
            selection,
            selection_identity,
            selection_bytes,
            anchor,
            anchor_identity,
            anchor_bytes,
            anchor_sha256,
            anchor_value,
            state: lock_state,
            lock,
            identity_identity,
            identity_bytes,
            losing_stages,
        } = initialized;
        validate_lock_binding(
            &anchored_root,
            &anchors,
            &selection,
            selection_identity,
            &selection_bytes,
            &anchor,
            anchor_identity,
            &anchor_bytes,
            &anchor_sha256,
            &anchor_value,
            &lock_state,
            &lock,
            identity_identity,
            &identity_bytes,
            request_hash,
            &output_namespace,
            true,
        )?;
        validate_lock_binding(
            &anchored_root,
            &anchors,
            &selection,
            selection_identity,
            &selection_bytes,
            &anchor,
            anchor_identity,
            &anchor_bytes,
            &anchor_sha256,
            &anchor_value,
            &lock_state,
            &lock,
            identity_identity,
            &identity_bytes,
            request_hash,
            &output_namespace,
            true,
        )?;
        hold_lock_for_test()?;
        validate_lock_binding(
            &anchored_root,
            &anchors,
            &selection,
            selection_identity,
            &selection_bytes,
            &anchor,
            anchor_identity,
            &anchor_bytes,
            &anchor_sha256,
            &anchor_value,
            &lock_state,
            &lock,
            identity_identity,
            &identity_bytes,
            request_hash,
            &output_namespace,
            true,
        )?;
        anchored_root.verify()?;
        let bins = anchored_root.directory.open_or_create_dir("bins")?;
        validate_lock_binding(
            &anchored_root,
            &anchors,
            &selection,
            selection_identity,
            &selection_bytes,
            &anchor,
            anchor_identity,
            &anchor_bytes,
            &anchor_sha256,
            &anchor_value,
            &lock_state,
            &lock,
            identity_identity,
            &identity_bytes,
            request_hash,
            &output_namespace,
            true,
        )?;
        let generations = anchored_root.directory.open_or_create_dir("generations")?;
        validate_lock_binding(
            &anchored_root,
            &anchors,
            &selection,
            selection_identity,
            &selection_bytes,
            &anchor,
            anchor_identity,
            &anchor_bytes,
            &anchor_sha256,
            &anchor_value,
            &lock_state,
            &lock,
            identity_identity,
            &identity_bytes,
            request_hash,
            &output_namespace,
            true,
        )?;
        let archive = anchored_root.directory.open_or_create_dir("archive")?;
        let mut storage = Self {
            anchored_root,
            anchors,
            selection,
            selection_identity,
            selection_bytes,
            anchor,
            anchor_identity,
            anchor_bytes,
            anchor_sha256,
            anchor_value,
            lock_state,
            bins,
            generations,
            archive,
            lock,
            identity_identity,
            identity_bytes,
            request_hash: request_hash.to_owned(),
            output_namespace,
            faults,
        };
        storage.verify_anchors()?;
        for stage in losing_stages {
            storage.verify_anchors()?;
            archive_entry(
                &storage.anchored_root.directory,
                &storage.archive,
                &stage,
                "lock-init-loser",
                &mut storage.faults,
            )?;
        }
        storage.archive_staging()?;
        Ok(storage)
    }

    fn verify_anchors(&self) -> Result<()> {
        validate_lock_binding(
            &self.anchored_root,
            &self.anchors,
            &self.selection,
            self.selection_identity,
            &self.selection_bytes,
            &self.anchor,
            self.anchor_identity,
            &self.anchor_bytes,
            &self.anchor_sha256,
            &self.anchor_value,
            &self.lock_state,
            &self.lock,
            self.identity_identity,
            &self.identity_bytes,
            &self.request_hash,
            &self.output_namespace,
            true,
        )?;
        ensure!(
            self.anchored_root
                .directory
                .same_entry("bins", &self.bins)?,
            "bins directory was replaced"
        );
        ensure!(
            self.anchored_root
                .directory
                .same_entry("generations", &self.generations)?,
            "generations directory was replaced"
        );
        ensure!(
            self.anchored_root
                .directory
                .same_entry("archive", &self.archive)?,
            "archive directory was replaced"
        );
        Ok(())
    }

    fn archive_staging(&mut self) -> Result<()> {
        let root_names = self
            .anchored_root
            .directory
            .entries()?
            .into_iter()
            .filter(|name| {
                name.starts_with(".tmp-")
                    && !name.starts_with(".tmp-lock-state-")
                    && !name.starts_with(".tmp-lock-anchor-")
                    && !name.starts_with(".tmp-lock-selection-")
            })
            .collect::<Vec<_>>();
        for name in root_names {
            self.verify_anchors()?;
            archive_entry(
                &self.anchored_root.directory,
                &self.archive,
                &name,
                "orphan-staging",
                &mut self.faults,
            )?;
        }
        for name in self
            .bins
            .entries()?
            .into_iter()
            .filter(|name| name.starts_with(".stage-"))
            .collect::<Vec<_>>()
        {
            self.verify_anchors()?;
            archive_entry(
                &self.bins,
                &self.archive,
                &name,
                "orphan-staging",
                &mut self.faults,
            )?;
        }
        for name in self
            .generations
            .entries()?
            .into_iter()
            .filter(|name| name.starts_with(".stage-"))
            .collect::<Vec<_>>()
        {
            self.verify_anchors()?;
            archive_entry(
                &self.generations,
                &self.archive,
                &name,
                "orphan-staging",
                &mut self.faults,
            )?;
        }
        Ok(())
    }

    fn read_pointer(&self) -> Result<Option<Pointer>> {
        let Some(file) = self
            .anchored_root
            .directory
            .open_file_optional("current-generation.json")?
        else {
            return Ok(None);
        };
        let bytes = read_regular_file(file, "current generation pointer")?;
        let pointer: Pointer =
            serde_json::from_slice(&bytes).context("malformed current generation pointer")?;
        ensure!(
            bytes == json_line(&pointer)?,
            "current generation pointer is not canonical"
        );
        ensure!(
            pointer.schema_version == "qmc-current-generation-v2",
            "current generation pointer schema mismatch"
        );
        ensure!(
            pointer.anchor_sha256 == self.anchor_sha256,
            "current generation pointer anchor mismatch"
        );
        ensure!(
            pointer.path == format!("generations/{}", pointer.generation_sha256),
            "stale current generation pointer path"
        );
        Ok(Some(pointer))
    }

    fn read_generations(
        &mut self,
        request: &Request,
        request_hash: &str,
    ) -> Result<BTreeMap<String, Generation>> {
        let mut generations = BTreeMap::new();
        for identity in self.generations.entries()? {
            let parsed = self.read_generation(&identity, request, request_hash);
            match parsed {
                Ok(generation) => {
                    generations.insert(identity, generation);
                }
                Err(error) => {
                    self.verify_anchors()?;
                    archive_entry(
                        &self.generations,
                        &self.archive,
                        &identity,
                        "invalid-generation",
                        &mut self.faults,
                    )?;
                    eprintln!("qmc-sse: archived invalid generation {identity}: {error:#}");
                }
            }
        }
        Ok(generations)
    }

    fn read_generation(
        &self,
        identity: &str,
        request: &Request,
        request_hash: &str,
    ) -> Result<Generation> {
        ensure!(
            is_sha256(identity),
            "generation directory name is not a SHA256"
        );
        let directory = self.generations.open_dir(identity)?;
        ensure!(
            directory.entries()? == ["manifest.json"],
            "generation contains unexpected entries"
        );
        let bytes =
            read_regular_file(directory.open_file("manifest.json")?, "generation manifest")?;
        let manifest: Generation =
            serde_json::from_slice(&bytes).context("malformed generation manifest")?;
        ensure!(
            bytes == json_line(&manifest)?,
            "generation manifest is not canonical"
        );
        ensure!(
            sha256(&bytes) == identity,
            "generation manifest hash mismatch"
        );
        ensure!(
            manifest.schema_version == "qmc-checkpoint-generation-v2",
            "generation schema mismatch"
        );
        ensure!(
            manifest.anchor_sha256 == self.anchor_sha256,
            "generation anchor mismatch"
        );
        ensure!(
            manifest.request_sha256 == request_hash,
            "stale request generation"
        );
        ensure!(manifest.adapter == "QMC_SSE", "generation adapter mismatch");
        ensure!(
            manifest.source_hash == env!("QMC_SSE_SOURCE_HASH"),
            "stale source generation"
        );
        ensure!(
            manifest.build_hash == env!("QMC_SSE_BUILD_HASH"),
            "stale build generation"
        );
        ensure!(manifest.seed == request.seed, "stale seed generation");
        ensure!(
            manifest.completed_bin_count > 0
                && manifest.completed_bin_count <= request.total_bins(),
            "generation completed bin count invalid"
        );
        ensure!(
            manifest.bin_object_hashes.len() as u64 == manifest.completed_bin_count
                && manifest
                    .bin_object_hashes
                    .iter()
                    .all(|hash| is_sha256(hash)),
            "generation bin hashes are malformed"
        );
        ensure!(
            manifest
                .previous_generation_sha256
                .as_deref()
                .is_none_or(is_sha256),
            "generation predecessor hash is malformed"
        );
        ensure!(
            manifest.replay_update_count
                == request.updates_through_bin(manifest.completed_bin_count)?,
            "generation replay update count mismatch"
        );
        Ok(manifest)
    }

    fn validate_bin(
        &self,
        hash: &str,
        expected_bytes: &[u8],
        expected_bin: &Bin,
        replay: &Replay<'_>,
    ) -> Result<()> {
        let name = format!("{hash}.ndjson");
        let file = self
            .bins
            .open_file_optional(&name)?
            .with_context(|| format!("missing bin object {hash}"))?;
        let bytes = read_regular_file(file, "bin object")?;
        ensure!(sha256(&bytes) == hash, "bin object content hash mismatch");
        ensure!(bytes == expected_bytes, "deterministic replay bin mismatch");
        let parsed: Bin = serde_json::from_slice(&bytes).context("malformed bin object")?;
        parsed.validate(
            expected_bin.bin_index,
            replay.request.bin_length,
            replay.request.thinning,
            replay.graph.site_count,
        )
    }

    fn validate_generation_replay(
        &self,
        hash: &str,
        generation: &Generation,
        replay: &Replay<'_>,
    ) -> Result<()> {
        let count = generation.completed_bin_count as usize;
        ensure!(
            generation.bin_object_hashes == replay.bin_hashes[..count],
            "generation deterministic replay hashes mismatch"
        );
        let directory = self.generations.open_dir(hash)?;
        ensure!(
            directory.entries()? == ["manifest.json"],
            "generation winner shape mismatch"
        );
        let bytes = read_regular_file(
            directory.open_file("manifest.json")?,
            "generation winner manifest",
        )?;
        ensure!(
            sha256(&bytes) == hash,
            "generation winner identity mismatch"
        );
        ensure!(
            bytes == json_line(generation)?,
            "generation winner is not canonical"
        );
        for index in 0..count {
            self.validate_bin(
                &replay.bin_hashes[index],
                &replay.bin_bytes[index],
                &replay.bins[index],
                replay,
            )?;
        }
        Ok(())
    }

    fn filter_invalid_genesis(
        &mut self,
        generations: &mut BTreeMap<String, Generation>,
        replay: &Replay<'_>,
    ) -> Result<()> {
        let candidates = generations
            .iter()
            .filter(|(_, generation)| generation.previous_generation_sha256.is_none())
            .map(|(hash, _)| hash.clone())
            .collect::<Vec<_>>();
        for hash in candidates {
            if let Err(error) = self.validate_generation_replay(&hash, &generations[&hash], replay)
            {
                self.verify_anchors()?;
                archive_entry(
                    &self.generations,
                    &self.archive,
                    &hash,
                    "invalid-genesis",
                    &mut self.faults,
                )?;
                generations.remove(&hash);
                eprintln!("qmc-sse: archived invalid genesis {hash}: {error:#}");
            }
        }
        Ok(())
    }

    fn select_chain(
        &self,
        request: &Request,
        generations: &BTreeMap<String, Generation>,
        pointer: Option<&Pointer>,
    ) -> Result<Vec<String>> {
        let start = if let Some(pointer) = pointer {
            ensure!(
                generations.contains_key(&pointer.generation_sha256),
                "stale current generation pointer {} (available: {:?})",
                pointer.generation_sha256,
                generations.keys().collect::<Vec<_>>()
            );
            pointer.generation_sha256.clone()
        } else {
            let genesis = generations
                .iter()
                .filter(|(_, generation)| generation.previous_generation_sha256.is_none())
                .map(|(hash, _)| hash.clone())
                .collect::<Vec<_>>();
            ensure!(
                genesis.len() <= 1,
                "multiple distinct fully valid genesis generation hashes"
            );
            if genesis.is_empty() {
                ensure!(
                    generations.is_empty(),
                    "generation ancestry gap: no valid genesis"
                );
                return Ok(Vec::new());
            }
            genesis[0].clone()
        };
        let mut backwards = Vec::new();
        let mut cursor = start;
        let mut seen = BTreeSet::new();
        loop {
            ensure!(seen.insert(cursor.clone()), "generation ancestry cycle");
            backwards.push(cursor.clone());
            match generations[&cursor].previous_generation_sha256.clone() {
                Some(previous) => {
                    ensure!(
                        generations.contains_key(&previous),
                        "generation ancestry gap"
                    );
                    cursor = previous;
                }
                None => break,
            }
        }
        backwards.reverse();
        ensure!(
            generations[&backwards[0]].completed_bin_count
                == request.checkpoint_bins.min(request.total_bins()),
            "genesis completed bin count mismatch"
        );
        for pair in backwards.windows(2) {
            ensure!(
                generations[&pair[1]].completed_bin_count
                    == (generations[&pair[0]].completed_bin_count + request.checkpoint_bins)
                        .min(request.total_bins()),
                "generation ancestry checkpoint gap"
            );
        }
        let mut chain = backwards;
        loop {
            let current = chain.last().expect("selected chain is nonempty");
            let descendants = generations
                .iter()
                .filter(|(_, generation)| {
                    generation.previous_generation_sha256.as_ref() == Some(current)
                })
                .map(|(hash, _)| hash.clone())
                .collect::<Vec<_>>();
            ensure!(descendants.len() <= 1, "conflicting generation descendants");
            if descendants.is_empty() {
                break;
            }
            let descendant = descendants[0].clone();
            ensure!(
                generations[&descendant].completed_bin_count
                    == (generations[current].completed_bin_count + request.checkpoint_bins)
                        .min(request.total_bins()),
                "generation ancestry checkpoint gap"
            );
            chain.push(descendant);
        }
        ensure!(
            chain.len() == generations.len(),
            "unrelated or gapped published generation"
        );
        Ok(chain)
    }

    fn verify_chain(
        &self,
        chain: &[String],
        generations: &BTreeMap<String, Generation>,
        replay: &Replay<'_>,
    ) -> Result<u64> {
        for hash in chain {
            self.validate_generation_replay(hash, &generations[hash], replay)?;
        }
        Ok(chain
            .last()
            .map(|hash| generations[hash].completed_bin_count)
            .unwrap_or(0))
    }

    fn audit_orphans(&mut self, completed: u64, replay: &Replay<'_>) -> Result<()> {
        let committed = replay.bin_hashes[..completed as usize]
            .iter()
            .map(|hash| format!("{hash}.ndjson"))
            .collect::<BTreeSet<_>>();
        let immediate = replay
            .bin_hashes
            .get(completed as usize)
            .map(|hash| format!("{hash}.ndjson"));
        for name in self.bins.entries()? {
            if name.starts_with(".stage-") || committed.contains(&name) {
                continue;
            }
            let keep_immediate = immediate.as_deref() == Some(&name)
                && self
                    .validate_bin(
                        &replay.bin_hashes[completed as usize],
                        &replay.bin_bytes[completed as usize],
                        &replay.bins[completed as usize],
                        replay,
                    )
                    .is_ok();
            if !keep_immediate {
                let future = replay
                    .bin_hashes
                    .iter()
                    .skip(completed as usize + 1)
                    .any(|hash| name == format!("{hash}.ndjson"));
                self.verify_anchors()?;
                archive_entry(
                    &self.bins,
                    &self.archive,
                    &name,
                    if future { "future-orphan" } else { "orphan" },
                    &mut self.faults,
                )?;
            }
        }
        Ok(())
    }

    fn publish_bin(&mut self, index: usize, replay: &Replay<'_>) -> Result<()> {
        self.verify_anchors()?;
        let hash = &replay.bin_hashes[index];
        let bytes = &replay.bin_bytes[index];
        let destination = format!("{hash}.ndjson");
        if self.bins.open_file_optional(&destination)?.is_some() {
            return self.validate_bin(hash, bytes, &replay.bins[index], replay);
        }
        let stage = format!(".stage-bin-{hash}-{}", std::process::id());
        let stage_identity = write_fsynced(
            &self.bins,
            &stage,
            bytes,
            &mut self.faults,
            "staged bin object",
            "after-bin-file-fsync",
        )?;
        self.faults.boundary("before-bin-rename")?;
        self.verify_anchors()?;
        ensure!(
            file_identity(&self.bins.open_file(&stage)?)? == stage_identity,
            "staged bin object was replaced"
        );
        if self
            .bins
            .rename_noreplace(&stage, &self.bins, &destination)?
        {
            self.faults.boundary("after-bin-rename")?;
            self.faults.fsync_dir(
                &self.bins,
                "bins directory after rename",
                "after-bins-directory-fsync",
            )?;
            self.validate_bin(hash, bytes, &replay.bins[index], replay)?;
        } else {
            self.validate_bin(hash, bytes, &replay.bins[index], replay)?;
            self.verify_anchors()?;
            archive_entry(
                &self.bins,
                &self.archive,
                &stage,
                "identical",
                &mut self.faults,
            )?;
        }
        Ok(())
    }

    fn publish_generation(
        &mut self,
        generation: &Generation,
        replay: &Replay<'_>,
    ) -> Result<String> {
        self.verify_anchors()?;
        let bytes = json_line(generation)?;
        let identity = sha256(&bytes);
        let stage = format!(".stage-generation-{identity}-{}", std::process::id());
        let stage_directory = self.generations.create_dir(&stage)?;
        write_fsynced(
            &stage_directory,
            "manifest.json",
            &bytes,
            &mut self.faults,
            "generation manifest",
            "after-generation-manifest-fsync",
        )?;
        self.faults.fsync_dir(
            &stage_directory,
            "staged generation directory",
            "after-generation-directory-fsync",
        )?;
        self.faults.boundary("before-generation-rename")?;
        self.verify_anchors()?;
        ensure!(
            self.generations.open_dir(&stage)?.identity()? == stage_directory.identity()?,
            "staged generation directory was replaced"
        );
        ensure!(
            stage_directory.entries()? == ["manifest.json"],
            "staged generation shape changed"
        );
        ensure!(
            read_regular_file(
                stage_directory.open_file("manifest.json")?,
                "staged generation manifest"
            )? == bytes,
            "staged generation manifest was replaced"
        );
        if self
            .generations
            .rename_noreplace(&stage, &self.generations, &identity)?
        {
            self.faults.boundary("after-generation-rename")?;
            self.faults.fsync_dir(
                &self.generations,
                "generations directory after rename",
                "after-generations-directory-fsync",
            )?;
            self.validate_generation_replay(&identity, generation, replay)?;
        } else {
            self.validate_generation_replay(&identity, generation, replay)?;
            self.verify_anchors()?;
            archive_entry(
                &self.generations,
                &self.archive,
                &stage,
                "identical",
                &mut self.faults,
            )?;
        }
        Ok(identity)
    }

    fn publish_pointer(&mut self, generation_hash: &str) -> Result<()> {
        self.verify_anchors()?;
        let pointer = Pointer {
            schema_version: "qmc-current-generation-v2".to_owned(),
            anchor_sha256: self.anchor_sha256.clone(),
            generation_sha256: generation_hash.to_owned(),
            path: format!("generations/{generation_hash}"),
        };
        let bytes = json_line(&pointer)?;
        let temporary = format!(".tmp-current-generation-{}", std::process::id());
        let temporary_identity = write_fsynced(
            &self.anchored_root.directory,
            &temporary,
            &bytes,
            &mut self.faults,
            "temporary generation pointer",
            "after-pointer-file-fsync",
        )?;
        self.faults.boundary("before-pointer-replace")?;
        self.verify_anchors()?;
        ensure!(
            file_identity(&self.anchored_root.directory.open_file(&temporary)?)?
                == temporary_identity,
            "temporary generation pointer was replaced"
        );
        self.anchored_root.directory.rename_replace(
            &temporary,
            &self.anchored_root.directory,
            "current-generation.json",
        )?;
        self.faults.boundary("after-pointer-rename")?;
        ensure!(
            read_regular_file(
                self.anchored_root
                    .directory
                    .open_file("current-generation.json")?,
                "published generation pointer"
            )? == bytes,
            "published generation pointer changed"
        );
        self.faults.fsync_dir(
            &self.anchored_root.directory,
            "run directory after pointer replace",
            "after-run-directory-fsync",
        )
    }
}

fn hold_lock_for_test() -> Result<()> {
    let (Ok(ready), Ok(release)) = (
        env::var("QMC_SSE_TEST_HOLD_LOCK_READY"),
        env::var("QMC_SSE_TEST_HOLD_LOCK_RELEASE"),
    ) else {
        return Ok(());
    };
    let ready = PathBuf::from(ready);
    let release = PathBuf::from(release);
    OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&ready)
        .context("cannot create held-lock test marker")?
        .sync_all()
        .context("cannot fsync held-lock test marker")?;
    let deadline = Instant::now() + Duration::from_secs(30);
    while !release.exists() {
        ensure!(
            Instant::now() < deadline,
            "held-lock test release timed out"
        );
        thread::sleep(Duration::from_millis(5));
    }
    Ok(())
}

pub fn publish(output: &Path, request: &Request, graph: &Graph) -> Result<()> {
    let request_hash = request.hash()?;
    let _local_lock = LocalLock::acquire(output, &request_hash)?;
    let storage = Storage::open(output, &request_hash)?;
    publish_with_storage(storage, request, graph, &request_hash)
}

pub fn publish_inherited(output_descriptor: i32, request: &Request, graph: &Graph) -> Result<()> {
    let request_hash = request.hash()?;
    let anchored_root = AnchoredDir::from_inherited_fd(output_descriptor)?;
    let (device, inode) = anchored_root.directory.identity()?;
    let output_namespace = format!("qmc-sse-fd-output-v1:{device}:{inode}");
    let _local_lock = LocalLock::acquire_namespace(&output_namespace, &request_hash)?;
    let storage = Storage::open_anchored(anchored_root, output_namespace, &request_hash)?;
    publish_with_storage(storage, request, graph, &request_hash)
}

fn publish_with_storage(
    mut storage: Storage,
    request: &Request,
    graph: &Graph,
    request_hash: &str,
) -> Result<()> {
    let bins = generate_bins(request, graph)?;
    let bin_bytes = bins
        .iter()
        .map(json_line)
        .collect::<Result<Vec<Vec<u8>>>>()?;
    let bin_hashes = bin_bytes
        .iter()
        .map(|bytes| sha256(bytes))
        .collect::<Vec<_>>();
    let replay = Replay {
        bin_hashes: &bin_hashes,
        bin_bytes: &bin_bytes,
        bins: &bins,
        request,
        graph,
    };
    let pointer = storage.read_pointer()?;
    let mut generations = storage.read_generations(request, request_hash)?;
    storage.filter_invalid_genesis(&mut generations, &replay)?;
    let chain = storage.select_chain(request, &generations, pointer.as_ref())?;
    let mut completed = storage.verify_chain(&chain, &generations, &replay)?;
    storage.audit_orphans(completed, &replay)?;

    let mut previous = chain.last().cloned();
    let recovered_complete = completed == request.total_bins();
    if let Some(latest) = previous.as_deref()
        && pointer
            .as_ref()
            .map(|value| value.generation_sha256.as_str())
            != Some(latest)
    {
        storage.publish_pointer(latest)?;
    }
    while completed < request.total_bins() {
        let next = (completed + request.checkpoint_bins).min(request.total_bins());
        for index in completed as usize..next as usize {
            storage.publish_bin(index, &replay)?;
        }
        let generation = Generation {
            schema_version: "qmc-checkpoint-generation-v2".to_owned(),
            anchor_sha256: storage.anchor_sha256.clone(),
            request_sha256: request_hash.to_owned(),
            adapter: "QMC_SSE".to_owned(),
            source_hash: env!("QMC_SSE_SOURCE_HASH").to_owned(),
            build_hash: env!("QMC_SSE_BUILD_HASH").to_owned(),
            seed: request.seed,
            completed_bin_count: next,
            bin_object_hashes: bin_hashes[..next as usize].to_vec(),
            previous_generation_sha256: previous.clone(),
            replay_update_count: request.updates_through_bin(next)?,
        };
        let generation_hash = storage.publish_generation(&generation, &replay)?;
        storage.publish_pointer(&generation_hash)?;
        previous = Some(generation_hash);
        completed = next;
    }
    if recovered_complete && let Some(latest) = previous {
        let generation = generations
            .get(&latest)
            .context("recovered terminal generation missing")?;
        let identity = storage.publish_generation(generation, &replay)?;
        ensure!(identity == latest, "terminal generation identity changed");
        storage.publish_pointer(&latest)?;
    }
    Ok(())
}
