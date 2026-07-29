from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import time
from typing import Any
import uuid

import jax

from qcontrol.config import ExperimentConfig


class ArtifactConflict(RuntimeError):
    """Raised when persisted state cannot safely be reused or replaced."""


class TrialClaimConflict(ArtifactConflict):
    """Raised when a trial has an active or unverifiable owner."""


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
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _safe_relative_path(value: str | os.PathLike[str]) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("artifact path must be a nonempty relative path")
    return path


def _git_state(root: Path) -> dict[str, object]:
    def run(*arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    try:
        revision = run("rev-parse", "HEAD")
        dirty = bool(run("status", "--porcelain", "--untracked-files=all"))
    except (OSError, subprocess.CalledProcessError):
        revision = "unavailable"
        dirty = True
    return {"dirty": dirty, "revision": revision}


def _collect_provenance(config_payload: object) -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    source_hashes = {
        path.relative_to(root).as_posix(): _file_sha256(path)
        for path in sorted((root / "src" / "qcontrol").glob("*.py"))
    }
    lock_path = root / "uv.lock"
    try:
        device = jax.devices()[0]
        device_platform = str(device.platform)
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
        "uv_lock_sha256": _file_sha256(lock_path),
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
    MANIFEST_SCHEMA = 1
    INDEX_SCHEMA = 1

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        stale_lock_seconds: float = 24 * 60 * 60,
    ) -> None:
        self.root = Path(root)
        if stale_lock_seconds < 0:
            raise ValueError("stale_lock_seconds must be nonnegative")
        self.stale_lock_seconds = float(stale_lock_seconds)
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def create(
        cls,
        root: str | os.PathLike[str],
        config: ExperimentConfig,
    ) -> ArtifactStore:
        store = cls(root)
        manifest_path = store.root / "manifest.json"
        if manifest_path.exists():
            raise ArtifactConflict("artifact store already has a manifest")
        store.publish_json(
            "manifest.json",
            {
                "provenance": collect_provenance(config),
                "schema_version": cls.MANIFEST_SCHEMA,
            },
        )
        return store

    @classmethod
    def resume(
        cls,
        root: str | os.PathLike[str],
        config: ExperimentConfig,
    ) -> ArtifactStore:
        store = cls(root)
        manifest = store.read_json("manifest.json")
        expected = {
            "provenance": collect_provenance(config),
            "schema_version": cls.MANIFEST_SCHEMA,
        }
        if manifest != expected:
            raise ArtifactConflict("artifact provenance does not match current state")
        return store

    def create_or_resume(self, config: ExperimentConfig) -> ArtifactStore:
        if (self.root / "manifest.json").exists():
            return type(self).resume(self.root, config)
        return type(self).create(self.root, config)

    def bind_provenance(self, config_payload: object) -> None:
        expected = {
            "provenance": _collect_provenance(config_payload),
            "schema_version": self.MANIFEST_SCHEMA,
        }
        path = self.root / "manifest.json"
        if path.exists():
            if self.read_json("manifest.json") != expected:
                raise ArtifactConflict(
                    "artifact provenance does not match current state"
                )
            return
        self.publish_json("manifest.json", expected, immutable=True)

    def _replace(self, source: Path, destination: Path) -> None:
        os.replace(source, destination)

    def _write_temp(self, parent: Path, data: bytes) -> Path:
        parent.mkdir(parents=True, exist_ok=True)
        temp = parent / f".artifact.tmp-{os.getpid()}-{uuid.uuid4().hex}"
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(descriptor)
        return temp

    def publish_json(
        self,
        relative_path: str | os.PathLike[str],
        payload: object,
        *,
        immutable: bool = False,
    ) -> str:
        data = canonical_json_bytes(payload)
        digest = _sha256(data)
        relative = _safe_relative_path(relative_path)
        destination = self.root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            raise ArtifactConflict("artifact destination cannot be a symbolic link")
        if immutable and destination.exists():
            if destination.read_bytes() != data:
                raise ArtifactConflict(f"immutable artifact differs: {relative}")
            return digest

        temp = self._write_temp(destination.parent, data)
        backup: Path | None = None
        replaced = False
        try:
            if destination.exists():
                backup = destination.parent / (
                    f".artifact.backup-{os.getpid()}-{uuid.uuid4().hex}"
                )
                os.link(destination, backup)
            self._replace(temp, destination)
            replaced = True
            _fsync_directory(destination.parent)
            if _file_sha256(destination) != digest:
                raise ArtifactConflict(
                    f"published artifact hash mismatch: {relative}"
                )
        except BaseException:
            if replaced:
                if backup is not None and backup.exists():
                    os.replace(backup, destination)
                    _fsync_directory(destination.parent)
                    backup = None
                else:
                    destination.unlink(missing_ok=True)
                    _fsync_directory(destination.parent)
            raise
        finally:
            temp.unlink(missing_ok=True)
            if backup is not None:
                backup.unlink(missing_ok=True)
        return digest

    def read_json(self, relative_path: str | os.PathLike[str]) -> Any:
        path = self.root / _safe_relative_path(relative_path)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ArtifactConflict(f"invalid artifact: {path.name}") from error

    def verify_file(
        self,
        relative_path: str | os.PathLike[str],
        expected_sha256: str,
    ) -> bool:
        path = self.root / _safe_relative_path(relative_path)
        return (
            len(expected_sha256) == 64
            and path.is_file()
            and not path.is_symlink()
            and _file_sha256(path) == expected_sha256
        )

    def _read_index(self) -> dict[str, object]:
        path = self.root / "index.json"
        if not path.exists():
            return {"schema_version": self.INDEX_SCHEMA, "trials": {}}
        index = self.read_json("index.json")
        if (
            not isinstance(index, dict)
            or index.get("schema_version") != self.INDEX_SCHEMA
            or not isinstance(index.get("trials"), dict)
        ):
            raise ArtifactConflict("invalid trial index schema")
        return index

    def publish_trial(self, trial_id: str, payload: object) -> str:
        if (
            not trial_id
            or not trial_id.isascii()
            or trial_id.lower() != trial_id
            or any(not (character.isalnum() or character in "-_") for character in trial_id)
        ):
            raise ValueError(
                "trial_id must contain lowercase ASCII letters, digits, hyphens, and underscores"
            )
        relative = f"trials/{trial_id}.json"
        digest = self.publish_json(relative, payload, immutable=True)
        deadline = time.monotonic() + 30.0
        while True:
            try:
                index_claim = self.claim_trial("index")
                break
            except TrialClaimConflict:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
        with index_claim:
            index = self._read_index()
            trials = dict(index["trials"])
            prior = trials.get(trial_id)
            if prior is not None and prior != digest:
                raise ArtifactConflict(f"immutable trial index differs: {trial_id}")
            trials[trial_id] = digest
            self.publish_json(
                "index.json",
                {"schema_version": self.INDEX_SCHEMA, "trials": trials},
            )
        return digest

    def trial_hashes(self) -> dict[str, str]:
        index = self._read_index()
        return {str(key): str(value) for key, value in index["trials"].items()}

    def completed_trial_ids(self) -> frozenset[str]:
        hashes = self.trial_hashes()
        for trial_id, digest in hashes.items():
            if not self.verify_file(f"trials/{trial_id}.json", digest):
                raise ArtifactConflict(f"trial hash mismatch: {trial_id}")
        return frozenset(hashes)

    def _claim_owner(self) -> dict[str, object]:
        return {
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "started_at": time.time(),
            "token": uuid.uuid4().hex,
        }

    def _owner_is_provably_stale(self, owner: object) -> bool:
        if not isinstance(owner, dict) or set(owner) != {
            "hostname",
            "pid",
            "started_at",
            "token",
        }:
            return False
        if (
            owner["hostname"] != socket.gethostname()
            or isinstance(owner["pid"], bool)
            or not isinstance(owner["pid"], int)
            or owner["pid"] <= 0
            or not isinstance(owner["started_at"], (int, float))
            or not isinstance(owner["token"], str)
            or not owner["token"]
        ):
            return False
        if time.time() - float(owner["started_at"]) < self.stale_lock_seconds:
            return False
        try:
            os.kill(int(owner["pid"]), 0)
        except ProcessLookupError:
            return True
        except (PermissionError, OSError):
            return False
        return False

    def claim_trial(self, trial_id: str) -> TrialClaim:
        if not trial_id:
            raise ValueError("trial_id must be nonempty")
        claims = self.root / "claims"
        claims.mkdir(parents=True, exist_ok=True)
        path = claims / f"{trial_id}.lock"
        owner = self._claim_owner()
        data = canonical_json_bytes(owner)
        for _ in range(2):
            try:
                descriptor = os.open(
                    path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o644,
                )
            except FileExistsError:
                try:
                    existing = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    raise TrialClaimConflict(
                        f"trial {trial_id} claim cannot prove stale"
                    ) from None
                if not self._owner_is_provably_stale(existing):
                    detail = (
                        "claimed by active owner"
                        if isinstance(existing, dict)
                        and existing.get("hostname") == socket.gethostname()
                        and existing.get("pid") == os.getpid()
                        else "claim cannot prove stale"
                    )
                    raise TrialClaimConflict(f"trial {trial_id} {detail}")
                stale = claims / f".{trial_id}.stale-{uuid.uuid4().hex}"
                try:
                    os.replace(path, stale)
                    _fsync_directory(claims)
                except FileNotFoundError:
                    continue
                finally:
                    stale.unlink(missing_ok=True)
                continue
            else:
                try:
                    with os.fdopen(descriptor, "wb", closefd=False) as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                finally:
                    os.close(descriptor)
                _fsync_directory(claims)
                return TrialClaim(self, trial_id, path, owner)
        raise TrialClaimConflict(f"trial {trial_id} claim raced with another owner")

    def _release_claim(self, claim: TrialClaim) -> None:
        try:
            current = json.loads(claim.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise TrialClaimConflict("trial claim disappeared before release") from None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TrialClaimConflict("trial claim is unreadable at release") from error
        if current != claim.owner:
            raise TrialClaimConflict("trial claim owner changed before release")
        claim.path.unlink()
        _fsync_directory(claim.path.parent)
