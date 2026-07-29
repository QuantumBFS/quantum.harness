from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

import h5py
import numpy as np

from .counter_rng import (
    RNG_VERSION,
    STREAM_COUNT,
    StreamIdentity,
    derive_stream_material,
)
from .trajectory import (
    TrajectoryRequest,
    TrajectoryResult,
    request_digest,
    validate_trajectory_request,
)


TRAJECTORY_SCHEMA = "challenge-194-trajectory-artifact-v1"
TRAJECTORY_DIGEST_SCHEMA = "challenge-194-trajectory-digest-v1"
BATCH_SCHEMA = "challenge-194-batch-manifest-v1"
PROGRESS_SCHEMA = "challenge-194-progress-v1"
CONVERSION_VERSION = "challenge-194-artifact-conversion-v1"

_HEX256 = re.compile(r"[0-9a-f]{64}")
_HEX160 = re.compile(r"[0-9a-f]{40}")
_SAFE_BATCH_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_TRAJECTORY_NAME = re.compile(r"trajectory-([0-9a-f]{64})\.h5")
_DIGEST_NAME = re.compile(r"trajectory-([0-9a-f]{64})\.sha256\.json")
_BATCH_NAME = re.compile(r"batch-([A-Za-z0-9][A-Za-z0-9._-]{0,127})\.json")
_PROVENANCE_KEYS = frozenset(
    {
        "source_revision",
        "clean_tree",
        "uv_lock_sha256",
        "runtime_capability_sha256",
        "analysis_plan_sha256",
        "rng_sha256",
        "conversion_version",
        "rng_version",
    }
)
_EXPECTED_KEYS = frozenset(
    {
        "request_sha256",
        "kernel_sha256",
        "source_revision",
        "uv_lock_sha256",
        "runtime_capability_sha256",
        "analysis_plan_sha256",
        "rng_sha256",
        "conversion_version",
        "rng_version",
    }
)
_ROOT_ENTRIES = frozenset(
    {
        "request.json",
        "environment.json",
        "kernel",
        "seed-manifest.json",
        "capability.json",
        "trajectories",
        "batches",
        "progress.json",
        "manifest.json",
    }
)


class ArtifactIntegrityError(RuntimeError):
    """An immutable artifact cannot be trusted or resumed."""


