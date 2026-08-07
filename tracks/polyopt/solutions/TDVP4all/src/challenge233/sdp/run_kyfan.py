"""Three-stage prepare, solve, and certify runner for Ky Fan cells."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from dataclasses import dataclass
import fcntl
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import resource
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from challenge233.sdp.dual_certificate import build_dual_certificate
from challenge233.sdp.hierarchy import LOCAL_LEVELS
from challenge233.sdp.kyfan import (
    build_global_kyfan_problem,
    build_local_kyfan_problem,
)
from challenge233.sdp.kyfan_artifact import export_kyfan_problem
from challenge233.sdp.kyfan_presolve import (
    build_kyfan_solver_reduction,
    solver_reduction_payload,
)
from challenge233.sdp.kyfan_sparse import (
    build_global_kyfan_structure,
    build_kyfan_instance,
    build_local_kyfan_structure,
)
from challenge233.sdp.kyfan_v2_artifact import (
    canonical_json_bytes,
    export_kyfan_instance,
    export_shared_structure,
    export_solver_reduction,
    logical_structure_sha256,
    structure_payload,
)
from challenge233.sdp.variational_upper import (
    generate_quspin_trial,
    write_trial_vector,
)
from challenge233.sdp.verify_kyfan_certificate import (
    verify_kyfan_certificate,
)
from challenge233.sdp.verify_kyfan_problem import verify_kyfan_problem
from challenge233.sdp.verify_kyfan_reduction import (
    verify_kyfan_reduction,
)
from challenge233.sdp.verify_kyfan_structure import (
    verify_bound_kyfan_structure,
    verify_kyfan_structure,
)


ROOT = Path(__file__).resolve().parents[3]
LOCAL_WALL_GATE_SECONDS = 480
LOCAL_MEMORY_GATE_BYTES = 8 * (1 << 30)
HAMILTONIAN = (
    "H_N(delta)=sum_i P_{i-1} X_i P_{i+1}"
    "-delta sum_i n_i"
)
LOCAL_LEVEL_BY_NAME = {level.name: level for level in LOCAL_LEVELS}


@dataclass(frozen=True)
class CellSelection:
    index: int
    cell_id: str
    size: int
    detuning: Fraction
    hierarchy: str
    localizer_mode: str
    run_directory: Path
    params: dict
    settings: dict
    provenance: dict

    @property
    def cell_directory(self) -> Path:
        return self.run_directory / "cells" / self.cell_id


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _atomic_write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("wb") as stream:
        stream.write(_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _load_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"missing JSON file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON file: {path}") from error


def _fraction_text(value: Fraction) -> str:
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _safe_cell_id(value) -> str:
    value = str(value)
    if (
        not value
        or Path(value).name != value
        or any(
            character
            not in (
                "abcdefghijklmnopqrstuvwxyz"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "0123456789._-"
            )
            for character in value
        )
    ):
        raise ValueError("cell_id is unsafe")
    return value


def _resolve_run_directory(value) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _safe_child_file(directory: Path, filename, purpose: str) -> Path:
    filename = str(filename)
    if not filename or Path(filename).name != filename:
        raise ValueError(f"{purpose} filename is unsafe")
    return directory / filename


def _exact_detuning(params, settings) -> Fraction:
    merged = {**settings, **params}
    if "detuning_tenths" in merged:
        value = merged["detuning_tenths"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("detuning_tenths must be an integer")
        return Fraction(value, 10)
    if (
        "detuning_numerator" in merged
        or "detuning_denominator" in merged
    ):
        if not {
            "detuning_numerator",
            "detuning_denominator",
        } <= set(merged):
            raise ValueError(
                "detuning numerator and denominator must be paired"
            )
        return Fraction(
            int(merged["detuning_numerator"]),
            int(merged["detuning_denominator"]),
        )
    if "detuning" in merged:
        value = merged["detuning"]
        if isinstance(value, float):
            raise TypeError("authoritative detuning cannot be a JSON float")
        return Fraction(str(value))
    raise ValueError("cell does not declare an exact detuning")


def select_cell(run_spec, cell_index: int) -> CellSelection:
    """Resolve one one-based run-spec cell and its exact physical settings."""
    if isinstance(cell_index, bool) or not isinstance(cell_index, int):
        raise TypeError("cell index must be an integer")
    cells = run_spec.get("cells", [])
    if not 1 <= cell_index <= len(cells):
        raise ValueError("cell index is outside the one-based range")
    cell = cells[cell_index - 1]
    params = dict(cell.get("params", {}))
    settings = {
        **dict(run_spec.get("settings", {})),
        **dict(cell.get("settings", {})),
    }
    merged = {**settings, **params}
    size = merged.get("size")
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeError("cell size must be an integer")
    if not 4 <= size <= 20:
        raise ValueError("cell size must satisfy 4 <= N <= 20")
    hierarchy = str(merged.get("hierarchy", "L0"))
    if hierarchy not in {
        "global-d2",
        "global-d3",
        "global-d4",
        *LOCAL_LEVEL_BY_NAME,
    }:
        raise ValueError("unsupported Ky Fan hierarchy")
    localizer_mode = str(merged.get("localizer_mode", "sound"))
    if localizer_mode not in {"sound", "none"}:
        raise ValueError("localizer_mode must be sound or none")
    run_directory = _resolve_run_directory(run_spec["run_dir"])
    detuning = _exact_detuning(params, settings)
    if not Fraction(0) <= detuning <= Fraction(3):
        raise ValueError("cell detuning must lie in [0,3]")
    return CellSelection(
        index=cell_index,
        cell_id=_safe_cell_id(cell["cell_id"]),
        size=size,
        detuning=detuning,
        hierarchy=hierarchy,
        localizer_mode=localizer_mode,
        run_directory=run_directory,
        params=params,
        settings=settings,
        provenance=dict(run_spec.get("provenance", {})),
    )


def _load_selection(run_spec_path, cell_index):
    run_spec_path = Path(run_spec_path).resolve()
    run_spec = _load_json(run_spec_path)
    return run_spec, select_cell(run_spec, cell_index)


def build_problem_for_cell(cell: CellSelection):
    if cell.hierarchy.startswith("global-d"):
        degree = int(cell.hierarchy.removeprefix("global-d"))
        return build_global_kyfan_problem(
            cell.size,
            cell.detuning,
            degree,
            cell.localizer_mode,
        )
    return build_local_kyfan_problem(
        cell.size,
        cell.detuning,
        LOCAL_LEVEL_BY_NAME[cell.hierarchy],
        cell.localizer_mode,
    )


def _peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(value)
    return int(value) * 1024


def _child_peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if sys.platform == "darwin":
        return int(value)
    return int(value) * 1024


def _git_provenance():
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    dirty_output = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {
        "commit": commit,
        "dirty": bool(dirty_output.strip()),
        "dirty_file_count": len(
            [line for line in dirty_output.splitlines() if line]
        ),
    }


def estimate_solve_resources(problem, problem_file_bytes: int):
    dimensions = [
        int(block.dimension) for block in problem.psd_blocks
    ]
    statistics = dict(problem.statistics)
    affine_nonzeros = int(
        statistics.get("affine_nonzero_count", 0)
    )
    dense_entries = sum(
        dimension * dimension for dimension in dimensions
    )
    memory_bytes = (
        8 * int(problem_file_bytes)
        + 256 * dense_entries
        + 128 * affine_nonzeros
        + 64 * 1024 * 1024
    )
    wall_seconds = max(
        1.0,
        affine_nonzeros / 75_000.0
        + sum(dimension**3 for dimension in dimensions) / 20_000_000.0,
    )
    return {
        "psd_dimensions": dimensions,
        "psd_block_count": len(dimensions),
        "largest_psd_dimension": max(dimensions, default=0),
        "affine_nonzero_count": affine_nonzeros,
        "problem_file_bytes": int(problem_file_bytes),
        "estimated_model_memory_bytes": int(memory_bytes),
        "estimated_solve_wall_seconds": wall_seconds,
        "automatic_local_allowed": (
            memory_bytes < LOCAL_MEMORY_GATE_BYTES
            and wall_seconds < LOCAL_WALL_GATE_SECONDS
        ),
    }


def estimate_v2_solve_resources(
    reduction,
    benchmark_wall_seconds=None,
):
    """Apply the automatic-local gate to an exact reduced inventory."""
    if hasattr(reduction, "resource_estimate"):
        resource_estimate = dict(reduction.resource_estimate)
    else:
        resource_estimate = dict(reduction["resource_estimate"])
    estimated_rss_bytes = int(
        resource_estimate["estimated_rss_bytes"]
    )
    if benchmark_wall_seconds is None:
        benchmark = None
    else:
        if (
            isinstance(benchmark_wall_seconds, bool)
            or not isinstance(benchmark_wall_seconds, (int, float))
            or not float(benchmark_wall_seconds) > 0
        ):
            raise ValueError(
                "benchmark wall time must be a positive number"
            )
        benchmark = float(benchmark_wall_seconds)
        if benchmark.is_integer():
            benchmark = int(benchmark)
    return {
        **resource_estimate,
        "benchmark_wall_seconds": benchmark,
        "automatic_local_allowed": (
            estimated_rss_bytes < LOCAL_MEMORY_GATE_BYTES
            and benchmark is not None
            and benchmark < LOCAL_WALL_GATE_SECONDS
        ),
        "hard_local_boundary": {
            "memory_bytes": 16 * (1 << 30),
            "wall_seconds": 600,
        },
    }


def _physical_contract(cell: CellSelection):
    return {
        "hamiltonian": HAMILTONIAN,
        "rabi_coefficient": "+1",
        "detuning": _fraction_text(cell.detuning),
        "detuning_sign": "-delta",
        "projectors": {
            "P": "(I-Z)/2 projects to 0=down",
            "n": "(I+Z)/2 projects to 1=up",
        },
        "lattice": "one-dimensional ring",
        "boundary": "periodic",
        "blockade": "n_i n_{i+1}=0 including the wrap bond",
        "symmetry": (
            "translation and reflection are Hamiltonian symmetries; "
            "no physical sector restriction"
        ),
        "target": "multiplicity-counted global E1-E0",
        "size": cell.size,
        "hierarchy": cell.hierarchy,
        "localizer_mode": cell.localizer_mode,
    }


def build_structure_for_cell(cell: CellSelection):
    if cell.hierarchy.startswith("global-d"):
        degree = int(cell.hierarchy.removeprefix("global-d"))
        return build_global_kyfan_structure(
            cell.size,
            degree,
            cell.localizer_mode,
        )
    return build_local_kyfan_structure(
        cell.size,
        LOCAL_LEVEL_BY_NAME[cell.hierarchy],
        cell.localizer_mode,
    )


def _v2_group_key(cell: CellSelection):
    return (cell.size, cell.hierarchy, cell.localizer_mode)


def _v2_ed_key(cell: CellSelection):
    return (cell.size, cell.detuning)


@contextmanager
def _v2_group_lock(cell: CellSelection):
    lock_directory = cell.run_directory / "shared/.locks"
    lock_directory.mkdir(parents=True, exist_ok=True)
    key = "-".join(map(str, _v2_group_key(cell)))
    path = lock_directory / f"{key}.lock"
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def _v2_ed_lock(cell: CellSelection):
    lock_directory = cell.run_directory / "shared/.locks"
    lock_directory.mkdir(parents=True, exist_ok=True)
    numerator = cell.detuning.numerator
    denominator = cell.detuning.denominator
    path = lock_directory / (
        f"ed-n{cell.size:04d}-delta-"
        f"{numerator}-over-{denominator}.lock"
    )
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _ed_oracle_directory(cell: CellSelection) -> Path:
    return (
        cell.run_directory
        / "shared/ed-oracles"
        / (
            f"n{cell.size:04d}-delta-"
            f"{cell.detuning.numerator}-over-"
            f"{cell.detuning.denominator}"
        )
    )


def _resolve_ed_oracle_directory(cell, reference) -> Path:
    if not isinstance(reference, str) or not reference:
        raise ValueError("ED oracle directory must be non-empty")
    pure = PurePosixPath(reference)
    if (
        pure.is_absolute()
        or "\\" in reference
        or any(part in {"", "."} for part in pure.parts)
        or pure.as_posix() != reference
    ):
        raise ValueError(
            "ED oracle directory must be normalized and relative"
        )
    resolved = (
        cell.cell_directory / Path(*pure.parts)
    ).resolve()
    if (
        resolved != cell.run_directory
        and cell.run_directory not in resolved.parents
    ):
        raise ValueError("ED oracle directory escapes the run")
    if not resolved.is_dir():
        raise FileNotFoundError(
            f"missing ED oracle directory: {resolved}"
        )
    return resolved


def _checked_ed_oracle_payload(cell, directory):
    from challenge233.ed.verify_pxp_gap import verify_run

    directory = Path(directory).resolve()
    verification = verify_run(directory)
    manifest_path = directory / "manifest.json"
    manifest = _load_json(manifest_path)
    expected_contract = {
        "hamiltonian": HAMILTONIAN,
        "rabi_coefficient": 1.0,
        "detuning_sign": "-delta",
        "boundary": "periodic",
        "local_state_convention": "0=down, 1=up",
        "blockade_constraint": "n_i n_{i+1}=0",
        "symmetry_sector": "full constrained Hilbert space",
        "target_gap": "E_1-E_0, all momenta",
    }
    for key, expected in expected_contract.items():
        if manifest.get(key) != expected:
            raise ValueError(f"ED oracle {key} does not match contract")
    if (
        tuple(map(int, manifest.get("sizes", ())))
        != (cell.size,)
        or len(manifest.get("detunings", ())) != 1
        or Fraction(str(manifest["detunings"][0]))
        != cell.detuning
    ):
        raise ValueError("ED oracle grid does not match cell")
    data_path = _safe_child_file(
        directory,
        manifest["data_file"],
        "ED data",
    )
    with data_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 1:
        raise ValueError("ED oracle must contain exactly one point")
    row = rows[0]
    if (
        int(row["size"]) != cell.size
        or Fraction(row["detuning"]) != cell.detuning
    ):
        raise ValueError("ED oracle row does not match cell")
    energy_columns = sorted(
        (
            key
            for key in row
            if key.startswith("e") and key[1:].isdigit()
        ),
        key=lambda key: int(key[1:]),
    )
    if len(energy_columns) < 2:
        raise ValueError("ED oracle does not contain E0 and E1")
    basis_metadata = manifest["basis_state_files"][str(cell.size)]
    basis_path = _safe_child_file(
        directory,
        basis_metadata["path"],
        "ED basis states",
    )
    return {
        "purpose": "verified-finite-N-ed-oracle",
        "directory": os.path.relpath(
            directory,
            cell.cell_directory,
        ),
        "size": cell.size,
        "detuning": _fraction_text(cell.detuning),
        "e0": row["e0"],
        "e1": row["e1"],
        "gap": row["gap"],
        "maximum_residual": row["max_residual"],
        "manifest_sha256": _sha256_file(manifest_path),
        "data_sha256": _sha256_file(data_path),
        "basis_state_sha256": _sha256_file(basis_path),
        "verification": verification,
    }


def _validate_ed_oracle_binding(cell, binding):
    if not isinstance(binding, dict):
        raise TypeError("ED oracle binding must be an object")
    if binding.get("purpose") != "verified-finite-N-ed-oracle":
        raise ValueError("unexpected ED oracle binding purpose")
    directory = _resolve_ed_oracle_directory(
        cell,
        binding.get("directory"),
    )
    checked = _checked_ed_oracle_payload(cell, directory)
    for key, expected in checked.items():
        if key == "verification":
            continue
        if binding.get(key) != expected:
            raise ValueError(f"ED oracle {key} binding mismatch")
    return checked


def _ensure_v2_ed_oracle(cell):
    directory = _ed_oracle_directory(cell)
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        if directory.exists() and any(directory.iterdir()):
            raise FileExistsError(
                "ED oracle directory is incomplete and nonempty"
            )
        from challenge233.ed.pxp_gap import run_sweep

        run_sweep(
            (cell.size,),
            (float(cell.detuning),),
            directory,
            eigenpairs=4,
            tolerance=float(
                cell.settings.get("arpack_tolerance", 1e-12)
            ),
            random_seed=int(cell.settings.get("random_seed", 233)),
        )
    return _checked_ed_oracle_payload(cell, directory)


def _build_v2_shared(cell: CellSelection):
    structure = build_structure_for_cell(cell)
    binding = export_shared_structure(
        structure,
        cell.run_directory / "shared",
    )
    structure_check = verify_kyfan_structure(binding.directory)
    reduction = build_kyfan_solver_reduction(
        structure,
        binding.structure_sha256,
    )
    reduction_binding = export_solver_reduction(
        reduction,
        binding,
    )
    reduction_check = verify_kyfan_reduction(
        reduction_binding.directory
    )
    return {
        "structure": structure,
        "structure_binding": binding,
        "structure_check": structure_check,
        "reduction": reduction,
        "reduction_binding": reduction_binding,
        "reduction_check": reduction_check,
    }


def _benchmark_for_binding(cell, structure_sha256, reduction_sha256):
    benchmark = cell.settings.get("solver_benchmark")
    if benchmark is None:
        return None
    if not isinstance(benchmark, dict):
        raise TypeError("solver_benchmark must be an object")
    if (
        benchmark.get("structure_sha256") != structure_sha256
        or benchmark.get("reduction_sha256") != reduction_sha256
    ):
        raise ValueError(
            "solver benchmark does not match this formulation"
        )
    return benchmark.get("wall_seconds")


def _prepare_v2_selection(cell: CellSelection, shared, ed_oracle):
    cell_directory = cell.cell_directory
    prepare_path = cell_directory / "prepare-manifest.json"
    if prepare_path.exists():
        raise FileExistsError("cell is already prepared")
    if cell_directory.exists() and any(cell_directory.iterdir()):
        raise FileExistsError("cell directory must be empty before prepare")
    cell_directory.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    trial_bits = int(cell.settings.get("trial_bits", 40))
    tolerance = float(cell.settings.get("arpack_tolerance", 1e-12))
    seed = int(cell.settings.get("random_seed", 233))
    trial = generate_quspin_trial(
        cell.size,
        cell.detuning,
        bits=trial_bits,
        tolerance=tolerance,
        seed=seed,
    )
    trial_directory = cell_directory / "trial"
    write_trial_vector(trial, trial_directory)
    trial_path = trial_directory / "trial-vector.json"
    if not trial_path.is_file():
        raise FileNotFoundError("trial writer did not produce metadata")
    trial_sha256 = _sha256_file(trial_path)

    instance = build_kyfan_instance(
        shared["structure"],
        cell.detuning,
        trial_manifest=trial_sha256,
    )
    problem_directory = cell_directory / "problem"
    export_kyfan_instance(
        instance,
        shared["structure_binding"],
        problem_directory,
        shared["reduction_binding"],
    )
    structure_check = verify_bound_kyfan_structure(
        problem_directory,
        cell.run_directory,
    )
    reduction_check = {
        **shared["reduction_check"],
        "cell_binding_checked": True,
    }
    problem_manifest_path = problem_directory / "manifest.json"
    problem_manifest = _load_json(problem_manifest_path)

    benchmark = _benchmark_for_binding(
        cell,
        shared["structure_binding"].structure_sha256,
        shared["reduction_binding"].reduction_sha256,
    )
    estimate = estimate_v2_solve_resources(
        shared["reduction"],
        benchmark,
    )
    manifest = {
        "schema_version": 2,
        "purpose": "prepared-ky-fan-cell",
        "cell_id": cell.cell_id,
        "cell_index": cell.index,
        "physical_contract": _physical_contract(cell),
        "params": cell.params,
        "settings": cell.settings,
        "provenance": cell.provenance,
        "git": _git_provenance(),
        "problem_manifest_sha256": _sha256_file(
            problem_manifest_path
        ),
        "instance_sha256": problem_manifest["instance_sha256"],
        "structure_sha256": problem_manifest["structure_sha256"],
        "structure_manifest_sha256": problem_manifest[
            "structure_manifest_sha256"
        ],
        "reduction_sha256": problem_manifest["reduction_sha256"],
        "reduction_manifest_sha256": problem_manifest[
            "reduction_manifest_sha256"
        ],
        "solver_view": shared["reduction"].selected_view,
        "structure_check": structure_check,
        "reduction_check": reduction_check,
        "trial_file": "trial/trial-vector.json",
        "trial_vector_sha256": trial_sha256,
        "ed_oracle": dict(ed_oracle),
        "statistics": dict(shared["reduction"].statistics),
        "resource_estimate": estimate,
        "prepare_wall_seconds": time.perf_counter() - started,
        "prepare_peak_rss_bytes": _peak_rss_bytes(),
        "source_file_sha256": _sha256_file(Path(__file__)),
    }
    _atomic_write_json(prepare_path, manifest)
    return {
        "status": "prepared",
        "cell_id": cell.cell_id,
        "instance_sha256": manifest["instance_sha256"],
        "structure_sha256": manifest["structure_sha256"],
        "reduction_sha256": manifest["reduction_sha256"],
        "trial_vector_sha256": trial_sha256,
        "resource_estimate": estimate,
    }


def _snapshot_file(path, root):
    path = Path(path).resolve()
    root = Path(root).resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("snapshot file lies outside its root") from error
    return {
        "file": relative,
        "byte_count": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _write_v2_staging_manifest(run_spec_path, selections):
    run_spec_path = Path(run_spec_path).resolve()
    selections = tuple(selections)
    source_paths = (
        ROOT / "src/challenge233/sdp/solve_kyfan.jl",
        ROOT / "julia-env/Project.toml",
        ROOT / "julia-env/Manifest.toml",
        ROOT / "scripts/harness_array_sbatch.sh",
    )
    cells = []
    for cell in selections:
        problem = cell.cell_directory / "problem"
        manifest_path = problem / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = _load_json(manifest_path)
        files = [
            manifest_path,
            problem / manifest["instance_file"],
        ]
        for key in (
            "structure_reference",
            "structure_manifest_reference",
            "reduction_reference",
            "reduction_manifest_reference",
        ):
            files.append(
                _resolve_v2_reference(
                    manifest_path,
                    manifest[key],
                    cell.run_directory,
                )
            )
        cells.append(
            {
                "cell_id": cell.cell_id,
                "cell_index": cell.index,
                "files": [
                    _snapshot_file(path, cell.run_directory)
                    for path in files
                ],
            }
        )
    payload = {
        "schema_version": 2,
        "purpose": "minimal-ky-fan-slurm-input-snapshot",
        "run_spec": _snapshot_file(
            run_spec_path,
            selections[0].run_directory,
        ),
        "source_files": [
            _snapshot_file(path, ROOT) for path in source_paths
        ],
        "path_bases": {
            "source_files": "repository root",
            "run_spec": "run root",
            "cells": "run root",
        },
        "cells": cells,
        "excludes": [
            "Python source and interpreters",
            "QuSpin",
            "unrelated results",
            "SSH keys",
            "Git metadata and remotes",
        ],
    }
    path = selections[0].run_directory / "slurm-staging-manifest.json"
    _atomic_write_json(path, payload)
    return path


def prepare_v2_cell(run_spec_path, cell_index: int):
    """Prepare one schema-v2 cell with locked shared exact artifacts."""
    run_spec, cell = _load_selection(run_spec_path, cell_index)
    with _v2_ed_lock(cell):
        ed_oracle = _ensure_v2_ed_oracle(cell)
    with _v2_group_lock(cell):
        shared = _build_v2_shared(cell)
        summary = _prepare_v2_selection(
            cell,
            shared,
            ed_oracle,
        )
    prepared_selections = tuple(
        selection
        for index in range(1, len(run_spec["cells"]) + 1)
        for selection in (select_cell(run_spec, index),)
        if (
            selection.cell_directory / "problem/manifest.json"
        ).is_file()
    )
    _write_v2_staging_manifest(run_spec_path, prepared_selections)
    return summary


def prepare_v2_run(run_spec_path, max_cells=None):
    """Prepare v2 cells while building each shared formulation once."""
    run_spec = _load_json(Path(run_spec_path))
    if run_spec.get("schema_version") != 2:
        raise ValueError("prepare_v2_run requires a schema-v2 run spec")
    count = len(run_spec["cells"])
    if max_cells is not None:
        count = min(count, int(max_cells))
    selections = [
        select_cell(run_spec, index)
        for index in range(1, count + 1)
    ]
    ed_by_point = {}
    for cell in selections:
        key = _v2_ed_key(cell)
        if key not in ed_by_point:
            with _v2_ed_lock(cell):
                ed_by_point[key] = _ensure_v2_ed_oracle(cell)
    groups = {}
    for cell in selections:
        groups.setdefault(_v2_group_key(cell), []).append(cell)
    summaries_by_index = {}
    for group in groups.values():
        with _v2_group_lock(group[0]):
            shared = _build_v2_shared(group[0])
            for cell in group:
                summaries_by_index[cell.index] = _prepare_v2_selection(
                    cell,
                    shared,
                    ed_by_point[_v2_ed_key(cell)],
                )
    if selections:
        _write_v2_staging_manifest(run_spec_path, selections)
    return [
        summaries_by_index[cell.index] for cell in selections
    ]


def prepare_cell(run_spec_path, cell_index: int):
    """Build and independently check only the problem and trial stages."""
    run_spec = _load_json(Path(run_spec_path))
    if run_spec.get("schema_version") == 2:
        return prepare_v2_cell(run_spec_path, cell_index)
    _, cell = _load_selection(run_spec_path, cell_index)
    cell_directory = cell.cell_directory
    prepare_path = cell_directory / "prepare-manifest.json"
    if prepare_path.exists():
        raise FileExistsError("cell is already prepared")
    if cell_directory.exists() and any(cell_directory.iterdir()):
        raise FileExistsError("cell directory must be empty before prepare")
    cell_directory.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    problem = build_problem_for_cell(cell)
    problem_directory = cell_directory / "problem"
    export_kyfan_problem(problem, problem_directory)
    problem_check = verify_kyfan_problem(problem_directory)
    problem_manifest_path = problem_directory / "manifest.json"
    problem_manifest = _load_json(problem_manifest_path)
    problem_path = _safe_child_file(
        problem_directory,
        problem_manifest["problem_file"],
        "problem",
    )
    if _sha256_file(problem_path) != problem_manifest["problem_sha256"]:
        raise ValueError("exported problem hash is inconsistent")

    trial_bits = int(cell.settings.get("trial_bits", 40))
    tolerance = float(cell.settings.get("arpack_tolerance", 1e-12))
    seed = int(cell.settings.get("random_seed", 233))
    trial = generate_quspin_trial(
        cell.size,
        cell.detuning,
        bits=trial_bits,
        tolerance=tolerance,
        seed=seed,
    )
    trial_directory = cell_directory / "trial"
    write_trial_vector(trial, trial_directory)
    trial_path = trial_directory / "trial-vector.json"
    if not trial_path.is_file():
        raise FileNotFoundError("trial writer did not produce metadata")

    elapsed = time.perf_counter() - started
    estimate = estimate_solve_resources(
        problem,
        problem_path.stat().st_size,
    )
    manifest = {
        "schema_version": 1,
        "purpose": "prepared-ky-fan-cell",
        "cell_id": cell.cell_id,
        "cell_index": cell.index,
        "physical_contract": _physical_contract(cell),
        "params": cell.params,
        "settings": cell.settings,
        "provenance": cell.provenance,
        "git": _git_provenance(),
        "problem_file": "problem/problem.json",
        "problem_sha256": problem_manifest["problem_sha256"],
        "problem_manifest_sha256": _sha256_file(
            problem_manifest_path
        ),
        "problem_check": problem_check,
        "trial_file": "trial/trial-vector.json",
        "trial_vector_sha256": _sha256_file(trial_path),
        "statistics": dict(problem.statistics),
        "resource_estimate": estimate,
        "prepare_wall_seconds": elapsed,
        "prepare_peak_rss_bytes": _peak_rss_bytes(),
        "source_file_sha256": _sha256_file(Path(__file__)),
    }
    _atomic_write_json(prepare_path, manifest)
    return {
        "status": "prepared",
        "cell_id": cell.cell_id,
        "problem_sha256": manifest["problem_sha256"],
        "trial_vector_sha256": manifest["trial_vector_sha256"],
        "resource_estimate": estimate,
    }


def _validated_prepare(cell: CellSelection):
    prepare_path = cell.cell_directory / "prepare-manifest.json"
    if not prepare_path.is_file():
        raise FileNotFoundError("missing prepare manifest")
    prepare = _load_json(prepare_path)
    if prepare.get("schema_version") == 2:
        problem_manifest_path = (
            cell.cell_directory / "problem/manifest.json"
        )
        if (
            _sha256_file(problem_manifest_path)
            != prepare["problem_manifest_sha256"]
        ):
            raise ValueError("prepared problem manifest hash changed")
        problem_manifest = _load_json(problem_manifest_path)
        for component, reference_key, hash_key in (
            ("instance", "instance_file", "instance_sha256"),
            (
                "structure",
                "structure_reference",
                "structure_sha256",
            ),
            (
                "structure manifest",
                "structure_manifest_reference",
                "structure_manifest_sha256",
            ),
            (
                "reduction",
                "reduction_reference",
                "reduction_sha256",
            ),
            (
                "reduction manifest",
                "reduction_manifest_reference",
                "reduction_manifest_sha256",
            ),
        ):
            path = _resolve_v2_reference(
                problem_manifest_path,
                problem_manifest[reference_key],
                cell.run_directory,
            )
            expected = problem_manifest[hash_key]
            if (
                _sha256_file(path) != expected
                or prepare[hash_key] != expected
            ):
                raise ValueError(f"prepared {component} hash changed")
        trial_path = cell.cell_directory / "trial/trial-vector.json"
        if _sha256_file(trial_path) != prepare["trial_vector_sha256"]:
            raise ValueError("prepared trial-vector hash changed")
        _validate_ed_oracle_binding(
            cell,
            prepare.get("ed_oracle"),
        )
        return prepare
    if prepare.get("schema_version") != 1:
        raise ValueError("unsupported prepared-cell schema version")
    problem_manifest_path = cell.cell_directory / "problem/manifest.json"
    problem_manifest = _load_json(problem_manifest_path)
    problem_path = _safe_child_file(
        problem_manifest_path.parent,
        problem_manifest["problem_file"],
        "problem",
    )
    current_problem_hash = _sha256_file(problem_path)
    if (
        current_problem_hash != problem_manifest["problem_sha256"]
        or current_problem_hash != prepare["problem_sha256"]
    ):
        raise ValueError("prepared problem hash changed")
    if (
        _sha256_file(problem_manifest_path)
        != prepare["problem_manifest_sha256"]
    ):
        raise ValueError("prepared problem manifest hash changed")
    trial_path = cell.cell_directory / "trial/trial-vector.json"
    if _sha256_file(trial_path) != prepare["trial_vector_sha256"]:
        raise ValueError("prepared trial-vector hash changed")
    return prepare


def _resolve_v2_reference(manifest_path, reference, run_root):
    if not isinstance(reference, str) or not reference:
        raise ValueError("artifact reference must be non-empty")
    pure = PurePosixPath(reference)
    if (
        pure.is_absolute()
        or "\\" in reference
        or any(part in {"", "."} for part in pure.parts)
        or pure.as_posix() != reference
    ):
        raise ValueError("artifact reference must be normalized and relative")
    resolved = (
        Path(manifest_path).parent / Path(*pure.parts)
    ).resolve()
    root = Path(run_root).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("artifact reference escapes the run directory")
    if not resolved.is_file():
        raise FileNotFoundError(f"missing bound artifact: {resolved}")
    return resolved


def remote_solve_command():
    """Return the pure-Julia command used locally and by the array wrapper."""
    return (
        "julia",
        "--project=julia-env",
        "src/challenge233/sdp/solve_kyfan.jl",
    )


def _write_solve_record(cell_directory: Path, record):
    _atomic_write_json(
        cell_directory / "solve-local-record.json",
        record,
    )


def solve_local_cell(
    run_spec_path,
    cell_index: int,
    *,
    timeout_seconds: int = LOCAL_WALL_GATE_SECONDS,
):
    """Run one prepared cell through Julia under the automatic local gate."""
    _, cell = _load_selection(run_spec_path, cell_index)
    prepare = _validated_prepare(cell)
    estimate = prepare["resource_estimate"]
    if prepare["schema_version"] == 2:
        if estimate.get("automatic_local_allowed") is not True:
            raise RuntimeError(
                "cell lacks a qualifying reduced-form local benchmark"
            )
    elif (
        float(estimate["estimated_solve_wall_seconds"])
        >= LOCAL_WALL_GATE_SECONDS
        or int(estimate["estimated_model_memory_bytes"])
        >= LOCAL_MEMORY_GATE_BYTES
    ):
        raise RuntimeError("cell exceeds the automatic local solve gate")
    timeout_seconds = min(
        int(timeout_seconds),
        LOCAL_WALL_GATE_SECONDS,
    )
    if timeout_seconds <= 0:
        raise ValueError("local solve timeout must be positive")
    solver_directory = cell.cell_directory / "solver"
    if solver_directory.exists() and any(solver_directory.iterdir()):
        raise FileExistsError("solver directory must be empty")

    command = (
        *remote_solve_command(),
        "--problem-dir",
        str(cell.cell_directory / "problem"),
        "--output-dir",
        str(solver_directory),
    )
    environment = {
        **os.environ,
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
    }
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        record = {
            "schema_version": 1,
            "purpose": "local-ky-fan-solve-record",
            "operational_status": "timeout",
            "command": list(command),
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": time.perf_counter() - started,
            "stdout": error.stdout,
            "stderr": error.stderr,
        }
        _write_solve_record(cell.cell_directory, record)
        raise RuntimeError("local Julia solve timed out") from error

    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        record = {
            "schema_version": 1,
            "purpose": "local-ky-fan-solve-record",
            "operational_status": "nonzero-exit",
            "returncode": completed.returncode,
            "command": list(command),
            "elapsed_seconds": elapsed,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        _write_solve_record(cell.cell_directory, record)
        raise RuntimeError("local Julia solve returned nonzero")

    solver_manifest_path = solver_directory / "solver-manifest.json"
    if not solver_manifest_path.is_file():
        raise FileNotFoundError("Julia solve did not write solver manifest")
    solver_manifest = _load_json(solver_manifest_path)
    if solver_manifest.get("success") is not True:
        raise ValueError("solver manifest does not report success")
    if prepare["schema_version"] == 1:
        if (
            solver_manifest.get("problem_sha256")
            != prepare["problem_sha256"]
        ):
            raise ValueError("solver manifest problem hash changed")
    else:
        for key in (
            "problem_manifest_sha256",
            "structure_sha256",
            "instance_sha256",
            "reduction_sha256",
        ):
            if solver_manifest.get(key) != prepare[key]:
                raise ValueError(f"solver manifest {key} changed")
        if solver_manifest.get("solver_view") != prepare["solver_view"]:
            raise ValueError("solver manifest selected view changed")
    result_path = _safe_child_file(
        solver_directory,
        solver_manifest["solver_result_file"],
        "solver-result",
    )
    if _sha256_file(result_path) != solver_manifest[
        "solver_result_sha256"
    ]:
        raise ValueError("solver-result hash is inconsistent")
    if prepare["schema_version"] == 2:
        solver_result = _load_json(result_path)
        for key in (
            "problem_manifest_sha256",
            "structure_sha256",
            "instance_sha256",
            "reduction_sha256",
        ):
            if solver_result.get(key) != prepare[key]:
                raise ValueError(f"solver result {key} changed")
        if solver_result.get("solver_view") != prepare["solver_view"]:
            raise ValueError("solver result selected view changed")
    peak_rss = _child_peak_rss_bytes()
    status = (
        "memory-overrun"
        if peak_rss >= LOCAL_MEMORY_GATE_BYTES
        else "success"
    )
    record = {
        "schema_version": 1,
        "purpose": "local-ky-fan-solve-record",
        "operational_status": status,
        "returncode": completed.returncode,
        "command": list(command),
        "elapsed_seconds": elapsed,
        "peak_rss_bytes": peak_rss,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "solver_manifest_sha256": _sha256_file(
            solver_manifest_path
        ),
        "solver_result_sha256": _sha256_file(result_path),
    }
    _write_solve_record(cell.cell_directory, record)
    if status != "success":
        raise RuntimeError("local Julia solve exceeded the memory gate")
    return {
        "status": "solved",
        "cell_id": cell.cell_id,
        "elapsed_seconds": elapsed,
        "peak_rss_bytes": peak_rss,
        "solver_manifest_sha256": record["solver_manifest_sha256"],
    }


def certify_cell(run_spec_path, cell_index: int):
    """Build, independently check, and finalize one solved cell."""
    _, cell = _load_selection(run_spec_path, cell_index)
    prepare = _validated_prepare(cell)
    solver_directory = cell.cell_directory / "solver"
    solver_manifest_path = solver_directory / "solver-manifest.json"
    if not solver_manifest_path.is_file():
        raise FileNotFoundError("missing solver manifest")
    solver_manifest = _load_json(solver_manifest_path)
    if solver_manifest.get("success") is not True:
        raise ValueError("solver manifest does not report success")
    if prepare["schema_version"] == 1:
        if (
            solver_manifest.get("problem_sha256")
            != prepare["problem_sha256"]
        ):
            raise ValueError("solver problem hash does not match prepare")
    else:
        for key in (
            "problem_manifest_sha256",
            "structure_sha256",
            "instance_sha256",
            "reduction_sha256",
            "solver_view",
        ):
            if solver_manifest.get(key) != prepare[key]:
                raise ValueError(
                    f"solver {key} does not match prepare"
                )
    solver_result_path = _safe_child_file(
        solver_directory,
        solver_manifest["solver_result_file"],
        "solver-result",
    )
    if _sha256_file(solver_result_path) != solver_manifest[
        "solver_result_sha256"
    ]:
        raise ValueError("solver-result hash does not match manifest")
    solver_result = _load_json(solver_result_path)
    if prepare["schema_version"] == 2:
        for key in (
            "problem_manifest_sha256",
            "structure_sha256",
            "instance_sha256",
            "reduction_sha256",
            "solver_view",
        ):
            if solver_result.get(key) != prepare[key]:
                raise ValueError(
                    f"solver result {key} does not match prepare"
                )
    solver_selection = dict(solver_result.get("selection", {}))
    solver_mode = solver_selection.get("mode")
    if solver_mode == "slurm-array":
        if (
            solver_selection.get("cell_id") != cell.cell_id
            or solver_selection.get("cell_index") != cell.index
        ):
            raise ValueError("Slurm solver selection does not match cell")
        slurm_record_path = (
            cell.cell_directory / "slurm-task-record.json"
        )
        if not slurm_record_path.is_file():
            raise FileNotFoundError("missing Slurm task accounting record")
        slurm_record = _load_json(slurm_record_path)
        if (
            slurm_record.get("purpose")
            != "slurm-array-task-accounting"
            or slurm_record.get("cell_id") != cell.cell_id
            or slurm_record.get("cell_index") != cell.index
            or slurm_record.get("array_task_id") != cell.index
        ):
            raise ValueError("Slurm task accounting does not match cell")
        if (
            slurm_record.get("classification") != "success"
            or slurm_record.get("state") != "COMPLETED"
            or slurm_record.get("exit_code") != "0:0"
        ):
            raise ValueError("Slurm task accounting does not report success")
        if not str(slurm_record.get("job_id", "")).isdigit():
            raise ValueError("Slurm task accounting has an invalid job id")
        slurm_record_sha256 = _sha256_file(slurm_record_path)
    else:
        slurm_record = None
        slurm_record_sha256 = None

    solve_record_path = cell.cell_directory / "solve-local-record.json"
    solve_record = (
        _load_json(solve_record_path)
        if solve_record_path.is_file()
        else None
    )
    if solve_record is not None:
        local_status = solve_record.get("operational_status")
        if local_status == "success":
            if (
                solve_record.get("solver_manifest_sha256")
                != _sha256_file(solver_manifest_path)
            ):
                raise ValueError(
                    "local solve record does not bind the solver manifest"
                )
        elif solver_mode != "slurm-array":
            raise ValueError("local solve record does not report success")

    if solver_mode == "slurm-array":
        placement = "slurm"
    elif solve_record is not None:
        placement = "local"
    else:
        placement = "external-direct"

    certificate_directory = cell.cell_directory / "certificate"
    if certificate_directory.exists() and any(
        certificate_directory.iterdir()
    ):
        raise FileExistsError("certificate directory must be empty")
    build_dual_certificate(
        cell.cell_directory / "problem",
        solver_directory,
        cell.cell_directory / "trial",
        certificate_directory,
        factor_bits=int(cell.settings.get("factor_bits", 30)),
        multiplier_bits=int(
            cell.settings.get("multiplier_bits", 40)
        ),
    )
    checked = verify_kyfan_certificate(cell.cell_directory)
    if checked.get("status") != "verified":
        raise ValueError("independent certificate check failed")

    certificate_manifest_path = certificate_directory / "manifest.json"
    certificate_manifest = _load_json(certificate_manifest_path)
    certificate_path = _safe_child_file(
        certificate_directory,
        certificate_manifest["certificate_file"],
        "certificate",
    )
    certificate = _load_json(certificate_path)
    residual_path = _safe_child_file(
        certificate_directory,
        certificate["dual_residuals_file"],
        "dual residual",
    )
    residual_sha256 = _sha256_file(residual_path)
    if residual_sha256 != certificate["dual_residuals_sha256"]:
        raise ValueError("dual residual hash does not match certificate")
    residual_payload = _load_json(residual_path)
    residual_values = [
        Fraction(row["value"])
        for row in residual_payload["residuals"]
    ]
    maximum_residual = max(
        (abs(value) for value in residual_values),
        default=Fraction(0),
    )
    residual_diagnostics = {
        "raw_constant_a": residual_payload["a"],
        "residual_count": len(residual_values),
        "nonzero_count": sum(
            value != 0 for value in residual_values
        ),
        "maximum_absolute_residual": _fraction_text(
            maximum_residual
        ),
        "residual_correction_rho": residual_payload["rho"],
    }
    if prepare["schema_version"] == 2:
        residual_diagnostics.update(
            {
                "pseudo_moment_correction_rho_mom": (
                    residual_payload["rho_mom"]
                ),
                "physical_operator_correction_rho_op": (
                    residual_payload["rho_op"]
                ),
                "residual_route": residual_payload[
                    "residual_route"
                ],
            }
        )
    final = {
        "schema_version": prepare["schema_version"],
        "purpose": "final-ky-fan-cell-manifest",
        "cell_id": cell.cell_id,
        "cell_index": cell.index,
        "physical_contract": _physical_contract(cell),
        "params": cell.params,
        "settings": cell.settings,
        "provenance": cell.provenance,
        "trial_vector_sha256": prepare["trial_vector_sha256"],
        "prepare_manifest_sha256": _sha256_file(
            cell.cell_directory / "prepare-manifest.json"
        ),
        "solver_manifest_sha256": _sha256_file(
            solver_manifest_path
        ),
        "solver_result_sha256": _sha256_file(solver_result_path),
        "certificate_manifest_sha256": _sha256_file(
            certificate_manifest_path
        ),
        "certificate_sha256": _sha256_file(certificate_path),
        "solver": {
            key: solver_result.get(key)
            for key in (
                "termination_status",
                "primal_status",
                "dual_status",
                "raw_status",
                "objective",
                "dual_objective",
                "solve_time_seconds",
                "wall_time_seconds",
                "versions",
                "settings",
                "result_count",
                "dual_cone",
                "dual_identity_sign_calibrated",
                "offdiagonal_scaling_calibrated",
                "maximum_dual_asymmetry",
            )
        },
        "certificate": {
            "a": certificate["a"],
            "a_cert": certificate["a_cert"],
            "b_var": certificate["b_var"],
            "rho": certificate["rho"],
            "delta_cert": certificate["delta_cert"],
            "status": certificate["status"],
            "dual_residuals_file": (
                f"certificate/{residual_path.name}"
            ),
            "dual_residuals_sha256": residual_sha256,
            "residual_diagnostics": residual_diagnostics,
        },
        "independent_check_passed": True,
        "independent_check": checked,
        "certificate_status": checked["certificate_status"],
        "resource_provenance": {
            "placement": placement,
            "solver_selection": solver_selection,
            "prior_local_attempt": solve_record,
            "slurm_task_record": slurm_record,
            "slurm_task_record_sha256": slurm_record_sha256,
        },
    }
    if prepare["schema_version"] == 1:
        final.update(
            {
                "problem_sha256": prepare["problem_sha256"],
                "problem_manifest_sha256": prepare[
                    "problem_manifest_sha256"
                ],
            }
        )
    else:
        final.update(
            {
                key: prepare[key]
                for key in (
                    "problem_manifest_sha256",
                    "structure_sha256",
                    "instance_sha256",
                    "reduction_sha256",
                    "solver_view",
                )
            }
        )
        final["ed_oracle"] = prepare["ed_oracle"]
        final["certificate"].update(
            {
                "rho_mom": certificate["rho_mom"],
                "rho_op": certificate["rho_op"],
                "residual_route": certificate["residual_route"],
            }
        )
    final_path = cell.cell_directory / "manifest.json"
    if final_path.exists():
        raise FileExistsError("final cell manifest already exists")
    _atomic_write_json(final_path, final)
    return {
        "status": checked["certificate_status"],
        "cell_id": cell.cell_id,
        "delta_cert": checked["delta_cert"],
        "manifest_sha256": _sha256_file(final_path),
    }


def prepare_run(run_spec_path, max_cells=None):
    run_spec = _load_json(Path(run_spec_path))
    if run_spec.get("schema_version") == 2:
        return prepare_v2_run(run_spec_path, max_cells)
    count = len(run_spec["cells"])
    if max_cells is not None:
        count = min(count, int(max_cells))
    return [
        prepare_cell(run_spec_path, index)
        for index in range(1, count + 1)
    ]


def _checked_accounting(final):
    provenance = final.get("resource_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("cell is missing solver accounting")
    placement = provenance.get("placement")
    if placement == "local":
        record = provenance.get("prior_local_attempt")
        if (
            not isinstance(record, dict)
            or record.get("operational_status") != "success"
            or record.get("solver_manifest_sha256")
            != final.get("solver_manifest_sha256")
            or record.get("solver_result_sha256")
            != final.get("solver_result_sha256")
        ):
            raise ValueError(
                "local solver accounting is missing or inconsistent"
            )
        return {
            "placement": placement,
            "elapsed_seconds": record.get("elapsed_seconds"),
            "peak_rss_bytes": record.get("peak_rss_bytes"),
            "record": record,
        }
    if placement == "slurm":
        record = provenance.get("slurm_task_record")
        if (
            not isinstance(record, dict)
            or record.get("classification") != "success"
            or record.get("state") != "COMPLETED"
            or record.get("exit_code") != "0:0"
            or not provenance.get("slurm_task_record_sha256")
        ):
            raise ValueError(
                "Slurm solver accounting is missing or inconsistent"
            )
        return {
            "placement": placement,
            "elapsed": record.get("elapsed"),
            "max_rss_bytes": record.get("max_rss_bytes"),
            "record_sha256": provenance[
                "slurm_task_record_sha256"
            ],
            "record": record,
        }
    raise ValueError(
        "solver accounting must be a checked local or Slurm record"
    )


def _require_n4_anchor_inventory(selections, run_spec):
    if run_spec.get("settings", {}).get(
        "exactness_tolerance"
    ) is None:
        return False
    if any(
        cell.size != 4 or cell.detuning != Fraction(1, 2)
        for cell in selections
    ):
        raise ValueError(
            "exactness anchor must use N=4 and detuning 1/2"
        )
    expected = {"global-d2", "global-d3", "global-d4"}
    if {cell.hierarchy for cell in selections} != expected:
        raise ValueError(
            "N4 exactness anchor requires all d2/d3/d4 cells"
        )
    if len(selections) != 3:
        raise ValueError(
            "N4 exactness anchor requires exactly d2/d3/d4"
        )
    return True


def _summary_fraction(value, component):
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(f"{component} must be an exact string")
    try:
        return Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError) as error:
        raise ValueError(f"invalid exact {component}") from error


def certify_run(run_spec_path):
    """Independently summarize already certified schema-v2 cells."""
    run_spec_path = Path(run_spec_path).resolve()
    run_spec = _load_json(run_spec_path)
    if run_spec.get("schema_version") != 2:
        return [
            certify_cell(run_spec_path, index)
            for index in range(1, len(run_spec["cells"]) + 1)
        ]
    selections = tuple(
        select_cell(run_spec, index)
        for index in range(1, len(run_spec["cells"]) + 1)
    )
    is_anchor = _require_n4_anchor_inventory(
        selections,
        run_spec,
    )
    cells = []
    for cell in selections:
        final_path = cell.cell_directory / "manifest.json"
        if not final_path.is_file():
            raise FileNotFoundError(
                f"missing final certificate manifest: {cell.cell_id}"
            )
        final = _load_json(final_path)
        if (
            final.get("schema_version") != 2
            or final.get("cell_id") != cell.cell_id
            or int(final.get("cell_index", -1)) != cell.index
            or final.get("independent_check_passed") is not True
        ):
            raise ValueError(
                f"invalid final certificate manifest: {cell.cell_id}"
            )
        contract = final.get("physical_contract", {})
        for key, expected in (
            ("size", cell.size),
            ("detuning", _fraction_text(cell.detuning)),
            ("hierarchy", cell.hierarchy),
            ("localizer_mode", "sound"),
            ("boundary", "periodic"),
            ("target", "multiplicity-counted global E1-E0"),
        ):
            if contract.get(key) != expected:
                raise ValueError(
                    f"cell physical contract {key} mismatch"
                )
        checked = verify_kyfan_certificate(cell.cell_directory)
        if (
            checked.get("status") != "verified"
            or checked.get("schema_version") != 2
            or checked.get("certificate_status")
            != final.get("certificate_status")
        ):
            raise ValueError(
                f"independent certificate check failed: {cell.cell_id}"
            )
        certificate = final.get("certificate", {})
        for key in (
            "a_cert",
            "b_var",
            "delta_cert",
            "rho_mom",
            "rho_op",
            "residual_route",
        ):
            if checked.get(key) != certificate.get(key):
                raise ValueError(
                    f"checked certificate {key} mismatch"
                )
        if "ed_oracle" not in final:
            raise ValueError(
                f"cell is missing an ED oracle: {cell.cell_id}"
            )
        ed = _validate_ed_oracle_binding(
            cell,
            final["ed_oracle"],
        )
        accounting = _checked_accounting(final)
        delta_cert = _summary_fraction(
            certificate["delta_cert"],
            "delta_cert",
        )
        ed_gap = Fraction(ed["gap"])
        ed_error = 2 * Fraction(ed["maximum_residual"])
        if delta_cert > ed_gap + ed_error:
            raise ValueError(
                "certified gap exceeds the identical ED oracle"
            )
        cells.append(
            {
                "cell_id": cell.cell_id,
                "cell_index": cell.index,
                "hierarchy": cell.hierarchy,
                "certificate_status": final[
                    "certificate_status"
                ],
                "certificate": {
                    key: certificate[key]
                    for key in (
                        "a_cert",
                        "b_var",
                        "delta_cert",
                        "rho_mom",
                        "rho_op",
                        "rho",
                        "residual_route",
                    )
                },
                "ed_oracle": ed,
                "ed_containment": {
                    "checked": True,
                    "ed_gap_upper_with_residual": _fraction_text(
                        ed_gap + ed_error
                    ),
                    "delta_cert": _fraction_text(delta_cert),
                },
                "hashes": {
                    key: final[key]
                    for key in (
                        "prepare_manifest_sha256",
                        "structure_sha256",
                        "instance_sha256",
                        "reduction_sha256",
                        "solver_manifest_sha256",
                        "solver_result_sha256",
                        "trial_vector_sha256",
                        "certificate_manifest_sha256",
                        "certificate_sha256",
                    )
                },
                "accounting": accounting,
                "final_manifest_sha256": _sha256_file(final_path),
            }
        )

    hierarchy_monotonicity = None
    exactness = None
    if is_anchor:
        by_level = {item["hierarchy"]: item for item in cells}
        ordered_levels = (
            "global-d2",
            "global-d3",
            "global-d4",
        )
        a_values = tuple(
            _summary_fraction(
                by_level[level]["certificate"]["a_cert"],
                "A_cert",
            )
            for level in ordered_levels
        )
        if any(
            left > right
            for left, right in zip(a_values, a_values[1:])
        ):
            raise ValueError(
                "N4 hierarchy lower bounds are not monotone d2/d3/d4"
            )
        b_values = {
            by_level[level]["certificate"]["b_var"]
            for level in ordered_levels
        }
        if len(b_values) != 1:
            raise ValueError(
                "N4 hierarchy cells do not share one B_var"
            )
        hierarchy_monotonicity = (
            "global-d2 <= global-d3 <= global-d4"
        )
        d4 = by_level["global-d4"]
        ed = d4["ed_oracle"]
        ed_sum = Fraction(ed["e0"]) + Fraction(ed["e1"])
        ed_error = 2 * Fraction(ed["maximum_residual"])
        difference = ed_sum - a_values[-1]
        tolerance = _summary_fraction(
            run_spec["settings"]["exactness_tolerance"],
            "exactness_tolerance",
        )
        if (
            difference + ed_error < 0
            or difference - ed_error > tolerance
        ):
            raise ValueError(
                "global-d4 exactness anchor exceeds its tolerance"
            )
        exactness = {
            "level": "global-d4",
            "tolerance": _fraction_text(tolerance),
            "ed_sum_minus_a_cert": _fraction_text(difference),
            "ed_residual_enclosure": _fraction_text(ed_error),
            "passed": True,
        }

    summary = {
        "schema_version": 2,
        "purpose": "independently-checked-ky-fan-run-summary",
        "status": "verified",
        "run_spec_sha256": _sha256_file(run_spec_path),
        "physical_contract": {
            "hamiltonian": HAMILTONIAN,
            "rabi_coefficient": "+1",
            "boundary": "periodic",
            "blockade": "n_i n_{i+1}=0 including the wrap bond",
            "symmetry": "all D_N sectors",
            "target": "multiplicity-counted global E1-E0",
        },
        "cell_count": len(cells),
        "cells": cells,
        "hierarchy_monotonicity": hierarchy_monotonicity,
        "exactness_anchor": exactness,
        "thermodynamic_limit_conclusion": (
            "none; finite-N positivity is not a thermodynamic certificate"
        ),
    }
    summary_path = selections[0].run_directory / (
        "certification-summary.json"
    )
    if summary_path.exists():
        raise FileExistsError(
            "certification summary already exists"
        )
    _atomic_write_json(summary_path, summary)
    return summary


def assembly_probe(
    size: int,
    level: str,
    detuning: Fraction,
    localizer_mode: str = "sound",
    *,
    schema_version: int = 1,
    output=None,
):
    run_spec = {
        "run_dir": str(ROOT / "results/assembly-probe-unused"),
        "settings": {
            "hierarchy": level,
            "localizer_mode": localizer_mode,
        },
        "provenance": {},
        "cells": [
            {
                "cell_id": "probe",
                "params": {
                    "size": size,
                    "detuning": _fraction_text(detuning),
                },
            }
        ],
    }
    cell = select_cell(run_spec, 1)
    if schema_version not in {1, 2}:
        raise ValueError("schema_version must be 1 or 2")
    started = time.perf_counter()
    rss_before = _peak_rss_bytes()
    if schema_version == 1:
        problem = build_problem_for_cell(cell)
        with TemporaryDirectory() as directory:
            export_kyfan_problem(problem, directory)
            checked = verify_kyfan_problem(directory)
            problem_path = Path(directory) / "problem.json"
            problem_bytes = problem_path.stat().st_size
            problem_sha256 = _sha256_file(problem_path)
        result = {
            "schema_version": 1,
            "status": checked["status"],
            "size": size,
            "detuning": _fraction_text(detuning),
            "hierarchy": level,
            "localizer_mode": localizer_mode,
            "statistics": dict(problem.statistics),
            "problem_bytes": problem_bytes,
            "problem_sha256": problem_sha256,
            "assembly_wall_seconds": time.perf_counter() - started,
            "peak_rss_bytes": max(_peak_rss_bytes(), rss_before),
            "solve_estimate": estimate_solve_resources(
                problem,
                problem_bytes,
            ),
        }
    else:
        structure = build_structure_for_cell(cell)
        structure_bytes = canonical_json_bytes(
            structure_payload(structure)
        )
        structure_sha256 = logical_structure_sha256(structure)
        reduction = build_kyfan_solver_reduction(
            structure,
            structure_sha256,
        )
        reduction_payload = solver_reduction_payload(reduction)
        reduction_bytes = canonical_json_bytes(reduction_payload)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            structure_binding = export_shared_structure(
                structure,
                root / "shared",
            )
            reduction_binding = export_solver_reduction(
                reduction,
                structure_binding,
            )
            structure_check = verify_kyfan_structure(
                structure_binding.directory
            )
            reduction_check = verify_kyfan_reduction(
                reduction_binding.directory
            )
        result = {
            "schema_version": 2,
            "purpose": "presolve-readiness-v2",
            "status": "verified",
            "size": size,
            "detuning": _fraction_text(detuning),
            "hierarchy": level,
            "localizer_mode": localizer_mode,
            "structure_sha256": structure_sha256,
            "reduction_sha256": hashlib.sha256(
                reduction_bytes
            ).hexdigest(),
            "inventories": {
                "structure": {
                    "moment_basis_dimension": len(
                        structure.moment_basis
                    ),
                    "moment_variable_count": len(
                        structure.variables
                    ),
                    "logical_equality_count": len(
                        structure.equalities
                    ),
                    "logical_psd_dimensions": [
                        block.dimension
                        for block in structure.psd_blocks
                    ],
                },
                "quotient": {
                    "action_rank": (
                        reduction.quotient.action_rank
                    ),
                    "kernel_count": len(
                        reduction.quotient.kernel
                    ),
                    "slater_rank": reduction_check["slater_rank"],
                },
                "equality": {
                    "row_rank": reduction.statistics[
                        "equality_row_rank"
                    ],
                    "kept_row_count": len(
                        reduction.kept_equalities
                    ),
                    "selected_view": reduction.selected_view,
                    "solver_variable_count": reduction.statistics[
                        "solver_variable_count"
                    ],
                },
                "spatial_blocks": reduction.statistics[
                    "spatial_dimensions"
                ],
                "original_test_dimension": reduction.statistics[
                    "original_test_dimension"
                ],
                "quotient_action_rank": reduction.statistics[
                    "quotient_action_rank"
                ],
                "slater_rank": reduction_check["slater_rank"],
                "spatial_blocks": reduction.statistics[
                    "spatial_dimensions"
                ],
                "reduced_psd_dimensions": [
                    block.dimension for block in reduction.psd_blocks
                ],
                "equality_row_rank": reduction.statistics[
                    "equality_row_rank"
                ],
                "kept_equality_count": len(
                    reduction.kept_equalities
                ),
                "solver_variable_count": reduction.statistics[
                    "solver_variable_count"
                ],
                "selected_view": reduction.selected_view,
                "serialization": {
                    "structure_bytes": len(structure_bytes),
                    "reduction_bytes": len(reduction_bytes),
                    "total_bytes": (
                        len(structure_bytes) + len(reduction_bytes)
                    ),
                },
                "memory": {
                    **estimate_v2_solve_resources(reduction),
                    "wall_anchor_status": "missing",
                },
            },
            "independent_checks": {
                "structure": structure_check,
                "reduction": reduction_check,
            },
            "assembly_wall_seconds": time.perf_counter() - started,
            "peak_rss_bytes": max(_peak_rss_bytes(), rss_before),
        }
    if output is not None:
        _atomic_write_json(Path(output), result)
    return result


def _exact_plan_fraction(value, component):
    if isinstance(value, float) or isinstance(value, bool):
        raise ValueError(f"{component} must be an exact rational")
    try:
        return Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError) as error:
        raise ValueError(
            f"{component} must be an exact rational"
        ) from error


def _unique_sequence(values, component):
    values = tuple(values)
    if len(set(values)) != len(values):
        raise ValueError(f"duplicate {component} values are forbidden")
    if not values:
        raise ValueError(f"{component} must be non-empty")
    return values


def plan_v2_run(
    output_directory,
    sizes,
    detunings,
    levels,
    localizer_mode,
    exactness_tolerance=None,
) -> dict:
    """Write a deterministic exact schema-v2 Cartesian run plan."""
    sizes = _unique_sequence(tuple(sizes), "size")
    for size in sizes:
        if isinstance(size, bool) or not isinstance(size, int):
            raise ValueError("sizes must be integers")
        if not 4 <= size <= 20:
            raise ValueError("every size must satisfy 4 <= N <= 20")
    detunings = tuple(
        _exact_plan_fraction(value, "detuning")
        for value in detunings
    )
    detunings = _unique_sequence(detunings, "detuning")
    if any(not Fraction(0) <= value <= Fraction(3) for value in detunings):
        raise ValueError("every detuning must lie in [0,3]")
    levels = _unique_sequence(tuple(map(str, levels)), "level")
    supported_levels = {
        "global-d2",
        "global-d3",
        "global-d4",
        *LOCAL_LEVEL_BY_NAME,
    }
    if any(level not in supported_levels for level in levels):
        raise ValueError("unsupported Ky Fan hierarchy in v2 plan")
    if localizer_mode != "sound":
        raise ValueError(
            "production v2 plans require sound localizing constraints"
        )
    if exactness_tolerance is not None:
        exactness_tolerance = _exact_plan_fraction(
            exactness_tolerance,
            "exactness tolerance",
        )
        if exactness_tolerance < 0:
            raise ValueError(
                "exactness tolerance must be nonnegative"
            )

    points = [
        (size, detuning, level)
        for size in sizes
        for detuning in detunings
        for level in levels
    ]
    if len(set(points)) != len(points):
        raise ValueError("duplicate v2 cells are forbidden")
    output_directory = Path(output_directory).resolve()
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError("v2 output directory must be empty")
    output_directory.mkdir(parents=True, exist_ok=True)
    settings = {
        "localizer_mode": localizer_mode,
        "trial_bits": 40,
    }
    if exactness_tolerance is not None:
        settings["exactness_tolerance"] = _fraction_text(
            exactness_tolerance
        )
    run_spec = {
        "schema_version": 2,
        "purpose": "planned-ky-fan-reduced-run",
        "run_id": output_directory.name,
        "run_dir": str(output_directory),
        "settings": settings,
        "provenance": {
            "physical_contract": "periodic-pxp-v1",
            "planner": "plan_v2_run",
        },
        "cells": [
            {
                "cell_id": f"cell-{index:04d}",
                "params": {
                    "size": size,
                    "detuning": _fraction_text(detuning),
                    "hierarchy": level,
                },
            }
            for index, (size, detuning, level) in enumerate(
                points,
                start=1,
            )
        ],
    }
    run_spec_path = output_directory / "run_spec.json"
    _atomic_write_json(run_spec_path, run_spec)
    return {
        "status": "planned",
        "schema_version": 2,
        "cell_count": len(points),
        "run_spec": str(run_spec_path),
        "run_spec_sha256": _sha256_file(run_spec_path),
    }


def plan_escalation(
    from_run,
    to_level: str,
    output_directory,
    robustness_margin: Fraction = Fraction(0),
):
    if to_level not in LOCAL_LEVEL_BY_NAME:
        raise ValueError("escalation target must be L0, L1, L2, or L3")
    robustness_margin = Fraction(robustness_margin)
    if robustness_margin < 0:
        raise ValueError("robustness margin must be nonnegative")
    from_run = Path(from_run).resolve()
    run_spec_path = (
        from_run
        if from_run.name == "run_spec.json"
        else from_run / "run_spec.json"
    )
    source = _load_json(run_spec_path)
    source_directory = _resolve_run_directory(source["run_dir"])
    selected = []
    retries = []
    for cell in source["cells"]:
        manifest_path = (
            source_directory
            / "cells"
            / cell["cell_id"]
            / "manifest.json"
        )
        if not manifest_path.is_file():
            retries.append(
                {
                    "source_cell_id": cell["cell_id"],
                    "reason": "missing-final-manifest",
                }
            )
            continue
        manifest = _load_json(manifest_path)
        if manifest.get("independent_check_passed") is not True:
            selected.append(
                (cell, "independent-check-failed")
            )
            continue
        delta = Fraction(manifest["certificate"]["delta_cert"])
        if manifest["certificate_status"] == "not_certified":
            selected.append((cell, "not-certified"))
        elif delta < robustness_margin:
            selected.append((cell, "below-robustness-margin"))

    output_directory = Path(output_directory).resolve()
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError("escalation output directory must be empty")
    output_directory.mkdir(parents=True, exist_ok=True)
    run_spec = {
        "run_id": output_directory.name,
        "run_dir": str(output_directory),
        "settings": {
            **source.get("settings", {}),
            "hierarchy": to_level,
            "localizer_mode": "sound",
        },
        "provenance": {
            **source.get("provenance", {}),
            "escalated_from": str(run_spec_path),
            "robustness_margin": _fraction_text(robustness_margin),
        },
        "cells": [
            {
                "cell_id": f"cell-{index:04d}",
                "params": {
                    **cell.get("params", {}),
                    "source_cell_id": cell["cell_id"],
                    "escalation_reason": reason,
                },
            }
            for index, (cell, reason) in enumerate(selected, start=1)
        ],
        "operational_retry_candidates": retries,
    }
    _atomic_write_json(output_directory / "run_spec.json", run_spec)
    return {
        "status": "planned",
        "selected_cells": len(selected),
        "retry_candidates": len(retries),
        "run_spec": str(output_directory / "run_spec.json"),
    }


def _comma_values(text, component):
    values = tuple(str(text).split(","))
    if not values or any(not value for value in values):
        raise ValueError(f"{component} must be a non-empty comma list")
    return values


def _cli_fraction(text, component):
    text = str(text)
    parts = text.split("/")
    if (
        len(parts) not in {1, 2}
        or any(
            not part
            or not part.lstrip("+-").isdigit()
            for part in parts
        )
    ):
        raise ValueError(
            f"{component} must use integer or numerator/denominator syntax"
        )
    return Fraction(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Three-stage finite-N Ky Fan cell runner"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("prepare-cell", "solve-local-cell", "certify-cell"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--run-spec", required=True)
        subparser.add_argument("--cell-index", required=True, type=int)

    prepare_run_parser = subparsers.add_parser("prepare-run")
    prepare_run_parser.add_argument("--run-spec", required=True)
    prepare_run_parser.add_argument("--max-cells", type=int)
    certify_run_parser = subparsers.add_parser("certify-run")
    certify_run_parser.add_argument("--run-spec", required=True)

    probe_parser = subparsers.add_parser("assembly-probe")
    probe_parser.add_argument("--size", required=True, type=int)
    probe_parser.add_argument("--level", required=True)
    probe_parser.add_argument("--detuning", required=True)
    probe_parser.add_argument("--localizer-mode", default="sound")
    probe_parser.add_argument(
        "--schema-version",
        type=int,
        choices=(1, 2),
        default=1,
    )
    probe_parser.add_argument("--output")

    v2_plan_parser = subparsers.add_parser("plan-v2-run")
    v2_plan_parser.add_argument("--output", required=True)
    v2_plan_parser.add_argument("--sizes", required=True)
    v2_plan_parser.add_argument("--detunings", required=True)
    v2_plan_parser.add_argument("--levels", required=True)
    v2_plan_parser.add_argument("--localizer-mode", default="sound")
    v2_plan_parser.add_argument("--exactness-tolerance")

    escalation_parser = subparsers.add_parser("plan-escalation")
    escalation_parser.add_argument("--from-run", required=True)
    escalation_parser.add_argument("--to-level", required=True)
    escalation_parser.add_argument("--output", required=True)
    escalation_parser.add_argument("--robustness-margin", default="0")

    arguments = parser.parse_args(argv)
    if arguments.command == "prepare-cell":
        result = prepare_cell(arguments.run_spec, arguments.cell_index)
    elif arguments.command == "solve-local-cell":
        result = solve_local_cell(
            arguments.run_spec,
            arguments.cell_index,
        )
    elif arguments.command == "certify-cell":
        result = certify_cell(arguments.run_spec, arguments.cell_index)
    elif arguments.command == "prepare-run":
        result = prepare_run(arguments.run_spec, arguments.max_cells)
    elif arguments.command == "certify-run":
        result = certify_run(arguments.run_spec)
    elif arguments.command == "assembly-probe":
        result = assembly_probe(
            arguments.size,
            arguments.level,
            _cli_fraction(arguments.detuning, "detuning"),
            arguments.localizer_mode,
            schema_version=arguments.schema_version,
            output=arguments.output,
        )
    elif arguments.command == "plan-v2-run":
        result = plan_v2_run(
            arguments.output,
            tuple(
                int(value)
                for value in _comma_values(arguments.sizes, "sizes")
            ),
            tuple(
                _cli_fraction(value, "detuning")
                for value in _comma_values(
                    arguments.detunings,
                    "detunings",
                )
            ),
            _comma_values(arguments.levels, "levels"),
            arguments.localizer_mode,
            (
                None
                if arguments.exactness_tolerance is None
                else _cli_fraction(
                    arguments.exactness_tolerance,
                    "exactness tolerance",
                )
            ),
        )
    else:
        result = plan_escalation(
            arguments.from_run,
            arguments.to_level,
            arguments.output,
            Fraction(arguments.robustness_margin),
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
