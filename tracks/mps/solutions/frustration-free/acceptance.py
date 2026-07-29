"""Transactional cross-language finite-bath MPS-versus-ED acceptance gate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import numbers
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import tempfile
import time
from typing import Any, Sequence


MODULE_VERSION = "2.3.0"
SCHEMA_VERSION = 2
DEFAULT_THRESHOLD = 1.0e-6
INTERIOR_GREEN_SIGNAL_MARGIN = 1.0e-5
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 64
SOLUTION_DIR = Path(__file__).resolve().parent
JULIA_DIR = SOLUTION_DIR / "julia"
JULIA_RUNNER = JULIA_DIR / "finite_bath_mps_runner.jl"
JULIA_PURIFICATION = JULIA_DIR / "finite_bath_purification.jl"
JULIA_OBSERVABLES = JULIA_DIR / "finite_bath_observables.jl"
JULIA_CHECKPOINT = JULIA_DIR / "finite_bath_checkpoint.jl"
CHAIN_MAPPING_SOURCE = SOLUTION_DIR / "chain_mapping.py"
MODEL_DEFINITION = SOLUTION_DIR / "model.json"
DEFAULT_OUTPUT_DIRECTORY = SOLUTION_DIR / "results" / "acceptance"
RUNNER_SCHEMA_VERSION = 3
CHECKPOINT_SCHEMA_VERSION = 1
CHECKPOINT_WRITER_VERSION = "1.0.0"


def _load_local_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SOLUTION_DIR / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bath = _load_local_module("challenge_81_acceptance_bath", "bath.py")
chain = _load_local_module(
    "challenge_81_acceptance_chain_mapping", "chain_mapping.py"
)
ed = _load_local_module("challenge_81_acceptance_ed", "finite_bath_ed.py")


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON constant {value!r} is forbidden")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def strict_json_loads(value: str | bytes, *, name: str = "JSON input") -> Any:
    """Parse RFC-compliant JSON while rejecting duplicate object keys."""

    encoded = value.encode("utf-8") if isinstance(value, str) else value
    if len(encoded) > MAX_JSON_BYTES:
        raise ValueError(f"{name} exceeds JSON size limit of {MAX_JSON_BYTES} bytes")
    try:
        parsed = json.loads(
            value,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"{name} is invalid: {error}") from error

    def check_depth(item: Any, depth: int) -> None:
        if depth > MAX_JSON_DEPTH:
            raise ValueError(
                f"{name} exceeds JSON depth limit of {MAX_JSON_DEPTH}"
            )
        if isinstance(item, list):
            for child in item:
                check_depth(child, depth + 1)
        elif isinstance(item, dict):
            for child in item.values():
                check_depth(child, depth + 1)

    check_depth(parsed, 0)
    return parsed


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _request_float(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("request contains a non-finite float")
    if value.is_integer():
        return str(int(value))
    encoded = repr(value).lower()
    if "e" in encoded:
        mantissa, exponent = encoded.split("e")
        if "." not in mantissa:
            mantissa += ".0"
        encoded = f"{mantissa}e{int(exponent)}"
    return encoded


def _request_canonical_text(value: Any) -> str:
    """Canonical request JSON shared exactly with the Julia runner."""

    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return _request_float(value)
    if isinstance(value, list):
        return "[" + ",".join(_request_canonical_text(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("request object keys must be strings")
        return (
            "{"
            + ",".join(
                f"{_request_canonical_text(key)}:"
                f"{_request_canonical_text(value[key])}"
                for key in sorted(value)
            )
            + "}"
        )
    raise TypeError(f"request contains unsupported type {type(value).__name__}")


def _request_canonical_json(value: Any) -> bytes:
    return _request_canonical_text(value).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _validate_digest(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be 64 lowercase hexadecimal digits")
    return value


def _require_exact_keys(value: Any, keys: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a JSON object")
    if set(value) != keys:
        missing = sorted(keys - set(value))
        unexpected = sorted(set(value) - keys)
        raise ValueError(
            f"{name} keys do not match the supported schema; "
            f"missing={missing}, unexpected={unexpected}"
        )
    return value


def _validate_real(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _validate_acceptance_threshold(value: Any) -> float:
    threshold = _validate_real(value, "threshold")
    if threshold < 0.0:
        raise ValueError("threshold must be nonnegative")
    if threshold > DEFAULT_THRESHOLD:
        raise ValueError(
            f"threshold must not exceed binding maximum {DEFAULT_THRESHOLD}"
        )
    return threshold


def _request_geometry_identity(
    request_payload: dict[str, Any],
) -> tuple[str, dict[str, Any] | None, str | None]:
    geometry = _require_exact_keys(
        request_payload["bath_geometry"],
        {
            "representation",
            "chain_mapping_artifact_json",
            "chain_mapping_artifact_file_sha256",
        },
        "bath geometry",
    )
    representation = geometry["representation"]
    mapping_json = geometry["chain_mapping_artifact_json"]
    mapping_file_sha256 = geometry["chain_mapping_artifact_file_sha256"]
    if representation == "direct_star":
        if mapping_json is not None or mapping_file_sha256 is not None:
            raise ValueError(
                "direct_star representation cannot consume a chain mapping"
            )
        return representation, None, None
    if representation != "chain":
        raise ValueError("bath representation must be direct_star or chain")
    if not isinstance(mapping_json, str):
        raise TypeError("chain representation requires mapping artifact JSON")
    mapping_bytes = mapping_json.encode("utf-8")
    if _validate_digest(
        mapping_file_sha256, "chain mapping artifact file SHA256"
    ) != _sha256_bytes(mapping_bytes):
        raise ValueError("chain mapping artifact file SHA256 mismatch")
    mapping = strict_json_loads(mapping_json, name="chain mapping artifact")
    if mapping_bytes != _canonical_json(mapping) + b"\n":
        raise ValueError("chain mapping artifact bytes are not canonical")
    bath_artifact = strict_json_loads(
        request_payload["bath_artifact_json"], name="bath artifact"
    )
    chain.verify_chain_mapping_artifact(mapping, bath_artifact)
    return representation, mapping, mapping["sha256"]


def _expected_output_settings(
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    representation, _mapping, mapping_sha256 = _request_geometry_identity(
        request_payload
    )
    return {
        **copy.deepcopy(request_payload["solver_settings"]),
        "bath_representation": representation,
        "chain_mapping_sha256": mapping_sha256,
    }


def _validate_finite_tree(value: Any, name: str) -> None:
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, numbers.Real):
        if not math.isfinite(float(value)):
            raise ValueError(f"{name} contains a non-finite number")
        return
    if isinstance(value, list):
        for item in value:
            _validate_finite_tree(item, name)
        return
    if isinstance(value, dict):
        for item in value.values():
            _validate_finite_tree(item, name)
        return
    raise TypeError(f"{name} contains a non-JSON value")


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(
        directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_json(path: str | os.PathLike[str], value: Any) -> None:
    """Atomically write one finite canonical JSON file inside a staging tree."""

    _validate_finite_tree(value, "JSON artifact")
    destination = Path(path)
    encoded = _canonical_json(value) + b"\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        _fsync_directory(destination.parent)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _unused_sibling_path(parent: Path, prefix: str) -> Path:
    descriptor, name = tempfile.mkstemp(dir=parent, prefix=prefix)
    os.close(descriptor)
    os.unlink(name)
    return Path(name)


def atomic_publish_directory(staging: Path, destination: Path) -> None:
    """Atomically swap a complete staging tree with rollback of the old tree."""

    staging = staging.resolve()
    destination = destination.resolve()
    if staging.parent != destination.parent:
        raise ValueError("staging and destination must share a parent directory")
    if not staging.is_dir() or staging.is_symlink():
        raise ValueError("staging must be a real directory")
    try:
        destination_status = destination.lstat()
    except FileNotFoundError:
        destination_status = None
    if destination_status is not None and (
        not stat.S_ISDIR(destination_status.st_mode) or destination.is_symlink()
    ):
        raise ValueError("existing acceptance destination must be a real directory")

    backup: Path | None = None
    old_moved = False
    new_published = False
    rollback_tree: Path | None = None
    try:
        if destination_status is not None:
            backup = _unused_sibling_path(
                destination.parent, f".{destination.name}.backup-"
            )
            os.replace(destination, backup)
            old_moved = True
            _fsync_directory(destination.parent)
        os.replace(staging, destination)
        new_published = True
        _fsync_directory(destination.parent)
    except BaseException:
        try:
            if new_published and destination.exists():
                rollback_tree = _unused_sibling_path(
                    destination.parent, f".{destination.name}.failed-"
                )
                os.replace(destination, rollback_tree)
                new_published = False
            if old_moved and backup is not None and backup.exists():
                os.replace(backup, destination)
                old_moved = False
            _fsync_directory(destination.parent)
        finally:
            if rollback_tree is not None and rollback_tree.exists():
                shutil.rmtree(rollback_tree, ignore_errors=True)
        raise

    if backup is not None and backup.exists():
        shutil.rmtree(backup)
        try:
            _fsync_directory(destination.parent)
        except OSError:
            # The published directory was already durably fsynced. Backup cleanup
            # durability is not part of acceptance publication.
            pass


ACCEPTANCE_RUN_FILES = {
    "acceptance.json",
    "bath.json",
    "ed-oracle.json",
    "mps-input.json",
    "mps-result.json",
    "completion.json",
}


def _completion_sha256(completion: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in completion.items()
        if key != "completion_sha256"
    }
    return _sha256_bytes(_canonical_json(payload))


def validate_acceptance_run(
    directory: str | os.PathLike[str],
    *,
    expected_artifact: dict[str, Any],
    julia_project: str | os.PathLike[str],
) -> dict[str, Any]:
    """Validate every byte and semantic binding in a published acceptance run."""

    root = Path(directory)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("acceptance run must be a real directory")
    entries = {path.name for path in root.iterdir()}
    if entries != ACCEPTANCE_RUN_FILES:
        raise ValueError(
            f"acceptance run files mismatch: expected {sorted(ACCEPTANCE_RUN_FILES)}, "
            f"got {sorted(entries)}"
        )
    for name in entries:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"acceptance run entry must be a real file: {name}")

    artifact = strict_json_loads(
        (root / "acceptance.json").read_bytes(), name="acceptance artifact"
    )
    artifact = _require_exact_keys(
        artifact, {"payload", "sha256"}, "acceptance artifact"
    )
    payload = artifact["payload"]
    if _validate_digest(artifact["sha256"], "acceptance SHA256") != _sha256_bytes(
        _canonical_json(payload)
    ):
        raise ValueError("acceptance artifact SHA256 mismatch")
    if artifact != expected_artifact:
        raise ValueError("existing acceptance artifact does not match fresh result")
    required_payload = {
        "schema_version",
        "passed",
        "comparison_passed",
        "ablation_passed",
        "threshold",
        "effective_threshold",
        "binding_max_threshold",
        "threshold_semantics",
        "point_errors",
        "max_errors",
        "global_max_error",
        "ablation",
        "convergence_study",
        "tau",
        "input",
        "model",
        "solver_settings",
        "solver_provenance",
        "provenance",
    }
    payload = _require_exact_keys(payload, required_payload, "acceptance payload")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported acceptance schema version")
    for name in ("passed", "comparison_passed", "ablation_passed"):
        if type(payload[name]) is not bool:
            raise TypeError(f"acceptance {name} must be boolean")
    if payload["passed"] != (
        payload["comparison_passed"] and payload["ablation_passed"]
    ):
        raise ValueError("acceptance pass flags are inconsistent")
    if payload["convergence_study"] != convergence_study_record():
        raise ValueError("acceptance convergence study is stale")
    provenance = _require_exact_keys(
        payload["provenance"],
        {
            "module",
            "module_version",
            "python_version",
            "numpy_version",
            "ed_module_version",
            "bath_module_version",
        },
        "acceptance provenance",
    )
    expected_module_provenance = {
        "module": "acceptance",
        "module_version": MODULE_VERSION,
        "python_version": platform.python_version(),
        "numpy_version": bath.np.__version__,
        "ed_module_version": ed.MODULE_VERSION,
        "bath_module_version": bath.MODULE_VERSION,
    }
    if provenance != expected_module_provenance:
        raise ValueError("acceptance module provenance is stale")

    bath_artifact = strict_json_loads(
        (root / "bath.json").read_bytes(), name="bath artifact"
    )
    bath.verify_bath_artifact(bath_artifact)
    oracle = strict_json_loads(
        (root / "ed-oracle.json").read_bytes(), name="ED oracle"
    )
    ed.verify_oracle_artifact(oracle)
    request = strict_json_loads(
        (root / "mps-input.json").read_bytes(), name="MPS request"
    )
    request = _require_exact_keys(request, {"payload_json", "sha256"}, "MPS request")
    request_payload_json = request["payload_json"]
    if not isinstance(request_payload_json, str):
        raise TypeError("MPS request payload_json must be a string")
    if _validate_digest(request["sha256"], "MPS request SHA256") != _sha256_bytes(
        request_payload_json.encode("utf-8")
    ):
        raise ValueError("MPS request payload SHA256 mismatch")
    request_payload = strict_json_loads(
        request_payload_json, name="MPS request payload"
    )
    request_payload = _require_exact_keys(
        request_payload,
        {
            "schema_version",
            "bath_artifact_json",
            "bath_artifact_file_sha256",
            "bath_geometry",
            "checkpoint",
            "model",
            "tau",
            "solver_settings",
        },
        "MPS request payload",
    )
    if request_payload["schema_version"] != RUNNER_SCHEMA_VERSION:
        raise ValueError("unsupported MPS request schema version")
    if request_payload["checkpoint"] != _checkpoint_request_identity():
        raise ValueError("MPS request checkpoint identity is stale")
    bath_bytes = (root / "bath.json").read_bytes()
    if request_payload["bath_artifact_json"].encode("utf-8") != bath_bytes:
        raise ValueError("MPS request embedded bath does not match bath.json")
    if request_payload["bath_artifact_file_sha256"] != _sha256_bytes(bath_bytes):
        raise ValueError("MPS request bath file SHA256 mismatch")
    representation, _mapping, mapping_sha256 = _request_geometry_identity(
        request_payload
    )
    expected_settings = _expected_output_settings(request_payload)

    solver_output = strict_json_loads(
        (root / "mps-result.json").read_bytes(), name="MPS result"
    )
    expected_solver_provenance = expected_runner_provenance(
        julia_project=Path(julia_project).resolve(strict=True),
        bath_file_sha256=request_payload["bath_artifact_file_sha256"],
        bath_representation=representation,
        chain_mapping_sha256=mapping_sha256,
        krylov_expansion_dim=request_payload["solver_settings"][
            "krylov_expansion_dim"
        ],
    )
    verify_mps_output(
        solver_output,
        expected_input_sha256=_sha256_file(root / "mps-input.json"),
        expected_input_payload_sha256=request["sha256"],
        expected_settings=expected_settings,
        expected_tau=request_payload["tau"],
        expected_provenance=expected_solver_provenance,
    )
    comparison = compare_observables(
        oracle, solver_output, threshold=payload["effective_threshold"]
    )
    for name in (
        "threshold",
        "threshold_semantics",
        "point_errors",
        "max_errors",
        "global_max_error",
    ):
        if payload[name] != comparison[name]:
            raise ValueError(f"acceptance comparison field mismatch: {name}")
    if payload["comparison_passed"] != comparison["passed"]:
        raise ValueError("acceptance comparison pass flag mismatch")
    if payload["tau"] != request_payload["tau"]:
        raise ValueError("acceptance tau does not match request")
    if payload["model"] != request_payload["model"]:
        raise ValueError("acceptance model does not match request")
    if payload["solver_settings"] != expected_settings:
        raise ValueError("acceptance solver settings do not match request")
    if payload["solver_provenance"] != solver_output["provenance"]:
        raise ValueError("acceptance solver provenance mismatch")
    input_links = _require_exact_keys(
        payload["input"],
        {
            "bath_sha256",
            "bath_artifact_file_sha256",
            "mps_input_sha256",
            "mps_input_payload_sha256",
            "ed_oracle_sha256",
            "mps_result_file_sha256",
        },
        "acceptance input links",
    )
    expected_links = {
        "bath_sha256": bath_artifact["sha256"],
        "bath_artifact_file_sha256": _sha256_file(root / "bath.json"),
        "mps_input_sha256": _sha256_file(root / "mps-input.json"),
        "mps_input_payload_sha256": request["sha256"],
        "ed_oracle_sha256": oracle["sha256"],
        "mps_result_file_sha256": _sha256_file(root / "mps-result.json"),
    }
    if input_links != expected_links:
        raise ValueError("acceptance artifact input hashes mismatch")

    completion = strict_json_loads(
        (root / "completion.json").read_bytes(), name="acceptance completion"
    )
    completion = _require_exact_keys(
        completion,
        {
            "schema_version",
            "run_id",
            "acceptance_sha256",
            "artifact_file_sha256",
            "completion_sha256",
        },
        "acceptance completion",
    )
    if completion["schema_version"] != 1:
        raise ValueError("unsupported acceptance completion schema")
    run_id = f"acceptance-{artifact['sha256'][:16]}"
    if (
        completion["run_id"] != run_id
        or completion["acceptance_sha256"] != artifact["sha256"]
    ):
        raise ValueError("acceptance completion identity mismatch")
    expected_file_hashes = {
        name: _sha256_file(root / name)
        for name in ACCEPTANCE_RUN_FILES
        if name != "completion.json"
    }
    if completion["artifact_file_sha256"] != expected_file_hashes:
        raise ValueError("acceptance completion file hashes mismatch")
    if _validate_digest(
        completion["completion_sha256"], "completion SHA256"
    ) != _completion_sha256(completion):
        raise ValueError("acceptance completion SHA256 mismatch")
    return completion


def publish_acceptance_run(
    staging: Path,
    output_root: Path,
    artifact: dict[str, Any],
    *,
    julia_project: str | os.PathLike[str],
) -> Path:
    """Publish an immutable run, then atomically advance its current pointer."""

    root = output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    digest = _validate_digest(artifact.get("sha256"), "acceptance SHA256")
    run_id = f"acceptance-{digest[:16]}"
    runs = root / "runs"
    runs.mkdir(exist_ok=True)
    destination = runs / run_id
    staging = staging.resolve()
    if staging.parent != root or not staging.is_dir() or staging.is_symlink():
        raise ValueError("acceptance staging must be a real child directory")
    completion = {
        "schema_version": 1,
        "run_id": run_id,
        "acceptance_sha256": digest,
        "artifact_file_sha256": {
            name: _sha256_file(staging / name)
            for name in ACCEPTANCE_RUN_FILES
            if name != "completion.json"
        },
    }
    completion["completion_sha256"] = _completion_sha256(completion)
    pointer = {
        "schema_version": 1,
        "run_id": run_id,
        "acceptance_sha256": digest,
        "completion_sha256": completion["completion_sha256"],
        "relative_path": f"runs/{run_id}",
    }
    atomic_write_json(staging / "completion.json", completion)
    _fsync_directory(staging)
    if destination.exists() or destination.is_symlink():
        existing_completion = validate_acceptance_run(
            destination,
            expected_artifact=artifact,
            julia_project=julia_project,
        )
        if existing_completion != completion:
            raise ValueError(
                "immutable acceptance run already exists with different content"
            )
        archived = _unused_sibling_path(
            root, ".acceptance.abandoned-stage-"
        )
        os.replace(staging, archived)
        _fsync_directory(root)
    else:
        validate_acceptance_run(
            staging,
            expected_artifact=artifact,
            julia_project=julia_project,
        )
        os.replace(staging, destination)
        _fsync_directory(runs)
    atomic_write_json(
        root / "current.json",
        pointer,
    )
    _fsync_directory(root)
    return destination


def recover_acceptance_state(output_root: Path) -> list[Path]:
    """Archive stages left by SIGKILL-equivalent termination."""

    root = output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    recovered = []
    for path in root.glob(".acceptance.stage-*"):
        archived = _unused_sibling_path(
            root, ".acceptance.abandoned-stage-"
        )
        os.replace(path, archived)
        recovered.append(archived)
    if recovered:
        _fsync_directory(root)
    return recovered


def resolve_julia(configured: str | os.PathLike[str] | None) -> Path:
    candidate = (
        os.fspath(configured)
        if configured is not None
        else os.environ.get("JULIA") or shutil.which("julia")
    )
    if candidate is None:
        raise FileNotFoundError(
            "Julia was not found; set JULIA or pass --julia with an executable path"
        )
    path = Path(candidate).expanduser().resolve(strict=True)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError(f"Julia executable is not executable: {path}")
    return path


def invoke_julia_runner(command: Sequence[str], *, output_path: Path) -> None:
    if output_path.exists() or output_path.is_symlink():
        raise ValueError("refusing pre-existing Julia output as stale")
    subprocess.run(list(command), cwd=SOLUTION_DIR, check=True)
    if not output_path.is_file() or output_path.is_symlink():
        raise ValueError("Julia runner exited successfully but did not create output")


def _numeric_list(value: Any, length: int, name: str) -> list[float]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{name} must be a list of length {length}")
    return [_validate_real(item, f"{name} values") for item in value]


def expected_runner_provenance(
    *,
    julia_project: Path,
    bath_file_sha256: str,
    krylov_expansion_dim: int,
    bath_representation: str = "direct_star",
    chain_mapping_sha256: str | None = None,
) -> dict[str, Any]:
    project = (julia_project / "Project.toml").resolve(strict=True)
    manifest = (julia_project / "Manifest.toml").resolve(strict=True)
    return {
        "active_project_path": str(project),
        "manifest_path": str(manifest),
        "project_toml_sha256": _sha256_file(project),
        "manifest_toml_sha256": _sha256_file(manifest),
        "runner_source_sha256": _sha256_file(JULIA_RUNNER),
        "checkpoint_source_sha256": _sha256_file(JULIA_CHECKPOINT),
        "purification_source_sha256": _sha256_file(JULIA_PURIFICATION),
        "observables_source_sha256": _sha256_file(JULIA_OBSERVABLES),
        "model_definition_sha256": _sha256_file(MODEL_DEFINITION),
        "chain_mapping_source_sha256": _sha256_file(CHAIN_MAPPING_SOURCE),
        "bath_artifact_file_sha256": bath_file_sha256,
        "bath_representation": bath_representation,
        "chain_mapping_sha256": chain_mapping_sha256,
        "krylov_expansion_dim": krylov_expansion_dim,
        "expansion_policy": (
            "tdvp_only"
            if krylov_expansion_dim == 0
            else "explicit_global_krylov"
        ),
    }


def verify_mps_output(
    output: Any,
    *,
    expected_input_sha256: str,
    expected_input_payload_sha256: str,
    expected_settings: dict[str, Any],
    expected_tau: Sequence[float],
    expected_provenance: dict[str, Any],
) -> None:
    """Validate result schema, finite values, and all provenance bindings."""

    output = _require_exact_keys(
        output,
        {
            "schema_version",
            "input_sha256",
            "input_payload_sha256",
            "solver",
            "tau",
            "observables",
            "diagnostics",
            "provenance",
        },
        "MPS output",
    )
    if (
        type(output["schema_version"]) is not int
        or output["schema_version"] != RUNNER_SCHEMA_VERSION
    ):
        raise ValueError("unsupported MPS output schema version")
    if _validate_digest(output["input_sha256"], "MPS input SHA256") != (
        expected_input_sha256
    ):
        raise ValueError("MPS input SHA256 does not match the current request")
    if _validate_digest(
        output["input_payload_sha256"], "MPS input payload SHA256"
    ) != expected_input_payload_sha256:
        raise ValueError("MPS input payload SHA256 does not match the request")

    solver = _require_exact_keys(output["solver"], {"name", "settings"}, "solver")
    if solver["name"] != "finite_bath_mps":
        raise ValueError("unsupported MPS solver")
    settings = _require_exact_keys(
        solver["settings"],
        {
            "time_step",
            "cutoff",
            "maxdim",
            "krylov_expansion_dim",
            "bath_representation",
            "chain_mapping_sha256",
        },
        "solver settings",
    )
    if (
        _validate_real(settings["time_step"], "time_step")
        != expected_settings["time_step"]
        or _validate_real(settings["cutoff"], "cutoff")
        != expected_settings["cutoff"]
        or type(settings["maxdim"]) is not int
        or settings["maxdim"] != expected_settings["maxdim"]
        or type(settings["krylov_expansion_dim"]) is not int
        or settings["krylov_expansion_dim"]
        != expected_settings["krylov_expansion_dim"]
        or settings["bath_representation"]
        != expected_settings["bath_representation"]
        or settings["chain_mapping_sha256"]
        != expected_settings["chain_mapping_sha256"]
    ):
        raise ValueError("MPS solver settings do not match the request")

    tau = _numeric_list(output["tau"], len(expected_tau), "MPS tau")
    if tau != list(expected_tau):
        raise ValueError("MPS tau does not match the request")
    observables = _require_exact_keys(
        output["observables"],
        {"n_d", "double_occupancy", "G_up", "G_down"},
        "MPS observables",
    )
    _validate_real(observables["n_d"], "MPS n_d")
    _validate_real(observables["double_occupancy"], "MPS double occupancy")
    _numeric_list(observables["G_up"], len(tau), "MPS G_up")
    _numeric_list(observables["G_down"], len(tau), "MPS G_down")

    required_provenance = {
        "runner",
        "runner_version",
        "julia_version",
        "itensors_version",
        "itensormps_version",
        *expected_provenance.keys(),
    }
    provenance = _require_exact_keys(
        output["provenance"], required_provenance, "MPS provenance"
    )
    if provenance["runner"] != "finite_bath_mps_runner":
        raise ValueError("MPS provenance runner is malformed")
    for name in (
        "runner_version",
        "julia_version",
        "itensors_version",
        "itensormps_version",
    ):
        if not isinstance(provenance[name], str) or not provenance[name]:
            raise ValueError(f"MPS provenance {name} is malformed")
    for name, expected in expected_provenance.items():
        actual = provenance[name]
        if name.endswith("_sha256") and actual is not None:
            _validate_digest(actual, f"MPS provenance {name}")
        if actual != expected:
            raise ValueError(
                f"MPS provenance {name} mismatch: {actual!r} != {expected!r}"
            )
    if not isinstance(output["diagnostics"], dict):
        raise TypeError("MPS diagnostics must be a JSON object")
    if (
        output["diagnostics"].get("krylov_expansion_dim")
        != expected_settings["krylov_expansion_dim"]
    ):
        raise ValueError("MPS diagnostics expansion setting does not match request")
    if (
        output["diagnostics"].get("bath_representation")
        != expected_settings["bath_representation"]
        or output["diagnostics"].get("chain_mapping_sha256")
        != expected_settings["chain_mapping_sha256"]
    ):
        raise ValueError("MPS diagnostics bath geometry does not match request")
    _validate_finite_tree(output, "MPS output")


def compare_observables(
    oracle_artifact: dict[str, Any],
    mps_output: dict[str, Any],
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    threshold = _validate_acceptance_threshold(threshold)
    oracle_observables = oracle_artifact["payload"]["observables"]
    mps_observables = mps_output["observables"]
    oracle_values = {
        "n_d": [oracle_observables["occupancy"]["total"]],
        "double_occupancy": [oracle_observables["double_occupancy"]],
        "G_up": oracle_observables["green_function"]["up"],
        "G_down": oracle_observables["green_function"]["down"],
    }
    mps_values = {
        "n_d": [mps_observables["n_d"]],
        "double_occupancy": [mps_observables["double_occupancy"]],
        "G_up": mps_observables["G_up"],
        "G_down": mps_observables["G_down"],
    }
    point_errors: dict[str, list[float]] = {}
    max_errors: dict[str, float] = {}
    for name in ("n_d", "double_occupancy", "G_up", "G_down"):
        if len(oracle_values[name]) != len(mps_values[name]):
            raise ValueError(f"{name} lengths do not match")
        errors = [
            abs(_validate_real(actual, name) - _validate_real(reference, name))
            for reference, actual in zip(oracle_values[name], mps_values[name])
        ]
        point_errors[name] = errors
        max_errors[name] = max(errors)
    global_max_error = max(max_errors.values())
    return {
        "threshold": threshold,
        "threshold_semantics": "every compared scalar error <= threshold",
        "point_errors": point_errors,
        "max_errors": max_errors,
        "global_max_error": global_max_error,
        "passed": all(value <= threshold for value in max_errors.values()),
    }


def _artifact(payload: dict[str, Any]) -> dict[str, Any]:
    _validate_finite_tree(payload, "artifact payload")
    return {"payload": payload, "sha256": _sha256_bytes(_canonical_json(payload))}


def acceptance_fixture() -> dict[str, Any]:
    parameters = bath.MODEL_DEFINITION["parameters"]
    return {
        "bath": {
            "gamma": parameters["Gamma"],
            "bandwidth": parameters["D"],
            "n_bath": 2,
        },
        "model": {
            "U": parameters["U"],
            "epsilon_d": parameters["epsilon_d"],
            "mu": parameters["mu"],
            "beta": 0.5,
        },
        "tau": [0.0, 0.125, 0.25, 0.375, 0.5],
        "solver_settings": {
            "time_step": 0.02,
            "cutoff": 1.0e-14,
            "maxdim": 128,
            "krylov_expansion_dim": 32,
            "bath_representation": "direct_star",
        },
    }


def _explicit_chain_fixture(
    chain_mapping_artifact_bytes: bytes,
) -> dict[str, Any]:
    """Return the focused-test fixture for an explicitly mapped finite chain."""

    if not isinstance(chain_mapping_artifact_bytes, bytes):
        raise TypeError("chain mapping artifact must be supplied as bytes")
    fixture = acceptance_fixture()
    fixture["solver_settings"]["bath_representation"] = "chain"
    fixture["chain_mapping_artifact_bytes"] = chain_mapping_artifact_bytes
    return fixture


def convergence_study_record() -> dict[str, Any]:
    """Deterministic record of the controlled beta=0.5 acceptance study."""

    return {
        "fixture_beta": 0.5,
        "fixture_tau": [0.0, 0.125, 0.25, 0.375, 0.5],
        "controlled_runs": {
            "time_step": [
                {
                    "time_step": 0.01,
                    "global_max_error": 2.621836803884392e-6,
                },
                {
                    "time_step": 0.02,
                    "global_max_error": 4.631353420214701e-8,
                },
            ],
            "cutoff": [
                {
                    "cutoff": 1.0e-12,
                    "global_max_error": 2.970672798419116e-5,
                },
                {
                    "cutoff": 1.0e-14,
                    "global_max_error": 4.631353420214701e-8,
                },
            ],
            "maxdim": [
                {"maxdim": 128, "global_max_error": 4.631353420214701e-8},
                {"maxdim": 256, "global_max_error": 4.631353420214701e-8},
            ],
            "krylov_expansion_dim": [
                {
                    "krylov_expansion_dim": 24,
                    "global_max_error": 1.9892100094898169e-7,
                },
                {
                    "krylov_expansion_dim": 32,
                    "global_max_error": 4.631353420214701e-8,
                },
            ],
        },
        "observed_nonmonotonic": True,
        "conclusion": (
            "For this beta=0.5 fixture, time_step=0.02 outperformed 0.01; "
            "the selected settings are empirical and not a monotonic "
            "time-step extrapolation."
        ),
        "scope_limitation": (
            "beta=16 and beta=32 production claims require a dedicated "
            "convergence investigation and are not justified by this "
            "beta=0.5 acceptance study."
        ),
    }


def _checkpoint_request_identity() -> dict[str, Any]:
    return {
        "checkpoint_schema": CHECKPOINT_SCHEMA_VERSION,
        "writer_version": CHECKPOINT_WRITER_VERSION,
        "source_hashes": {
            "chain_mapping": _sha256_file(CHAIN_MAPPING_SOURCE),
            "checkpoint": _sha256_file(JULIA_CHECKPOINT),
            "model_definition": _sha256_file(MODEL_DEFINITION),
            "observables": _sha256_file(JULIA_OBSERVABLES),
            "purification": _sha256_file(JULIA_PURIFICATION),
            "runner": _sha256_file(JULIA_RUNNER),
        },
        "project_toml_sha256": _sha256_file(JULIA_DIR / "Project.toml"),
        "manifest_toml_sha256": _sha256_file(JULIA_DIR / "Manifest.toml"),
    }


def _make_mps_request(
    bath_json: str, fixture: dict[str, Any]
) -> dict[str, Any]:
    fixture_settings = copy.deepcopy(fixture["solver_settings"])
    numerical_setting_keys = {
        "time_step",
        "cutoff",
        "maxdim",
        "krylov_expansion_dim",
    }
    if not isinstance(fixture_settings, dict):
        raise TypeError("acceptance fixture solver settings must be an object")
    if set(fixture_settings) == numerical_setting_keys:
        representation = "direct_star"
    elif set(fixture_settings) == numerical_setting_keys | {
        "bath_representation"
    }:
        representation = fixture_settings.pop("bath_representation")
    else:
        _require_exact_keys(
            fixture_settings,
            numerical_setting_keys | {"bath_representation"},
            "acceptance fixture solver settings",
        )
        raise AssertionError("unreachable fixture settings validation")
    mapping_bytes = fixture.get("chain_mapping_artifact_bytes")
    if representation == "direct_star":
        if mapping_bytes is not None:
            raise ValueError(
                "direct_star representation cannot consume a chain mapping"
            )
        geometry = {
            "representation": "direct_star",
            "chain_mapping_artifact_json": None,
            "chain_mapping_artifact_file_sha256": None,
        }
    elif representation == "chain":
        if not isinstance(mapping_bytes, bytes):
            raise TypeError("chain representation requires mapping bytes")
        try:
            mapping_json = mapping_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("chain mapping bytes are not UTF-8") from error
        mapping = strict_json_loads(
            mapping_bytes, name="chain mapping artifact"
        )
        if mapping_bytes != _canonical_json(mapping) + b"\n":
            raise ValueError("chain mapping artifact bytes are not canonical")
        bath_artifact = strict_json_loads(bath_json, name="bath artifact")
        chain.verify_chain_mapping_artifact(mapping, bath_artifact)
        geometry = {
            "representation": "chain",
            "chain_mapping_artifact_json": mapping_json,
            "chain_mapping_artifact_file_sha256": _sha256_bytes(mapping_bytes),
        }
    else:
        raise ValueError(
            "bath representation must be direct_star or chain"
        )
    payload = {
        "schema_version": RUNNER_SCHEMA_VERSION,
        "bath_artifact_json": bath_json,
        "bath_artifact_file_sha256": _sha256_bytes(bath_json.encode("utf-8")),
        "bath_geometry": geometry,
        "checkpoint": _checkpoint_request_identity(),
        "model": copy.deepcopy(fixture["model"]),
        "tau": copy.deepcopy(fixture["tau"]),
        "solver_settings": fixture_settings,
    }
    payload_json = _request_canonical_json(payload)
    return {
        "payload_json": payload_json.decode("utf-8"),
        "sha256": _sha256_bytes(payload_json),
    }


def _ablation_variant(
    baseline: dict[str, Any],
    changed: dict[str, Any],
    tau: Sequence[float],
    beta: float,
) -> dict[str, Any]:
    point_changes = {
        "n_d": [
            abs(
                baseline["occupancy"]["total"]
                - changed["occupancy"]["total"]
            )
        ],
        "double_occupancy": [
            abs(
                baseline["double_occupancy"]
                - changed["double_occupancy"]
            )
        ],
        "G_up": [
            abs(left - right)
            for left, right in zip(
                baseline["green_function"]["up"],
                changed["green_function"]["up"],
            )
        ],
        "G_down": [
            abs(left - right)
            for left, right in zip(
                baseline["green_function"]["down"],
                changed["green_function"]["down"],
            )
        ],
    }
    interior_indices = [
        index for index, point in enumerate(tau) if 0.0 < point < beta
    ]
    interior_green = {
        name: max(point_changes[name][index] for index in interior_indices)
        for name in ("G_up", "G_down")
    }
    signal = max(interior_green.values())
    return {
        "point_changes": point_changes,
        "max_changes": {
            name: max(changes) for name, changes in point_changes.items()
        },
        "interior_green_max_changes": interior_green,
        "interior_green_signal": signal,
        "passed": signal > INTERIOR_GREEN_SIGNAL_MARGIN,
    }


def compute_ablation_signals(fixture: dict[str, Any]) -> dict[str, float]:
    bath_config = fixture["bath"]
    base_artifact = bath.make_bath_artifact(
        **bath_config, frequency_grid=[-1.0, 0.0, 1.0]
    )
    payload = base_artifact["payload"]
    model = fixture["model"]
    common = {
        "U": model["U"],
        "epsilon_d": model["epsilon_d"],
        "mu": model["mu"],
        "beta": model["beta"],
        "tau": fixture["tau"],
        "max_dimension": ed.MAX_DENSE_DIMENSION,
        "max_dense_bytes": ed.MAX_DENSE_BYTES,
    }
    baseline = ed.solve_finite_bath(bath_artifact=base_artifact, **common)
    consumed = {
        "epsilon": payload["epsilon"],
        "V": payload["V"],
        "n_bath": payload["parameters"]["n_bath"],
    }
    zero_v = ed._solve_consumed_bath(
        consumed_bath={**consumed, "V": [0.0] * consumed["n_bath"]},
        **common,
    )
    shifted_epsilon = [value + 0.17 for value in consumed["epsilon"]]
    changed_epsilon = ed._solve_consumed_bath(
        consumed_bath={**consumed, "epsilon": shifted_epsilon},
        **common,
    )
    variants = {
        "V_zero": _ablation_variant(
            baseline, zero_v, fixture["tau"], model["beta"]
        ),
        "changed_epsilon": _ablation_variant(
            baseline, changed_epsilon, fixture["tau"], model["beta"]
        ),
    }
    return {
        "interior_green_safety_margin": INTERIOR_GREEN_SIGNAL_MARGIN,
        **variants,
        "passed": all(variant["passed"] for variant in variants.values()),
    }


def run_acceptance(
    *,
    output_directory: str | os.PathLike[str] = DEFAULT_OUTPUT_DIRECTORY,
    julia_executable: str | os.PathLike[str] | None = None,
    julia_project: str | os.PathLike[str] = JULIA_DIR,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """Build, validate, and transactionally publish one complete acceptance tree."""

    started = time.monotonic()
    threshold = _validate_acceptance_threshold(threshold)
    destination = Path(output_directory).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    recover_acceptance_state(destination)
    julia = resolve_julia(julia_executable)
    project = Path(julia_project).resolve(strict=True)
    if not (project / "Project.toml").is_file() or not (
        project / "Manifest.toml"
    ).is_file():
        raise ValueError("Julia project must contain Project.toml and Manifest.toml")

    staging = Path(
        tempfile.mkdtemp(
            dir=destination, prefix=".acceptance.stage-"
        )
    )
    fixture = acceptance_fixture()
    try:
        bath_path = staging / "bath.json"
        oracle_path = staging / "ed-oracle.json"
        input_path = staging / "mps-input.json"
        mps_path = staging / "mps-result.json"
        checkpoint_root = staging / ".mps-checkpoint"
        acceptance_path = staging / "acceptance.json"

        print("Building shared two-site bath in unique staging tree", flush=True)
        bath_artifact = bath.write_bath_json(
            bath_path,
            **fixture["bath"],
            frequency_grid=[-1.0, -0.5, 0.0, 0.5, 1.0],
        )
        bath_json = bath_path.read_text(encoding="utf-8")
        parsed_bath = strict_json_loads(bath_json, name="bath artifact")
        bath.verify_bath_artifact(parsed_bath)
        if parsed_bath != bath_artifact:
            raise ValueError("bath artifact changed during serialization")

        request = _make_mps_request(bath_json, fixture)
        atomic_write_json(input_path, request)
        parsed_request = strict_json_loads(
            input_path.read_text(encoding="utf-8"), name="MPS request"
        )
        if parsed_request != request:
            raise ValueError("MPS request changed during serialization")
        input_bytes = input_path.read_bytes()
        input_sha256 = _sha256_bytes(input_bytes)
        request_payload = strict_json_loads(
            request["payload_json"], name="MPS request payload"
        )
        model = request_payload["model"]
        tau = request_payload["tau"]
        request_settings = request_payload["solver_settings"]
        representation, mapping_artifact, mapping_sha256 = (
            _request_geometry_identity(request_payload)
        )
        settings = _expected_output_settings(request_payload)

        print("Computing independent dense-ED oracle", flush=True)
        written_oracle = ed.write_oracle_json(
            oracle_path,
            bath_artifact=parsed_bath,
            U=model["U"],
            epsilon_d=model["epsilon_d"],
            mu=model["mu"],
            beta=model["beta"],
            tau=tau,
            bath_representation=representation,
            chain_mapping_artifact=mapping_artifact,
        )
        oracle_artifact = strict_json_loads(
            oracle_path.read_text(encoding="utf-8"), name="ED oracle"
        )
        if oracle_artifact != written_oracle:
            raise ValueError("ED oracle changed during serialization")
        ed.verify_oracle_artifact(oracle_artifact)

        expected_provenance = expected_runner_provenance(
            julia_project=project,
            bath_file_sha256=request_payload["bath_artifact_file_sha256"],
            bath_representation=representation,
            chain_mapping_sha256=mapping_sha256,
            krylov_expansion_dim=request_settings["krylov_expansion_dim"],
        )
        command = [
            str(julia),
            f"--project={project}",
            str(JULIA_RUNNER),
            str(input_path),
            str(mps_path),
            str(checkpoint_root),
        ]
        print("Invoking Julia finite-bath MPS runner", flush=True)
        invoke_julia_runner(command, output_path=mps_path)
        shutil.rmtree(checkpoint_root, ignore_errors=True)
        mps_output = strict_json_loads(
            mps_path.read_text(encoding="utf-8"), name="Julia MPS output"
        )
        verify_mps_output(
            mps_output,
            expected_input_sha256=input_sha256,
            expected_input_payload_sha256=request["sha256"],
            expected_settings=settings,
            expected_tau=tau,
            expected_provenance=expected_provenance,
        )
        comparison = compare_observables(
            oracle_artifact, mps_output, threshold=threshold
        )
        ablation = compute_ablation_signals(fixture)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "passed": comparison["passed"] and ablation["passed"],
            "comparison_passed": comparison["passed"],
            "ablation_passed": ablation["passed"],
            "threshold": comparison["threshold"],
            "effective_threshold": comparison["threshold"],
            "binding_max_threshold": DEFAULT_THRESHOLD,
            "threshold_semantics": comparison["threshold_semantics"],
            "point_errors": comparison["point_errors"],
            "max_errors": comparison["max_errors"],
            "global_max_error": comparison["global_max_error"],
            "ablation": ablation,
            "convergence_study": convergence_study_record(),
            "tau": copy.deepcopy(tau),
            "input": {
                "bath_sha256": bath_artifact["sha256"],
                "bath_artifact_file_sha256": request_payload[
                    "bath_artifact_file_sha256"
                ],
                "mps_input_sha256": input_sha256,
                "mps_input_payload_sha256": request["sha256"],
                "ed_oracle_sha256": oracle_artifact["sha256"],
                "mps_result_file_sha256": _sha256_file(mps_path),
            },
            "model": copy.deepcopy(model),
            "solver_settings": copy.deepcopy(settings),
            "solver_provenance": copy.deepcopy(mps_output["provenance"]),
            "provenance": {
                "module": "acceptance",
                "module_version": MODULE_VERSION,
                "python_version": platform.python_version(),
                "numpy_version": bath.np.__version__,
                "ed_module_version": ed.MODULE_VERSION,
                "bath_module_version": bath.MODULE_VERSION,
            },
        }
        artifact = _artifact(payload)
        atomic_write_json(acceptance_path, artifact)
        strict_json_loads(
            acceptance_path.read_text(encoding="utf-8"),
            name="acceptance artifact",
        )
        published = publish_acceptance_run(
            staging,
            destination,
            artifact,
            julia_project=project,
        )

        runtime_seconds = time.monotonic() - started
        print(
            f"Acceptance passed={payload['passed']} "
            f"global_max_error={payload['global_max_error']:.3e}",
            flush=True,
        )
        paths = {
            name: published / filename
            for name, filename in (
                ("bath", "bath.json"),
                ("oracle", "ed-oracle.json"),
                ("mps_input", "mps-input.json"),
                ("mps_result", "mps-result.json"),
                ("acceptance", "acceptance.json"),
            )
        }
        return {
            "artifact": artifact,
            "runtime_seconds": runtime_seconds,
            "command": command,
            "paths": paths,
        }
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--julia",
        type=Path,
        default=None,
        help="Julia executable; defaults to JULIA then PATH",
    )
    parser.add_argument("--julia-project", type=Path, default=JULIA_DIR)
    parser.add_argument(
        "--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    arguments = parser.parse_args(argv)
    result = run_acceptance(
        output_directory=arguments.output_directory,
        julia_executable=arguments.julia,
        julia_project=arguments.julia_project,
        threshold=arguments.threshold,
    )
    return 0 if result["artifact"]["payload"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