def _canonical_json_bytes(document: object) -> bytes:
    try:
        return (
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise ArtifactIntegrityError("document is not canonical JSON") from error


def _checked_regular(path: Path, description: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ArtifactIntegrityError(f"unable to inspect {description}") from error
    if stat.S_ISLNK(metadata.st_mode):
        raise ArtifactIntegrityError(f"{description} must not be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise ArtifactIntegrityError(f"{description} must be a regular file")
    return metadata


def _check_existing_path_chain(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current = current / component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise ArtifactIntegrityError("unable to inspect run path") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise ArtifactIntegrityError("run path must not contain symlinks")


def _prepare_run_directory(run_dir: Path) -> tuple[Path, Path, Path]:
    if not isinstance(run_dir, Path):
        raise TypeError("run_dir must be a pathlib.Path")
    _check_existing_path_chain(run_dir)
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ArtifactIntegrityError("unable to create run directory") from error
    try:
        mode = run_dir.lstat().st_mode
    except OSError as error:
        raise ArtifactIntegrityError("unable to inspect run directory") from error
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ArtifactIntegrityError("run directory must be a non-symlink directory")
    directories = []
    for name in ("trajectories", "batches"):
        candidate = run_dir / name
        if candidate.exists() or candidate.is_symlink():
            try:
                mode = candidate.lstat().st_mode
            except OSError as error:
                raise ArtifactIntegrityError(
                    f"unable to inspect {name} directory"
                ) from error
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise ArtifactIntegrityError(
                    f"{name} must be a non-symlink directory"
                )
        else:
            try:
                candidate.mkdir()
            except FileExistsError:
                mode = candidate.lstat().st_mode
                if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                    raise ArtifactIntegrityError(
                        f"{name} must be a non-symlink directory"
                    )
            except OSError as error:
                raise ArtifactIntegrityError(f"unable to create {name}") from error
        directories.append(candidate)
    return run_dir, directories[0], directories[1]


@contextmanager
def _directory_lock(directory: Path):
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(directory, flags)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _flush_hdf5(stream: h5py.File) -> None:
    stream.flush()


def _fsync_file(stream: h5py.File) -> None:
    handle = stream.id.get_vfd_handle()
    if not isinstance(handle, int):
        raise ArtifactIntegrityError("HDF5 driver did not expose a file descriptor")
    os.fsync(handle)


def _replace(source: Path, destination: Path) -> None:
    os.replace(source, destination)


def _hash_file(path: Path) -> tuple[str, int]:
    _checked_regular(path, "trajectory")
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
                size += len(block)
    except OSError as error:
        raise ArtifactIntegrityError("unable to hash trajectory") from error
    return digest.hexdigest(), size


def _write_unique_fsynced(path: Path, payload: bytes) -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_json_once(path: Path, payload: bytes) -> None:
    partial = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.partial"
    try:
        _write_unique_fsynced(partial, payload)
        try:
            os.link(partial, path, follow_symlinks=False)
        except FileExistsError:
            raise FileExistsError(f"immutable artifact already exists: {path}")
        _checked_regular(path, "published JSON artifact")
        partial.unlink()
        _fsync_directory(path.parent)
    except BaseException:
        # A partial is intentionally retained across publication failures.
        raise


def _validate_provenance(provenance: dict[str, object]) -> None:
    if not isinstance(provenance, dict) or set(provenance) != _PROVENANCE_KEYS:
        raise ArtifactIntegrityError("provenance fields are not exact")
    if provenance["clean_tree"] is not True:
        raise ArtifactIntegrityError("dirty-tree provenance is forbidden")
    if (
        not isinstance(provenance["source_revision"], str)
        or _HEX160.fullmatch(provenance["source_revision"]) is None
    ):
        raise ArtifactIntegrityError("source revision is malformed")
    for key in (
        "uv_lock_sha256",
        "runtime_capability_sha256",
        "rng_sha256",
    ):
        if not isinstance(provenance[key], str) or _HEX256.fullmatch(
            provenance[key]
        ) is None:
            raise ArtifactIntegrityError(f"{key} is malformed")
    analysis = provenance["analysis_plan_sha256"]
    if analysis != "not-created-pre-pilot" and (
        not isinstance(analysis, str) or _HEX256.fullmatch(analysis) is None
    ):
        raise ArtifactIntegrityError("analysis plan hash is malformed")
    if provenance["rng_version"] != RNG_VERSION:
        raise ArtifactIntegrityError("RNG version is stale")
    if provenance["conversion_version"] != CONVERSION_VERSION:
        raise ArtifactIntegrityError("conversion version is stale")


def _validate_expected(expected: dict[str, str]) -> None:
    if not isinstance(expected, dict) or set(expected) != _EXPECTED_KEYS:
        raise ArtifactIntegrityError("expected dependency fields are not exact")
    for key, value in expected.items():
        if not isinstance(value, str):
            raise ArtifactIntegrityError(f"expected {key} is not a string")
    if _HEX256.fullmatch(expected["request_sha256"]) is None:
        raise ArtifactIntegrityError("expected request hash is malformed")
    if _HEX256.fullmatch(expected["kernel_sha256"]) is None:
        raise ArtifactIntegrityError("expected kernel hash is malformed")
    if _HEX160.fullmatch(expected["source_revision"]) is None:
        raise ArtifactIntegrityError("expected source revision is malformed")
    for key in ("uv_lock_sha256", "runtime_capability_sha256", "rng_sha256"):
        if _HEX256.fullmatch(expected[key]) is None:
            raise ArtifactIntegrityError(f"expected {key} is malformed")
    analysis = expected["analysis_plan_sha256"]
    if analysis != "not-created-pre-pilot" and _HEX256.fullmatch(analysis) is None:
        raise ArtifactIntegrityError("expected analysis plan hash is malformed")


def _stream_material(request: TrajectoryRequest) -> tuple[np.ndarray, np.ndarray, list[str]]:
    materials = [
        derive_stream_material(
            StreamIdentity(
                master_seed=request.master_seed,
                phase=request.phase,
                length=request.length,
                sigma_grid_id=request.sigma_grid_id,
                replica=request.replica,
                stream_id=stream_id,
            )
        )
        for stream_id in range(STREAM_COUNT)
    ]
    hashes = [material.material_sha256 for material in materials]
    if len(hashes) != len(set(hashes)):
        raise ArtifactIntegrityError("derived RNG key material collides")
    return (
        np.stack([material.initial_counter for material in materials]).astype(
            "<u4", copy=False
        ),
        np.stack([material.key for material in materials]).astype("<u4", copy=False),
        hashes,
    )


def _write_hdf5(
    path: Path,
    request: TrajectoryRequest,
    result: TrajectoryResult,
    provenance: Mapping[str, object],
) -> None:
    counters, keys, material_hashes = _stream_material(request)
    with h5py.File(path, "x", libver="earliest") as stream:
        attributes: tuple[tuple[str, object], ...] = (
            ("schema_version", TRAJECTORY_SCHEMA),
            ("rng_version", provenance["rng_version"]),
            ("conversion_version", provenance["conversion_version"]),
            ("request_sha256", result.request_sha256),
            ("kernel_sha256", request.kernel_sha256),
            ("source_revision", provenance["source_revision"]),
            ("clean_tree", np.uint8(1)),
            ("uv_lock_sha256", provenance["uv_lock_sha256"]),
            ("runtime_capability_sha256", provenance["runtime_capability_sha256"]),
            ("analysis_plan_sha256", provenance["analysis_plan_sha256"]),
            ("rng_sha256", provenance["rng_sha256"]),
            ("length", np.uint64(request.length)),
            ("sigma", np.float64(request.sigma)),
            ("sigma_grid_id", request.sigma_grid_id),
            ("master_seed", np.uint64(request.master_seed)),
            ("phase", request.phase),
            ("replica", np.uint64(request.replica)),
            ("event_count", np.uint64(result.event_count)),
            ("duplicate_count", np.uint64(result.duplicate_count)),
        )
        for key, value in attributes:
            stream.attrs[key] = value
        request_group = stream.create_group("request", track_order=False)
        result_group = stream.create_group("result", track_order=False)
        rng_group = stream.create_group("rng", track_order=False)
        request_group.create_dataset(
            "kappas", data=request.kappas.astype("<f8", copy=False), track_times=False
        )
        result_group.create_dataset(
            "observables",
            data=result.observables.astype("<f8", copy=False),
            track_times=False,
        )
        result_group.create_dataset(
            "terminal_counters",
            data=result.terminal_counters.astype("<u4", copy=False),
            track_times=False,
        )
        result_group.create_dataset(
            "draw_counts",
            data=result.draw_counts.astype("<u8", copy=False),
            track_times=False,
        )
        result_group.create_dataset(
            "hash_diagnostics",
            data=result.hash_diagnostics.astype("<u8", copy=False),
            track_times=False,
        )
        rng_group.create_dataset(
            "initial_counters", data=counters, track_times=False
        )
        rng_group.create_dataset("keys", data=keys, track_times=False)
        string_dtype = h5py.string_dtype(encoding="ascii", length=64)
        rng_group.create_dataset(
            "key_material_sha256",
            data=np.asarray(material_hashes, dtype=string_dtype),
            dtype=string_dtype,
            track_times=False,
        )
        _flush_hdf5(stream)
        _fsync_file(stream)


def _exact_group(group: h5py.Group, names: set[str], label: str) -> None:
    if set(group.keys()) != names:
        raise ArtifactIntegrityError(f"{label} dataset membership is not exact")
    if any(not isinstance(group[name], h5py.Dataset) for name in names):
        raise ArtifactIntegrityError(f"{label} contains a non-dataset member")


def _text_attribute(attributes: h5py.AttributeManager, key: str) -> str:
    try:
        value = attributes[key]
    except KeyError as error:
        raise ArtifactIntegrityError(f"missing HDF5 attribute: {key}") from error
    if not isinstance(value, str):
        raise ArtifactIntegrityError(f"HDF5 attribute {key} is not text")
    return value


def _unsigned_attribute(attributes: h5py.AttributeManager, key: str) -> int:
    try:
        value = attributes[key]
    except KeyError as error:
        raise ArtifactIntegrityError(f"missing HDF5 attribute: {key}") from error
    if not isinstance(value, np.unsignedinteger):
        raise ArtifactIntegrityError(f"HDF5 attribute {key} is not unsigned")
    return int(value)


def _read_dataset(
    group: h5py.Group,
    name: str,
    dtype: str,
    shape: tuple[int, ...],
) -> np.ndarray:
    dataset = group[name]
    assert isinstance(dataset, h5py.Dataset)
    if dataset.dtype.str != dtype or dataset.shape != shape:
        raise ArtifactIntegrityError(f"dataset {name} has stale dtype or shape")
    value = np.asarray(dataset[...])
    if not value.flags.c_contiguous:
        value = np.ascontiguousarray(value)
    return value


def _load_hdf5(path: Path, expected: dict[str, str]) -> TrajectoryResult:
    _validate_expected(expected)
    _checked_regular(path, "trajectory")
    try:
        with h5py.File(path, "r") as stream:
            if set(stream.keys()) != {"request", "result", "rng"}:
                raise ArtifactIntegrityError("HDF5 top-level membership is not exact")
            if set(stream.attrs.keys()) != {
                "schema_version",
                "rng_version",
                "conversion_version",
                "request_sha256",
                "kernel_sha256",
                "source_revision",
                "clean_tree",
                "uv_lock_sha256",
                "runtime_capability_sha256",
                "analysis_plan_sha256",
                "rng_sha256",
                "length",
                "sigma",
                "sigma_grid_id",
                "master_seed",
                "phase",
                "replica",
                "event_count",
                "duplicate_count",
            }:
                raise ArtifactIntegrityError("HDF5 attributes are not exact")
            request_group = stream["request"]
            result_group = stream["result"]
            rng_group = stream["rng"]
            if not all(
                isinstance(group, h5py.Group)
                for group in (request_group, result_group, rng_group)
            ):
                raise ArtifactIntegrityError("HDF5 group structure is invalid")
            assert isinstance(request_group, h5py.Group)
            assert isinstance(result_group, h5py.Group)
            assert isinstance(rng_group, h5py.Group)
            _exact_group(request_group, {"kappas"}, "request")
            _exact_group(
                result_group,
                {
                    "observables",
                    "terminal_counters",
                    "draw_counts",
                    "hash_diagnostics",
                },
                "result",
            )
            _exact_group(
                rng_group,
                {"initial_counters", "keys", "key_material_sha256"},
                "rng",
            )
            if _text_attribute(stream.attrs, "schema_version") != TRAJECTORY_SCHEMA:
                raise ArtifactIntegrityError("trajectory schema is stale")
            if _unsigned_attribute(stream.attrs, "clean_tree") != 1:
                raise ArtifactIntegrityError("dirty-tree trajectory is forbidden")
            for key in _EXPECTED_KEYS:
                if _text_attribute(stream.attrs, key) != expected[key]:
                    raise ArtifactIntegrityError(f"trajectory dependency mismatch: {key}")
            length = _unsigned_attribute(stream.attrs, "length")
            master_seed = _unsigned_attribute(stream.attrs, "master_seed")
            replica = _unsigned_attribute(stream.attrs, "replica")
            sigma_raw = stream.attrs.get("sigma")
            if not isinstance(sigma_raw, np.floating):
                raise ArtifactIntegrityError("sigma attribute is not float64")
            sigma = float(sigma_raw)
            sigma_grid_id = _text_attribute(stream.attrs, "sigma_grid_id")
            phase = _text_attribute(stream.attrs, "phase")
            kappas_dataset = request_group["kappas"]
            if not isinstance(kappas_dataset, h5py.Dataset):
                raise ArtifactIntegrityError("kappas is not a dataset")
            if kappas_dataset.dtype.str != "<f8" or len(kappas_dataset.shape) != 1:
                raise ArtifactIntegrityError("kappas dtype or rank is stale")
            kappas = np.asarray(kappas_dataset[...], dtype=np.float64)
            request = TrajectoryRequest(
                length=length,
                sigma=sigma,
                sigma_grid_id=sigma_grid_id,
                kappas=kappas,
                master_seed=master_seed,
                phase=phase,  # type: ignore[arg-type]
                replica=replica,
                kernel_sha256=expected["kernel_sha256"],
            )
            validate_trajectory_request(request)
            if request_digest(request) != expected["request_sha256"]:
                raise ArtifactIntegrityError("stored request does not match request hash")
            n_kappa = request.kappas.size
            observables = _read_dataset(
                result_group, "observables", "<f8", (n_kappa, 10)
            )
            terminal = _read_dataset(
                result_group, "terminal_counters", "<u4", (STREAM_COUNT, 4)
            )
            draw_counts = _read_dataset(
                result_group, "draw_counts", "<u8", (STREAM_COUNT, 3)
            )
            diagnostics = _read_dataset(
                result_group, "hash_diagnostics", "<u8", (5,)
            )
            initial = _read_dataset(
                rng_group, "initial_counters", "<u4", (STREAM_COUNT, 4)
            )
            keys = _read_dataset(rng_group, "keys", "<u4", (STREAM_COUNT, 2))
            hashes_dataset = rng_group["key_material_sha256"]
            if (
                not isinstance(hashes_dataset, h5py.Dataset)
                or hashes_dataset.shape != (STREAM_COUNT,)
                or hashes_dataset.dtype.kind != "S"
                or hashes_dataset.dtype.itemsize != 64
            ):
                raise ArtifactIntegrityError("key-material hash dataset is stale")
            try:
                material_hashes = [
                    value.decode("ascii") for value in hashes_dataset[...]
                ]
            except (UnicodeDecodeError, AttributeError) as error:
                raise ArtifactIntegrityError("key-material hashes are malformed") from error
            expected_initial, expected_keys, expected_material_hashes = (
                _stream_material(request)
            )
            if (
                not np.array_equal(initial, expected_initial)
                or not np.array_equal(keys, expected_keys)
                or material_hashes != expected_material_hashes
            ):
                raise ArtifactIntegrityError("RNG stream material is corrupt")
            event_count = _unsigned_attribute(stream.attrs, "event_count")
            duplicate_count = _unsigned_attribute(stream.attrs, "duplicate_count")
            try:
                return TrajectoryResult(
                    request_sha256=expected["request_sha256"],
                    observables=observables,
                    terminal_counters=terminal,
                    draw_counts=draw_counts,
                    event_count=event_count,
                    duplicate_count=duplicate_count,
                    hash_diagnostics=diagnostics,
                )
            except ValueError as error:
                raise ArtifactIntegrityError("trajectory result is invalid") from error
    except ArtifactIntegrityError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ArtifactIntegrityError("unable to parse trajectory HDF5") from error


def _semantic_reload(path: Path, expected: dict[str, str]) -> TrajectoryResult:
    return _load_hdf5(path, expected)


def _read_canonical_json(path: Path, description: str) -> object:
    _checked_regular(path, description)
    try:
        payload = path.read_bytes()
        document = json.loads(payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArtifactIntegrityError(f"unable to read {description}") from error
    if payload != _canonical_json_bytes(document):
        raise ArtifactIntegrityError(f"{description} is not canonical JSON")
    return document


def _verify_digest(path: Path, trajectory_id: str) -> tuple[str, int]:
    sidecar = path.with_suffix(".sha256.json")
    document = _read_canonical_json(sidecar, "trajectory digest sidecar")
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "trajectory_id",
        "trajectory_sha256",
        "artifact_size",
    }:
        raise ArtifactIntegrityError("trajectory digest fields are not exact")
    if (
        document["schema_version"] != TRAJECTORY_DIGEST_SCHEMA
        or document["trajectory_id"] != trajectory_id
        or not isinstance(document["artifact_size"], int)
        or isinstance(document["artifact_size"], bool)
        or document["artifact_size"] < 0
        or not isinstance(document["trajectory_sha256"], str)
        or _HEX256.fullmatch(document["trajectory_sha256"]) is None
    ):
        raise ArtifactIntegrityError("trajectory digest sidecar is invalid")
    actual_hash, actual_size = _hash_file(path)
    if (
        document["trajectory_sha256"] != actual_hash
        or document["artifact_size"] != actual_size
    ):
        raise ArtifactIntegrityError("whole-file trajectory digest mismatch")
    return actual_hash, actual_size


def publish_trajectory(
    run_dir: Path,
    request: TrajectoryRequest,
    result: TrajectoryResult,
    provenance: dict[str, object],
) -> Path:
    validate_trajectory_request(request)
    if not isinstance(result, TrajectoryResult):
        raise TypeError("result must be a TrajectoryResult")
    trajectory_id = request_digest(request)
    if result.request_sha256 != trajectory_id:
        raise ArtifactIntegrityError("result belongs to a different request")
    if result.observables.shape[0] != request.kappas.size:
        raise ArtifactIntegrityError("result does not cover every requested coupling")
    _validate_provenance(provenance)
    expected = {
        key: str(value)
        for key, value in provenance.items()
        if key != "clean_tree"
    }
    expected["request_sha256"] = trajectory_id
    expected["kernel_sha256"] = request.kernel_sha256
    _, trajectories, _ = _prepare_run_directory(run_dir)
    final = trajectories / f"trajectory-{trajectory_id}.h5"
    sidecar = final.with_suffix(".sha256.json")
    unique = f"{os.getpid()}.{uuid.uuid4().hex}"
    partial = trajectories / f".trajectory-{trajectory_id}.{unique}.partial"
    digest_partial = trajectories / f".trajectory-{trajectory_id}.{unique}.sha256.partial"
    intent = trajectories / f".trajectory-{trajectory_id}.{unique}.intent"
    intent_document = {
        "final_name": final.name,
        "partial_name": partial.name,
        "semantic_hashes": expected,
        "trajectory_id": trajectory_id,
    }
    with _directory_lock(trajectories):
        if final.exists() or final.is_symlink() or sidecar.exists() or sidecar.is_symlink():
            raise FileExistsError(f"immutable trajectory already exists: {final}")
        _write_unique_fsynced(intent, _canonical_json_bytes(intent_document))
        _fsync_directory(trajectories)
        _write_hdf5(partial, request, result, provenance)
        _semantic_reload(partial, expected)
        trajectory_hash, artifact_size = _hash_file(partial)
        digest_document = {
            "artifact_size": artifact_size,
            "schema_version": TRAJECTORY_DIGEST_SCHEMA,
            "trajectory_id": trajectory_id,
            "trajectory_sha256": trajectory_hash,
        }
        _write_unique_fsynced(
            digest_partial, _canonical_json_bytes(digest_document)
        )
        if final.exists() or final.is_symlink() or sidecar.exists() or sidecar.is_symlink():
            raise FileExistsError(f"immutable trajectory already exists: {final}")
        _replace(partial, final)
        try:
            os.link(digest_partial, sidecar, follow_symlinks=False)
        except FileExistsError as error:
            raise ArtifactIntegrityError("trajectory sidecar publication raced") from error
        digest_partial.unlink()
        _fsync_directory(trajectories)
        intent.unlink()
        try:
            _fsync_directory(trajectories)
        except BaseException:
            # If cleanup durability is not confirmed, restore a visible marker.
            # The preceding durable directory state also still contains it after
            # a real crash, but restoring it makes an I/O-error return fail closed
            # without relying on a subsequent restart.
            if not intent.exists():
                _write_unique_fsynced(
                    intent, _canonical_json_bytes(intent_document)
                )
            raise
    return final


def load_verified_trajectory(
    path: Path, expected: dict[str, str]
) -> TrajectoryResult:
    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path")
    match = _TRAJECTORY_NAME.fullmatch(path.name)
    if match is None:
        raise ArtifactIntegrityError("trajectory filename is not canonical")
    _check_existing_path_chain(path)
    _verify_digest(path, match.group(1))
    result = _load_hdf5(path, expected)
    if result.request_sha256 != match.group(1):
        raise ArtifactIntegrityError("trajectory ID does not match its filename")
    return result


def _internal_expected(path: Path) -> dict[str, str]:
    _checked_regular(path, "trajectory")
    try:
        with h5py.File(path, "r") as stream:
            return {key: _text_attribute(stream.attrs, key) for key in _EXPECTED_KEYS}
    except ArtifactIntegrityError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ArtifactIntegrityError("unable to read trajectory dependencies") from error


def publish_batch_manifest(
    run_dir: Path,
    batch_id: str,
    trajectory_paths: Sequence[Path],
) -> Path:
    if not isinstance(batch_id, str) or _SAFE_BATCH_ID.fullmatch(batch_id) is None:
        raise ValueError("batch_id is not in the safe canonical namespace")
    if isinstance(trajectory_paths, (str, bytes)) or not isinstance(
        trajectory_paths, Sequence
    ):
        raise TypeError("trajectory_paths must be a sequence of paths")
    _, trajectories, batches = _prepare_run_directory(run_dir)
    members: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in trajectory_paths:
        if not isinstance(path, Path):
            raise TypeError("trajectory path must be a pathlib.Path")
        if path.parent != trajectories:
            raise ArtifactIntegrityError("batch member is outside trajectories directory")
        match = _TRAJECTORY_NAME.fullmatch(path.name)
        if match is None:
            raise ArtifactIntegrityError("batch member filename is not canonical")
        trajectory_id = match.group(1)
        if trajectory_id in seen:
            raise ArtifactIntegrityError("batch contains duplicate trajectory ID")
        seen.add(trajectory_id)
        load_verified_trajectory(path, _internal_expected(path))
        trajectory_hash, _ = _verify_digest(path, trajectory_id)
        members.append(
            {
                "path": f"trajectories/{path.name}",
                "trajectory_id": trajectory_id,
                "trajectory_sha256": trajectory_hash,
            }
        )
    if not members:
        raise ArtifactIntegrityError("batch must retain at least one trajectory")
    members.sort(key=lambda member: member["trajectory_id"])
    document = {
        "batch_id": batch_id,
        "members": members,
        "schema_version": BATCH_SCHEMA,
    }
    final = batches / f"batch-{batch_id}.json"
    with _directory_lock(batches):
        if final.exists() or final.is_symlink():
            raise FileExistsError(f"immutable batch already exists: {final}")
        _publish_json_once(final, _canonical_json_bytes(document))
    return final


def _directory_entries(directory: Path) -> list[Path]:
    try:
        return sorted(directory.iterdir(), key=lambda path: path.name)
    except OSError as error:
        raise ArtifactIntegrityError("unable to inspect artifact directory") from error


def _verify_root_membership(run_dir: Path) -> None:
    for path in _directory_entries(run_dir):
        if path.name not in _ROOT_ENTRIES:
            raise ArtifactIntegrityError(f"unknown run artifact: {path.name}")
        if path.is_symlink():
            raise ArtifactIntegrityError("run artifacts must not be symlinks")


def reconstruct_progress(
    run_dir: Path, expected: dict[str, str]
) -> dict[str, object]:
    _validate_expected(expected)
    run_dir, trajectories, batches = _prepare_run_directory(run_dir)
    _verify_root_membership(run_dir)
    trajectory_files: list[Path] = []
    sidecar_ids: set[str] = set()
    for path in _directory_entries(trajectories):
        if path.is_symlink():
            raise ArtifactIntegrityError("trajectory entries must not be symlinks")
        trajectory_match = _TRAJECTORY_NAME.fullmatch(path.name)
        digest_match = _DIGEST_NAME.fullmatch(path.name)
        if trajectory_match is not None:
            trajectory_files.append(path)
        elif digest_match is not None:
            sidecar_ids.add(digest_match.group(1))
        elif path.name.endswith(".intent"):
            raise ArtifactIntegrityError("surviving publication intent marker")
        elif path.name.endswith(".partial"):
            raise ArtifactIntegrityError("stale partial trajectory artifact")
        else:
            raise ArtifactIntegrityError(f"unknown trajectory artifact: {path.name}")
    trajectory_records: dict[str, dict[str, str]] = {}
    file_ids: set[str] = set()
    for path in trajectory_files:
        filename_id_match = _TRAJECTORY_NAME.fullmatch(path.name)
        assert filename_id_match is not None
        filename_id = filename_id_match.group(1)
        internal = _internal_expected(path)
        internal_id = internal["request_sha256"]
        if internal_id in file_ids:
            raise ArtifactIntegrityError("duplicate trajectory ID")
        file_ids.add(internal_id)
        result = load_verified_trajectory(path, expected)
        if result.request_sha256 != filename_id:
            raise ArtifactIntegrityError("trajectory ID does not match filename")
        digest, _ = _verify_digest(path, filename_id)
        trajectory_records[filename_id] = {
            "path": f"trajectories/{path.name}",
            "trajectory_id": filename_id,
            "trajectory_sha256": digest,
        }
    if sidecar_ids != set(trajectory_records):
        raise ArtifactIntegrityError("trajectory and digest membership differ")

    manifests: list[dict[str, object]] = []
    memberships: set[str] = set()
    for path in _directory_entries(batches):
        if path.is_symlink():
            raise ArtifactIntegrityError("batch entries must not be symlinks")
        match = _BATCH_NAME.fullmatch(path.name)
        if match is None:
            if path.name.endswith(".partial"):
                raise ArtifactIntegrityError("stale partial batch manifest")
            raise ArtifactIntegrityError(f"unknown batch artifact: {path.name}")
        document = _read_canonical_json(path, "batch manifest")
        if not isinstance(document, dict) or set(document) != {
            "schema_version",
            "batch_id",
            "members",
        }:
            raise ArtifactIntegrityError("batch manifest fields are not exact")
        batch_id = match.group(1)
        if document["schema_version"] != BATCH_SCHEMA or document["batch_id"] != batch_id:
            raise ArtifactIntegrityError("batch manifest identity is invalid")
        members = document["members"]
        if not isinstance(members, list) or not members:
            raise ArtifactIntegrityError("batch manifest has no members")
        if members != sorted(
            members,
            key=lambda member: member.get("trajectory_id", "")
            if isinstance(member, dict)
            else "",
        ):
            raise ArtifactIntegrityError("batch members are not canonical")
        for member in members:
            if not isinstance(member, dict) or set(member) != {
                "path",
                "trajectory_id",
                "trajectory_sha256",
            }:
                raise ArtifactIntegrityError("batch member fields are not exact")
            trajectory_id = member["trajectory_id"]
            if not isinstance(trajectory_id, str) or _HEX256.fullmatch(
                trajectory_id
            ) is None:
                raise ArtifactIntegrityError("batch trajectory ID is malformed")
            record = trajectory_records.get(trajectory_id)
            if record is None:
                raise ArtifactIntegrityError("batch manifest references missing member")
            if member != record:
                raise ArtifactIntegrityError("batch member hash or path is stale")
            if trajectory_id in memberships:
                raise ArtifactIntegrityError("trajectory appears in duplicate manifests")
            memberships.add(trajectory_id)
        manifests.append(
            {
                "batch_id": batch_id,
                "path": f"batches/{path.name}",
                "trajectory_count": len(members),
            }
        )
    if memberships != set(trajectory_records):
        raise ArtifactIntegrityError(
            "every valid trajectory must belong to one batch manifest"
        )
    manifests.sort(key=lambda record: str(record["batch_id"]))
    trajectories_document = [
        trajectory_records[key] for key in sorted(trajectory_records)
    ]
    progress: dict[str, object] = {
        "batch_count": len(manifests),
        "batches": manifests,
        "schema_version": PROGRESS_SCHEMA,
        "trajectory_count": len(trajectories_document),
        "trajectories": trajectories_document,
    }
    payload = _canonical_json_bytes(progress)
    progress_path = run_dir / "progress.json"
    if progress_path.exists() or progress_path.is_symlink():
        _checked_regular(progress_path, "progress")
        try:
            existing = progress_path.read_bytes()
        except OSError as error:
            raise ArtifactIntegrityError("unable to read progress") from error
        if existing != payload:
            raise ArtifactIntegrityError("existing progress is stale or corrupt")
    else:
        _publish_json_once(progress_path, payload)
    return progress
