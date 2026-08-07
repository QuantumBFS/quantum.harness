from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import stat
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from .acceptance import validate_qmc_adapter_output_descriptor
from .extension import validate_directed_extension_plan
from .planning import _write_immutable, validate_plan
from .provenance import canonical_json
from .statistics import jackknife_binder


_STAGE = "QMC_SSE coarse localization"
_SIZE_PAIRS = ((4, 6), (6, 8))
_REFINEMENT_LENGTHS = [8, 12, 16, 20]
_HEX = frozenset("0123456789abcdef")
_COMPLETION_KEYS = {
    "schema_version",
    "cell_id",
    "cell_index",
    "plan_sha256",
    "request_sha256",
    "graph_sha256",
    "build_info_sha256",
    "executable_sha256",
    "current_generation_sha256",
    "semantic_snapshot_sha256",
    "log_sha256",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _finite_vector(values: object, label: str) -> npt.NDArray[np.float64]:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1 or result.size < 2 or not np.all(np.isfinite(result)):
        raise ValueError(f"{label} must be a finite one-dimensional vector")
    return result


def binder_summary(
    m2_bin_means: npt.ArrayLike,
    m4_bin_means: npt.ArrayLike,
) -> dict[str, Any]:
    """Jackknife the ratio of aggregate primitive moments.

    The paired arrays stay paired through every delete-one-bin replicate, so
    their covariance is retained. Per-bin Binder ratios are never averaged.
    """

    return jackknife_binder(
        _finite_vector(m2_bin_means, "m2 bin means"),
        _finite_vector(m4_bin_means, "m4 bin means"),
    )


jackknife_binder_summary = binder_summary


def bootstrap_binder_chains(
    chains: Sequence[tuple[npt.ArrayLike, npt.ArrayLike]],
    *,
    replicates: int,
    seed: int,
) -> npt.NDArray[np.float64]:
    """Bootstrap whole chains, preserving all bins and paired moments."""

    if (
        not isinstance(replicates, int)
        or isinstance(replicates, bool)
        or replicates < 2
    ):
        raise ValueError("bootstrap replicates must be an integer of at least two")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("bootstrap seed must be a non-negative integer")
    if len(chains) < 2:
        raise ValueError("complete-chain bootstrap requires at least two chains")

    validated: list[tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]] = []
    bin_count: int | None = None
    for m2_values, m4_values in chains:
        m2 = _finite_vector(m2_values, "chain m2")
        m4 = _finite_vector(m4_values, "chain m4")
        if m2.shape != m4.shape or np.any(m4 <= 0.0):
            raise ValueError("each chain requires paired positive primitive moments")
        if bin_count is None:
            bin_count = m2.size
        elif m2.size != bin_count:
            raise ValueError("all complete chains must contain the same number of bins")
        validated.append((m2, m4))

    rng = np.random.default_rng(seed)
    samples = np.empty(replicates, dtype=np.float64)
    for replicate in range(replicates):
        selected = rng.integers(0, len(validated), size=len(validated))
        m2 = np.concatenate([validated[index][0] for index in selected])
        m4 = np.concatenate([validated[index][1] for index in selected])
        samples[replicate] = float(m2.mean() ** 2 / m4.mean())
    if not np.all(np.isfinite(samples)):
        raise ValueError("complete-chain bootstrap produced a non-finite Binder ratio")
    return samples


def find_sign_change_bracket(
    fields: Sequence[float],
    differences: Sequence[float],
) -> dict[str, float]:
    """Return the unique exact-grid sign-change bracket."""

    field_values = _finite_vector(fields, "fields")
    difference_values = _finite_vector(differences, "differences")
    if field_values.shape != difference_values.shape:
        raise ValueError("fields and differences must have the same shape")
    if np.any(np.diff(field_values) <= 0.0):
        raise ValueError("fields must be strictly increasing")

    zero_indices = np.flatnonzero(difference_values == 0.0)
    candidates: list[tuple[float, float]] = [
        (float(field_values[index]), float(field_values[index]))
        for index in zero_indices
    ]
    for index in range(field_values.size - 1):
        left = float(difference_values[index])
        right = float(difference_values[index + 1])
        if left * right < 0.0:
            candidates.append(
                (float(field_values[index]), float(field_values[index + 1]))
            )
    if not candidates:
        raise ValueError("no sign-change bracket on the coarse field grid")
    if len(candidates) != 1:
        raise ValueError("multiple sign-change brackets on the coarse field grid")
    lower, upper = candidates[0]
    return {"lower_field": lower, "upper_field": upper}


