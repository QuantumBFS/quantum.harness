from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import threading
import time
from typing import Any
import uuid

import jax

from qcontrol.config import ExperimentConfig


_TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]*\Z", re.ASCII)
_THREAD_LOCKS_GUARD = threading.Lock()
_THREAD_LOCKS: dict[str, threading.RLock] = {}
_OWNER_FIELDS = {
    "boot_id",
    "hostname",
    "lease_expires_at",
    "nonce",
    "pid",
    "process_start_id",
    "started_at",
}


class ArtifactConflict(RuntimeError):
    """Persisted state cannot safely be reused or replaced."""


class TrialClaimConflict(ArtifactConflict):
    """A trial has an active or unverifiable owner."""


class ArtifactDurabilityError(ArtifactConflict):
    """A replace or rollback reached an uncertain durability boundary."""

    def __init__(
        self,
        message: str,
        *,
        old_sha256: str | None,
        new_sha256: str,
        present: str,
    ) -> None:
        self.old_sha256 = old_sha256
        self.new_sha256 = new_sha256
        self.present = present
        super().__init__(
            f"{message}; present={present}, old_sha256={old_sha256}, "
            f"new_sha256={new_sha256}"
        )


def canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _strict_token(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a strict lowercase ASCII token")
    return value


def _safe_relative_path(value: str | os.PathLike[str]) -> Path:
    raw = os.fspath(value)
    if not isinstance(raw, str) or "\\" in raw or "\0" in raw:
        raise ValueError("artifact path must be a nonempty relative path")
    path = Path(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("artifact path must be a nonempty relative path")
    return path


def _git_state(root: Path) -> dict[str, object]:
    def run_text(*arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    try:
        revision = run_text("rev-parse", "HEAD")
        repository = Path(run_text("rev-parse", "--show-toplevel"))
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        tracked_diff = subprocess.run(
            ["git", "diff", "--binary", "HEAD", "--"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout.split(b"\0")
        digest = hashlib.sha256()
        digest.update(status)
        digest.update(tracked_diff)
        for raw_path in sorted(path for path in untracked if path):
            relative = os.fsdecode(raw_path)
            path = repository / relative
            digest.update(raw_path)
            digest.update(b"\0")
            if path.is_symlink():
                digest.update(os.readlink(path).encode("utf-8"))
            elif path.is_file():
                digest.update(bytes.fromhex(_file_sha256(path)))
            else:
                digest.update(b"<non-file>")
        dirty = bool(status)
        worktree_sha256 = digest.hexdigest()
    except (OSError, subprocess.CalledProcessError):
        revision = "unavailable"
        dirty = True
        worktree_sha256 = "unavailable"
    return {
        "dirty": dirty,
        "revision": revision,
        "worktree_sha256": worktree_sha256,
    }


def _collect_provenance(config_payload: object) -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    source_hashes = {
        path.relative_to(root).as_posix(): _file_sha256(path)
        for path in sorted((root / "src" / "qcontrol").glob("*.py"))
    }
    try:
        device_platform = str(jax.devices()[0].platform)
    except (IndexError, RuntimeError):
        device_platform = "unavailable"
    return {
        "config": config_payload,
        "git": _git_state(root),
        "jax": {
            "platform": device_platform,
            "x64_enabled": bool(jax.config.x64_enabled),
        },
        "source_hashes": source_hashes,
        "uv_lock_sha256": _file_sha256(root / "uv.lock"),
        "versions": {
            "jax": importlib.metadata.version("jax"),
            "jaxlib": importlib.metadata.version("jaxlib"),
            "numpy": importlib.metadata.version("numpy"),
            "python": platform.python_version(),
            "scipy": importlib.metadata.version("scipy"),
        },
    }


def collect_provenance(config: ExperimentConfig) -> dict[str, object]:
    if not isinstance(config, ExperimentConfig):
        raise ValueError("config must be an ExperimentConfig")
    return _collect_provenance(config.canonical_dict())


def _boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return "unavailable"


def _process_start_identity(pid: int) -> str | None:
    try:
        value = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    try:
        fields = value.rsplit(")", 1)[1].split()
        return fields[19]
    except (IndexError, ValueError):
        return None


@dataclass
class TrialClaim(AbstractContextManager["TrialClaim"]):
    store: ArtifactStore
    trial_id: str
    path: Path
    owner: dict[str, object]
    _released: bool = False

    def __enter__(self) -> TrialClaim:
        return self

    def release(self) -> None:
        if self._released:
            return
        self.store._release_claim(self)
        self._released = True

    def __exit__(self, *exc_info: object) -> None:
        self.release()


class ArtifactStore:
    MANIFEST_SCHEMA = 2
    INDEX_SCHEMA = 1
    READY_SCHEMA = 1

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        stale_lock_seconds: float = 24 * 60 * 60,
    ) -> None:
        if isinstance(stale_lock_seconds, bool) or stale_lock_seconds < 0:
            raise ValueError("stale_lock_seconds must be nonnegative")
        requested = Path(root).absolute()
        self._reject_symlink_chain(requested, include_final=True)
        requested.mkdir(parents=True, exist_ok=True)
        self._reject_symlink_chain(requested, include_final=True)
        requested = requested.resolve(strict=True)
        if not requested.is_dir():
            raise ArtifactConflict("artifact store root must be a directory")
        self.root = requested
        self.stale_lock_seconds = float(stale_lock_seconds)
        self._instance_lock = threading.RLock()
        self._lock_depth = 0
        self._bound_config_payload: object | None = None
        self._bound_plan_sha256: str | None = None
        key = str(self.root)
        with _THREAD_LOCKS_GUARD:
            self._thread_lock = _THREAD_LOCKS.setdefault(key, threading.RLock())

    @staticmethod
    def _reject_symlink_chain(path: Path, *, include_final: bool) -> None:
        limit = len(path.parts) if include_final else len(path.parts) - 1
        current = Path(path.anchor)
        for part in path.parts[1:limit]:
            current /= part
            if current.is_symlink():
                raise ArtifactConflict(f"symlink path component rejected: {current}")

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        with self._thread_lock, self._instance_lock:
            if self._lock_depth:
                self._lock_depth += 1
                try:
                    yield
                finally:
                    self._lock_depth -= 1
                return
            lock_path = self.root / ".store.lock"
            descriptor = os.open(
                lock_path,
                os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                self._lock_depth = 1
                yield
            finally:
                self._lock_depth = 0
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)

    def _path(self, relative_path: str | os.PathLike[str], *, create: bool) -> Path:
        relative = _safe_relative_path(relative_path)
        destination = self.root.joinpath(relative)
        try:
            destination.relative_to(self.root)
        except ValueError:
            raise ValueError("artifact path must remain beneath store root") from None
        current = self.root
        for part in relative.parts[:-1]:
            current /= part
            if current.exists() or current.is_symlink():
                if current.is_symlink():
                    raise ArtifactConflict(
                        f"symlink parent rejected: {current.relative_to(self.root)}"
                    )
                if not current.is_dir():
                    raise ArtifactConflict("artifact parent is not a directory")
            elif create:
                current.mkdir()
                self._fsync_directory(current.parent)
            else:
                break
        if destination.is_symlink():
            raise ArtifactConflict(
                f"symlink artifact rejected: {destination.relative_to(self.root)}"
            )
        return destination

    @classmethod
    def create(
        cls,
        root: str | os.PathLike[str],
        config: ExperimentConfig,
    ) -> ArtifactStore:
        store = cls(root)
        store.initialize_run(config.canonical_dict(), None)
        return store

    @classmethod
    def resume(
        cls,
        root: str | os.PathLike[str],
        config: ExperimentConfig,
    ) -> ArtifactStore:
        store = cls(root)
        store._bound_config_payload = config.canonical_dict()
        store.verify_bound_provenance()
        return store

    def create_or_resume(self, config: ExperimentConfig) -> ArtifactStore:
        if (self.root / "ready.json").exists():
            return type(self).resume(self.root, config)
        return type(self).create(self.root, config)

    def initialize_run(
        self,
        config_payload: object,
        plan_payload: object | None,
    ) -> None:
        manifest = {
            "provenance": _collect_provenance(config_payload),
            "schema_version": self.MANIFEST_SCHEMA,
        }
        manifest_bytes = canonical_json_bytes(manifest)
        plan_bytes = (
            None if plan_payload is None else canonical_json_bytes(plan_payload)
        )
        marker = {
            "manifest_sha256": _sha256(manifest_bytes),
            "plan_sha256": None if plan_bytes is None else _sha256(plan_bytes),
            "schema_version": self.READY_SCHEMA,
        }
        with self._exclusive():
            ready_path = self._path("ready.json", create=False)
            if ready_path.exists():
                self._verify_initialization_locked(marker, manifest_bytes, plan_bytes)
                self._bound_config_payload = config_payload
                self._bound_plan_sha256 = marker["plan_sha256"]
                return
            transaction_path = self._path("initializing.json", create=True)
            if transaction_path.exists():
                if transaction_path.read_bytes() != canonical_json_bytes(marker):
                    raise ArtifactConflict(
                        "incomplete initialization belongs to different configuration"
                    )
            else:
                self._publish_bytes_locked(
                    Path("initializing.json"),
                    canonical_json_bytes(marker),
                    immutable=True,
                )
            self._publish_bytes_locked(
                Path("manifest.json"),
                manifest_bytes,
                immutable=True,
            )
            if plan_bytes is not None:
                self._publish_bytes_locked(
                    Path("plan.json"),
                    plan_bytes,
                    immutable=True,
                )
            self._publish_bytes_locked(
                Path("ready.json"),
                canonical_json_bytes(marker),
                immutable=True,
            )
            self._best_effort_unlink(transaction_path)
            self._bound_config_payload = config_payload
            self._bound_plan_sha256 = marker["plan_sha256"]

    def _verify_initialization_locked(
        self,
        marker: dict[str, object],
        manifest_bytes: bytes,
        plan_bytes: bytes | None,
    ) -> None:
        ready = self._path("ready.json", create=False)
        manifest = self._path("manifest.json", create=False)
        plan = self._path("plan.json", create=False)
        if ready.read_bytes() != canonical_json_bytes(marker):
            raise ArtifactConflict("run plan/initialization marker differs")
        if not manifest.is_file() or manifest.read_bytes() != manifest_bytes:
            raise ArtifactConflict("run manifest differs")
        if plan_bytes is None:
            if plan.exists():
                raise ArtifactConflict("unexpected plan for single-config store")
        elif not plan.is_file() or plan.read_bytes() != plan_bytes:
            raise ArtifactConflict("run plan differs")

    def verify_bound_provenance(self) -> None:
        if self._bound_config_payload is None:
            raise ArtifactConflict("store has no bound provenance configuration")
        expected = {
            "provenance": _collect_provenance(self._bound_config_payload),
            "schema_version": self.MANIFEST_SCHEMA,
        }
        with self._exclusive():
            ready = self._read_json_locked(Path("ready.json"))
            manifest_path = self._path("manifest.json", create=False)
            if (
                not isinstance(ready, dict)
                or set(ready) != {
                    "manifest_sha256",
                    "plan_sha256",
                    "schema_version",
                }
                or ready["schema_version"] != self.READY_SCHEMA
                or ready["manifest_sha256"] != _file_sha256(manifest_path)
                or self._read_json_locked(Path("manifest.json")) != expected
            ):
                raise ArtifactConflict(
                    "artifact provenance does not match current state"
                )
            if ready["plan_sha256"] != self._bound_plan_sha256:
                raise ArtifactConflict("artifact plan binding changed")
            if self._bound_plan_sha256 is None:
                if self._path("plan.json", create=False).exists():
                    raise ArtifactConflict("unexpected plan in single-config store")
            elif not self.verify_file("plan.json", self._bound_plan_sha256):
                raise ArtifactConflict("artifact plan changed during execution")

    def bind_provenance(self, config_payload: object) -> None:
        self.initialize_run(config_payload, None)

    def _replace(self, source: Path, destination: Path) -> None:
        os.replace(source, destination)

    def _unlink(self, path: Path, *, missing_ok: bool = False) -> None:
        path.unlink(missing_ok=missing_ok)

    def _fsync_directory(self, path: Path) -> None:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _write_temp(self, parent: Path, data: bytes) -> Path:
        temp = parent / f".artifact.tmp-{os.getpid()}-{uuid.uuid4().hex}"
        descriptor = os.open(
            temp,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o644,
        )
        try:
            try:
                view = memoryview(data)
                while view:
                    written = os.write(descriptor, view)
                    view = view[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except BaseException:
            self._best_effort_unlink(temp)
            raise
        return temp

    def _best_effort_unlink(self, path: Path) -> None:
        try:
            self._unlink(path, missing_ok=True)
        except OSError:
            pass

    def _present_state(
        self,
        destination: Path,
        old_digest: str | None,
        new_digest: str,
    ) -> str:
        if not destination.exists():
            return "missing"
        try:
            digest = _file_sha256(destination)
        except OSError:
            return "unreadable"
        if digest == new_digest:
            return "new"
        if old_digest is not None and digest == old_digest:
            return "old"
        return f"other:{digest}"

    def _rollback_or_raise(
        self,
        *,
        destination: Path,
        backup: Path | None,
        old_digest: str | None,
        new_digest: str,
        cause: BaseException,
    ) -> None:
        try:
            if backup is None:
                self._unlink(destination, missing_ok=True)
            else:
                self._replace(backup, destination)
            self._fsync_directory(destination.parent)
        except BaseException as rollback_error:
            raise ArtifactDurabilityError(
                f"publication durability failed ({cause!r}); "
                f"rollback failed ({rollback_error!r})",
                old_sha256=old_digest,
                new_sha256=new_digest,
                present=self._present_state(
                    destination,
                    old_digest,
                    new_digest,
                ),
            ) from cause
        raise ArtifactDurabilityError(
            f"publication durability failed and rollback completed ({cause!r})",
            old_sha256=old_digest,
            new_sha256=new_digest,
            present=self._present_state(destination, old_digest, new_digest),
        ) from cause

    def _publish_bytes_locked(
        self,
        relative: Path,
        data: bytes,
        *,
        immutable: bool,
    ) -> str:
        destination = self._path(relative, create=True)
        digest = _sha256(data)
        if destination.exists():
            existing = destination.read_bytes()
            if immutable:
                if existing != data:
                    raise ArtifactConflict(f"immutable artifact differs: {relative}")
                return digest
        temp = self._write_temp(destination.parent, data)
        backup: Path | None = None
        old_digest: str | None = None
        replaced = False
        try:
            if destination.exists():
                old_digest = _file_sha256(destination)
                backup = destination.parent / (
                    f".artifact.backup-{os.getpid()}-{uuid.uuid4().hex}"
                )
                os.link(destination, backup, follow_symlinks=False)
            self._replace(temp, destination)
            replaced = True
            try:
                self._fsync_directory(destination.parent)
            except BaseException as error:
                self._rollback_or_raise(
                    destination=destination,
                    backup=backup,
                    old_digest=old_digest,
                    new_digest=digest,
                    cause=error,
                )
            if _file_sha256(destination) != digest:
                try:
                    if backup is None:
                        self._unlink(destination)
                    else:
                        self._replace(backup, destination)
                    self._fsync_directory(destination.parent)
                except BaseException as error:
                    raise ArtifactDurabilityError(
                        "published hash mismatch and rollback failed",
                        old_sha256=old_digest,
                        new_sha256=digest,
                        present=self._present_state(
                            destination,
                            old_digest,
                            digest,
                        ),
                    ) from error
                raise ArtifactConflict(f"published artifact hash mismatch: {relative}")
            return digest
        finally:
            if not replaced:
                self._best_effort_unlink(temp)
            if backup is not None:
                self._best_effort_unlink(backup)

    def publish_json(
        self,
        relative_path: str | os.PathLike[str],
        payload: object,
        *,
        immutable: bool = False,
    ) -> str:
        relative = _safe_relative_path(relative_path)
        data = canonical_json_bytes(payload)
        with self._exclusive():
            return self._publish_bytes_locked(
                relative,
                data,
                immutable=immutable,
            )

    def _read_json_locked(self, relative: Path) -> Any:
        path = self._path(relative, create=False)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ArtifactConflict(f"invalid artifact: {path.name}") from error

    def read_json(self, relative_path: str | os.PathLike[str]) -> Any:
        relative = _safe_relative_path(relative_path)
        with self._exclusive():
            return self._read_json_locked(relative)

    def verify_file(
        self,
        relative_path: str | os.PathLike[str],
        expected_sha256: str,
    ) -> bool:
        relative = _safe_relative_path(relative_path)
        if (
            not isinstance(expected_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256, re.ASCII) is None
        ):
            return False
        with self._exclusive():
            path = self._path(relative, create=False)
            return path.is_file() and _file_sha256(path) == expected_sha256

    def _read_index_locked(self) -> dict[str, object]:
        path = self._path("index.json", create=False)
        if not path.exists():
            return {"schema_version": self.INDEX_SCHEMA, "trials": {}}
        index = self._read_json_locked(Path("index.json"))
        if (
            not isinstance(index, dict)
            or set(index) != {"schema_version", "trials"}
            or type(index["schema_version"]) is not int
            or index["schema_version"] != self.INDEX_SCHEMA
            or not isinstance(index["trials"], dict)
            or any(
                _TOKEN.fullmatch(key) is None
                or not isinstance(value, str)
                or re.fullmatch(r"[0-9a-f]{64}", value, re.ASCII) is None
                for key, value in index["trials"].items()
            )
        ):
            raise ArtifactConflict("invalid trial index schema")
        return index

    def _update_index_locked(self, trial_id: str, digest: str) -> None:
        index = self._read_index_locked()
        trials = dict(index["trials"])
        prior = trials.get(trial_id)
        if prior is not None and prior != digest:
            raise ArtifactConflict(f"immutable trial index differs: {trial_id}")
        trials[trial_id] = digest
        self._publish_bytes_locked(
            Path("index.json"),
            canonical_json_bytes(
                {"schema_version": self.INDEX_SCHEMA, "trials": trials}
            ),
            immutable=False,
        )

    def publish_trial(self, trial_id: str, payload: object) -> str:
        token = _strict_token(trial_id, name="trial ID token")
        data = canonical_json_bytes(payload)
        with self._exclusive():
            digest = self._publish_bytes_locked(
                Path("trials") / f"{token}.json",
                data,
                immutable=True,
            )
            self._update_index_locked(token, digest)
            return digest

    def adopt_trial(
        self,
        trial_id: str,
        validator: Callable[[object], None],
    ) -> bool:
        token = _strict_token(trial_id, name="trial ID token")
        with self._exclusive():
            path = self._path(Path("trials") / f"{token}.json", create=False)
            if not path.exists():
                return False
            payload = self._read_json_locked(
                Path("trials") / f"{token}.json"
            )
            validator(payload)
            digest = _file_sha256(path)
            self._update_index_locked(token, digest)
            return True

    def trial_hashes(self) -> dict[str, str]:
        with self._exclusive():
            index = self._read_index_locked()
            return dict(index["trials"])

    def completed_trial_ids(self) -> frozenset[str]:
        with self._exclusive():
            hashes = dict(self._read_index_locked()["trials"])
            for trial_id, digest in hashes.items():
                path = self._path(
                    Path("trials") / f"{trial_id}.json",
                    create=False,
                )
                if not path.is_file() or _file_sha256(path) != digest:
                    raise ArtifactConflict(f"trial hash mismatch: {trial_id}")
            return frozenset(hashes)

    def owner_identity(
        self,
        *,
        lease_seconds: float | None = None,
    ) -> dict[str, object]:
        lease = (
            self.stale_lock_seconds
            if lease_seconds is None
            else float(lease_seconds)
        )
        now = time.time()
        return {
            "boot_id": _boot_id(),
            "hostname": socket.gethostname(),
            "lease_expires_at": now + lease,
            "nonce": uuid.uuid4().hex,
            "pid": os.getpid(),
            "process_start_id": _process_start_identity(os.getpid()),
            "started_at": now,
        }

    def _owner_is_stale(self, owner: object) -> bool:
        if (
            not isinstance(owner, dict)
            or set(owner) != _OWNER_FIELDS
            or not isinstance(owner["hostname"], str)
            or type(owner["pid"]) is not int
            or owner["pid"] <= 0
            or not isinstance(owner["process_start_id"], str)
            or not owner["process_start_id"]
            or not isinstance(owner["boot_id"], str)
            or type(owner["started_at"]) not in {int, float}
            or type(owner["lease_expires_at"]) not in {int, float}
            or not isinstance(owner["nonce"], str)
            or re.fullmatch(r"[0-9a-f]{32}", owner["nonce"], re.ASCII) is None
        ):
            return False
        if time.time() <= float(owner["lease_expires_at"]):
            return False
        if owner["hostname"] != socket.gethostname():
            return True
        if owner["boot_id"] != _boot_id():
            return True
        current_start = _process_start_identity(int(owner["pid"]))
        return current_start is None or current_start != owner["process_start_id"]

    def claim_trial(self, trial_id: str) -> TrialClaim:
        token = _strict_token(trial_id, name="trial ID token")
        owner = self.owner_identity()
        relative = Path("claims") / f"{token}.lock"
        with self._exclusive():
            path = self._path(relative, create=True)
            if path.exists():
                try:
                    existing = self._read_json_locked(relative)
                except ArtifactConflict:
                    raise TrialClaimConflict(
                        f"trial {token} claim cannot prove stale"
                    ) from None
                if not self._owner_is_stale(existing):
                    detail = (
                        "claimed by active owner"
                        if isinstance(existing, dict)
                        and type(existing.get("lease_expires_at")) in {int, float}
                        and time.time() <= float(existing["lease_expires_at"])
                        else "claim cannot prove stale"
                    )
                    raise TrialClaimConflict(f"trial {token} {detail}")
                reread = self._read_json_locked(relative)
                if (
                    reread != existing
                    or not isinstance(reread, dict)
                    or reread.get("nonce") != existing.get("nonce")
                    or not self._owner_is_stale(reread)
                ):
                    raise TrialClaimConflict(
                        f"trial {token} stale owner changed during reclamation"
                    )
                self._unlink(path)
                self._fsync_directory(path.parent)
            self._publish_bytes_locked(
                relative,
                canonical_json_bytes(owner),
                immutable=True,
            )
            return TrialClaim(self, token, path, owner)

    def _release_claim(self, claim: TrialClaim) -> None:
        with self._exclusive():
            try:
                current = self._read_json_locked(
                    Path("claims") / f"{claim.trial_id}.lock"
                )
            except ArtifactConflict as error:
                raise TrialClaimConflict(
                    "trial claim disappeared or became unreadable before release"
                ) from error
            if (
                current != claim.owner
                or not isinstance(current, dict)
                or current.get("nonce") != claim.owner.get("nonce")
            ):
                raise TrialClaimConflict(
                    "trial claim owner changed before release"
                )
            self._unlink(claim.path)
            self._fsync_directory(claim.path.parent)
