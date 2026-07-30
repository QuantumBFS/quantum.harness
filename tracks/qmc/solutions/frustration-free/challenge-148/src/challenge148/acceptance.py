from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import jsonschema

from .artifacts import atomic_write_json, publish_run
from .lattice import read_graph_json
from .provenance import canonical_json
from .statistics import agreement_z_score, summarize_bin_records

_ADAPTER_KEYS = {"QMC_SSE": "qmc_sse", "QMC_LTFIM": "qmc_ltfim"}
_ADAPTER_LABELS = {
    "QMC_SSE": "primary_qmc_sse",
    "QMC_LTFIM": "independent_qmc_ltfim",
}
_OBSERVABLES = ("energy", "transverse_magnetization", "m2", "m4", "binder_ratio")
_SCIENTIFIC_THRESHOLDS = {
    "max_normalized_residual": 4.0,
    "median_normalized_residual": 1.5,
    "agreement_sigma": 3.0,
}
_SCIENTIFIC_PREREGISTRATION_SHA256 = (
    "4a28d43824fa162eba639f32d820e5ba0500585c297858f50fbcddfa8bc76cc5"
)


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _schema(name: str) -> dict[str, Any]:
    return json.loads((_root() / "schemas" / name).read_text(encoding="utf-8"))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _request_hash(request: dict[str, Any]) -> str:
    return _sha256_bytes(canonical_json(request))


def _subprocess_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def _julia_canonical_json(value: object) -> bytes:
    def encode(item: object) -> str:
        if item is None:
            return "null"
        if isinstance(item, bool):
            return "true" if item else "false"
        if isinstance(item, int):
            return str(item)
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("non-finite value is not canonical JSON")
            if item.is_integer() and -(2**63) <= item <= 2**63 - 1:
                return str(int(item))
            return json.dumps(item, allow_nan=False, separators=(",", ":"))
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        if isinstance(item, list):
            return "[" + ",".join(encode(child) for child in item) + "]"
        if isinstance(item, dict):
            if not all(isinstance(key, str) for key in item):
                raise ValueError("canonical JSON object keys must be strings")
            return (
                "{"
                + ",".join(
                    f"{encode(key)}:{encode(item[key])}" for key in sorted(item)
                )
                + "}"
            )
        raise ValueError("value is not Julia canonical JSON encodable")

    return (encode(value) + "\n").encode("utf-8")


def _adapter_request_hash(request: dict[str, Any], adapter: str) -> str:
    if adapter == "QMC_SSE":
        payload = canonical_json(request)
    elif adapter == "QMC_LTFIM":
        payload = _julia_canonical_json(request)
    else:
        raise ValueError("unknown adapter")
    return _sha256_bytes(payload)


def _scientific_preregistration() -> dict[str, Any]:
    path = _root() / "preregistration" / "scientific-v1.json"
    payload = path.read_bytes()
    if _sha256_bytes(payload) != _SCIENTIFIC_PREREGISTRATION_SHA256:
        raise ValueError("committed scientific preregistration digest mismatch")
    value = json.loads(payload)
    if set(value) != {"schema_version", "protocol"} or value["schema_version"] != (
        "challenge148-scientific-preregistration-v1"
    ):
        raise ValueError("committed scientific preregistration schema mismatch")
    return value


def _scientific_protocol_projection(request: dict[str, Any]) -> dict[str, Any]:
    cells = []
    for cell in request["cells"]:
        adapters = {}
        for adapter_key in ("qmc_sse", "qmc_ltfim"):
            adapter = cell["adapters"][adapter_key]
            chains = []
            for chain in adapter["chains"]:
                if (
                    chain["serial_measurement_stride_samples"]
                    != request["analysis"]["serial_measurement_stride_samples"]
                    or chain["analysis_bin_length_samples"]
                    != request["analysis"]["analysis_bin_length_samples"]
                ):
                    raise ValueError(
                        "scientific request does not match committed preregistration"
                    )
                chains.append(
                    {
                        key: chain[key]
                        for key in (
                            "checkpoint_analysis_bins",
                            "retained_samples",
                            "seed",
                            "thermalization_sweeps",
                            "thinning",
                        )
                    }
                )
            adapters[adapter_key] = {
                "chains": chains,
                "seed_derivation": adapter["seed_derivation"],
                "seed_domain": adapter["seed_domain"],
            }
        cells.append(
            {
                key: cell[key]
                for key in (
                    "cell_id",
                    "lattice",
                    "length",
                    "graph_sha256",
                    "beta",
                    "coupling",
                    "field",
                )
            }
            | {"adapters": adapters}
        )
    return {
        "analysis": request["analysis"],
        "cells": cells,
        "ed_oracle": request["ed_oracle"],
        "launch_timeout_seconds": request["launch_timeout_seconds"],
        "observables": request["observables"],
        "thresholds": request["thresholds"],
    }