def compare_beta_ratios(
    brackets: Mapping[int, Mapping[str, float]],
) -> dict[str, Any]:
    if set(brackets) != {1, 2}:
        raise ValueError("beta-ratio comparison requires exactly ratios 1 and 2")
    normalized: dict[int, tuple[float, float]] = {}
    for ratio in (1, 2):
        bracket = brackets[ratio]
        try:
            lower = float(bracket["lower_field"])
            upper = float(bracket["upper_field"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("malformed beta-ratio bracket") from exc
        if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
            raise ValueError("malformed beta-ratio bracket")
        normalized[ratio] = (lower, upper)

    overlap_lower = max(normalized[1][0], normalized[2][0])
    overlap_upper = min(normalized[1][1], normalized[2][1])
    midpoint = {
        ratio: (bounds[0] + bounds[1]) / 2.0
        for ratio, bounds in normalized.items()
    }
    return {
        "beta_ratios": [1, 2],
        "consistent": overlap_lower <= overlap_upper,
        "overlap": (
            {"lower_field": overlap_lower, "upper_field": overlap_upper}
            if overlap_lower <= overlap_upper
            else None
        ),
        "midpoint_shift": midpoint[2] - midpoint[1],
    }


def _coordinate_seed(seed: int, coordinate: tuple[str, int, int, float]) -> int:
    material = {"bootstrap_seed": seed, "coordinate": list(coordinate)}
    return int.from_bytes(hashlib.sha256(canonical_json(material)).digest()[:8], "big")


def _validate_point(point: Mapping[str, Any]) -> tuple[
    tuple[str, int, int, float],
    list[tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]],
]:
    try:
        lattice = point["lattice"]
        beta_ratio = point["beta_ratio"]
        length = point["length"]
        field = float(point["field"])
        chain_values = point["chains"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("malformed coarse Binder point") from exc
    if (
        lattice not in {"triangular", "honeycomb"}
        or beta_ratio not in {1, 2}
        or length not in {4, 6, 8}
        or not math.isfinite(field)
        or field <= 0.0
        or not isinstance(chain_values, Sequence)
        or isinstance(chain_values, (str, bytes))
        or len(chain_values) != 2
    ):
        raise ValueError("coarse Binder point violates the frozen design")
    chains = []
    for chain in chain_values:
        if not isinstance(chain, Mapping):
            raise ValueError("malformed primitive-moment chain")
        m2 = _finite_vector(chain.get("m2"), "chain m2")
        m4 = _finite_vector(chain.get("m4"), "chain m4")
        if m2.shape != m4.shape or np.any(m4 <= 0.0):
            raise ValueError("primitive-moment chains must be paired with positive m4")
        chains.append((m2, m4))
    return (lattice, beta_ratio, length, field), chains


def _analyze_validated_grid(
    by_coordinate: Mapping[
        tuple[str, int, int, float],
        list[tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]],
    ],
    grouped_fields: Mapping[tuple[str, int, int], set[float]],
    *,
    plan_sha256: str,
    input_bindings: Sequence[Mapping[str, Any]],
    bootstrap_replicates: int,
    bootstrap_seed: int,
    extension_plan_sha256: str | None = None,
    crossing_fields: Mapping[tuple[str, int, int, int], set[float]] | None = None,
) -> dict[str, Any]:
    summaries: dict[tuple[str, int, int, float], dict[str, Any]] = {}
    bootstrap: dict[tuple[str, int, int, float], npt.NDArray[np.float64]] = {}
    for coordinate in sorted(by_coordinate):
        chains = by_coordinate[coordinate]
        m2 = np.concatenate([chain[0] for chain in chains])
        m4 = np.concatenate([chain[1] for chain in chains])
        summary = binder_summary(m2, m4)
        samples = bootstrap_binder_chains(
            chains,
            replicates=bootstrap_replicates,
            seed=_coordinate_seed(bootstrap_seed, coordinate),
        )
        summary["complete_chain_bootstrap_standard_error"] = float(
            samples.std(ddof=1)
        )
        summary.pop("leave_one_out")
        summaries[coordinate] = summary
        bootstrap[coordinate] = samples

    brackets: list[dict[str, Any]] = []
    bracket_lookup: dict[tuple[str, str], dict[int, dict[str, float]]] = defaultdict(dict)
    for lattice in ("triangular", "honeycomb"):
        for beta_ratio in (1, 2):
            for small, large in _SIZE_PAIRS:
                if crossing_fields is None:
                    small_fields = grouped_fields[(lattice, beta_ratio, small)]
                    large_fields = grouped_fields[(lattice, beta_ratio, large)]
                    if small_fields != large_fields:
                        raise ValueError(
                            "field grids must match within each crossing series"
                        )
                    fields = sorted(small_fields)
                else:
                    fields = sorted(
                        crossing_fields[(lattice, beta_ratio, small, large)]
                    )
                differences = [
                    summaries[(lattice, beta_ratio, small, field)]["mean"]
                    - summaries[(lattice, beta_ratio, large, field)]["mean"]
                    for field in fields
                ]
                bracket = find_sign_change_bracket(fields, differences)
                pair_name = f"{small}<->{large}"
                difference_bootstrap = [
                    bootstrap[(lattice, beta_ratio, small, field)]
                    - bootstrap[(lattice, beta_ratio, large, field)]
                    for field in fields
                ]
                bracket_support = np.mean(
                    [
                        any(
                            replicate_values[index]
                            * replicate_values[index + 1]
                            <= 0.0
                            for index in range(len(fields) - 1)
                        )
                        for replicate_values in zip(*difference_bootstrap, strict=True)
                    ]
                )
                entry = {
                    "lattice": lattice,
                    "beta_ratio": beta_ratio,
                    "size_pair": pair_name,
                    **bracket,
                    "binder_differences": [
                        {"field": field, "mean": float(difference)}
                        for field, difference in zip(fields, differences, strict=True)
                    ],
                    "complete_chain_bootstrap_bracket_support": float(bracket_support),
                }
                brackets.append(entry)
                bracket_lookup[(lattice, pair_name)][beta_ratio] = bracket

    comparisons = []
    for lattice in ("triangular", "honeycomb"):
        for small, large in _SIZE_PAIRS:
            pair_name = f"{small}<->{large}"
            comparisons.append(
                {
                    "lattice": lattice,
                    "size_pair": pair_name,
                    **compare_beta_ratios(bracket_lookup[(lattice, pair_name)]),
                }
            )

    windows = []
    for lattice in ("triangular", "honeycomb"):
        lattice_brackets = [item for item in brackets if item["lattice"] == lattice]
        windows.append(
            {
                "lattice": lattice,
                "lower_field": min(item["lower_field"] for item in lattice_brackets),
                "upper_field": max(item["upper_field"] for item in lattice_brackets),
                "source": "union of exact coarse 4<->6 and 6<->8 brackets",
            }
        )

    result: dict[str, Any] = {
        "schema_version": (
            "challenge148-directed-extension-fss-analysis-v1"
            if extension_plan_sha256 is not None
            else "challenge148-coarse-fss-analysis-v1"
        ),
        "stage": _STAGE,
        "plan_sha256": plan_sha256,
        "input_bindings": [dict(binding) for binding in input_bindings],
        "bootstrap": {
            "method": "complete-chain-resampling-v1",
            "replicates": bootstrap_replicates,
            "seed": bootstrap_seed,
        },
        "binder_estimator": "delete-one-analysis-bin-jackknife-pseudovalue-v1",
        "binder_summaries": [
            {
                "lattice": coordinate[0],
                "beta_ratio": coordinate[1],
                "length": coordinate[2],
                "field": coordinate[3],
                **summaries[coordinate],
            }
            for coordinate in sorted(summaries)
        ],
        "crossing_brackets": brackets,
        "beta_ratio_comparisons": comparisons,
        "refinement": {
            "schema_version": "challenge148-qmc-sse-refinement-v1",
            "source_stage": _STAGE,
            "lengths": list(_REFINEMENT_LENGTHS),
            "beta_ratios": [1, 2],
            "field_windows": windows,
            "interpretation": (
                "Refinement request only; this coarse localization is not a "
                "final two-code verdict."
            ),
        },
    }
    if extension_plan_sha256 is not None:
        result["extension_plan_sha256"] = extension_plan_sha256
    result["analysis_sha256"] = _sha256(canonical_json(result))
    return result


def analyze_coarse_points(
    points: Sequence[Mapping[str, Any]],
    *,
    plan_sha256: str,
    input_bindings: Sequence[Mapping[str, Any]],
    bootstrap_replicates: int = 4096,
    bootstrap_seed: int = 148,
) -> dict[str, Any]:
    """Analyze the frozen 36 coordinates formed by exactly 72 chains."""

    if len(plan_sha256) != 64 or any(character not in _HEX for character in plan_sha256):
        raise ValueError("plan_sha256 must be lowercase hexadecimal")
    if len(input_bindings) != 72:
        raise ValueError("analysis requires bindings for exactly 72 validated cells")

    by_coordinate: dict[
        tuple[str, int, int, float],
        list[tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]],
    ] = {}
    for point in points:
        if not isinstance(point, Mapping):
            raise ValueError("coarse points must be mappings")
        coordinate, chains = _validate_point(point)
        if coordinate in by_coordinate:
            raise ValueError("duplicate coarse Binder coordinate")
        by_coordinate[coordinate] = chains
    if len(by_coordinate) != 36:
        raise ValueError("analysis requires exactly 36 frozen Binder coordinates")

    expected_shape = {
        (lattice, beta_ratio, length)
        for lattice in ("triangular", "honeycomb")
        for beta_ratio in (1, 2)
        for length in (4, 6, 8)
    }
    grouped_fields: dict[tuple[str, int, int], set[float]] = defaultdict(set)
    for lattice, beta_ratio, length, field in by_coordinate:
        grouped_fields[(lattice, beta_ratio, length)].add(field)
    if set(grouped_fields) != expected_shape or any(
        len(fields) != 3 for fields in grouped_fields.values()
    ):
        raise ValueError("coarse points do not cover the frozen 2x2x3x3 design")
    for lattice in ("triangular", "honeycomb"):
        reference = grouped_fields[(lattice, 1, 4)]
        if any(
            grouped_fields[(lattice, ratio, length)] != reference
            for ratio in (1, 2)
            for length in (4, 6, 8)
        ):
            raise ValueError("field grids must match within each lattice")
    return _analyze_validated_grid(
        by_coordinate,
        grouped_fields,
        plan_sha256=plan_sha256,
        input_bindings=input_bindings,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
    )


