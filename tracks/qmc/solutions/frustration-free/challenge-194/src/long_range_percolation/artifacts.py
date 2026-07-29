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
from typing import BinaryIO
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
MAX_JSON_BYTES = 1_048_576
MAX_HDF5_BYTES = 67_108_864
MAX_KAPPA_COUNT = 4096
MAX_DATASET_BYTES = 1_048_576

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
_REQUIRED_ROOT_ENTRIES = _ROOT_ENTRIES - {"progress.json"}
_ROOT_DIRECTORY_ENTRIES = frozenset({"kernel", "trajectories", "batches"})
_ROOT_FILE_ENTRIES = _REQUIRED_ROOT_ENTRIES - _ROOT_DIRECTORY_ENTRIES
_LAYOUT_SCHEMA = "challenge-194-run-layout-entry-v1"


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


def _open_regular(
    path: Path,
    description: str,
    *,
    maximum_size: int | None = None,
) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ArtifactIntegrityError(f"unable to open {description}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ArtifactIntegrityError(f"{description} must be a regular file")
        if maximum_size is not None and metadata.st_size > maximum_size:
            raise ArtifactIntegrityError(f"{description} exceeds the byte-size limit")
        return descriptor, metadata
    except BaseException:
        os.close(descriptor)
        raise


def _file_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _require_stable_descriptor(
    descriptor: int,
    original: os.stat_result,
    description: str,
) -> os.stat_result:
    try:
        current = os.fstat(descriptor)
    except OSError as error:
        raise ArtifactIntegrityError(f"unable to restat {description}") from error
    if _file_identity(current) != _file_identity(original):
        raise ArtifactIntegrityError(f"{description} identity or size mutated")
    return current


def _require_path_identity(
    path: Path,
    original: os.stat_result,
    description: str,
) -> None:
    try:
        current = path.lstat()
    except OSError as error:
        raise ArtifactIntegrityError(f"{description} pathname identity changed") from error
    if (
        stat.S_ISLNK(current.st_mode)
        or current.st_dev != original.st_dev
        or current.st_ino != original.st_ino
    ):
        raise ArtifactIntegrityError(f"{description} pathname identity changed")


def _read_descriptor_bounded(
    descriptor: int,
    maximum_size: int,
    description: str,
) -> bytes:
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = maximum_size + 1
        while remaining:
            block = os.read(descriptor, min(remaining, 64 * 1024))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
    except OSError as error:
        raise ArtifactIntegrityError(f"unable to read {description}") from error
    payload = b"".join(chunks)
    if len(payload) > maximum_size:
        raise ArtifactIntegrityError(f"{description} exceeds the byte-size limit")
    return payload


def _hash_descriptor(descriptor: int, description: str) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        while block := os.read(descriptor, 1024 * 1024):
            digest.update(block)
            size += len(block)
    except OSError as error:
        raise ArtifactIntegrityError(f"unable to hash {description}") from error
    return digest.hexdigest(), size


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


def _layout_document(name: str) -> dict[str, str]:
    return {
        "entry": name,
        "schema_version": _LAYOUT_SCHEMA,
        "status": "reserved",
    }


def _initialize_run_directory(run_dir: Path) -> None:
    marker = run_dir / f".layout.{os.getpid()}.{uuid.uuid4().hex}.intent"
    _write_unique_fsynced(marker, _canonical_json_bytes({"schema_version": _LAYOUT_SCHEMA}))
    _fsync_directory_raw(run_dir)
    try:
        for name in sorted(_ROOT_DIRECTORY_ENTRIES):
            (run_dir / name).mkdir()
        for name in sorted(_ROOT_FILE_ENTRIES):
            _write_unique_fsynced(
                run_dir / name,
                _canonical_json_bytes(_layout_document(name)),
            )
        _fsync_directory_raw(run_dir)
        marker.unlink()
        _fsync_directory_raw(run_dir)
    except BaseException:
        raise


def _prepare_publication_run(run_dir: Path) -> tuple[Path, Path, Path]:
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
    with _directory_lock(run_dir):
        entries = list(run_dir.iterdir())
        if not entries:
            _initialize_run_directory(run_dir)
    _verify_run_layout(run_dir)
    return run_dir, run_dir / "trajectories", run_dir / "batches"


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


def _fsync_directory_raw(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(directory: Path) -> None:
    _fsync_directory_raw(directory)


def _flush_hdf5(stream: h5py.File) -> None:
    stream.flush()


def _fsync_file(stream: h5py.File) -> None:
    handle = stream.id.get_vfd_handle()
    if not isinstance(handle, int):
        raise ArtifactIntegrityError("HDF5 driver did not expose a file descriptor")
    os.fsync(handle)


def _install_no_clobber(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination, follow_symlinks=False)
    except FileExistsError:
        raise FileExistsError(f"immutable artifact already exists: {destination}")
    source_stat = _checked_regular(source, "staged artifact")
    destination_stat = _checked_regular(destination, "installed artifact")
    if (
        source_stat.st_dev != destination_stat.st_dev
        or source_stat.st_ino != destination_stat.st_ino
    ):
        raise ArtifactIntegrityError("installed artifact inode identity mismatch")


def _replace(source: Path, destination: Path) -> None:
    # Kept as the explicit publication boundary used by crash-injection tests.
    _install_no_clobber(source, destination)


def _hash_file(path: Path) -> tuple[str, int]:
    descriptor, original = _open_regular(
        path, "trajectory", maximum_size=MAX_HDF5_BYTES
    )
    try:
        result = _hash_descriptor(descriptor, "trajectory")
        _require_stable_descriptor(descriptor, original, "trajectory")
        return result
    finally:
        os.close(descriptor)


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


def _verify_installed_bytes(path: Path, payload: bytes, description: str) -> None:
    descriptor, original = _open_regular(
        path, description, maximum_size=MAX_JSON_BYTES
    )
    try:
        installed = _read_descriptor_bounded(
            descriptor, MAX_JSON_BYTES, description
        )
        _require_stable_descriptor(descriptor, original, description)
        _require_path_identity(path, original, description)
    finally:
        os.close(descriptor)
    if installed != payload:
        raise ArtifactIntegrityError(f"{description} installed bytes mismatch")


def _publish_json_once(path: Path, payload: bytes) -> None:
    partial = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.partial"
    try:
        _write_unique_fsynced(partial, payload)
        try:
            _install_no_clobber(partial, path)
        except FileExistsError:
            raise FileExistsError(f"immutable artifact already exists: {path}")
        _verify_installed_bytes(path, payload, "published JSON artifact")
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
    if expected["rng_version"] != RNG_VERSION:
        raise ArtifactIntegrityError("expected RNG version is stale")
    if expected["conversion_version"] != CONVERSION_VERSION:
        raise ArtifactIntegrityError("expected conversion version is stale")


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


def _hard_link_object(
    group: h5py.Group | h5py.File,
    name: str,
    expected_type: type[h5py.Group] | type[h5py.Dataset],
) -> h5py.Group | h5py.Dataset:
    link = group.get(name, getlink=True)
    if not isinstance(link, h5py.HardLink):
        raise ArtifactIntegrityError(f"HDF5 link {name} is not canonical")
    value = group.get(name, getlink=False)
    if not isinstance(value, expected_type):
        raise ArtifactIntegrityError(f"HDF5 object {name} has the wrong kind")
    return value


def _object_address(value: h5py.Group | h5py.Dataset) -> int:
    try:
        return int(h5py.h5o.get_info(value.id).addr)
    except (TypeError, ValueError, RuntimeError) as error:
        raise ArtifactIntegrityError("unable to inspect HDF5 object identity") from error


def _exact_group(
    group: h5py.Group,
    names: set[str],
    label: str,
) -> dict[str, h5py.Dataset]:
    if set(group.keys()) != names or set(group.attrs.keys()):
        raise ArtifactIntegrityError(f"{label} object tree is not exact")
    datasets: dict[str, h5py.Dataset] = {}
    for name in names:
        value = _hard_link_object(group, name, h5py.Dataset)
        assert isinstance(value, h5py.Dataset)
        datasets[name] = value
    return datasets


def _text_attribute(attributes: h5py.AttributeManager, key: str) -> str:
    try:
        value = attributes[key]
    except KeyError as error:
        raise ArtifactIntegrityError(f"missing HDF5 attribute: {key}") from error
    try:
        attribute = attributes.get_id(key)
    except KeyError as error:
        raise ArtifactIntegrityError(f"missing HDF5 attribute: {key}") from error
    string_info = h5py.check_string_dtype(attribute.dtype)
    if (
        attribute.shape != ()
        or string_info is None
        or string_info.encoding != "utf-8"
        or string_info.length is not None
        or not isinstance(value, str)
    ):
        raise ArtifactIntegrityError(
            f"HDF5 attribute {key} has noncanonical dtype representation"
        )
    return value


def _numeric_attribute(
    attributes: h5py.AttributeManager,
    key: str,
    dtype: str,
) -> int | float:
    try:
        value = attributes[key]
    except KeyError as error:
        raise ArtifactIntegrityError(f"missing HDF5 attribute: {key}") from error
    attribute = attributes.get_id(key)
    if attribute.shape != () or attribute.dtype.str != dtype:
        raise ArtifactIntegrityError(
            f"HDF5 attribute {key} has noncanonical dtype representation"
        )
    if dtype == "<f8":
        return float(value)
    return int(value)


def _validate_dataset_metadata(
    dataset: h5py.Dataset,
    name: str,
    dtype: str,
    shape: tuple[int, ...],
) -> None:
    try:
        external = dataset.external
    except (OSError, RuntimeError, ValueError) as error:
        raise ArtifactIntegrityError(f"unable to inspect dataset {name}") from error
    if (
        dataset.dtype.str != dtype
        or dataset.shape != shape
        or dataset.maxshape != shape
        or dataset.nbytes > MAX_DATASET_BYTES
    ):
        raise ArtifactIntegrityError(f"dataset {name} has stale dtype or shape")
    if (
        dataset.is_virtual
        or external is not None
        or dataset.chunks is not None
        or dataset.compression is not None
        or dataset.compression_opts is not None
        or dataset.shuffle
        or dataset.fletcher32
        or dataset.scaleoffset is not None
        or set(dataset.attrs.keys())
        or dataset.dtype.hasobject
        or h5py.check_dtype(ref=dataset.dtype) is not None
        or dataset.id.get_create_plist().get_layout() != h5py.h5d.CONTIGUOUS
    ):
        raise ArtifactIntegrityError(
            f"dataset {name} uses noncanonical external, virtual, or chunked storage"
        )


def _read_dataset(dataset: h5py.Dataset, name: str) -> np.ndarray:
    try:
        value = np.asarray(dataset[...])
    except (MemoryError, OSError, RuntimeError, ValueError) as error:
        raise ArtifactIntegrityError(f"unable to load bounded dataset {name}") from error
    if not value.flags.c_contiguous:
        value = np.ascontiguousarray(value)
    return value


def _parse_hdf5(
    stream: h5py.File,
    expected: dict[str, str] | None,
) -> tuple[TrajectoryResult, dict[str, str]]:
    try:
        top_names = {"request", "result", "rng"}
        if set(stream.keys()) != top_names or set(stream.attrs.keys()) != {
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
            raise ArtifactIntegrityError("HDF5 object tree or attributes are not exact")
        request_group = _hard_link_object(stream, "request", h5py.Group)
        result_group = _hard_link_object(stream, "result", h5py.Group)
        rng_group = _hard_link_object(stream, "rng", h5py.Group)
        assert isinstance(request_group, h5py.Group)
        assert isinstance(result_group, h5py.Group)
        assert isinstance(rng_group, h5py.Group)
        request_datasets = _exact_group(request_group, {"kappas"}, "request")
        result_datasets = _exact_group(
            result_group,
            {
                "observables",
                "terminal_counters",
                "draw_counts",
                "hash_diagnostics",
            },
            "result",
        )
        rng_datasets = _exact_group(
            rng_group,
            {"initial_counters", "keys", "key_material_sha256"},
            "rng",
        )
        objects: list[h5py.Group | h5py.Dataset] = [
            request_group,
            result_group,
            rng_group,
            *request_datasets.values(),
            *result_datasets.values(),
            *rng_datasets.values(),
        ]
        addresses = [_object_address(value) for value in objects]
        if len(addresses) != len(set(addresses)):
            raise ArtifactIntegrityError("HDF5 object tree contains hard-link aliases")
        if _text_attribute(stream.attrs, "schema_version") != TRAJECTORY_SCHEMA:
            raise ArtifactIntegrityError("trajectory schema version is stale")
        stored = {key: _text_attribute(stream.attrs, key) for key in _EXPECTED_KEYS}
        _validate_expected(stored)
        if expected is not None:
            _validate_expected(expected)
            for key in _EXPECTED_KEYS:
                if stored[key] != expected[key]:
                    raise ArtifactIntegrityError(
                        f"trajectory dependency mismatch: {key}"
                    )
        if stored["rng_version"] != RNG_VERSION:
            raise ArtifactIntegrityError("trajectory RNG version is stale")
        if stored["conversion_version"] != CONVERSION_VERSION:
            raise ArtifactIntegrityError("trajectory conversion version is stale")
        if _numeric_attribute(stream.attrs, "clean_tree", "|u1") != 1:
            raise ArtifactIntegrityError("dirty-tree trajectory is forbidden")
        length = int(_numeric_attribute(stream.attrs, "length", "<u8"))
        master_seed = int(_numeric_attribute(stream.attrs, "master_seed", "<u8"))
        replica = int(_numeric_attribute(stream.attrs, "replica", "<u8"))
        sigma = float(_numeric_attribute(stream.attrs, "sigma", "<f8"))
        sigma_grid_id = _text_attribute(stream.attrs, "sigma_grid_id")
        phase = _text_attribute(stream.attrs, "phase")
        kappas_dataset = request_datasets["kappas"]
        if (
            len(kappas_dataset.shape) != 1
            or not 1 <= kappas_dataset.shape[0] <= MAX_KAPPA_COUNT
        ):
            raise ArtifactIntegrityError("kappa shape exceeds the frozen resource limit")
        _validate_dataset_metadata(
            kappas_dataset, "kappas", "<f8", (kappas_dataset.shape[0],)
        )
        kappas = _read_dataset(kappas_dataset, "kappas").astype(
            np.float64, copy=False
        )
        request = TrajectoryRequest(
            length=length,
            sigma=sigma,
            sigma_grid_id=sigma_grid_id,
            kappas=kappas,
            master_seed=master_seed,
            phase=phase,  # type: ignore[arg-type]
            replica=replica,
            kernel_sha256=stored["kernel_sha256"],
        )
        validate_trajectory_request(request)
        if request_digest(request) != stored["request_sha256"]:
            raise ArtifactIntegrityError("stored request does not match request hash")
        n_kappa = request.kappas.size
        metadata = (
            (result_datasets["observables"], "observables", "<f8", (n_kappa, 10)),
            (
                result_datasets["terminal_counters"],
                "terminal_counters",
                "<u4",
                (STREAM_COUNT, 4),
            ),
            (
                result_datasets["draw_counts"],
                "draw_counts",
                "<u8",
                (STREAM_COUNT, 3),
            ),
            (
                result_datasets["hash_diagnostics"],
                "hash_diagnostics",
                "<u8",
                (5,),
            ),
            (
                rng_datasets["initial_counters"],
                "initial_counters",
                "<u4",
                (STREAM_COUNT, 4),
            ),
            (rng_datasets["keys"], "keys", "<u4", (STREAM_COUNT, 2)),
            (
                rng_datasets["key_material_sha256"],
                "key_material_sha256",
                "|S64",
                (STREAM_COUNT,),
            ),
        )
        for dataset, name, dtype, shape in metadata:
            _validate_dataset_metadata(dataset, name, dtype, shape)
        observables = _read_dataset(result_datasets["observables"], "observables")
        terminal = _read_dataset(
            result_datasets["terminal_counters"], "terminal_counters"
        )
        draw_counts = _read_dataset(
            result_datasets["draw_counts"], "draw_counts"
        )
        diagnostics = _read_dataset(
            result_datasets["hash_diagnostics"], "hash_diagnostics"
        )
        initial = _read_dataset(rng_datasets["initial_counters"], "initial_counters")
        keys = _read_dataset(rng_datasets["keys"], "keys")
        hashes_dataset = rng_datasets["key_material_sha256"]
        try:
            material_hashes = [
                value.decode("ascii")
                for value in _read_dataset(
                    hashes_dataset, "key_material_sha256"
                )
            ]
        except (UnicodeDecodeError, AttributeError) as error:
            raise ArtifactIntegrityError("key-material hashes are malformed") from error
        expected_initial, expected_keys, expected_material_hashes = _stream_material(
            request
        )
        if (
            not np.array_equal(initial, expected_initial)
            or not np.array_equal(keys, expected_keys)
            or material_hashes != expected_material_hashes
        ):
            raise ArtifactIntegrityError("RNG stream material is corrupt")
        event_count = int(_numeric_attribute(stream.attrs, "event_count", "<u8"))
        duplicate_count = int(
            _numeric_attribute(stream.attrs, "duplicate_count", "<u8")
        )
        try:
            result = TrajectoryResult(
                request_sha256=stored["request_sha256"],
                observables=observables,
                terminal_counters=terminal,
                draw_counts=draw_counts,
                event_count=event_count,
                duplicate_count=duplicate_count,
                hash_diagnostics=diagnostics,
            )
        except ValueError as error:
            raise ArtifactIntegrityError("trajectory result is invalid") from error
        return result, stored
    except ArtifactIntegrityError:
        raise
    except (KeyError, MemoryError, OSError, RuntimeError, TypeError, ValueError) as error:
        raise ArtifactIntegrityError("unable to parse trajectory HDF5") from error


def _load_hdf5_verified(
    path: Path,
    expected: dict[str, str] | None,
    required_digest: str | None = None,
    required_size: int | None = None,
) -> tuple[TrajectoryResult, dict[str, str], str, int]:
    if expected is not None:
        _validate_expected(expected)
    descriptor, original = _open_regular(
        path, "trajectory", maximum_size=MAX_HDF5_BYTES
    )
    try:
        before_hash, before_size = _hash_descriptor(descriptor, "trajectory")
        if required_digest is not None and before_hash != required_digest:
            raise ArtifactIntegrityError("whole-file trajectory digest mismatch")
        if required_size is not None and before_size != required_size:
            raise ArtifactIntegrityError("whole-file trajectory size mismatch")
        os.lseek(descriptor, 0, os.SEEK_SET)
        duplicate = os.dup(descriptor)
        file_object: BinaryIO = os.fdopen(duplicate, "rb", closefd=True)
        try:
            with h5py.File(file_object, "r") as stream:
                result, stored = _parse_hdf5(stream, expected)
        finally:
            file_object.close()
        after_hash, after_size = _hash_descriptor(descriptor, "trajectory")
        _require_stable_descriptor(descriptor, original, "trajectory")
        _require_path_identity(path, original, "trajectory")
        if (after_hash, after_size) != (before_hash, before_size):
            raise ArtifactIntegrityError("trajectory mutated during semantic parsing")
        return result, stored, before_hash, before_size
    except ArtifactIntegrityError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise ArtifactIntegrityError("unable to parse trajectory HDF5") from error
    finally:
        os.close(descriptor)


def _load_hdf5(path: Path, expected: dict[str, str]) -> TrajectoryResult:
    return _load_hdf5_verified(path, expected)[0]


def _semantic_reload(
    path: Path,
    expected: dict[str, str],
) -> tuple[TrajectoryResult, str, int]:
    result, _, digest, size = _load_hdf5_verified(path, expected)
    return result, digest, size


def _read_canonical_json(path: Path, description: str) -> object:
    descriptor, original = _open_regular(
        path, description, maximum_size=MAX_JSON_BYTES
    )
    try:
        payload = _read_descriptor_bounded(descriptor, MAX_JSON_BYTES, description)
        document = json.loads(payload)
        _require_stable_descriptor(descriptor, original, description)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArtifactIntegrityError(f"unable to read {description}") from error
    finally:
        os.close(descriptor)
    if payload != _canonical_json_bytes(document):
        raise ArtifactIntegrityError(f"{description} is not canonical JSON")
    return document


def _read_digest(path: Path, trajectory_id: str) -> tuple[str, int]:
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
    return str(document["trajectory_sha256"]), int(document["artifact_size"])


def _verify_trajectory(
    path: Path,
    trajectory_id: str,
    expected: dict[str, str] | None,
) -> tuple[TrajectoryResult, dict[str, str], str, int]:
    digest, size = _read_digest(path, trajectory_id)
    return _load_hdf5_verified(
        path,
        expected,
        required_digest=digest,
        required_size=size,
    )


def _verify_digest(path: Path, trajectory_id: str) -> tuple[str, int]:
    _, _, digest, size = _verify_trajectory(path, trajectory_id, None)
    return digest, size


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
    if request.kappas.size > MAX_KAPPA_COUNT:
        raise ArtifactIntegrityError("kappa count exceeds the frozen resource limit")
    _validate_provenance(provenance)
    expected = {
        key: str(value)
        for key, value in provenance.items()
        if key != "clean_tree"
    }
    expected["request_sha256"] = trajectory_id
    expected["kernel_sha256"] = request.kernel_sha256
    _, trajectories, _ = _prepare_publication_run(run_dir)
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
        _, trajectory_hash, artifact_size = _semantic_reload(partial, expected)
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
            _install_no_clobber(digest_partial, sidecar)
        except FileExistsError as error:
            raise ArtifactIntegrityError("trajectory sidecar publication raced") from error
        final_stat = _checked_regular(final, "installed trajectory")
        partial_stat = _checked_regular(partial, "staged trajectory")
        if (
            final_stat.st_dev != partial_stat.st_dev
            or final_stat.st_ino != partial_stat.st_ino
        ):
            raise ArtifactIntegrityError("installed trajectory inode changed")
        _load_hdf5_verified(
            final,
            expected,
            required_digest=trajectory_hash,
            required_size=artifact_size,
        )
        _verify_installed_bytes(
            sidecar,
            _canonical_json_bytes(digest_document),
            "trajectory digest sidecar",
        )
        partial.unlink()
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
            try:
                _fsync_directory(trajectories)
            except BaseException as recovery_error:
                raise ArtifactIntegrityError(
                    "intent recovery directory fsync failed; publication is uncommitted"
                ) from recovery_error
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
    result, _, _, _ = _verify_trajectory(path, match.group(1), expected)
    if result.request_sha256 != match.group(1):
        raise ArtifactIntegrityError("trajectory ID does not match its filename")
    return result


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
    _verify_run_layout(run_dir)
    trajectories = run_dir / "trajectories"
    batches = run_dir / "batches"
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
        result, _, trajectory_hash, _ = _verify_trajectory(
            path, trajectory_id, None
        )
        if result.request_sha256 != trajectory_id:
            raise ArtifactIntegrityError("trajectory ID does not match its filename")
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


def _verify_run_layout(run_dir: Path) -> None:
    if not isinstance(run_dir, Path):
        raise TypeError("run_dir must be a pathlib.Path")
    _check_existing_path_chain(run_dir)
    try:
        root_stat = run_dir.lstat()
    except OSError as error:
        raise ArtifactIntegrityError("run layout is missing") from error
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise ArtifactIntegrityError("run layout root has the wrong kind")
    entries = _directory_entries(run_dir)
    names = {path.name for path in entries}
    for path in entries:
        try:
            metadata = path.lstat()
        except OSError as error:
            raise ArtifactIntegrityError("unable to inspect run layout") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise ArtifactIntegrityError("run layout must not contain symlinks")
    if not _REQUIRED_ROOT_ENTRIES.issubset(names):
        missing = sorted(_REQUIRED_ROOT_ENTRIES - names)
        raise ArtifactIntegrityError(f"run layout is missing entries: {missing}")
    if not names.issubset(_ROOT_ENTRIES):
        unknown = sorted(names - _ROOT_ENTRIES)
        raise ArtifactIntegrityError(f"unknown run artifact: {unknown}")
    identities: set[tuple[int, int]] = set()
    for path in entries:
        try:
            metadata = path.lstat()
        except OSError as error:
            raise ArtifactIntegrityError("unable to inspect run layout") from error
        identity = (metadata.st_dev, metadata.st_ino)
        if identity in identities:
            raise ArtifactIntegrityError("run layout contains inode aliases")
        identities.add(identity)
        if path.name in _ROOT_DIRECTORY_ENTRIES:
            if not stat.S_ISDIR(metadata.st_mode):
                raise ArtifactIntegrityError(
                    f"run layout entry {path.name} has the wrong directory kind"
                )
        else:
            if not stat.S_ISREG(metadata.st_mode):
                raise ArtifactIntegrityError(
                    f"run layout entry {path.name} must be a regular file"
                )
            if metadata.st_nlink != 1:
                raise ArtifactIntegrityError(
                    f"run layout entry {path.name} is a hard-link alias"
                )
            if path.name in _ROOT_FILE_ENTRIES:
                document = _read_canonical_json(path, f"run layout {path.name}")
                if document != _layout_document(path.name):
                    raise ArtifactIntegrityError(
                        f"run layout entry {path.name} is not canonical"
                    )


def reconstruct_progress(
    run_dir: Path, expected: dict[str, str]
) -> dict[str, object]:
    _validate_expected(expected)
    _verify_run_layout(run_dir)
    trajectories = run_dir / "trajectories"
    batches = run_dir / "batches"
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
    if not trajectory_files:
        raise ArtifactIntegrityError("run layout has no trajectory artifacts")
    for path in trajectory_files:
        filename_id_match = _TRAJECTORY_NAME.fullmatch(path.name)
        assert filename_id_match is not None
        filename_id = filename_id_match.group(1)
        result, _, digest, _ = _verify_trajectory(path, filename_id, expected)
        internal_id = result.request_sha256
        if internal_id in file_ids:
            raise ArtifactIntegrityError("duplicate trajectory ID")
        file_ids.add(internal_id)
        if result.request_sha256 != filename_id:
            raise ArtifactIntegrityError("trajectory ID does not match filename")
        trajectory_records[filename_id] = {
            "path": f"trajectories/{path.name}",
            "trajectory_id": filename_id,
            "trajectory_sha256": digest,
        }
    if sidecar_ids != set(trajectory_records):
        raise ArtifactIntegrityError("trajectory and digest membership differ")

    manifests: list[dict[str, object]] = []
    memberships: set[str] = set()
    batch_paths = _directory_entries(batches)
    if not batch_paths:
        raise ArtifactIntegrityError("run layout has no batch manifests")
    for path in batch_paths:
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
        descriptor, original = _open_regular(
            progress_path, "progress", maximum_size=MAX_JSON_BYTES
        )
        try:
            existing = _read_descriptor_bounded(
                descriptor, MAX_JSON_BYTES, "progress"
            )
            _require_stable_descriptor(descriptor, original, "progress")
        finally:
            os.close(descriptor)
        if existing != payload:
            raise ArtifactIntegrityError("existing progress is stale or corrupt")
    else:
        _publish_json_once(progress_path, payload)
    return progress