def _require_regular(path: Path, label: str) -> None:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError as exc:
        raise ValueError(f"missing {label}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"{label} must be a regular non-symlink file")


def _require_directory(path: Path, label: str) -> None:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError as exc:
        raise ValueError(f"missing {label}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"{label} must be a real directory")


def _load_json(path: Path, label: str, *, canonical: bool = False) -> dict[str, Any]:
    _require_regular(path, label)

    def reject(token: str) -> None:
        raise ValueError(f"{label} contains non-finite JSON token {token}")

    payload = path.read_bytes()
    try:
        value = json.loads(payload, parse_constant=reject)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid {label} JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    if canonical and payload != canonical_json(value) + b"\n":
        raise ValueError(f"{label} is not canonical newline-terminated JSON")
    return value


def validate_acceptance_request(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("acceptance request must be an object")
    canonical_json(request)
    try:
        jsonschema.validate(request, _schema("acceptance.schema.json"))
    except jsonschema.ValidationError as exc:
        if request.get("mode") == "scientific":
            raise ValueError(
                f"scientific request violates committed preregistration: {exc.message}"
            ) from exc
        raise ValueError(f"invalid acceptance request: {exc.message}") from exc
    if request["mode"] == "scientific" and {
        key: float(value) for key, value in request["thresholds"].items()
    } != _SCIENTIFIC_THRESHOLDS:
        raise ValueError("scientific acceptance thresholds are fixed and cannot be weakened")
    if request["mode"] == "scientific":
        preregistration = _scientific_preregistration()
        if (
            request["preregistration_sha256"]
            != _SCIENTIFIC_PREREGISTRATION_SHA256
            or _scientific_protocol_projection(request) != preregistration["protocol"]
        ):
            raise ValueError(
                "scientific request does not match committed preregistration"
            )

    cell_ids: set[str] = set()
    seeds: set[int] = set()
    lattice_points: dict[str, set[tuple[float, float]]] = {
        "honeycomb": set(),
        "triangular": set(),
    }
    for cell in request["cells"]:
        if cell["cell_id"] in cell_ids:
            raise ValueError("acceptance cell_id values must be unique")
        cell_ids.add(cell["cell_id"])
        graph_path = Path(cell["graph_path"])
        if not graph_path.is_absolute():
            raise ValueError("acceptance graph paths must be absolute")
        graph = read_graph_json(graph_path)
        if (
            graph.lattice != cell["lattice"]
            or graph.length != cell["length"]
            or cell["graph_sha256"]
            != json.loads(graph_path.read_text(encoding="utf-8"))["sha256"]
        ):
            raise ValueError("acceptance graph provenance mismatch")
        lattice_points[cell["lattice"]].add((float(cell["beta"]), float(cell["field"])))

        for adapter_key in ("qmc_sse", "qmc_ltfim"):
            for chain in cell["adapters"][adapter_key]["chains"]:
                seed = chain["seed"]
                if seed in seeds:
                    raise ValueError("adapter seeds must be globally unique")
                seeds.add(seed)
                bin_length = chain["analysis_bin_length_samples"]
                if chain["retained_samples"] % bin_length != 0:
                    raise ValueError(
                        "retained_samples must be divisible by analysis bin length"
                    )
                if chain["retained_samples"] // bin_length < 16:
                    raise ValueError("at least 16 pre-registered bins are required")
    if any(len(points) < 2 for points in lattice_points.values()):
        raise ValueError("both lattices require at least two beta/field points")
    return request


def _validate_anchor(
    output: Path, request_hash: str, adapter: str, *, archival: bool = False
) -> str:
    selection_path = output / "run-lock-anchor.json"
    selection = _load_json(selection_path, "run-lock anchor selection", canonical=True)
    if adapter == "QMC_SSE":
        selection_keys = {
            "schema_version",
            "anchor_device",
            "anchor_inode",
            "anchor_sha256",
            "path",
        }
        selection_schema = "qmc-sse-run-lock-anchor-selection-v1"
        anchor_schema = "qmc-sse-run-lock-anchor-v2"
        state_name, lock_name = ".qmc-sse-lock-state", ".qmc-sse.lock"
    else:
        selection_keys = {"schema_version", "anchor_sha256", "path"}
        selection_schema = "qmc-ltfim-run-lock-anchor-selection-v1"
        anchor_schema = "qmc-ltfim-run-lock-anchor-v1"
        state_name, lock_name = ".qmc-ltfim-lock-state", ".qmc-ltfim.lock"
    if set(selection) != selection_keys or selection["schema_version"] != selection_schema:
        raise ValueError("adapter-specific run-lock anchor selection mismatch")
    digest = selection["anchor_sha256"]
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("malformed run-lock anchor hash")
    expected_relative = f"run-lock-anchors/{digest}.json"
    if selection["path"] != expected_relative:
        raise ValueError("run-lock anchor path mismatch")
    anchors = output / "run-lock-anchors"
    _require_directory(anchors, "run-lock anchors directory")
    expected_anchor_names = [f"{digest}.json", f"{digest}.pin"]
    if sorted(path.name for path in anchors.iterdir()) != expected_anchor_names:
        raise ValueError("run-lock anchor object set mismatch")
    anchor_path = output / expected_relative
    anchor_payload = anchor_path.read_bytes()
    if _sha256_bytes(anchor_payload) != digest:
        raise ValueError("run-lock anchor content hash mismatch")
    pin_path = anchors / f"{digest}.pin"
    if pin_path.read_bytes() != anchor_payload:
        raise ValueError("run-lock anchor inode pin content mismatch")
    anchor = _load_json(anchor_path, "run-lock anchor", canonical=True)
    common_keys = {
        "schema_version",
        "request_sha256",
        "output_namespace",
        "state_device",
        "state_inode",
        "lock_device",
        "lock_inode",
    }
    anchor_keys = (
        common_keys
        | {
            "identity_device",
            "identity_inode",
            "lock_state_identity_sha256",
        }
        if adapter == "QMC_SSE"
        else common_keys
    )
    if set(anchor) != anchor_keys or anchor["schema_version"] != anchor_schema:
        raise ValueError("adapter-specific run-lock anchor mismatch")
    if anchor["request_sha256"] != request_hash:
        raise ValueError("run-lock anchor request hash mismatch")
    if archival:
        return digest
    anchor_stat, pin_stat = anchor_path.stat(), pin_path.stat()
    if adapter == "QMC_SSE":
        expected_identity = (selection["anchor_device"], selection["anchor_inode"])
        if (
            (anchor_stat.st_dev, anchor_stat.st_ino) != expected_identity
            or (pin_stat.st_dev, pin_stat.st_ino) != expected_identity
        ):
            raise ValueError("run-lock anchor inode pin identity mismatch")
    elif (anchor_stat.st_dev, anchor_stat.st_ino) != (pin_stat.st_dev, pin_stat.st_ino):
        raise ValueError("run-lock anchor inode pin identity mismatch")
    if Path(anchor["output_namespace"]).resolve() != output.resolve():
        raise ValueError("run-lock anchor output namespace mismatch")

    state = output / state_name
    lock = state / lock_name
    _require_directory(state, "run-lock state")
    _require_regular(lock, "run-lock file")
    state_stat, lock_stat = state.stat(), lock.stat()
    if (anchor["state_device"], anchor["state_inode"]) != (
        state_stat.st_dev,
        state_stat.st_ino,
    ) or (anchor["lock_device"], anchor["lock_inode"]) != (
        lock_stat.st_dev,
        lock_stat.st_ino,
    ):
        raise ValueError("run-lock anchor inode binding mismatch")
    if adapter == "QMC_SSE":
        identity = state / "identity.json"
        _require_regular(identity, "run-lock identity")
        identity_stat = identity.stat()
        if (anchor["identity_device"], anchor["identity_inode"]) != (
            identity_stat.st_dev,
            identity_stat.st_ino,
        ):
            raise ValueError("run-lock identity inode binding mismatch")
        binding = {
            key: anchor[key]
            for key in (
                "identity_device",
                "identity_inode",
                "lock_device",
                "lock_inode",
                "output_namespace",
                "request_sha256",
                "state_device",
                "state_inode",
            )
        }
        binding["schema_version"] = "qmc-sse-lock-state-binding-v2"
        if anchor["lock_state_identity_sha256"] != _sha256_bytes(canonical_json(binding)):
            raise ValueError("run-lock state identity hash mismatch")
        anchor_stat = anchor_path.stat()
        if (selection["anchor_device"], selection["anchor_inode"]) != (
            anchor_stat.st_dev,
            anchor_stat.st_ino,
        ):
            raise ValueError("run-lock anchor selection inode binding mismatch")
    return digest


def _validate_bin_cross_fields(record: dict[str, Any], request: dict[str, Any]) -> None:
    if record["sample_count"] != request["bin_length"]:
        raise ValueError("bin sample count does not match pre-registered bin length")
    expected_sweeps = record["sample_count"] * request["thinning"]
    if record["sweep_count"] != expected_sweeps:
        raise ValueError("bin sweep count does not match common sweep units")
    if record["cluster_accepted_count"] > record["cluster_attempt_count"]:
        raise ValueError("accepted cluster count exceeds attempted count")
    if (
        record["serial_measurement_stride_samples"]
        != request["serial_measurement_stride_samples"]
        or len(record["serial_observations"]["energy"]) != record["sample_count"]
        or any(
            len(record["serial_observations"][name]) != record["sample_count"]
            for name in ("transverse_magnetization", "m2", "m4")
        )
    ):
        raise ValueError("serial retained-sample measurement cadence mismatch")
    for name in ("energy", "transverse_magnetization", "m2", "m4"):
        observations = record["serial_observations"][name]
        if not math.isclose(
            math.fsum(observations),
            float(record[f"{name}_sum"]),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("serial retained measurements do not reproduce bin sums")
        if not math.isclose(
            math.fsum(value * value for value in observations),
            float(record[f"{name}_sum_squares"]),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "serial retained measurements do not reproduce bin sum squares"
            )
    if record["adapter"] == "QMC_LTFIM":
        if (
            record["cluster_attempt_count"] != record["cluster_count_sum"]
            or record["cluster_size_observation_count"] != record["cluster_count_sum"]
            or record["cluster_list_size_observation_count"] != record["sweep_count"]
        ):
            raise ValueError("QMC_LTFIM bin diagnostics are inconsistent")


def _descriptor_identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _open_descriptor_directory(parent: int, name: str, label: str) -> int:
    if "/" in name or name in {"", ".", ".."}:
        raise ValueError(f"invalid {label} component")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(name, flags, dir_fd=parent)
    except OSError as exc:
        raise ValueError(f"{label} must be a real directory") from exc
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError(f"{label} must be a real directory")
    return descriptor


def _open_descriptor_file(parent: int, name: str, label: str) -> int:
    if "/" in name or name in {"", ".", ".."}:
        raise ValueError(f"invalid {label} component")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent)
    except OSError as exc:
        raise ValueError(f"{label} must be a regular non-symlink file") from exc
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError(f"{label} must be a regular non-symlink file")
    return descriptor


def _read_descriptor_bytes(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    offset = 0
    while True:
        chunk = os.pread(descriptor, 1024 * 1024, offset)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        offset += len(chunk)


def _descriptor_json(
    descriptor: int, label: str, *, canonical: bool = False
) -> tuple[bytes, dict[str, Any]]:
    payload = _read_descriptor_bytes(descriptor)

    def reject(token: str) -> None:
        raise ValueError(f"{label} contains non-finite JSON token {token}")

    try:
        value = json.loads(payload, parse_constant=reject)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid {label} JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    if canonical and payload != canonical_json(value) + b"\n":
        raise ValueError(f"{label} is not canonical newline-terminated JSON")
    return payload, value


def validate_qmc_adapter_output_descriptor(
    output_descriptor: int,
    request: dict[str, Any],
    adapter: str,
    *,
    graph: dict[str, Any],
    output_namespace: str,
    archival: bool = False,
) -> dict[str, Any]:
    """Validate live or copied QMC output using retained descriptors only."""
    if adapter not in _ADAPTER_KEYS or request.get("adapter") != adapter:
        raise ValueError("executable-specific adapter mismatch")
    try:
        jsonschema.validate(request, _schema("qmc-request.schema.json"))
    except jsonschema.ValidationError as exc:
        raise ValueError("invalid adapter request") from exc
    if (
        not isinstance(graph, dict)
        or graph.get("sha256") != request["graph_sha256"]
        or graph.get("lattice") not in {"honeycomb", "triangular"}
    ):
        raise ValueError("adapter request graph hash mismatch")
    output_metadata = os.fstat(output_descriptor)
    if not stat.S_ISDIR(output_metadata.st_mode):
        raise ValueError("adapter output descriptor must name a directory")

    retained: list[tuple[int, str, int, bytes | None, str]] = []
    enumerations: list[tuple[int, tuple[str, ...], str]] = []
    opened: list[int] = []
    descriptor_paths: dict[int, tuple[str, ...]] = {output_descriptor: ()}

    def directory(parent: int, name: str, label: str) -> int:
        descriptor = _open_descriptor_directory(parent, name, label)
        opened.append(descriptor)
        descriptor_paths[descriptor] = (*descriptor_paths[parent], name)
        retained.append((parent, name, descriptor, None, label))
        return descriptor

    def file(
        parent: int, name: str, label: str, *, canonical: bool = False
    ) -> tuple[int, bytes, dict[str, Any]]:
        descriptor = _open_descriptor_file(parent, name, label)
        opened.append(descriptor)
        descriptor_paths[descriptor] = (*descriptor_paths[parent], name)
        payload, value = _descriptor_json(descriptor, label, canonical=canonical)
        retained.append((parent, name, descriptor, payload, label))
        return descriptor, payload, value

    def names(descriptor: int, label: str) -> tuple[str, ...]:
        value = tuple(sorted(os.listdir(descriptor)))
        enumerations.append((descriptor, value, label))
        return value

    try:
        selection_fd, _, selection = file(
            output_descriptor,
            "run-lock-anchor.json",
            "run-lock anchor selection",
            canonical=True,
        )
        if adapter == "QMC_SSE":
            selection_keys = {
                "schema_version",
                "anchor_device",
                "anchor_inode",
                "anchor_sha256",
                "path",
            }
            selection_schema = "qmc-sse-run-lock-anchor-selection-v1"
            anchor_schema = "qmc-sse-run-lock-anchor-v2"
            state_name, lock_name = ".qmc-sse-lock-state", ".qmc-sse.lock"
        else:
            selection_keys = {"schema_version", "anchor_sha256", "path"}
            selection_schema = "qmc-ltfim-run-lock-anchor-selection-v1"
            anchor_schema = "qmc-ltfim-run-lock-anchor-v1"
            state_name, lock_name = ".qmc-ltfim-lock-state", ".qmc-ltfim.lock"
        if set(selection) != selection_keys or selection["schema_version"] != selection_schema:
            raise ValueError("adapter-specific run-lock anchor selection mismatch")
        anchor_hash = selection["anchor_sha256"]
        if not isinstance(anchor_hash, str) or len(anchor_hash) != 64:
            raise ValueError("malformed run-lock anchor hash")
        expected_anchor_path = f"run-lock-anchors/{anchor_hash}.json"
        if selection["path"] != expected_anchor_path:
            raise ValueError("run-lock anchor path mismatch")

        anchors_fd = directory(output_descriptor, "run-lock-anchors", "run-lock anchors")
        if names(anchors_fd, "run-lock anchors") != (
            f"{anchor_hash}.json",
            f"{anchor_hash}.pin",
        ):
            raise ValueError("run-lock anchor object set mismatch")
        anchor_fd, anchor_payload, anchor = file(
            anchors_fd, f"{anchor_hash}.json", "run-lock anchor", canonical=True
        )
        pin_fd = _open_descriptor_file(
            anchors_fd, f"{anchor_hash}.pin", "run-lock anchor pin"
        )
        opened.append(pin_fd)
        descriptor_paths[pin_fd] = (
            *descriptor_paths[anchors_fd],
            f"{anchor_hash}.pin",
        )
        pin_payload = _read_descriptor_bytes(pin_fd)
        retained.append(
            (anchors_fd, f"{anchor_hash}.pin", pin_fd, pin_payload, "run-lock anchor pin")
        )
        if _sha256_bytes(anchor_payload) != anchor_hash or pin_payload != anchor_payload:
            raise ValueError("run-lock anchor content or pin hash mismatch")
        if not archival and _descriptor_identity(
            os.fstat(anchor_fd)
        ) != _descriptor_identity(os.fstat(pin_fd)):
            raise ValueError("run-lock anchor inode pin identity mismatch")
        common_keys = {
            "schema_version",
            "request_sha256",
            "output_namespace",
            "state_device",
            "state_inode",
            "lock_device",
            "lock_inode",
        }
        anchor_keys = (
            common_keys
            | {
                "identity_device",
                "identity_inode",
                "lock_state_identity_sha256",
            }
            if adapter == "QMC_SSE"
            else common_keys
        )
        if set(anchor) != anchor_keys or anchor["schema_version"] != anchor_schema:
            raise ValueError("adapter-specific run-lock anchor mismatch")
        request_hash = _adapter_request_hash(request, adapter)
        if anchor["request_sha256"] != request_hash or (
            not archival and anchor["output_namespace"] != output_namespace
        ):
            raise ValueError("run-lock anchor request or output namespace mismatch")
        if not archival and adapter == "QMC_SSE" and (
            selection["anchor_device"],
            selection["anchor_inode"],
        ) != _descriptor_identity(os.fstat(anchor_fd)):
            raise ValueError("run-lock anchor selection inode binding mismatch")

        if not archival:
            state_fd = directory(output_descriptor, state_name, "run-lock state")
            lock_fd = _open_descriptor_file(state_fd, lock_name, "run-lock file")
            opened.append(lock_fd)
            descriptor_paths[lock_fd] = (*descriptor_paths[state_fd], lock_name)
            lock_payload = _read_descriptor_bytes(lock_fd)
            retained.append(
                (state_fd, lock_name, lock_fd, lock_payload, "run-lock file")
            )
            if (
                anchor["state_device"],
                anchor["state_inode"],
            ) != _descriptor_identity(os.fstat(state_fd)) or (
                anchor["lock_device"],
                anchor["lock_inode"],
            ) != _descriptor_identity(os.fstat(lock_fd)):
                raise ValueError("run-lock anchor inode binding mismatch")
            if adapter == "QMC_SSE":
                identity_fd = _open_descriptor_file(
                    state_fd, "identity.json", "run-lock identity"
                )
                opened.append(identity_fd)
                descriptor_paths[identity_fd] = (
                    *descriptor_paths[state_fd],
                    "identity.json",
                )
                identity_payload = _read_descriptor_bytes(identity_fd)
                retained.append(
                    (
                        state_fd,
                        "identity.json",
                        identity_fd,
                        identity_payload,
                        "run-lock identity",
                    )
                )
                if (
                    anchor["identity_device"],
                    anchor["identity_inode"],
                ) != _descriptor_identity(os.fstat(identity_fd)):
                    raise ValueError("run-lock identity inode binding mismatch")
                binding = {
                    key: anchor[key]
                    for key in (
                        "identity_device",
                        "identity_inode",
                        "lock_device",
                        "lock_inode",
                        "output_namespace",
                        "request_sha256",
                        "state_device",
                        "state_inode",
                    )
                }
                binding["schema_version"] = "qmc-sse-lock-state-binding-v2"
                if anchor["lock_state_identity_sha256"] != _sha256_bytes(
                    canonical_json(binding)
                ):
                    raise ValueError("run-lock state identity hash mismatch")

        pointer_fd, pointer_payload, pointer = file(
            output_descriptor,
            "current-generation.json",
            "current generation pointer",
            canonical=True,
        )
        if set(pointer) != {
            "schema_version",
            "anchor_sha256",
            "generation_sha256",
            "path",
        } or pointer["schema_version"] != "qmc-current-generation-v2":
            raise ValueError("current pointer must be qmc-current-generation-v2")
        if pointer["anchor_sha256"] != anchor_hash:
            raise ValueError("current pointer anchor mismatch")
        current_hash = pointer["generation_sha256"]
        if pointer["path"] != f"generations/{current_hash}":
            raise ValueError("current pointer path mismatch")

        generations_fd = directory(output_descriptor, "generations", "generations directory")
        generation_names = names(generations_fd, "generations directory")
        manifests: dict[str, dict[str, Any]] = {}
        generation_schema = _schema("qmc-checkpoint-generation.schema.json")
        for generation_name in generation_names:
            if len(generation_name) != 64:
                raise ValueError("malformed generation directory")
            generation_fd = directory(generations_fd, generation_name, "generation")
            if names(generation_fd, f"generation {generation_name}") != ("manifest.json",):
                raise ValueError("malformed generation directory")
            _, manifest_payload, manifest = file(
                generation_fd, "manifest.json", "generation manifest", canonical=True
            )
            if _sha256_bytes(manifest_payload) != generation_name:
                raise ValueError("generation content hash mismatch")
            try:
                jsonschema.validate(manifest, generation_schema)
            except jsonschema.ValidationError as exc:
                raise ValueError("generation manifest schema mismatch") from exc
            bindings = {
                "anchor_sha256": anchor_hash,
                "request_sha256": request_hash,
                "adapter": adapter,
                "source_hash": request["expected_source_hash"],
                "build_hash": request["expected_build_hash"],
                "seed": request["seed"],
            }
            if any(manifest[key] != value for key, value in bindings.items()):
                raise ValueError("generation provenance binding mismatch")
            if manifest["completed_bin_count"] != len(manifest["bin_object_hashes"]):
                raise ValueError("generation completed bin count mismatch")
            manifests[generation_name] = manifest

        chain: list[tuple[str, dict[str, Any]]] = []
        seen: set[str] = set()
        cursor: str | None = current_hash
        while cursor is not None:
            if cursor in seen or cursor not in manifests:
                raise ValueError("generation ancestry is cyclic or incomplete")
            seen.add(cursor)
            manifest = manifests[cursor]
            chain.append((cursor, manifest))
            cursor = manifest["previous_generation_sha256"]
        chain.reverse()
        if (
            set(manifests) != seen
            or not chain
            or chain[0][1]["previous_generation_sha256"] is not None
        ):
            raise ValueError("generation ancestry contains an unreferenced generation")
        previous_hashes: list[str] = []
        for _, manifest in chain:
            hashes = manifest["bin_object_hashes"]
            if (
                hashes[: len(previous_hashes)] != previous_hashes
                or len(hashes) <= len(previous_hashes)
            ):
                raise ValueError("generation bin ancestry is not append-only")
            previous_hashes = hashes
        expected_bins = request["retained_samples"] // request["bin_length"]
        final = chain[-1][1]
        if final["completed_bin_count"] != expected_bins:
            raise ValueError("final generation is incomplete")

        bins_fd = directory(output_descriptor, "bins", "bins directory")
        expected_names = tuple(
            sorted(f"{digest}.ndjson" for digest in final["bin_object_hashes"])
        )
        if names(bins_fd, "bins directory") != expected_names:
            raise ValueError("immutable bin directory does not exactly match current generation")
        bin_schema = _schema(
            "qmc-sse-bin.schema.json"
            if adapter == "QMC_SSE"
            else "qmc-ltfim-bin.schema.json"
        )
        records = []
        for digest in final["bin_object_hashes"]:
            # Adapter serializers use different valid shortest-float exponent
            # spellings (Rust emits e-6 while Python emits e-06). The immutable
            # object name binds the exact bytes below, so validate JSON,
            # content hash, schema, and cross-fields without reserializing it
            # through Python's non-cross-language canonical float formatter.
            _, bin_payload, record = file(
                bins_fd, f"{digest}.ndjson", "immutable bin", canonical=False
            )
            if _sha256_bytes(bin_payload) != digest:
                raise ValueError("immutable bin content hash mismatch")
            try:
                jsonschema.validate(record, bin_schema)
            except jsonschema.ValidationError as exc:
                raise ValueError("adapter-specific bin schema mismatch") from exc
            _validate_bin_cross_fields(record, request)
            records.append(record)
        if [record["bin_index"] for record in records] != list(range(expected_bins)):
            raise ValueError("immutable bin indices are not contiguous")

        for descriptor, initial_names, label in enumerations:
            if tuple(sorted(os.listdir(descriptor))) != initial_names:
                raise ValueError(f"{label} changed during descriptor validation")
        for parent, name, descriptor, payload, label in retained:
            try:
                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except OSError as exc:
                raise ValueError(f"{label} changed during descriptor validation") from exc
            if _descriptor_identity(current) != _descriptor_identity(os.fstat(descriptor)):
                raise ValueError(f"{label} identity changed during descriptor validation")
            if payload is not None and _read_descriptor_bytes(descriptor) != payload:
                raise ValueError(f"{label} bytes changed during descriptor validation")
        descriptor_snapshot = {
            "directories": [
                {
                    "path": list(descriptor_paths[descriptor]),
                    "identity": list(_descriptor_identity(os.fstat(descriptor))),
                    "label": label,
                }
                for _, _, descriptor, payload, label in retained
                if payload is None
            ],
            "files": [
                {
                    "path": list(descriptor_paths[descriptor]),
                    "identity": list(_descriptor_identity(os.fstat(descriptor))),
                    "payload": payload,
                    "label": label,
                }
                for _, _, descriptor, payload, label in retained
                if payload is not None
            ],
            "enumerations": [
                {
                    "path": list(descriptor_paths[descriptor]),
                    "names": list(initial_names),
                    "label": label,
                }
                for descriptor, initial_names, label in enumerations
            ],
        }
        semantic_material = {
            "files": [
                {
                    "path": entry["path"],
                    "sha256": _sha256_bytes(entry["payload"]),
                }
                for entry in descriptor_snapshot["files"]
            ],
            "enumerations": [
                {"path": entry["path"], "names": entry["names"]}
                for entry in descriptor_snapshot["enumerations"]
            ],
        }
        return {
            "records": records,
            "current_generation_payload": pointer_payload,
            "current_generation_identity": list(
                _descriptor_identity(os.fstat(pointer_fd))
            ),
            "descriptor_snapshot": descriptor_snapshot,
            "semantic_snapshot_sha256": _sha256_bytes(
                canonical_json(semantic_material)
            ),
        }
    finally:
        for descriptor in reversed(opened):
            os.close(descriptor)


def _open_descriptor_path(
    root: int, parts: list[str], label: str, *, directory: bool
) -> tuple[int, list[int]]:
    parent = root
    opened: list[int] = []
    try:
        for component in parts[:-1]:
            parent = _open_descriptor_directory(parent, component, f"{label} parent")
            opened.append(parent)
        descriptor = (
            _open_descriptor_directory(parent, parts[-1], label)
            if directory
            else _open_descriptor_file(parent, parts[-1], label)
        )
        return descriptor, opened
    except BaseException:
        for descriptor in reversed(opened):
            os.close(descriptor)
        raise


def revalidate_qmc_adapter_output_descriptor_snapshot(
    output_descriptor: int, snapshot: dict[str, Any]
) -> None:
    """Prove every semantically validated descriptor still names exact bytes."""
    for entry in snapshot["directories"]:
        descriptor, parents = _open_descriptor_path(
            output_descriptor, entry["path"], entry["label"], directory=True
        )
        try:
            if list(_descriptor_identity(os.fstat(descriptor))) != entry["identity"]:
                raise ValueError(f"{entry['label']} identity changed after validation")
        finally:
            os.close(descriptor)
            for parent in reversed(parents):
                os.close(parent)
    for entry in snapshot["files"]:
        descriptor, parents = _open_descriptor_path(
            output_descriptor, entry["path"], entry["label"], directory=False
        )
        try:
            if list(_descriptor_identity(os.fstat(descriptor))) != entry["identity"]:
                raise ValueError(f"{entry['label']} identity changed after validation")
            if _read_descriptor_bytes(descriptor) != entry["payload"]:
                raise ValueError(f"{entry['label']} bytes changed after validation")
        finally:
            os.close(descriptor)
            for parent in reversed(parents):
                os.close(parent)
    for entry in snapshot["enumerations"]:
        descriptor, parents = _open_descriptor_path(
            output_descriptor,
            entry["path"],
            entry["label"],
            directory=True,
        )
        try:
            if sorted(os.listdir(descriptor)) != entry["names"]:
                raise ValueError(f"{entry['label']} changed after validation")
        finally:
            os.close(descriptor)
            for parent in reversed(parents):
                os.close(parent)


def validate_qmc_adapter_output(
    output: Path,
    request: dict[str, Any],
    adapter: str,
    *,
    graph_path_override: Path | None = None,
    archival: bool = False,
) -> list[dict[str, Any]]:
    output = Path(output).resolve()
    if adapter not in _ADAPTER_KEYS or request.get("adapter") != adapter:
        raise ValueError("executable-specific adapter mismatch")
    try:
        jsonschema.validate(request, _schema("qmc-request.schema.json"))
    except jsonschema.ValidationError as exc:
        raise ValueError("invalid adapter request") from exc
    graph_path = (
        Path(graph_path_override)
        if graph_path_override is not None
        else Path(request["graph_path"])
    )
    graph = read_graph_json(graph_path)
    graph_payload = json.loads(graph_path.read_text(encoding="utf-8"))
    if graph_payload["sha256"] != request["graph_sha256"] or graph.lattice not in {
        "honeycomb",
        "triangular",
    }:
        raise ValueError("adapter request graph hash mismatch")
    request_hash = _adapter_request_hash(request, adapter)
    anchor_hash = _validate_anchor(output, request_hash, adapter, archival=archival)

    pointer = _load_json(
        output / "current-generation.json", "current generation pointer", canonical=True
    )
    if set(pointer) != {
        "schema_version",
        "anchor_sha256",
        "generation_sha256",
        "path",
    } or pointer["schema_version"] != "qmc-current-generation-v2":
        raise ValueError("current pointer must be qmc-current-generation-v2")
    if pointer["anchor_sha256"] != anchor_hash:
        raise ValueError("current pointer anchor mismatch")
    current_hash = pointer["generation_sha256"]
    if pointer["path"] != f"generations/{current_hash}":
        raise ValueError("current pointer path mismatch")

    generations_root = output / "generations"
    _require_directory(generations_root, "generations directory")
    generation_schema = _schema("qmc-checkpoint-generation.schema.json")
    manifests: dict[str, dict[str, Any]] = {}
    for directory in sorted(generations_root.iterdir()):
        _require_directory(directory, "generation")
        if len(directory.name) != 64 or sorted(path.name for path in directory.iterdir()) != [
            "manifest.json"
        ]:
            raise ValueError("malformed generation directory")
        manifest_path = directory / "manifest.json"
        payload = manifest_path.read_bytes()
        if _sha256_bytes(payload) != directory.name:
            raise ValueError("generation content hash mismatch")
        manifest = _load_json(manifest_path, "generation manifest", canonical=True)
        try:
            jsonschema.validate(manifest, generation_schema)
        except jsonschema.ValidationError as exc:
            raise ValueError("generation manifest schema mismatch") from exc
        bindings = {
            "anchor_sha256": anchor_hash,
            "request_sha256": request_hash,
            "adapter": adapter,
            "source_hash": request["expected_source_hash"],
            "build_hash": request["expected_build_hash"],
            "seed": request["seed"],
        }
        if any(manifest[key] != value for key, value in bindings.items()):
            raise ValueError("generation provenance binding mismatch")
        if manifest["completed_bin_count"] != len(manifest["bin_object_hashes"]):
            raise ValueError("generation completed bin count mismatch")
        manifests[directory.name] = manifest

    chain: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    cursor: str | None = current_hash
    while cursor is not None:
        if cursor in seen or cursor not in manifests:
            raise ValueError("generation ancestry is cyclic or incomplete")
        seen.add(cursor)
        manifest = manifests[cursor]
        chain.append((cursor, manifest))
        cursor = manifest["previous_generation_sha256"]
    chain.reverse()
    if set(manifests) != seen or not chain or chain[0][1]["previous_generation_sha256"] is not None:
        raise ValueError("generation ancestry contains an unreferenced generation")
    previous_hashes: list[str] = []
    for digest, manifest in chain:
        hashes = manifest["bin_object_hashes"]
        if hashes[: len(previous_hashes)] != previous_hashes or len(hashes) <= len(previous_hashes):
            raise ValueError("generation bin ancestry is not append-only")
        previous_hashes = hashes
    expected_bins = request["retained_samples"] // request["bin_length"]
    final = chain[-1][1]
    if final["completed_bin_count"] != expected_bins:
        raise ValueError("final generation is incomplete")

    bins_root = output / "bins"
    _require_directory(bins_root, "bins directory")
    expected_names = {f"{digest}.ndjson" for digest in final["bin_object_hashes"]}
    if {path.name for path in bins_root.iterdir()} != expected_names:
        raise ValueError("immutable bin directory does not exactly match current generation")
    bin_schema = _schema(
        "qmc-sse-bin.schema.json" if adapter == "QMC_SSE" else "qmc-ltfim-bin.schema.json"
    )
    records = []
    for digest in final["bin_object_hashes"]:
        path = bins_root / f"{digest}.ndjson"
        payload = path.read_bytes()
        if _sha256_bytes(payload) != digest:
            raise ValueError("immutable bin content hash mismatch")
        record = _load_json(path, "immutable bin", canonical=True)
        try:
            jsonschema.validate(record, bin_schema)
        except jsonschema.ValidationError as exc:
            raise ValueError("adapter-specific bin schema mismatch") from exc
        _validate_bin_cross_fields(record, request)
        records.append(record)
    if [record["bin_index"] for record in records] != list(range(expected_bins)):
        raise ValueError("immutable bin indices are not contiguous")
    return records


def validate_adapter_run(
    output: Path,
    request: dict[str, Any],
    adapter: str,
    *,
    graph_path_override: Path | None = None,
    archival: bool = False,
) -> list[dict[str, Any]]:
    """Compatibility entry point for acceptance-specific callers."""
    return validate_qmc_adapter_output(
        output,
        request,
        adapter,
        graph_path_override=graph_path_override,
        archival=archival,
    )


def validate_archived_adapter_run(
    output: Path, replay_request: dict[str, Any], archive_root: Path
) -> list[dict[str, Any]]:
    required = {
        "schema_version",
        "adapter",
        "launch_request",
        "launch_request_sha256",
        "authoritative_graph",
    }
    if (
        not isinstance(replay_request, dict)
        or set(replay_request) != required
        or replay_request["schema_version"] != "acceptance-replay-request-v1"
    ):
        raise ValueError("archived replay request schema mismatch")
    adapter = replay_request["adapter"]
    request = replay_request["launch_request"]
    if replay_request["launch_request_sha256"] != _adapter_request_hash(
        request, adapter
    ):
        raise ValueError("archived replay launch request hash mismatch")
    graph_reference = replay_request["authoritative_graph"]
    if (
        not isinstance(graph_reference, dict)
        or set(graph_reference) != {"path", "sha256"}
        or graph_reference["sha256"] != request["graph_sha256"]
    ):
        raise ValueError("archived replay graph binding mismatch")
    relative = Path(graph_reference["path"])
    if relative.is_absolute():
        raise ValueError("archived replay graph path must be internal")
    archive_root = Path(archive_root).resolve()
    output = Path(output).resolve()
    try:
        output.relative_to(archive_root)
    except ValueError as exc:
        raise ValueError("archived adapter run escapes publication") from exc
    graph_path = (archive_root / relative).resolve()
    try:
        graph_path.relative_to(archive_root)
    except ValueError as exc:
        raise ValueError("archived replay graph path escapes publication") from exc
    return validate_adapter_run(
        output,
        request,
        adapter,
        graph_path_override=graph_path,
        archival=True,
    )


def _absolute_owned_environment() -> tuple[Path, Path, Path]:
    solution_text = os.environ.get("CH148_SOLUTION_DIR")
    executable_text = os.environ.get("CH148_QMC_SSE_BIN")
    if not solution_text or not executable_text:
        raise ValueError("CH148_SOLUTION_DIR and CH148_QMC_SSE_BIN must be set")
    solution = Path(solution_text)
    executable_input = Path(executable_text)
    if not solution.is_absolute() or not executable_input.is_absolute():
        raise ValueError("owned adapter environment paths must be absolute")
    executable = _absolute_lexical(executable_input)
    solution = solution.resolve()
    if solution != _root().resolve():
        raise ValueError("CH148_SOLUTION_DIR does not name the owned Challenge 148 solution")
    expected_adapter = solution / "adapters" / "qmc-sse"
    try:
        executable.relative_to(expected_adapter)
    except ValueError as exc:
        raise ValueError("CH148_QMC_SSE_BIN is outside the owned adapter") from exc
    executable_status = executable.lstat()
    if not (
        stat.S_ISREG(executable_status.st_mode)
        or stat.S_ISLNK(executable_status.st_mode)
    ):
        raise ValueError("QMC_SSE executable has unsupported path type")
    if not os.access(executable, os.X_OK):
        raise ValueError("QMC_SSE executable is not executable")
    julia_text = os.environ.get("JULIA_EXECUTABLE") or shutil.which("julia")
    if not julia_text:
        raise ValueError("Julia executable is not available on PATH")
    if not Path(julia_text).is_absolute():
        raise ValueError("JULIA_EXECUTABLE must be absolute")
    julia = _absolute_lexical(Path(julia_text))
    julia_status = julia.lstat()
    if not (
        stat.S_ISREG(julia_status.st_mode)
        or stat.S_ISLNK(julia_status.st_mode)
    ):
        raise ValueError("Julia executable has unsupported path type")
    if not os.access(julia, os.X_OK):
        raise ValueError("Julia executable is not executable")
    return solution, executable, julia


class AdapterLaunchError(RuntimeError):
    def __init__(self, message: str, evidence: dict[str, Any]):
        super().__init__(message)
        self.evidence = evidence


class AcceptanceRunFailed(RuntimeError):
    def __init__(self, message: str, run_path: Path):
        super().__init__(message)
        self.run_path = Path(run_path)


class AcceptancePrelaunchError(RuntimeError):
    pass


def _open_validated_launch_fd(identity: dict[str, Any], label: str) -> int:
    entry = identity[label]
    binding = entry["binding"]
    expected = binding.get("target_file", binding)
    path = Path(binding.get("target", entry["path"]))
    descriptor = os.open(path, _FILE_OPEN_FLAGS)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_dev != expected["device"]
            or before.st_ino != expected["inode"]
            or before.st_size != expected["size"]
        ):
            raise ValueError(f"{label} launch file identity drift")
        digest = hashlib.sha256()
        size = 0
        while True:
            payload = os.read(descriptor, 1024 * 1024)
            if not payload:
                break
            digest.update(payload)
            size += len(payload)
        after = os.fstat(descriptor)
        if (
            _file_stability_identity(after) != _file_stability_identity(before)
            or size != expected["size"]
            or digest.hexdigest() != expected["sha256"]
        ):
            raise ValueError(f"{label} launch file content drift")
        os.lseek(descriptor, 0, os.SEEK_SET)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_initial_identity_fd(path: Path, label: str) -> tuple[int, dict[str, Any]]:
    descriptor = os.open(path, _FILE_OPEN_FLAGS)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"{label} initial identity is not a regular file")
        digest = hashlib.sha256()
        size = 0
        while True:
            payload = os.read(descriptor, 1024 * 1024)
            if not payload:
                break
            digest.update(payload)
            size += len(payload)
        after = os.fstat(descriptor)
        if (
            _file_stability_identity(after) != _file_stability_identity(before)
            or size != before.st_size
        ):
            raise ValueError(f"{label} changed during initial identity hashing")
        os.lseek(descriptor, 0, os.SEEK_SET)
        binding = {
            "type": "file",
            "device": before.st_dev,
            "inode": before.st_ino,
            "sha256": digest.hexdigest(),
            "size": size,
        }
        return descriptor, {
            "path": str(_absolute_lexical(path)),
            "binding": binding,
            "sha256": binding["sha256"],
            "size": size,
        }
    except BaseException:
        os.close(descriptor)
        raise


def _open_initial_julia_identity(
    solution: Path, julia: Path
) -> tuple[dict[str, Any], dict[str, int]]:
    paths = {
        "julia_executable": julia,
        "julia_runner": solution / "adapters/qmc-ltfim/run_independent.jl",
        "julia_project": solution / "adapters/qmc-ltfim/Project.toml",
        "julia_manifest": solution / "adapters/qmc-ltfim/Manifest.toml",
        "julia_module": solution
        / "adapters/qmc-ltfim/src/Challenge148LTFIM.jl",
    }
    identity = {}
    descriptors = {}
    try:
        for label, path in paths.items():
            descriptor, entry = _open_initial_identity_fd(path, label)
            descriptors[label] = descriptor
            identity[label] = entry
        return identity, descriptors
    except BaseException:
        _close_launch_descriptors(descriptors)
        raise


def _open_adapter_launch_descriptors(
    adapter: str, runtime_identity: dict[str, Any]
) -> dict[str, int]:
    labels = (
        ("qmc_sse_executable",)
        if adapter == "QMC_SSE"
        else (
            "julia_executable",
            "julia_runner",
            "julia_project",
            "julia_manifest",
            "julia_module",
        )
        if adapter == "QMC_LTFIM"
        else ()
    )
    if not labels:
        raise ValueError("unknown adapter")
    descriptors = {}
    try:
        for label in labels:
            descriptors[label] = _open_validated_launch_fd(
                runtime_identity, label
            )
        return descriptors
    except BaseException:
        for descriptor in descriptors.values():
            os.close(descriptor)
        raise


def _create_fd_project_view(
    descriptors: dict[str, int],
) -> dict[str, Any]:
    root = Path(tempfile.mkdtemp(prefix="challenge148-julia-project-"))
    directory_descriptor = None
    try:
        os.chmod(root, 0o700)
        source = root / "src"
        source.mkdir(mode=0o700)
        bindings = {
            root / "Project.toml": descriptors["julia_project"],
            root / "Manifest.toml": descriptors["julia_manifest"],
            source / "Challenge148LTFIM.jl": descriptors["julia_module"],
        }
        for path, descriptor in bindings.items():
            os.symlink(f"/proc/self/fd/{descriptor}", path)
        directory_descriptor = os.open(root, _DIRECTORY_OPEN_FLAGS)
        status = os.fstat(directory_descriptor)
        if (
            not stat.S_ISDIR(status.st_mode)
            or stat.S_IMODE(status.st_mode) != 0o700
        ):
            raise ValueError("Julia FD project view permissions are invalid")
        return {
            "root": str(root),
            "descriptor": directory_descriptor,
        }
    except BaseException as exc:
        if directory_descriptor is not None:
            os.close(directory_descriptor)
        shutil.rmtree(root, ignore_errors=True)
        if isinstance(exc, ValueError):
            raise
        raise ValueError("Julia FD project view setup failed") from exc


def _close_fd_project_view(project_view: dict[str, Any] | None) -> None:
    if project_view is None:
        return
    os.close(project_view["descriptor"])
    shutil.rmtree(project_view["root"])


def _fd_launch_commands(
    adapter: str,
    runtime_identity: dict[str, Any],
    descriptors: dict[str, int],
    arguments: list[str],
    project_view: dict[str, Any] | None,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    if adapter == "QMC_SSE":
        labels = ("qmc_sse_executable",)
        prefix = [f"/proc/self/fd/{descriptors[labels[0]]}"]
        diagnostic_prefix = [runtime_identity[labels[0]]["path"]]
    elif adapter == "QMC_LTFIM":
        labels = (
            "julia_executable",
            "julia_runner",
            "julia_project",
            "julia_manifest",
            "julia_module",
        )
        if project_view is None:
            raise ValueError("Julia FD project view is required")
        project = str(Path(runtime_identity["julia_project"]["path"]).parent)
        prefix = [
            f"/proc/self/fd/{descriptors[labels[0]]}",
            f"--project=/proc/self/fd/{project_view['descriptor']}",
            "--compiled-modules=no",
            f"/proc/self/fd/{descriptors[labels[1]]}",
        ]
        diagnostic_prefix = [
            runtime_identity[labels[0]]["path"],
            f"--project={project}",
            "--compiled-modules=no",
            runtime_identity[labels[1]]["path"],
        ]
    else:
        raise ValueError("unknown adapter")
    bindings = [
        {
            "label": label,
            "diagnostic_path": runtime_identity[label]["path"],
            "fd_path": f"/proc/self/fd/{descriptors[label]}",
            "sha256": runtime_identity[label]["sha256"],
        }
        for label in labels
    ]
    return prefix + arguments, diagnostic_prefix + arguments, bindings


def _close_launch_descriptors(descriptors: dict[str, int]) -> None:
    for descriptor in descriptors.values():
        os.close(descriptor)


def launch_adapter(
    adapter: str,
    request_path: Path,
    output: Path,
    *,
    timeout: int,
    launch_nonce: str,
    runtime_identity: dict[str, Any],
) -> dict[str, Any]:
    request_path = Path(request_path).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("stale pre-existing adapter output is forbidden")
    output.parent.mkdir(parents=True, exist_ok=True)
    _require_directory(output.parent, "adapter output parent")
    request = _load_json(request_path, "adapter request")
    descriptors = _open_adapter_launch_descriptors(adapter, runtime_identity)
    project_view = None
    try:
        if adapter == "QMC_LTFIM":
            project_view = _create_fd_project_view(descriptors)
        arguments = [
            "--request",
            str(request_path),
            "--output-directory",
            str(output),
        ]
        command, diagnostic_command, fd_bindings = _fd_launch_commands(
            adapter, runtime_identity, descriptors, arguments, project_view
        )
        environment = os.environ.copy()
        environment["PATH"] = (
            f"{Path.home() / '.cargo' / 'bin'}:{environment.get('PATH', '')}"
        )
        started_ns = time.time_ns()
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                env=environment,
                text=True,
                timeout=timeout,
                pass_fds=(
                    *descriptors.values(),
                    *(
                        (project_view["descriptor"],)
                        if project_view is not None
                        else ()
                    ),
                ),
            )
        except subprocess.TimeoutExpired as exc:
            evidence = {
                "adapter": adapter,
                "command": command,
                "diagnostic_command": diagnostic_command,
                "fd_bound_files": fd_bindings,
                "fd_bound_launch": True,
                "fd_project_view": adapter == "QMC_LTFIM",
                "launch_nonce": launch_nonce,
                "timeout_seconds": timeout,
                "request": request,
                "request_path": str(request_path),
                "output_path": str(output),
                "started_unix_ns": started_ns,
                "completed_unix_ns": time.time_ns(),
                "elapsed_seconds": time.monotonic() - started,
                "stdout": _subprocess_text(exc.stdout),
                "stderr": _subprocess_text(exc.stderr),
                "timed_out": True,
            }
            raise AdapterLaunchError(
                "adapter launch timed out", evidence
            ) from exc
    finally:
        _close_fd_project_view(project_view)
        _close_launch_descriptors(descriptors)
    elapsed = time.monotonic() - started
    evidence = {
        "adapter": adapter,
        "command": command,
        "diagnostic_command": diagnostic_command,
        "fd_bound_files": fd_bindings,
        "fd_bound_launch": True,
        "fd_project_view": adapter == "QMC_LTFIM",
        "launch_nonce": launch_nonce,
        "request": request,
        "request_path": str(request_path),
        "output_path": str(output),
        "started_unix_ns": started_ns,
        "completed_unix_ns": time.time_ns(),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "elapsed_seconds": elapsed,
        "timed_out": False,
    }
    if completed.returncode != 0:
        raise AdapterLaunchError(
            f"adapter subprocess exit {completed.returncode}", evidence
        )
    pointer = output / "current-generation.json"
    try:
        _require_regular(pointer, "post-launch current generation pointer")
        if pointer.stat().st_mtime_ns < started_ns:
            raise ValueError("stale post-launch adapter artifact")
    except ValueError as exc:
        raise AdapterLaunchError(str(exc), evidence) from exc
    binding = {
        "schema_version": "acceptance-launch-binding-v1",
        "launch_nonce": launch_nonce,
        "request_sha256": _adapter_request_hash(request, adapter),
        "adapter": adapter,
        "started_unix_ns": started_ns,
        "completed_unix_ns": time.time_ns(),
    }
    atomic_write_json(output / "acceptance-launch-binding.json", binding)
    evidence["binding"] = binding
    return evidence


def evaluate_adapter(
    label: str,
    chains: list[dict[str, Any]],
    exact: dict[str, float],
    thresholds: dict[str, float],
) -> dict[str, Any]:
    if len(chains) < 2:
        raise ValueError("at least two independent chains are required")
    failures: list[str] = []
    observables: dict[str, Any] = {}
    residuals: list[float] = []
    for name in _OBSERVABLES:
        chain_values = [chain["observables"][name] for chain in chains]
        errors = [float(value["standard_error"]) for value in chain_values]
        if any(not math.isfinite(error) or error <= 0.0 for error in errors):
            raise ValueError("chain errors must be finite and positive")
        weights = [1.0 / error**2 for error in errors]
        weight_sum = sum(weights)
        combined_mean = sum(
            weight * float(value["mean"])
            for weight, value in zip(weights, chain_values, strict=True)
        ) / weight_sum
        combined_error = math.sqrt(1.0 / weight_sum)
        chain_z = max(
            agreement_z_score(
                float(chain_values[left]["mean"]),
                errors[left],
                float(chain_values[right]["mean"]),
                errors[right],
            )
            for left in range(len(chains))
            for right in range(left + 1, len(chains))
        )
        half_z = max(float(value["half_agreement_z"]) for value in chain_values)
        residual = abs(combined_mean - float(exact[name])) / combined_error
        residuals.append(residual)
        observables[name] = {
            "mean": combined_mean,
            "standard_error": combined_error,
            "exact": float(exact[name]),
            "normalized_residual": residual,
            "chain_agreement_z": chain_z,
            "max_half_agreement_z": half_z,
        }
        if residual > thresholds["max_normalized_residual"]:
            failures.append(f"{label}.{name}.normalized_residual")
        if chain_z > thresholds["agreement_sigma"]:
            failures.append(f"{label}.{name}.chain_agreement")
        if half_z > thresholds["agreement_sigma"]:
            failures.append(f"{label}.{name}.half_agreement")
    median = float(sorted(residuals)[len(residuals) // 2])
    return {
        "observables": observables,
        "median_normalized_residual": median,
        "failures": failures,
    }


def evaluate_matrix_median(
    label: str, residuals: list[float], *, threshold: float
) -> dict[str, Any]:
    if not residuals or any(not math.isfinite(value) or value < 0.0 for value in residuals):
        raise ValueError("matrix residuals must be finite and non-negative")
    if not math.isfinite(threshold) or threshold <= 0.0:
        raise ValueError("matrix median threshold must be finite and positive")
    ordered = sorted(residuals)
    median = float(
        (ordered[(len(ordered) - 1) // 2] + ordered[len(ordered) // 2]) / 2.0
    )
    return {
        "median": median,
        "failure": (
            f"{label}.matrix_median_normalized_residual"
            if median > threshold
            else None
        ),
    }


def _adapter_build_info(
    adapter: str,
    solution: Path,
    executable: Path,
    julia: Path,
    timeout: int,
    *,
    runtime_identity: dict[str, Any],
) -> dict:
    descriptors = _open_adapter_launch_descriptors(adapter, runtime_identity)
    project_view = None
    try:
        if adapter == "QMC_LTFIM":
            project_view = _create_fd_project_view(descriptors)
        command, diagnostic_command, fd_bindings = _fd_launch_commands(
            adapter,
            runtime_identity,
            descriptors,
            ["--build-info"],
            project_view,
        )
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                pass_fds=(
                    *descriptors.values(),
                    *(
                        (project_view["descriptor"],)
                        if project_view is not None
                        else ()
                    ),
                ),
            )
        except subprocess.TimeoutExpired as exc:
            raise AdapterLaunchError(
                f"{adapter} build-info timed out",
                {
                    "adapter": adapter,
                    "phase": "build-info",
                    "command": command,
                    "diagnostic_command": diagnostic_command,
                    "fd_bound_files": fd_bindings,
                    "fd_bound_launch": True,
                    "fd_project_view": adapter == "QMC_LTFIM",
                    "elapsed_seconds": time.monotonic() - started,
                    "stdout": _subprocess_text(exc.stdout),
                    "stderr": _subprocess_text(exc.stderr),
                    "timed_out": True,
                },
            ) from exc
    finally:
        _close_fd_project_view(project_view)
        _close_launch_descriptors(descriptors)
    evidence = {
        "adapter": adapter,
        "phase": "build-info",
        "command": command,
        "diagnostic_command": diagnostic_command,
        "fd_bound_files": fd_bindings,
        "fd_bound_launch": True,
        "fd_project_view": adapter == "QMC_LTFIM",
        "elapsed_seconds": time.monotonic() - started,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "timed_out": False,
    }
    if completed.returncode != 0:
        raise AdapterLaunchError(
            f"{adapter} build-info exited {completed.returncode}", evidence
        )
    try:
        info = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AdapterLaunchError(f"{adapter} build-info malformed JSON", evidence) from exc
    expected_keys = (
        {
            "adapter", "build_hash", "codegen_units", "compiler",
            "encoded_rustflags", "features", "lto", "panic", "profile",
            "qmc_revision", "rng", "seed_derivation", "source_hash",
            "sweep_semantics", "target",
        }
        if adapter == "QMC_SSE"
        else {
            "adapter", "build_hash", "julia", "qmc_license", "qmc_revision",
            "rng", "seed_derivation", "seed_namespace", "source_hash",
            "sweep_semantics",
        }
    )
    if set(info) != expected_keys or info["adapter"] != adapter:
        raise AdapterLaunchError("build-info closed schema mismatch", evidence)
    for key in ("build_hash", "source_hash"):
        if not isinstance(info[key], str) or len(info[key]) != 64:
            raise AdapterLaunchError("build-info hash is malformed", evidence)
    return {
        "command": command,
        "diagnostic_command": diagnostic_command,
        "fd_bound_files": fd_bindings,
        "fd_bound_launch": True,
        "fd_project_view": adapter == "QMC_LTFIM",
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "info": info,
    }


def _dependency_relative_paths() -> list[str]:
    return [
        "pyproject.toml",
        "uv.lock",
        "src/challenge148/acceptance.py",
        "src/challenge148/statistics.py",
        "src/challenge148/ed.py",
        "src/challenge148/lattice.py",
        "src/challenge148/provenance.py",
        "src/challenge148/artifacts.py",
        "scripts/run_acceptance.py",
        "schemas/acceptance.schema.json",
        "schemas/qmc-request.schema.json",
        "schemas/qmc-sse-bin.schema.json",
        "schemas/qmc-ltfim-bin.schema.json",
        "schemas/qmc-checkpoint-generation.schema.json",
        "schemas/completion.schema.json",
        "schemas/ed-result.schema.json",
        "schemas/graph.schema.json",
        "preregistration/scientific-v1.json",
        "adapters/qmc-sse/Cargo.toml",
        "adapters/qmc-sse/Cargo.lock",
        "adapters/qmc-sse/build.rs",
        "adapters/qmc-ltfim/Project.toml",
        "adapters/qmc-ltfim/Manifest.toml",
        "adapters/qmc-ltfim/run_independent.jl",
        "adapters/qmc-ltfim/src/Challenge148LTFIM.jl",
        "adapters/qmc-sse/src/graph.rs",
        "adapters/qmc-sse/src/local_lock.rs",
        "adapters/qmc-sse/src/main.rs",
        "adapters/qmc-sse/src/request.rs",
        "adapters/qmc-sse/src/secure_fs.rs",
        "adapters/qmc-sse/src/simulation.rs",
        "adapters/qmc-sse/src/storage.rs",
    ]


def _dependency_closure(
    solution: Path,
    executable: Path,
    julia: Path,
    build_info: dict[str, Any],
    runtime_identity: dict[str, Any],
) -> dict[str, Any]:
    files = {}
    explicit_entries = runtime_identity["owned_runtime_closure"]["explicit_entries"]
    for relative in _dependency_relative_paths():
        path_text = str(_absolute_lexical(solution / relative))
        entry = explicit_entries[path_text].get(
            "target_file", explicit_entries[path_text]
        )
        if entry.get("type") != "file":
            raise ValueError(f"dependency closure file {relative} is not regular")
        files[relative] = {
            "sha256": entry["sha256"],
            "size": entry["size"],
        }
    packages = runtime_identity["python_discovery"]["distributions"]
    julia_packages = runtime_identity["julia_discovery"]["packages"]
    return {
        "schema_version": "acceptance-dependency-closure-v1",
        "files": files,
        "owned_runtime_closure": runtime_identity["owned_runtime_closure"],
        "python_discovery": runtime_identity["python_discovery"],
        "julia_discovery": runtime_identity["julia_discovery"],
        "runtime_closure_boundary": runtime_identity["closure_boundary"],
        "python_environment": runtime_identity["python_environment"],
        "non_owned_environment": runtime_identity["non_owned_environment"],
        "python": {
            "executable_path": runtime_identity["python_environment"]["executable"],
            "executable_sha256": next(
                entry.get("target_file", entry)["sha256"]
                for path, entry in runtime_identity["owned_runtime_closure"][
                    "explicit_entries"
                ].items()
                if path == runtime_identity["python_environment"]["executable"]
            ),
            "version": sys.version,
            "packages": dict(sorted(packages.items())),
        },
        "qmc_sse": {
            "executable_path": str(executable),
            "executable_sha256": runtime_identity["qmc_sse_executable"]["sha256"],
            "build_info": build_info["QMC_SSE"]["info"],
        },
        "qmc_ltfim": {
            "julia_executable_path": str(julia),
            "julia_executable_sha256": runtime_identity["julia_executable"]["sha256"],
            "build_info": build_info["QMC_LTFIM"]["info"],
            "packages": dict(sorted(julia_packages.items())),
        },
    }


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


_DIRECTORY_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_FILE_OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW


def _stat_identity(status: os.stat_result) -> tuple[int, int, int]:
    return status.st_dev, status.st_ino, stat.S_IFMT(status.st_mode)


def _file_stability_identity(status: os.stat_result) -> tuple[int, ...]:
    return (
        status.st_dev,
        status.st_ino,
        stat.S_IFMT(status.st_mode),
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


def _invoke_race_hook(
    race_hook: Any, event: str, *, root_path: str, relative_path: str
) -> None:
    if race_hook is not None:
        race_hook(
            event,
            {"root_path": root_path, "relative_path": relative_path},
        )


def _open_absolute_directory(path: Path) -> int:
    path = _absolute_lexical(path)
    if not path.is_absolute():
        raise ValueError("runtime closure anchor must be absolute")
    descriptor = os.open("/", _DIRECTORY_OPEN_FLAGS)
    try:
        for component in path.parts[1:]:
            child = os.open(component, _DIRECTORY_OPEN_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _assert_anchor_path_identity(path: Path, descriptor: int) -> os.stat_result:
    anchored = os.fstat(descriptor)
    current = os.stat(path, follow_symlinks=False)
    if (
        not stat.S_ISDIR(current.st_mode)
        or _stat_identity(current) != _stat_identity(anchored)
    ):
        raise ValueError("runtime closure root inode replacement")
    return anchored


def _select_anchor(
    path: Path, anchors: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], str]:
    path = _absolute_lexical(path)
    candidates = []
    for anchor in anchors.values():
        root = Path(anchor["path"])
        if path == root or path.is_relative_to(root):
            candidates.append(anchor)
    if not candidates:
        raise ValueError("authoritative path is outside owned roots")
    candidates.sort(key=lambda item: len(Path(item["path"]).parts), reverse=True)
    if (
        len(candidates) > 1
        and len(Path(candidates[0]["path"]).parts)
        == len(Path(candidates[1]["path"]).parts)
    ):
        raise ValueError("ambiguous authoritative root")
    selected = candidates[0]
    relative = path.relative_to(Path(selected["path"])).as_posix()
    return selected, relative


def _open_relative_parent(
    anchor_descriptor: int, relative_path: str
) -> tuple[int, str]:
    parts = Path(relative_path).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("invalid authoritative relative path")
    descriptor = os.dup(anchor_descriptor)
    try:
        for component in parts[:-1]:
            child = os.open(component, _DIRECTORY_OPEN_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor, parts[-1]
    except BaseException:
        os.close(descriptor)
        raise


def _anchored_lstat(
    path: Path, anchors: dict[str, dict[str, Any]]
) -> tuple[os.stat_result, str | None]:
    anchor, relative = _select_anchor(path, anchors)
    if relative == ".":
        return os.fstat(anchor["descriptor"]), None
    parent, name = _open_relative_parent(anchor["descriptor"], relative)
    try:
        status = os.stat(name, dir_fd=parent, follow_symlinks=False)
        link_text = (
            os.readlink(name, dir_fd=parent)
            if stat.S_ISLNK(status.st_mode)
            else None
        )
        return status, link_text
    finally:
        os.close(parent)


def _resolve_anchored_symlink(
    source: Path,
    link_text: str,
    anchors: dict[str, dict[str, Any]],
) -> tuple[Path, str]:
    current = _absolute_lexical(
        Path(link_text) if os.path.isabs(link_text) else source.parent / link_text
    )
    seen: set[str] = set()
    for _ in range(40):
        current_text = str(current)
        if current_text in seen:
            raise ValueError("runtime closure symlink loop")
        seen.add(current_text)
        try:
            status, next_link = _anchored_lstat(current, anchors)
        except ValueError as exc:
            raise ValueError(
                "runtime closure symlink escapes authoritative roots"
            ) from exc
        if stat.S_ISLNK(status.st_mode):
            assert next_link is not None
            current = _absolute_lexical(
                Path(next_link)
                if os.path.isabs(next_link)
                else current.parent / next_link
            )
            continue
        if stat.S_ISDIR(status.st_mode):
            return current, "directory"
        if stat.S_ISREG(status.st_mode):
            return current, "file"
        raise ValueError("runtime closure symlink target type is unsupported")
    raise ValueError("runtime closure symlink loop")


def _hash_open_file(
    parent_descriptor: int,
    name: str,
    expected: os.stat_result,
    *,
    race_hook: Any,
    root_path: str,
    relative_path: str,
) -> dict[str, Any]:
    _invoke_race_hook(
        race_hook,
        "after_entry_stat",
        root_path=root_path,
        relative_path=relative_path,
    )
    descriptor = os.open(name, _FILE_OPEN_FLAGS, dir_fd=parent_descriptor)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or _stat_identity(before) != _stat_identity(expected)
        ):
            raise ValueError("runtime closure file replacement")
        _invoke_race_hook(
            race_hook,
            "after_file_open",
            root_path=root_path,
            relative_path=relative_path,
        )
        digest = hashlib.sha256()
        size = 0
        while True:
            payload = os.read(descriptor, 1024 * 1024)
            if not payload:
                break
            digest.update(payload)
            size += len(payload)
        after = os.fstat(descriptor)
        current = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        if (
            _file_stability_identity(after) != _file_stability_identity(before)
            or _file_stability_identity(current)
            != _file_stability_identity(before)
            or size != before.st_size
        ):
            raise ValueError("runtime closure file changed during hashing")
        return {
            "type": "file",
            "device": before.st_dev,
            "inode": before.st_ino,
            "sha256": digest.hexdigest(),
            "size": size,
        }
    finally:
        os.close(descriptor)


def _hash_anchored_absolute_file(
    path: Path,
    anchors: dict[str, dict[str, Any]],
    *,
    race_hook: Any,
) -> dict[str, Any]:
    anchor, relative = _select_anchor(path, anchors)
    if relative == ".":
        raise ValueError("runtime closure file target names a directory root")
    parent, name = _open_relative_parent(anchor["descriptor"], relative)
    try:
        status = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(status.st_mode):
            raise ValueError("runtime closure symlink target is not regular")
        return _hash_open_file(
            parent,
            name,
            status,
            race_hook=race_hook,
            root_path=anchor["path"],
            relative_path=relative,
        )
    finally:
        os.close(parent)


def _snapshot_named_entry(
    parent_descriptor: int,
    name: str,
    status: os.stat_result,
    *,
    absolute_path: Path,
    anchors: dict[str, dict[str, Any]],
    race_hook: Any,
    root_path: str,
    relative_path: str,
) -> dict[str, Any]:
    if stat.S_ISREG(status.st_mode):
        return _hash_open_file(
            parent_descriptor,
            name,
            status,
            race_hook=race_hook,
            root_path=root_path,
            relative_path=relative_path,
        )
    if stat.S_ISLNK(status.st_mode):
        _invoke_race_hook(
            race_hook,
            "after_entry_stat",
            root_path=root_path,
            relative_path=relative_path,
        )
        link_text = os.readlink(name, dir_fd=parent_descriptor)
        current = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        if _stat_identity(current) != _stat_identity(status):
            raise ValueError("runtime closure symlink replacement")
        target, target_type = _resolve_anchored_symlink(
            absolute_path, link_text, anchors
        )
        entry = {
            "type": "symlink",
            "device": status.st_dev,
            "inode": status.st_ino,
            "link_text": link_text,
            "target": str(target),
            "target_type": target_type,
        }
        if target_type == "file":
            entry["target_file"] = _hash_anchored_absolute_file(
                target, anchors, race_hook=race_hook
            )
        return entry
    raise ValueError("runtime closure contains unsupported path type")


def _enumerate_anchored_directory(
    descriptor: int,
    *,
    label: str,
    root_path: Path,
    relative_directory: str,
    anchors: dict[str, dict[str, Any]],
    entries: dict[str, dict[str, Any]],
    race_hook: Any,
) -> None:
    names = sorted(os.listdir(descriptor))
    if len(names) != len(set(names)):
        raise ValueError("duplicate authoritative directory entry")
    for name in names:
        if name in {"", ".", ".."} or "/" in name:
            raise ValueError("ambiguous authoritative directory entry")
        relative_path = (
            name
            if relative_directory == "."
            else f"{relative_directory}/{name}"
        )
        key = f"{label}:{relative_path}"
        if key in entries:
            raise ValueError("duplicate authoritative relative entry")
        status = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        absolute_path = root_path / relative_path
        if stat.S_ISDIR(status.st_mode):
            _invoke_race_hook(
                race_hook,
                "after_entry_stat",
                root_path=str(root_path),
                relative_path=relative_path,
            )
            child = os.open(name, _DIRECTORY_OPEN_FLAGS, dir_fd=descriptor)
            try:
                opened = os.fstat(child)
                if _stat_identity(opened) != _stat_identity(status):
                    raise ValueError("runtime closure directory replacement")
                entries[key] = {
                    "type": "directory",
                    "device": opened.st_dev,
                    "inode": opened.st_ino,
                }
                _invoke_race_hook(
                    race_hook,
                    "after_directory_open",
                    root_path=str(root_path),
                    relative_path=relative_path,
                )
                _enumerate_anchored_directory(
                    child,
                    label=label,
                    root_path=root_path,
                    relative_directory=relative_path,
                    anchors=anchors,
                    entries=entries,
                    race_hook=race_hook,
                )
                current = os.stat(
                    name, dir_fd=descriptor, follow_symlinks=False
                )
                if _stat_identity(current) != _stat_identity(opened):
                    raise ValueError("runtime closure directory changed")
            finally:
                os.close(child)
        else:
            entries[key] = _snapshot_named_entry(
                descriptor,
                name,
                status,
                absolute_path=absolute_path,
                anchors=anchors,
                race_hook=race_hook,
                root_path=str(root_path),
                relative_path=relative_path,
            )


def _snapshot_authoritative_closure(
    root_descriptors: list[dict[str, str]],
    explicit_paths: list[str],
    boundary_paths: list[str] | None = None,
    *,
    race_hook: Any = None,
) -> dict[str, Any]:
    descriptors = sorted(
        (
            {
                "label": descriptor["label"],
                "path": str(_absolute_lexical(Path(descriptor["path"]))),
            }
            for descriptor in root_descriptors
        ),
        key=lambda descriptor: (descriptor["label"], descriptor["path"]),
    )
    roots = [Path(descriptor["path"]) for descriptor in descriptors]
    labels = [descriptor["label"] for descriptor in descriptors]
    if len(set(roots)) != len(roots) or len(set(labels)) != len(labels):
        raise ValueError("runtime closure root descriptors are not unique")
    for left_index, left in enumerate(roots):
        for right in roots[left_index + 1 :]:
            if left.is_relative_to(right) or right.is_relative_to(left):
                raise ValueError("runtime closure roots overlap ambiguously")
    explicit = sorted(
        {str(_absolute_lexical(Path(path))) for path in explicit_paths}
    )
    boundaries = sorted(
        {
            str(_absolute_lexical(Path(path)))
            for path in (boundary_paths or [str(root) for root in roots])
        }
    )
    anchor_paths = sorted(set(boundaries) | {str(root) for root in roots})
    anchors: dict[str, dict[str, Any]] = {}
    try:
        for path_text in anchor_paths:
            path = Path(path_text)
            descriptor = None
            try:
                descriptor = _open_absolute_directory(path)
                status = _assert_anchor_path_identity(path, descriptor)
            except BaseException as exc:
                if descriptor is not None:
                    os.close(descriptor)
                if isinstance(exc, OSError):
                    raise ValueError(
                        "runtime closure root anchor rejected"
                    ) from exc
                raise
            anchors[path_text] = {
                "path": path_text,
                "descriptor": descriptor,
                "device": status.st_dev,
                "inode": status.st_ino,
            }
        entries: dict[str, dict[str, Any]] = {}
        anchored_descriptors = []
        for descriptor in descriptors:
            anchor = anchors[descriptor["path"]]
            anchored = {
                **descriptor,
                "device": anchor["device"],
                "inode": anchor["inode"],
            }
            anchored_descriptors.append(anchored)
            entries[f"{descriptor['label']}:."] = {
                "type": "directory",
                "device": anchor["device"],
                "inode": anchor["inode"],
            }
            _invoke_race_hook(
                race_hook,
                "after_root_open",
                root_path=descriptor["path"],
                relative_path=".",
            )
            _enumerate_anchored_directory(
                anchor["descriptor"],
                label=descriptor["label"],
                root_path=Path(descriptor["path"]),
                relative_directory=".",
                anchors=anchors,
                entries=entries,
                race_hook=race_hook,
            )
            _assert_anchor_path_identity(
                Path(descriptor["path"]), anchor["descriptor"]
            )
        explicit_entries = {}
        for path_text in explicit:
            path = Path(path_text)
            anchor, relative = _select_anchor(path, anchors)
            if relative == ".":
                explicit_entries[path_text] = {
                    "type": "directory",
                    "device": anchor["device"],
                    "inode": anchor["inode"],
                }
                continue
            parent, name = _open_relative_parent(
                anchor["descriptor"], relative
            )
            try:
                status = os.stat(
                    name, dir_fd=parent, follow_symlinks=False
                )
                explicit_entries[path_text] = _snapshot_named_entry(
                    parent,
                    name,
                    status,
                    absolute_path=path,
                    anchors=anchors,
                    race_hook=race_hook,
                    root_path=anchor["path"],
                    relative_path=relative,
                )
            finally:
                os.close(parent)
        for anchor in anchors.values():
            _assert_anchor_path_identity(
                Path(anchor["path"]), anchor["descriptor"]
            )
        return {
            "schema_version": "owned-runtime-closure-v3",
            "root_descriptors": anchored_descriptors,
            "boundary_descriptors": [
                {
                    "path": anchor["path"],
                    "device": anchor["device"],
                    "inode": anchor["inode"],
                }
                for anchor in anchors.values()
            ],
            "boundary_paths": boundaries,
            "explicit_paths": explicit,
            "entries": dict(sorted(entries.items())),
            "explicit_entries": dict(sorted(explicit_entries.items())),
        }
    except OSError as exc:
        raise ValueError("runtime closure descriptor operation failed") from exc
    finally:
        for anchor in anchors.values():
            os.close(anchor["descriptor"])


def _verify_authoritative_closure(snapshot: dict[str, Any]) -> None:
    try:
        current = _snapshot_authoritative_closure(
            [
                {"label": entry["label"], "path": entry["path"]}
                for entry in snapshot["root_descriptors"]
            ],
            snapshot["explicit_paths"],
            snapshot["boundary_paths"],
        )
    except (OSError, ValueError) as exc:
        raise ValueError("runtime closure drift") from exc
    if current != snapshot:
        raise ValueError("runtime closure drift")


_PYTHON_CLOSURE_AUTHORITY = (
    "isolated scientific-path loaded module files and complete owning "
    "distributions under explicit owned roots"
)


_PYTHON_DISCOVERY_SCRIPT = r'''
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import sysconfig

solution = Path(sys.argv[1])
sys.path.insert(0, str(solution / "src"))
from challenge148.ed import exact_thermal_observables
from challenge148.lattice import honeycomb_graph
exact_thermal_observables(honeycomb_graph(2), coupling=1.0, field=1.2, beta=0.55)

module_paths = set()
owners = set()
owner_map = importlib.metadata.packages_distributions()
for name, module in sorted(sys.modules.items()):
    for attribute in ("__file__", "__cached__"):
        value = getattr(module, attribute, None)
        if value and (Path(value).exists() or Path(value).is_symlink()):
            module_paths.update({os.path.abspath(value), os.path.realpath(value)})
    owners.update(owner_map.get(name.partition(".")[0], ()))
distribution_files = set()
distribution_roots = set()
distributions = {}
for name in sorted(owners):
    distribution = importlib.metadata.distribution(name)
    distributions[name] = distribution.version
    for relative in distribution.files or ():
        path = Path(distribution.locate_file(relative))
        if path.exists() or path.is_symlink():
            distribution_files.update(
                {os.path.abspath(path), os.path.realpath(path)}
            )
        if relative.parts:
            top = Path(distribution.locate_file(relative.parts[0]))
            top.is_dir() and distribution_roots.add(os.path.abspath(top))
paths = sysconfig.get_paths()
owned_roots = {
    os.path.abspath(solution / "src"),
    *(os.path.abspath(value) for key, value in paths.items()
      if key in {"stdlib", "platstdlib", "purelib", "platlib"}),
}
executable = os.path.abspath(sys.executable)
owned_roots.update({os.path.dirname(executable), os.path.dirname(os.path.realpath(executable))})
print(json.dumps({
    "schema_version": "python-science-discovery-v1",
    "authority": (
        "isolated scientific-path loaded module files and complete owning "
        "distributions under explicit owned roots"
    ),
    "owned_roots": sorted(owned_roots),
    "module_paths": sorted(module_paths),
    "distribution_files": sorted(distribution_files),
    "distribution_roots": sorted(distribution_roots),
    "distribution_names": sorted(owners),
    "distributions": distributions,
    "executable_paths": sorted({executable, os.path.realpath(executable)}),
    "environment": {
        "cache_tag": sys.implementation.cache_tag,
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "version": sys.version,
    },
}, sort_keys=True))
'''


def _discover_python_runtime_closure(
    solution: Path, python: Path, timeout: int = 120
) -> dict[str, Any]:
    command = [str(python), "-I", "-c", _PYTHON_DISCOVERY_SCRIPT, str(solution)]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"Python scientific runtime discovery failed: {completed.stderr.strip()}"
        )
    try:
        values = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("Python runtime discovery returned malformed JSON") from exc
    if (
        values.get("schema_version") != "python-science-discovery-v1"
        or values.get("authority") != _PYTHON_CLOSURE_AUTHORITY
    ):
        raise ValueError("Python runtime discovery authority/schema mismatch")
    roots = sorted(str(_absolute_lexical(Path(path))) for path in values["owned_roots"])
    root_paths = [Path(path) for path in roots]
    path_keys = (
        "module_paths",
        "distribution_files",
        "distribution_roots",
        "executable_paths",
    )
    normalized = dict(values)
    for key in path_keys:
        normalized[key] = sorted(
            {
                str(_absolute_lexical(Path(path)))
                for path in values.get(key, [])
            }
        )
        for path_text in normalized[key]:
            path = Path(path_text)
            if not any(
                path == root or path.is_relative_to(root) for root in root_paths
            ):
                raise ValueError("Python authoritative path is outside owned roots")
    normalized["owned_roots"] = roots
    normalized["distribution_names"] = sorted(values["distribution_names"])
    normalized["distributions"] = dict(sorted(values["distributions"].items()))
    return normalized


_JULIA_DISCOVERY_SCRIPT = r'''
using Pkg, Pkg.Artifacts, Pkg.BinaryPlatforms, Libdl, JSON3, TOML
using Challenge148LTFIM, QMC
canonical_project = abspath(ARGS[1])
active_root = dirname(Base.active_project())
model = Challenge148LTFIM.build_model(2, [(0, 1)], 1.0, 1.0)
state = QMC.BinaryThermalState(model, 64)
diagnostics = QMC.Diagnostics(QMC.RunStats(), QMC.NoTransitionMatrix())
rng = Challenge148LTFIM.rng_from_seed(148)
noop(cluster_list_size, qmc_state, active_model) = nothing
QMC.mc_step_beta!(noop, rng, state, model, 0.5, diagnostics; eq=true, p=1.0)
dependencies = Pkg.dependencies()
function authoritative_source(source_value)
    source = abspath(String(source_value))
    if source == active_root
        return canonical_project
    end
    if startswith(source, active_root * "/")
        return joinpath(canonical_project, relpath(source, active_root))
    end
    return source
end
roots = sort!(unique!([
    authoritative_source(info.source) for info in values(dependencies)
    if info.source !== nothing && isdir(info.source)
]))
packages = Dict{String, Any}()
for (uuid, info) in dependencies
    entry = Dict{String, Any}("uuid" => string(uuid))
    for field in (:name, :version, :tree_hash, :git_revision, :git_source)
        if hasproperty(info, field)
            value = getproperty(info, field)
            value !== nothing && (entry[string(field)] = string(value))
        end
    end
    packages[string(uuid)] = entry
end
platform = HostPlatform()
artifacts = Any[]
for root in roots
    for (directory, subdirs, names) in walkdir(root)
        filter!(name -> name != ".git", subdirs)
        if "Artifacts.toml" in names
            artifact_file = joinpath(directory, "Artifacts.toml")
            for name in sort!(collect(keys(TOML.parsefile(artifact_file))))
                metadata = artifact_meta(name, artifact_file; platform=platform)
                applicable = metadata !== nothing
                hash = applicable ? artifact_hash(name, artifact_file; platform=platform) : nothing
                path = hash === nothing ? nothing : artifact_path(hash)
                push!(artifacts, Dict(
                    "name" => String(name),
                    "artifacts_toml" => artifact_file,
                    "applicable" => applicable,
                    "hash" => hash === nothing ? nothing : string(hash),
                    "path" => path !== nothing && isdir(path) ? path : nothing,
                ))
            end
        end
    end
end
image = unsafe_string(Base.JLOptions().image_file)
print(JSON3.write(Dict(
    "schema_version" => "julia-science-discovery-v1",
    "project_root" => canonical_project,
    "depot_roots" => abspath.(DEPOT_PATH),
    "source_roots" => roots,
    "packages" => packages,
    "artifacts" => artifacts,
    "julia_root" => dirname(Sys.BINDIR),
    "sysimage" => image,
    "loaded_libraries" => sort!(unique!(filter(isfile, abspath.(Libdl.dllist())))),
)))
'''


def _run_bound_julia_discovery(
    runtime_identity: dict[str, Any],
    descriptors: dict[str, int],
    project_view: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    canonical_project = str(
        Path(runtime_identity["julia_project"]["path"]).parent
    )
    command = [
        f"/proc/self/fd/{descriptors['julia_executable']}",
        f"--project=/proc/self/fd/{project_view['descriptor']}",
        "--compiled-modules=no",
        "-e",
        _JULIA_DISCOVERY_SCRIPT,
        canonical_project,
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        pass_fds=(
            *descriptors.values(),
            project_view["descriptor"],
        ),
    )
    if completed.returncode != 0:
        raise ValueError(
            f"Julia runtime source discovery failed: {completed.stderr.strip()}"
        )
    try:
        values = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("Julia runtime source discovery returned malformed JSON") from exc
    return _parse_julia_discovery(values)


def _discover_julia_runtime_closure(
    solution: Path,
    julia: Path,
    timeout: int = 120,
    *,
    runtime_identity: dict[str, Any],
) -> dict[str, Any]:
    del solution
    if (
        str(_absolute_lexical(julia))
        != runtime_identity["julia_executable"]["path"]
    ):
        raise ValueError("Julia discovery diagnostic path identity mismatch")
    descriptors = _open_adapter_launch_descriptors(
        "QMC_LTFIM", runtime_identity
    )
    project_view = None
    try:
        project_view = _create_fd_project_view(descriptors)
        return _run_bound_julia_discovery(
            runtime_identity, descriptors, project_view, timeout
        )
    finally:
        _close_fd_project_view(project_view)
        _close_launch_descriptors(descriptors)


def _parse_julia_discovery(values: dict[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(values, dict)
        or values.get("schema_version") != "julia-science-discovery-v1"
        or not values.get("project_root")
        or not values.get("depot_roots")
        or not values.get("source_roots")
        or not isinstance(values.get("packages"), dict)
        or not values.get("julia_root")
        or not values.get("sysimage")
        or not isinstance(values.get("artifacts"), list)
    ):
        raise ValueError("Julia runtime source discovery returned incomplete closure")
    project_root = _absolute_lexical(Path(values["project_root"]))
    depot_roots = sorted(
        _absolute_lexical(Path(value)) for value in values["depot_roots"]
    )
    package_boundaries = [project_root, *depot_roots]
    source_roots = sorted(
        str(_absolute_lexical(Path(value))) for value in values["source_roots"]
    )
    if any(
        not any(
            Path(path) == boundary or Path(path).is_relative_to(boundary)
            for boundary in package_boundaries
        )
        for path in source_roots
    ):
        raise ValueError("Julia package source is outside owned roots")
    julia_root = str(_absolute_lexical(Path(values["julia_root"])))
    artifacts = []
    artifact_roots = []
    for artifact in sorted(
        values["artifacts"],
        key=lambda item: (
            str(item.get("artifacts_toml", "")),
            str(item.get("name", "")),
        ),
    ):
        normalized = dict(artifact)
        artifact_file = _absolute_lexical(Path(artifact.get("artifacts_toml", "")))
        if not any(
            artifact_file == Path(root) or artifact_file.is_relative_to(Path(root))
            for root in source_roots
        ):
            raise ValueError("Julia artifact definition is outside package roots")
        normalized["artifacts_toml"] = str(artifact_file)
        if artifact.get("applicable"):
            path_text = artifact.get("path")
            hash_text = artifact.get("hash")
            if (
                not isinstance(hash_text, str)
                or len(hash_text) != 40
                or any(character not in "0123456789abcdef" for character in hash_text)
                or not path_text
                or not Path(path_text).is_dir()
            ):
                raise ValueError("applicable Julia artifact is missing")
            path = str(_absolute_lexical(Path(path_text)))
            if not any(
                Path(path) == depot or Path(path).is_relative_to(depot)
                for depot in depot_roots
            ):
                raise ValueError("Julia artifact is outside owned depot roots")
            normalized["path"] = path
            artifact_roots.append(path)
        artifacts.append(normalized)
    authoritative_roots = [
        *(Path(path) for path in source_roots),
        *(Path(path) for path in artifact_roots),
        Path(julia_root),
    ]
    owned_libraries = []
    external_libraries = []
    for value in sorted(values["loaded_libraries"]):
        path = _absolute_lexical(Path(value))
        if any(
            path == root or path.is_relative_to(root)
            for root in authoritative_roots
        ):
            owned_libraries.append(str(path))
        else:
            external_libraries.append(str(path))
    sysimage = str(_absolute_lexical(Path(values["sysimage"])))
    if not any(
        Path(sysimage) == root or Path(sysimage).is_relative_to(root)
        for root in authoritative_roots
    ):
        raise ValueError("Julia sysimage is outside owned roots")
    return {
        "schema_version": "julia-science-discovery-v1",
        "project_root": str(project_root),
        "depot_roots": [str(path) for path in depot_roots],
        "source_roots": source_roots,
        "packages": dict(sorted(values["packages"].items())),
        "artifacts": artifacts,
        "artifact_roots": sorted(set(artifact_roots)),
        "julia_root": julia_root,
        "sysimage": sysimage,
        "owned_libraries": owned_libraries,
        "external_abi_libraries": external_libraries,
        "authority": (
            "pinned package trees, host-platform applicable artifacts selected "
            "through Pkg.Artifacts, complete Julia runtime root, active sysimage, "
            "and owned libraries loaded after a real QMC update"
        ),
    }


def _dynamic_abi_metadata(paths: list[str]) -> dict[str, dict[str, Any]]:
    metadata = {}
    for path_text in sorted(set(paths)):
        path = Path(path_text)
        if ".so" not in path.name and path.suffix not in {".dylib", ".pyd"}:
            continue
        completed = subprocess.run(
            ["ldd", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        metadata[str(_absolute_lexical(path))] = {
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "returncode": completed.returncode,
        }
    return metadata


def _minimal_root_descriptors(
    descriptors: list[dict[str, str]],
) -> list[dict[str, str]]:
    selected = []
    for descriptor in sorted(
        descriptors,
        key=lambda item: (
            len(_absolute_lexical(Path(item["path"])).parts),
            item["label"],
        ),
    ):
        path = _absolute_lexical(Path(descriptor["path"]))
        if any(
            path == Path(existing["path"])
            or path.is_relative_to(Path(existing["path"]))
            for existing in selected
        ):
            continue
        selected.append({"label": descriptor["label"], "path": str(path)})
    return selected


def _runtime_artifact_identity(
    solution: Path, executable: Path, julia: Path
) -> dict[str, Any]:
    paths = {
        "qmc_sse_executable": _absolute_lexical(executable),
        "julia_executable": _absolute_lexical(julia),
        "julia_runner": solution / "adapters/qmc-ltfim/run_independent.jl",
        "julia_module": solution
        / "adapters/qmc-ltfim/src/Challenge148LTFIM.jl",
        "julia_project": solution / "adapters/qmc-ltfim/Project.toml",
        "julia_manifest": solution / "adapters/qmc-ltfim/Manifest.toml",
    }
    identity = {}
    python_closure = _discover_python_runtime_closure(
        solution, Path(sys.executable), timeout=120
    )
    initial_julia_identity, initial_julia_descriptors = (
        _open_initial_julia_identity(solution, julia)
    )
    initial_project_view = None
    try:
        initial_project_view = _create_fd_project_view(
            initial_julia_descriptors
        )
        julia_closure = _run_bound_julia_discovery(
            initial_julia_identity,
            initial_julia_descriptors,
            initial_project_view,
            120,
        )
    finally:
        _close_fd_project_view(initial_project_view)
        _close_launch_descriptors(initial_julia_descriptors)
    root_descriptors = _minimal_root_descriptors([
        {"label": "solution-source", "path": str(solution / "src")},
        {
            "label": "qmc-sse-source",
            "path": str(solution / "adapters/qmc-sse/src"),
        },
        *(
            {"label": f"python-distribution-{index}", "path": path}
            for index, path in enumerate(python_closure["distribution_roots"])
        ),
        *(
            {"label": f"julia-package-{index}", "path": path}
            for index, path in enumerate(julia_closure["source_roots"])
        ),
        *(
            {"label": f"julia-artifact-{index}", "path": path}
            for index, path in enumerate(julia_closure["artifact_roots"])
        ),
        {"label": "julia-runtime", "path": julia_closure["julia_root"]},
    ])
    explicit_paths = [
        *python_closure["module_paths"],
        *python_closure.get("distribution_files", []),
        *python_closure["executable_paths"],
        julia_closure["sysimage"],
        *julia_closure["owned_libraries"],
        *(str(_absolute_lexical(path)) for path in paths.values()),
        *(
            str(_absolute_lexical(solution / relative))
            for relative in _dependency_relative_paths()
        ),
    ]
    identity["owned_runtime_closure"] = _snapshot_authoritative_closure(
        root_descriptors,
        explicit_paths,
        [
            *python_closure["owned_roots"],
            *julia_closure["source_roots"],
            *julia_closure["artifact_roots"],
            julia_closure["julia_root"],
            str(solution / "adapters/qmc-sse"),
            str(_absolute_lexical(julia).parent),
        ],
    )
    explicit_entries = identity["owned_runtime_closure"]["explicit_entries"]
    for label, path in paths.items():
        path_text = str(_absolute_lexical(path))
        entry = explicit_entries[path_text]
        file_entry = entry.get("target_file", entry)
        if file_entry.get("type") != "file":
            raise ValueError(f"{label} is not an anchored regular file")
        identity[label] = {
            "path": path_text,
            "binding": entry,
            "sha256": file_entry["sha256"],
            "size": file_entry["size"],
        }
    for label, initial_entry in initial_julia_identity.items():
        if identity[label] != initial_entry:
            raise ValueError(
                f"{label} changed after FD-bound Julia discovery"
            )
    identity["python_discovery"] = python_closure
    identity["julia_discovery"] = julia_closure
    identity["discovery_inputs"] = {
        "solution": str(solution),
        "python": str(_absolute_lexical(Path(sys.executable))),
        "julia": str(_absolute_lexical(julia)),
    }
    identity["closure_boundary"] = {
        "python": python_closure["authority"],
        "python_distributions": python_closure["distribution_names"],
        "julia": julia_closure["authority"],
        "julia_source_roots": julia_closure["source_roots"],
        "julia_artifact_roots": julia_closure["artifact_roots"],
        "julia_root": julia_closure["julia_root"],
        "julia_sysimage": julia_closure["sysimage"],
        "excluded": "unloaded OS files and unrelated installed packages",
    }
    identity["python_environment"] = {
        **python_closure["environment"],
        "executable": python_closure["executable_paths"][0],
        "executable_binding": explicit_entries[
            python_closure["executable_paths"][0]
        ],
        "platform": platform.platform(),
        "pythonpath": os.environ.get("PYTHONPATH", ""),
    }
    dynamic_abi = subprocess.run(
        ["ldd", str(executable)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    identity["non_owned_environment"] = {
        "julia_external_abi_libraries": julia_closure["external_abi_libraries"],
        "kernel": " ".join(os.uname()),
        "libc": platform.libc_ver(),
        "python_native_extension_dynamic_abi": _dynamic_abi_metadata(
            python_closure["module_paths"]
        ),
        "rust_executable_dynamic_abi": dynamic_abi.stdout,
        "rust_executable_dynamic_abi_stderr": dynamic_abi.stderr,
        "rust_executable_dynamic_abi_returncode": dynamic_abi.returncode,
    }
    return identity


def _verify_runtime_artifact_identity(identity: dict[str, Any]) -> None:
    discovery_inputs = identity["discovery_inputs"]
    current_python = _discover_python_runtime_closure(
        Path(discovery_inputs["solution"]),
        Path(discovery_inputs["python"]),
        timeout=120,
    )
    current_julia = _discover_julia_runtime_closure(
        Path(discovery_inputs["solution"]),
        Path(discovery_inputs["julia"]),
        timeout=120,
        runtime_identity=identity,
    )
    if current_python != identity["python_discovery"]:
        raise ValueError("Python runtime discovery drift")
    julia_authority_keys = {
        "schema_version",
        "project_root",
        "depot_roots",
        "source_roots",
        "packages",
        "artifacts",
        "artifact_roots",
        "julia_root",
        "sysimage",
        "owned_libraries",
        "authority",
    }
    if (
        {key: current_julia[key] for key in julia_authority_keys}
        != {key: identity["julia_discovery"][key] for key in julia_authority_keys}
    ):
        raise ValueError("Julia runtime discovery drift")
    _verify_authoritative_closure(identity["owned_runtime_closure"])


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _raw_run_reference(path: Path, *, reference_path: str | None = None) -> dict[str, Any]:
    _require_directory(path, "raw adapter run")
    files: dict[str, dict[str, Any]] = {}
    for directory, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
        dirnames.sort()
        filenames.sort()
        directory_path = Path(directory)
        for name in dirnames:
            _require_directory(directory_path / name, "raw adapter directory")
        for name in filenames:
            file_path = directory_path / name
            _require_regular(file_path, "raw adapter artifact")
            payload = file_path.read_bytes()
            files[file_path.relative_to(path).as_posix()] = {
                "sha256": _sha256_bytes(payload),
                "size": len(payload),
            }
    manifest_sha256 = _sha256_bytes(canonical_json(files))
    return {
        "path": reference_path if reference_path is not None else str(path.resolve()),
        "manifest_sha256": manifest_sha256,
        "files": files,
    }


def _copy_validated_raw_run(source: Path, destination: Path, stage: Path) -> dict[str, Any]:
    source_reference = _raw_run_reference(source)
    shutil.copytree(source, destination, symlinks=False)
    internal_path = destination.relative_to(stage).as_posix()
    copied_reference = _raw_run_reference(
        destination, reference_path=internal_path
    )
    if (
        source_reference["manifest_sha256"] != copied_reference["manifest_sha256"]
        or source_reference["files"] != copied_reference["files"]
    ):
        raise ValueError("published raw adapter copy failed closure revalidation")
    return copied_reference


def run_acceptance(request: dict, output_root: Path) -> Path:
    from .ed import exact_thermal_observables

    validate_acceptance_request(request)
    output_root = Path(output_root).resolve()
    launch_nonce = uuid.uuid4().hex
    raw_root = output_root / "raw-adapter-runs" / launch_nonce
    solution = executable = julia = None
    prelaunch_error: Exception | None = None
    try:
        solution, executable, julia = _absolute_owned_environment()
        runtime_identity: dict[str, Any] = _runtime_artifact_identity(
            solution, executable, julia
        )
    except Exception as exc:
        prelaunch_error = exc
        runtime_identity = {
            "status": "unavailable",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    publication_spec = {
        "schema_version": "acceptance-publication-v1",
        "acceptance_request": request,
        "acceptance_request_sha256": _request_hash(request),
        "launch_nonce": launch_nonce,
        "runtime_artifact_identity": runtime_identity,
    }

    failure_state: dict[str, Any] = {}

    def produce_success(stage: Path) -> None:
        if prelaunch_error is not None:
            raise AcceptancePrelaunchError(str(prelaunch_error))
        assert solution is not None and executable is not None and julia is not None
        if raw_root.exists():
            raise AcceptancePrelaunchError(
                "stale pre-existing raw acceptance root"
            )
        timeout = request["launch_timeout_seconds"]
        build_info = {}
        for adapter in ("QMC_SSE", "QMC_LTFIM"):
            try:
                _verify_runtime_artifact_identity(runtime_identity)
            except ValueError as exc:
                raise AcceptancePrelaunchError(
                    "runtime executable or source artifact changed"
                ) from exc
            build_info[adapter] = _adapter_build_info(
                adapter,
                solution,
                executable,
                julia,
                timeout,
                runtime_identity=runtime_identity,
            )
        atomic_write_json(stage / "build-info.json", build_info)
        dependency_closure = _dependency_closure(
            solution, executable, julia, build_info, runtime_identity
        )
        atomic_write_json(
            stage / "dependency-closure.json",
            dependency_closure,
        )
        gate_sources = {}
        for relative in (
            "src/challenge148/acceptance.py",
            "src/challenge148/statistics.py",
            "schemas/acceptance.schema.json",
            "scripts/run_acceptance.py",
        ):
            gate_sources[relative] = dependency_closure["files"][relative]
        atomic_write_json(stage / "gate-source.json", gate_sources)
        environment = {
            "CH148_QMC_SSE_BIN": str(executable),
            "CH148_SOLUTION_DIR": str(solution),
            "JULIA_EXECUTABLE": str(julia),
            "PATH": os.environ.get("PATH", ""),
            "python": os.sys.version,
        }
        atomic_write_json(stage / "environment.json", environment)
        failures: list[str] = []
        cells_payload: list[dict[str, Any]] = []
        raw_references: list[dict[str, Any]] = []
        adapter_residuals: dict[str, list[float]] = {
            "primary_qmc_sse": [],
            "independent_qmc_ltfim": [],
        }
        for cell_index, cell in enumerate(request["cells"]):
            print(
                f"[{cell_index + 1}/{len(request['cells'])}] acceptance cell {cell['cell_id']}",
                flush=True,
            )
            graph = read_graph_json(Path(cell["graph_path"]))
            graph_payload = Path(cell["graph_path"]).read_bytes()
            graph_snapshot = stage / "graphs" / f"{cell['graph_sha256']}.json"
            graph_snapshot.parent.mkdir(parents=True, exist_ok=True)
            if graph_snapshot.exists() and graph_snapshot.read_bytes() != graph_payload:
                raise ValueError("graph snapshot hash collision")
            graph_snapshot.write_bytes(graph_payload)
            ed = exact_thermal_observables(
                graph,
                coupling=cell["coupling"],
                field=cell["field"],
                beta=cell["beta"],
            )
            exact = {name: float(getattr(ed, name)) for name in _OBSERVABLES}
            cell_result: dict[str, Any] = {
                "cell_id": cell["cell_id"],
                "lattice": cell["lattice"],
                "length": cell["length"],
                "beta": cell["beta"],
                "field": cell["field"],
                "graph_sha256": cell["graph_sha256"],
                "exact_ed": exact,
                "adapters": {},
            }
            for adapter in ("QMC_SSE", "QMC_LTFIM"):
                adapter_key = _ADAPTER_KEYS[adapter]
                label = _ADAPTER_LABELS[adapter]
                adapter_spec = cell["adapters"][adapter_key]
                expected_build = request["build_closure"][adapter_key]
                info = build_info[adapter]["info"]
                if (
                    info.get("source_hash") != expected_build["expected_source_hash"]
                    or info.get("build_hash") != expected_build["expected_build_hash"]
                ):
                    raise ValueError(f"{adapter} executable provenance drift")
                chain_summaries = []
                launch_evidence = []
                for chain_index, settings in enumerate(adapter_spec["chains"]):
                    try:
                        _verify_runtime_artifact_identity(runtime_identity)
                    except ValueError as exc:
                        raise AcceptancePrelaunchError(
                            "runtime executable or source artifact changed"
                        ) from exc
                    qmc_request = {
                        "schema_version": "qmc-request-v1",
                        "adapter": adapter,
                        "graph_path": cell["graph_path"],
                        "graph_sha256": cell["graph_sha256"],
                        "beta": cell["beta"],
                        "coupling": cell["coupling"],
                        "field": cell["field"],
                        "seed": settings["seed"],
                        "thermalization_sweeps": settings["thermalization_sweeps"],
                        "retained_samples": settings["retained_samples"],
                        "thinning": settings["thinning"],
                        "serial_measurement_stride_samples": settings[
                            "serial_measurement_stride_samples"
                        ],
                        "bin_length": settings["analysis_bin_length_samples"],
                        "checkpoint_bins": settings["checkpoint_analysis_bins"],
                        "expected_source_hash": expected_build["expected_source_hash"],
                        "expected_build_hash": expected_build["expected_build_hash"],
                    }
                    request_path = (
                        stage
                        / "diagnostics"
                        / "launch-requests"
                        / cell["cell_id"]
                        / adapter_key
                        / f"chain-{chain_index}.json"
                    )
                    atomic_write_json(request_path, qmc_request)
                    raw_output = (
                        raw_root
                        / cell["cell_id"]
                        / adapter_key
                        / f"chain-{chain_index}"
                    )
                    evidence = launch_adapter(
                        adapter,
                        request_path,
                        raw_output,
                        timeout=timeout,
                        launch_nonce=launch_nonce,
                        runtime_identity=runtime_identity,
                    )
                    launch_evidence.append(evidence)
                    log_root = (
                        stage
                        / "subprocess"
                        / cell["cell_id"]
                        / adapter_key
                        / f"chain-{chain_index}"
                    )
                    _write_text(log_root / "stdout.txt", evidence["stdout"])
                    _write_text(log_root / "stderr.txt", evidence["stderr"])
                    atomic_write_json(log_root / "launch.json", evidence)
                    records = validate_adapter_run(raw_output, qmc_request, adapter)
                    binding = _load_json(
                        raw_output / "acceptance-launch-binding.json",
                        "acceptance launch binding",
                    )
                    if (
                        binding["launch_nonce"] != launch_nonce
                        or binding["request_sha256"]
                        != _adapter_request_hash(qmc_request, adapter)
                    ):
                        raise ValueError("stale launch nonce/request binding")
                    chain_summaries.append(
                        summarize_bin_records(
                            records,
                            analysis_bin_length_samples=settings[
                                "analysis_bin_length_samples"
                            ],
                            serial_measurement_stride_samples=settings[
                                "serial_measurement_stride_samples"
                            ],
                            minimum_analysis_bin_tau_ratio=request["analysis"][
                                "minimum_analysis_bin_tau_ratio"
                            ],
                        )
                    )
                    archived_raw = (
                        stage
                        / "raw-adapter-runs"
                        / cell["cell_id"]
                        / adapter_key
                        / f"chain-{chain_index}"
                    )
                    copied_reference = _copy_validated_raw_run(
                        raw_output, archived_raw, stage
                    )
                    replay_request = {
                        "schema_version": "acceptance-replay-request-v1",
                        "adapter": adapter,
                        "launch_request": qmc_request,
                        "launch_request_sha256": _adapter_request_hash(
                            qmc_request, adapter
                        ),
                        "authoritative_graph": {
                            "path": graph_snapshot.relative_to(stage).as_posix(),
                            "sha256": cell["graph_sha256"],
                        },
                    }
                    replay_path = (
                        stage
                        / "requests"
                        / cell["cell_id"]
                        / adapter_key
                        / f"chain-{chain_index}.json"
                    )
                    atomic_write_json(replay_path, replay_request)
                    validate_archived_adapter_run(
                        archived_raw, replay_request, stage
                    )
                    raw_references.append(
                        {
                            "cell_id": cell["cell_id"],
                            "adapter": adapter,
                            "chain_index": chain_index,
                            "replay_request_path": replay_path.relative_to(
                                stage
                            ).as_posix(),
                            **copied_reference,
                        }
                    )
                evaluated = evaluate_adapter(
                    label, chain_summaries, exact, request["thresholds"]
                )
                failures.extend(
                    f"{cell['cell_id']}.{failure}" for failure in evaluated["failures"]
                )
                adapter_residuals[label].extend(
                    value["normalized_residual"]
                    for value in evaluated["observables"].values()
                )
                cell_result["adapters"][adapter_key] = {
                    **evaluated,
                    "chains": chain_summaries,
                    "launches": launch_evidence,
                }
            cells_payload.append(cell_result)

        medians = {}
        for label, values in adapter_residuals.items():
            evaluated_median = evaluate_matrix_median(
                label,
                values,
                threshold=request["thresholds"]["median_normalized_residual"],
            )
            medians[label] = evaluated_median["median"]
            if evaluated_median["failure"] is not None:
                failures.append(evaluated_median["failure"])
        summary = {
            "schema_version": "acceptance-summary-v1",
            "mode": request["mode"],
            "scientific_acceptance": request["mode"] == "scientific" and not failures,
            "passed": not failures,
            "failures": sorted(failures),
            "thresholds": request["thresholds"],
            "matrix_median_normalized_residual": medians,
            "cells": cells_payload,
            "raw_adapter_runs": raw_references,
            "launch_nonce": launch_nonce,
            "acceptance_request_sha256": _request_hash(request),
        }
        atomic_write_json(stage / "summary.json", summary)

    def produce(stage: Path) -> None:
        try:
            produce_success(stage)
        except Exception as exc:
            partial_raw = None
            partial_raw_error = None
            if raw_root.exists():
                try:
                    partial_raw = _copy_validated_raw_run(
                        raw_root, stage / "failure-raw-adapter-runs", stage
                    )
                except Exception as archive_exc:
                    partial_raw_error = str(archive_exc)
            failure = {
                "schema_version": "acceptance-failure-v1",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "phase": (
                    "prelaunch"
                    if isinstance(exc, AcceptancePrelaunchError)
                    else "execution"
                ),
                "launch": exc.evidence if isinstance(exc, AdapterLaunchError) else None,
                "launch_nonce": launch_nonce,
                "acceptance_request_sha256": _request_hash(request),
                "partial_raw": partial_raw,
                "partial_raw_error": partial_raw_error,
            }
            atomic_write_json(stage / "failure.json", failure)
            atomic_write_json(
                stage / "summary.json",
                {
                    "schema_version": "acceptance-summary-v1",
                    "mode": request["mode"],
                    "scientific_acceptance": False,
                    "passed": False,
                    "failures": [f"execution.{type(exc).__name__}"],
                    "error": str(exc),
                    "launch_nonce": launch_nonce,
                    "acceptance_request_sha256": _request_hash(request),
                },
            )
            failure_state["message"] = str(exc)

    run_path = publish_run(output_root, run_spec=publication_spec, producer=produce)
    if failure_state:
        raise AcceptanceRunFailed(failure_state["message"], run_path)
    return run_path