def _read_canonical_json(path: Path, label: str, *, indented: bool = False) -> tuple[bytes, dict[str, Any]]:
    def reject_non_finite(token: str) -> None:
        raise ValueError(f"non-finite token {token}")

    try:
        metadata = path.lstat()
        payload = path.read_bytes()
        value = json.loads(payload, parse_constant=reject_non_finite)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid {label}") from exc
    if not stat.S_ISREG(metadata.st_mode) or not isinstance(value, dict):
        raise ValueError(f"{label} must be a regular JSON object")
    expected = (
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
        if indented
        else canonical_json(value) + b"\n"
    )
    if payload != expected:
        raise ValueError(f"{label} is not canonical newline-terminated JSON")
    return payload, value


def _relative_path(root: Path, parts: object, label: str) -> Path:
    if (
        not isinstance(parts, list)
        or any(
            not isinstance(part, str) or part in {"", ".", ".."} or "/" in part
            for part in parts
        )
    ):
        raise ValueError(f"{label} path is malformed")
    candidate = root.joinpath(*parts)
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise ValueError(f"{label} path is missing") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError(f"{label} path must not be a symlink")
    return candidate


def _validate_snapshot_manifest(
    output: Path,
    manifest: Mapping[str, Any],
    completion_payload: bytes,
) -> str:
    if set(manifest) != {
        "schema_version",
        "source_semantic_snapshot_sha256",
        "completion_sha256",
        "files",
        "enumerations",
        "tree",
    } or manifest["schema_version"] != "challenge148-completed-evidence-v1":
        raise ValueError("completed evidence manifest schema mismatch")
    if manifest["completion_sha256"] != _sha256(completion_payload):
        raise ValueError("completed evidence completion hash mismatch")
    files = manifest["files"]
    enumerations = manifest["enumerations"]
    tree = manifest["tree"]
    if not all(isinstance(value, list) for value in (files, enumerations, tree)):
        raise ValueError("completed evidence manifest collections are malformed")

    file_paths: set[tuple[str, ...]] = set()
    for entry in files:
        if not isinstance(entry, Mapping) or set(entry) != {"path", "sha256", "size"}:
            raise ValueError("completed evidence file entry is malformed")
        parts = tuple(entry["path"]) if isinstance(entry["path"], list) else ()
        if not parts or parts in file_paths:
            raise ValueError("completed evidence file paths must be unique")
        file_paths.add(parts)
        path = _relative_path(output, entry["path"], "completed evidence file")
        payload = path.read_bytes()
        if (
            not stat.S_ISREG(path.lstat().st_mode)
            or entry["size"] != len(payload)
            or entry["sha256"] != _sha256(payload)
        ):
            raise ValueError("completed evidence file hash mismatch")

    tree_paths: set[tuple[str, ...]] = set()
    tree_names: dict[tuple[str, ...], list[str]] = {}
    for entry in tree:
        if not isinstance(entry, Mapping) or set(entry) != {"path", "names"}:
            raise ValueError("completed evidence tree entry is malformed")
        path_parts = entry["path"]
        names = entry["names"]
        parts = tuple(path_parts) if isinstance(path_parts, list) else ()
        if (
            parts in tree_paths
            or not isinstance(names, list)
            or names != sorted(names)
            or len(names) != len(set(names))
        ):
            raise ValueError("completed evidence tree is malformed")
        tree_paths.add(parts)
        tree_names[parts] = names
        path = _relative_path(output, path_parts, "completed evidence directory")
        if not stat.S_ISDIR(path.lstat().st_mode) or sorted(os.listdir(path)) != names:
            raise ValueError("completed evidence tree membership mismatch")
    if () not in tree_paths:
        raise ValueError("completed evidence tree omits its output root")
    represented_paths = tree_paths | file_paths
    for directory, names in tree_names.items():
        represented_names = sorted(
            path[len(directory)]
            for path in represented_paths
            if len(path) == len(directory) + 1 and path[: len(directory)] == directory
        )
        if names != represented_names:
            raise ValueError("completed evidence manifest omits an output descendant")

    enumeration_paths: set[tuple[str, ...]] = set()
    for entry in enumerations:
        if not isinstance(entry, Mapping) or set(entry) != {"path", "names"}:
            raise ValueError("completed evidence enumeration is malformed")
        path_parts = entry["path"]
        names = entry["names"]
        parts = tuple(path_parts) if isinstance(path_parts, list) else ()
        if (
            parts in enumeration_paths
            or not isinstance(names, list)
            or names != sorted(names)
        ):
            raise ValueError("completed evidence enumeration is malformed")
        enumeration_paths.add(parts)
        path = _relative_path(output, path_parts, "completed evidence enumeration")
        if not stat.S_ISDIR(path.lstat().st_mode) or sorted(os.listdir(path)) != names:
            raise ValueError("completed evidence enumeration mismatch")

    semantic_material = {
        "files": [
            {"path": entry["path"], "sha256": entry["sha256"]} for entry in files
        ],
        "enumerations": list(enumerations),
    }
    semantic_sha256 = manifest["source_semantic_snapshot_sha256"]
    if semantic_sha256 != _sha256(canonical_json(semantic_material)):
        raise ValueError("completed evidence source semantic hash mismatch")
    return semantic_sha256


def _load_validated_cell(
    root: Path,
    plan: Mapping[str, Any],
    cell: Mapping[str, Any],
    cell_index: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cell_root = root / "cells" / cell["cell_id"]
    if not cell_root.is_dir() or stat.S_ISLNK(cell_root.lstat().st_mode):
        raise ValueError(f"cell root is not a real directory: {cell['cell_id']}")
    evidence_root = cell_root / "completed-evidence"
    if not evidence_root.is_dir() or stat.S_ISLNK(evidence_root.lstat().st_mode):
        raise ValueError(f"missing validated completion for {cell['cell_id']}")
    evidence_entries = list(evidence_root.iterdir())
    if len(evidence_entries) != 1:
        raise ValueError(f"ambiguous validated completion for {cell['cell_id']}")
    evidence = evidence_entries[0]
    evidence_metadata = evidence.lstat()
    if not stat.S_ISDIR(evidence_metadata.st_mode) or stat.S_ISLNK(evidence_metadata.st_mode):
        raise ValueError("completed evidence must be a real directory")
    if len(evidence.name) != 64 or any(character not in _HEX for character in evidence.name):
        raise ValueError("completed evidence content address is malformed")
    if sorted(path.name for path in evidence.iterdir()) != [
        "completion.json",
        "manifest.json",
        "output",
    ]:
        raise ValueError("completed evidence root membership mismatch")

    _, manifest = _read_canonical_json(
        evidence / "manifest.json", "completed evidence manifest"
    )
    if _sha256(canonical_json(manifest)) != evidence.name:
        raise ValueError("completed evidence manifest hash mismatch")
    completion_payload, completion = _read_canonical_json(
        evidence / "completion.json", "cell completion"
    )
    if set(completion) != _COMPLETION_KEYS:
        raise ValueError("cell completion closed schema mismatch")
    expected_completion = {
        "schema_version": "challenge148-production-cell-completion-v3",
        "cell_id": cell["cell_id"],
        "cell_index": cell_index,
        "plan_sha256": plan["plan_sha256"],
        "request_sha256": cell["request_sha256"],
        "graph_sha256": cell["graph_sha256"],
        "build_info_sha256": _sha256(canonical_json(plan["build_info"])),
    }
    if any(completion.get(key) != value for key, value in expected_completion.items()):
        raise ValueError("cell completion binding mismatch")
    hash_keys = {
        "executable_sha256",
        "current_generation_sha256",
        "semantic_snapshot_sha256",
    }
    if any(
        not isinstance(completion[key], str)
        or len(completion[key]) != 64
        or any(character not in _HEX for character in completion[key])
        for key in hash_keys
    ):
        raise ValueError("cell completion hash binding is malformed")
    log_hashes = completion["log_sha256"]
    if (
        not isinstance(log_hashes, list)
        or len(log_hashes) != 2
        or len(set(log_hashes)) != 2
    ):
        raise ValueError("cell completion log binding is malformed")
    for digest in log_hashes:
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in _HEX for character in digest)
        ):
            raise ValueError("cell completion log hash is malformed")
        log_payload, _ = _read_canonical_json(
            cell_root / "logs" / f"{digest}.json", "immutable subprocess log"
        )
        if _sha256(log_payload) != digest:
            raise ValueError("immutable subprocess log hash mismatch")

    output = evidence / "output"
    semantic_sha256 = _validate_snapshot_manifest(output, manifest, completion_payload)
    if completion["semantic_snapshot_sha256"] != semantic_sha256:
        raise ValueError("cell completion semantic binding mismatch")
    descriptor = os.open(
        output,
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        _, graph = _read_canonical_json(
            root / cell["graph_path"], "planned graph", indented=True
        )
        expected_graph = next(
            entry for entry in plan["graphs"] if entry["path"] == cell["graph_path"]
        )
        if graph != expected_graph["content"]:
            raise ValueError("planned graph artifact binding mismatch")
        validation = validate_qmc_adapter_output_descriptor(
            descriptor,
            cell["request"],
            "QMC_SSE",
            graph=graph,
            output_namespace=f"analysis:{evidence}",
            archival=True,
        )
    finally:
        os.close(descriptor)
    if completion["current_generation_sha256"] != _sha256(
        validation["current_generation_payload"]
    ):
        raise ValueError("validated cell current-generation binding mismatch")
    return validation["records"], {
        "cell_id": cell["cell_id"],
        "sha256": evidence.name,
        "completion_sha256": _sha256(completion_payload),
        "semantic_snapshot_sha256": semantic_sha256,
    }


def load_validated_production_root(
    production_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Load exactly 72 immutable, semantically validated QMC_SSE cells."""

    root = Path(production_root).resolve()
    if not root.is_dir() or stat.S_ISLNK(root.lstat().st_mode):
        raise ValueError("production root must be a real directory")
    _, plan = _read_canonical_json(root / "plan.json", "production plan", indented=True)
    validate_plan(plan)
    cells = plan["cells"]
    if len(cells) != 72:
        raise ValueError("production plan must contain exactly 72 cells")
    cells_root = root / "cells"
    if not cells_root.is_dir() or stat.S_ISLNK(cells_root.lstat().st_mode):
        raise ValueError("production cells root must be a real directory")
    expected_cell_ids = {cell["cell_id"] for cell in cells}
    if {path.name for path in cells_root.iterdir()} != expected_cell_ids:
        raise ValueError("production root must contain exactly the 72 planned cells")

    point_chains: dict[tuple[str, int, int, float], list[dict[str, Any]]] = defaultdict(list)
    bindings: list[dict[str, Any]] = []
    for cell_index, cell in enumerate(cells):
        records, binding = _load_validated_cell(root, plan, cell, cell_index)
        m2 = [record["m2_sum"] / record["sample_count"] for record in records]
        m4 = [record["m4_sum"] / record["sample_count"] for record in records]
        coordinate = (
            cell["lattice"],
            cell["beta_ratio"],
            cell["length"],
            float(cell["field"]),
        )
        point_chains[coordinate].append({"m2": m2, "m4": m4})
        bindings.append(binding)

    points = [
        {
            "lattice": coordinate[0],
            "beta_ratio": coordinate[1],
            "length": coordinate[2],
            "field": coordinate[3],
            "chains": chains,
        }
        for coordinate, chains in sorted(point_chains.items())
    ]
    return plan, points, bindings


def load_validated_extension_root(
    extension_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Load exactly 24 immutable, semantically validated directed cells."""

    root = Path(extension_root).resolve()
    if not root.is_dir() or stat.S_ISLNK(root.lstat().st_mode):
        raise ValueError("extension root must be a real directory")
    _, plan = _read_canonical_json(root / "plan.json", "extension plan", indented=True)
    validate_directed_extension_plan(plan)
    cells = plan["cells"]
    if len(cells) != 24:
        raise ValueError("extension plan must contain exactly 24 cells")
    cells_root = root / "cells"
    if not cells_root.is_dir() or stat.S_ISLNK(cells_root.lstat().st_mode):
        raise ValueError("extension cells root must be a real directory")
    expected_cell_ids = {cell["cell_id"] for cell in cells}
    if {path.name for path in cells_root.iterdir()} != expected_cell_ids:
        raise ValueError("extension root must contain exactly the 24 planned cells")

    point_chains: dict[tuple[str, int, int, float], list[dict[str, Any]]] = defaultdict(list)
    bindings: list[dict[str, Any]] = []
    for cell_index, cell in enumerate(cells):
        records, binding = _load_validated_cell(root, plan, cell, cell_index)
        m2 = [record["m2_sum"] / record["sample_count"] for record in records]
        m4 = [record["m4_sum"] / record["sample_count"] for record in records]
        coordinate = (
            cell["lattice"],
            cell["beta_ratio"],
            cell["length"],
            float(cell["field"]),
        )
        point_chains[coordinate].append({"m2": m2, "m4": m4})
        bindings.append(binding)

    points = [
        {
            "lattice": coordinate[0],
            "beta_ratio": coordinate[1],
            "length": coordinate[2],
            "field": coordinate[3],
            "chains": chains,
        }
        for coordinate, chains in sorted(point_chains.items())
    ]
    if len(points) != 12 or any(len(point["chains"]) != 2 for point in points):
        raise ValueError("extension evidence must form exactly 12 paired coordinates")
    return plan, points, bindings


def analyze_production_root(
    production_root: Path,
    *,
    bootstrap_replicates: int = 4096,
    bootstrap_seed: int = 148,
) -> dict[str, Any]:
    plan, points, bindings = load_validated_production_root(production_root)
    return analyze_coarse_points(
        points,
        plan_sha256=plan["plan_sha256"],
        input_bindings=bindings,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
    )


def analyze_extended_production_roots(
    base_root: Path,
    extension_root: Path,
    *,
    bootstrap_replicates: int = 4096,
    bootstrap_seed: int = 148,
) -> dict[str, Any]:
    """Analyze the closed merge of 72 base and 24 directed evidence cells."""

    base_plan, base_points, base_bindings = load_validated_production_root(base_root)
    extension_plan, extension_points, extension_bindings = (
        load_validated_extension_root(extension_root)
    )
    if len(base_bindings) != 72 or len(extension_bindings) != 24:
        raise ValueError("extended analysis requires exactly 96 evidence bindings")

    base_coordinates: dict[
        tuple[str, int, int, float],
        list[tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]],
    ] = {}
    extension_coordinates: dict[
        tuple[str, int, int, float],
        list[tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]],
    ] = {}
    for label, points, target in (
        ("base", base_points, base_coordinates),
        ("extension", extension_points, extension_coordinates),
    ):
        for point in points:
            if not isinstance(point, Mapping):
                raise ValueError(f"{label} points must be mappings")
            coordinate, chains = _validate_point(point)
            if coordinate in target:
                raise ValueError(f"duplicate {label} Binder coordinate")
            target[coordinate] = chains
    if len(base_coordinates) != 36:
        raise ValueError("base analysis requires exactly 36 frozen Binder coordinates")
    if len(extension_coordinates) != 12:
        raise ValueError("extension analysis requires exactly 12 directed coordinates")
    if set(base_coordinates) & set(extension_coordinates):
        raise ValueError("base and extension Binder coordinates overlap")

    expected_shape = {
        (lattice, beta_ratio, length)
        for lattice in ("triangular", "honeycomb")
        for beta_ratio in (1, 2)
        for length in (4, 6, 8)
    }
    base_fields: dict[tuple[str, int, int], set[float]] = defaultdict(set)
    for lattice, beta_ratio, length, field in base_coordinates:
        base_fields[(lattice, beta_ratio, length)].add(field)
    if set(base_fields) != expected_shape or any(
        len(fields) != 3 for fields in base_fields.values()
    ):
        raise ValueError("base points do not cover the frozen 2x2x3x3 design")
    lattice_base_fields: dict[str, set[float]] = {}
    for lattice in ("triangular", "honeycomb"):
        reference = base_fields[(lattice, 1, 4)]
        if any(
            base_fields[(lattice, ratio, length)] != reference
            for ratio in (1, 2)
            for length in (4, 6, 8)
        ):
            raise ValueError("base field grids must match within each lattice")
        lattice_base_fields[lattice] = reference

    directed_series = {
        ("triangular", 1, 4, 6),
        ("triangular", 2, 6, 8),
        ("honeycomb", 1, 6, 8),
    }
    extension_fields: dict[tuple[str, int, int], set[float]] = defaultdict(set)
    for lattice, beta_ratio, length, field in extension_coordinates:
        extension_fields[(lattice, beta_ratio, length)].add(field)
    expected_extension_shape = {
        (lattice, beta_ratio, length)
        for lattice, beta_ratio, small, large in directed_series
        for length in (small, large)
    }
    if set(extension_fields) != expected_extension_shape or any(
        len(fields) != 2 for fields in extension_fields.values()
    ):
        raise ValueError("extension points violate the frozen directed merge")

    crossing_fields: dict[tuple[str, int, int, int], set[float]] = {}
    for lattice in ("triangular", "honeycomb"):
        for beta_ratio in (1, 2):
            for small, large in _SIZE_PAIRS:
                series = (lattice, beta_ratio, small, large)
                fields = set(lattice_base_fields[lattice])
                if series in directed_series:
                    small_extension = extension_fields[(lattice, beta_ratio, small)]
                    large_extension = extension_fields[(lattice, beta_ratio, large)]
                    if small_extension != large_extension:
                        raise ValueError(
                            "directed field grids must match within each crossing series"
                        )
                    fields.update(small_extension)
                crossing_fields[series] = fields
    if sorted(len(fields) for fields in crossing_fields.values()) != [3] * 5 + [5] * 3:
        raise ValueError("extended analysis field grids violate the closed merge")

    combined = {**base_coordinates, **extension_coordinates}
    combined_fields: dict[tuple[str, int, int], set[float]] = defaultdict(set)
    for lattice, beta_ratio, length, field in combined:
        combined_fields[(lattice, beta_ratio, length)].add(field)
    return _analyze_validated_grid(
        combined,
        combined_fields,
        plan_sha256=base_plan["plan_sha256"],
        extension_plan_sha256=extension_plan["plan_sha256"],
        input_bindings=[*base_bindings, *extension_bindings],
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
        crossing_fields=crossing_fields,
    )


def write_analysis_artifact(path: Path, analysis: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(analysis))
    digest = value.pop("analysis_sha256", None)
    if digest != _sha256(canonical_json(value)):
        raise ValueError("analysis_sha256 does not bind the analysis content")
    payload = (
        json.dumps(analysis, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    _write_immutable(Path(path), payload)
