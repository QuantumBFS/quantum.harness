"""N=6 ED reveal, D+0 overlap, and operator-span diagnostics."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import subprocess
import time
from collections import defaultdict
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np

from benchmark_v0.fock_ed import (
    apply_annihilation,
    apply_creation,
    fixed_m_basis,
    hamiltonian_matrix,
    l_squared_matrix,
)
from benchmark_v0.lll_coulomb import (
    antisymmetrized_pair_matrix,
    coulomb_integrals,
)
from route_d_plus.future.verify import (
    load_json,
    require_artifact,
    sha256_file,
    validate_dispatch,
    validate_payload,
)
from route_d_plus.scalar import FockSpace, scalar_generator_pair
from route_d_plus.tensor import canonical_tensor

N_ELECTRONS = 6
TWO_Q = 15
RAW_RANKS = (2, 3, 4)
DOMAIN_VERSION = "challenge-15-route-d-plus-phase7-domain-v1"
TASK_VERSION = "challenge-15-route-d-plus-future-task-certificate-v1"
DEPENDENCY_VERSION = "challenge-15-route-d-plus-future-dependency-v1"
DISPATCH_VERSION = "challenge-15-route-d-plus-future-dispatch-v1"
STAGE_GATE_VERSION = "challenge-15-route-d-plus-future-stage-gate-v1"
MODULE_ROOT = Path(__file__).resolve().parent


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def artifact(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def git_output(repo_root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def require_clean_revision(repo_root: Path) -> str:
    revision = git_output(repo_root, "rev-parse", "HEAD")
    if git_output(repo_root, "status", "--porcelain"):
        raise RuntimeError("Phase 7 requires a clean source checkout")
    return revision


def _phase7_tasks() -> list[dict[str, Any]]:
    tasks = []
    for magnetic_number in range(-2, 3):
        sign = (
            f"minus-{abs(magnetic_number)}"
            if magnetic_number < 0
            else f"plus-{magnetic_number}"
            if magnetic_number > 0
            else "zero"
        )
        tasks.append(
            {
                "task_id": f"m-{sign}",
                "kind": "ed-sector",
                "run_dir": f"tasks/m-{sign}",
                "required_gates": [
                    "sector_energy",
                    "sector_normalization",
                    "symmetry_readback",
                    "slurm_evidence",
                ],
                "n_electrons": N_ELECTRONS,
                "m_sector": magnetic_number,
            }
        )
    tasks.extend(
        [
            {
                "task_id": "overlap",
                "kind": "overlap",
                "run_dir": "tasks/overlap",
                "required_gates": [
                    "ground_overlap",
                    "tower_overlap",
                    "gap_comparison",
                    "slurm_evidence",
                ],
                "n_electrons": N_ELECTRONS,
                "m_sector": None,
            },
            {
                "task_id": "span-ceiling",
                "kind": "span-ceiling",
                "run_dir": "tasks/span-ceiling",
                "required_gates": [
                    "ground_span_ceiling",
                    "tower_span_ceiling",
                    "slurm_evidence",
                ],
                "n_electrons": N_ELECTRONS,
                "m_sector": None,
            },
        ]
    )
    return tasks


def authorize(
    *,
    repo_root: Path,
    run_root: Path,
    run_id: str,
    architecture_path: Path,
    checkpoint_paths: list[Path],
    capacity_protocol_path: Path,
) -> dict[str, Any]:
    revision = require_clean_revision(repo_root)
    if len(checkpoint_paths) != 3:
        raise ValueError("the reveal must bind exactly three frozen checkpoints")
    authorization_path = run_root / "authorization.json"
    authorization = {
        "schema_version": (
            "challenge-15-route-d-plus-phase7-authorization-v1"
        ),
        "authorized_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "instruction": "phase7 ed不需要禁止，直接跑",
        "scope": (
            "run N=6 Phase 7 ED concurrently with unfinished "
            "Phase 6 measurement"
        ),
        "phase6_frozen": False,
        "checkpoint_modified": False,
        "capacity_protocol_modified": False,
        "heldout_accessed": False,
        "beyond_ed_accessed": False,
    }
    schema = load_json(MODULE_ROOT / "phase7-authorization.schema.json")
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    ).validate(authorization)
    write_json(authorization_path, authorization)

    dependency_path = run_root / "user-authorized-dependency.json"
    dependency = {
        "schema_version": DEPENDENCY_VERSION,
        "kind": "user-authorized-phase7-reveal",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_revision": revision,
        "authorization": artifact(authorization_path),
        "architecture": artifact(architecture_path),
        "checkpoints": [artifact(path) for path in checkpoint_paths],
        "capacity_protocol": artifact(capacity_protocol_path),
        "phase6_frozen": False,
        "capacity_protocol_modified": False,
        "checkpoint_modified": False,
        "heldout_accessed": False,
        "beyond_ed_accessed": False,
        "passed": True,
    }
    validate_payload(dependency, "dependency.schema.json")
    write_json(dependency_path, dependency)

    dispatch_path = run_root / "phase7-dispatch.json"
    dispatch = {
        "schema_version": DISPATCH_VERSION,
        "stage": "phase7",
        "run_id": run_id,
        "run_root": str(run_root.resolve()),
        "source_revision": revision,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "prerequisites": [
            {
                "kind": dependency["kind"],
                **artifact(dependency_path),
            }
        ],
        "tasks": _phase7_tasks(),
    }
    validate_dispatch(dispatch)
    write_json(dispatch_path, dispatch)
    return dispatch


def prepare_integrals(output_path: Path) -> None:
    integrals = coulomb_integrals(TWO_Q)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, integrals=integrals)


def authorize_remediation(
    *,
    repo_root: Path,
    run_root: Path,
    run_id: str,
    baseline_phase7_aggregate_path: Path,
    remediation_certificate_path: Path,
    remediation_readback_path: Path,
    architecture_path: Path,
    checkpoint_paths: list[Path],
    capacity_protocol_path: Path,
) -> dict[str, Any]:
    revision = require_clean_revision(repo_root)
    if len(checkpoint_paths) != 3:
        raise ValueError("reevaluation must bind exactly three checkpoints")
    baseline = load_json(baseline_phase7_aggregate_path)
    validate_payload(baseline, "aggregate-certificate.schema.json")
    if not baseline["passed"] or baseline["stage"] != "phase7":
        raise RuntimeError("baseline Phase 7 aggregate did not pass")
    remediation = load_json(remediation_certificate_path)
    schema = load_json(MODULE_ROOT / "optimization-remediation.schema.json")
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    ).validate(remediation)
    readback = load_json(remediation_readback_path)
    readback_schema = load_json(
        MODULE_ROOT / "optimization-remediation-readback.schema.json"
    )
    jsonschema.Draft202012Validator(
        readback_schema, format_checker=jsonschema.FormatChecker()
    ).validate(readback)
    if (
        not remediation["passed"]
        or not readback["passed"]
        or readback["remediation_certificate"]["sha256"]
        != sha256_file(remediation_certificate_path)
    ):
        raise RuntimeError("optimizer remediation/readback gate did not pass")
    expected_checkpoint_hashes = {
        item["seed"]: item["checkpoint"]["sha256"]
        for item in remediation["seed_results"]
    }
    observed = {}
    checkpoint_schema = load_json(
        MODULE_ROOT / "remediated-checkpoint.schema.json"
    )
    checkpoint_validator = jsonschema.Draft202012Validator(
        checkpoint_schema,
        format_checker=jsonschema.FormatChecker(),
    )
    for path in checkpoint_paths:
        checkpoint = load_json(path)
        checkpoint_validator.validate(checkpoint)
        observed[checkpoint["seed"]] = sha256_file(path)
    if observed != expected_checkpoint_hashes:
        raise RuntimeError("remediated checkpoint set/hash mismatch")

    dependency_path = run_root / "dplus0-remediation-dependency.json"
    dependency = {
        "schema_version": DEPENDENCY_VERSION,
        "kind": "dplus0-remediation-gate",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_revision": revision,
        "baseline_phase7_aggregate": artifact(
            baseline_phase7_aggregate_path
        ),
        "remediation_certificate": artifact(
            remediation_certificate_path
        ),
        "remediation_readback": artifact(remediation_readback_path),
        "architecture": artifact(architecture_path),
        "checkpoints": [artifact(path) for path in checkpoint_paths],
        "capacity_protocol": artifact(capacity_protocol_path),
        "capacity": "D+0",
        "architecture_modified": False,
        "ed_used_for_gradient": False,
        "ed_used_for_checkpoint_selection": False,
        "heldout_accessed": False,
        "beyond_ed_accessed": False,
        "passed": True,
    }
    validate_payload(dependency, "dependency.schema.json")
    write_json(dependency_path, dependency)
    dispatch_path = run_root / "phase7-dispatch.json"
    dispatch = {
        "schema_version": DISPATCH_VERSION,
        "stage": "phase7",
        "run_id": run_id,
        "run_root": str(run_root.resolve()),
        "source_revision": revision,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "prerequisites": [
            {"kind": dependency["kind"], **artifact(dependency_path)}
        ],
        "tasks": _phase7_tasks(),
    }
    validate_dispatch(dispatch)
    write_json(dispatch_path, dispatch)
    return dispatch


def _route_gauge_phases(basis: tuple[int, ...]) -> np.ndarray:
    phases = []
    for state in basis:
        phase = 1
        for orbital in range(TWO_Q + 1):
            if state & (1 << orbital):
                phase *= -1 if (TWO_Q - orbital) % 2 else 1
        phases.append(phase)
    return np.asarray(phases, dtype=np.float64)


def _sector(
    magnetic_number: int,
    integrals: np.ndarray,
) -> tuple[tuple[int, ...], np.ndarray, np.ndarray]:
    basis = fixed_m_basis(
        N_ELECTRONS, TWO_Q, float(magnetic_number)
    )
    pairs, pair_matrix = antisymmetrized_pair_matrix(integrals)
    benchmark_hamiltonian = hamiltonian_matrix(basis, pairs, pair_matrix)
    phases = _route_gauge_phases(basis)
    hamiltonian = (
        phases[:, None] * benchmark_hamiltonian * phases[None, :]
    )
    hamiltonian = 0.5 * (hamiltonian + hamiltonian.T.conj())
    l_squared = l_squared_matrix(
        basis,
        two_q=TWO_Q,
        target_m=float(magnetic_number),
    )
    return basis, hamiltonian, l_squared


def _lowest_l_state(
    hamiltonian: np.ndarray,
    l_squared: np.ndarray,
    target_l: int,
) -> tuple[float, np.ndarray, dict[str, float]]:
    l_values, l_vectors = np.linalg.eigh(l_squared)
    target = float(target_l * (target_l + 1))
    selected = np.isclose(l_values, target, rtol=0.0, atol=1.0e-9)
    subspace = l_vectors[:, selected]
    if subspace.shape[1] == 0:
        raise RuntimeError(f"empty L={target_l} subspace")
    projected = subspace.T.conj() @ hamiltonian @ subspace
    energies, vectors = np.linalg.eigh(projected)
    vector = subspace @ vectors[:, 0]
    vector /= np.linalg.norm(vector)
    expectation = float(np.real(vector.conj() @ l_squared @ vector))
    variance = float(
        max(
            0.0,
            np.real(vector.conj() @ l_squared @ l_squared @ vector)
            - expectation**2,
        )
    )
    residual = float(
        np.linalg.norm(hamiltonian @ vector - energies[0] * vector)
    )
    return (
        float(energies[0]),
        vector,
        {
            "l2_expectation": expectation,
            "l2_variance": variance,
            "eigen_residual": residual,
            "subspace_dimension": int(subspace.shape[1]),
        },
    )


@cache
def _laughlin_polynomial() -> dict[tuple[int, ...], int]:
    coefficients: dict[tuple[int, ...], int] = {(0,) * N_ELECTRONS: 1}
    for first in range(N_ELECTRONS):
        for second in range(first + 1, N_ELECTRONS):
            updated: dict[tuple[int, ...], int] = defaultdict(int)
            for powers, value in coefficients.items():
                for first_power in range(4):
                    next_powers = list(powers)
                    next_powers[first] += first_power
                    next_powers[second] += 3 - first_power
                    if (
                        next_powers[first] <= TWO_Q
                        and next_powers[second] <= TWO_Q
                    ):
                        factor = (
                            math.comb(3, first_power)
                            * (-1) ** (3 - first_power)
                        )
                        updated[tuple(next_powers)] += value * factor
            coefficients = {
                powers: value
                for powers, value in updated.items()
                if value
            }
    return coefficients


@cache
def _laughlin_coefficients(basis: tuple[int, ...]) -> np.ndarray:
    polynomial = _laughlin_polynomial()
    normalizations = np.sqrt(
        (TWO_Q + 1)
        * np.asarray(
            [math.comb(TWO_Q, power) for power in range(TWO_Q + 1)]
        )
        / (4.0 * math.pi)
    )
    result = np.zeros(len(basis), dtype=np.complex128)
    for index, state in enumerate(basis):
        occupied = tuple(
            orbital
            for orbital in range(TWO_Q + 1)
            if state & (1 << orbital)
        )
        coefficient = polynomial.get(occupied, 0)
        result[index] = (
            coefficient
            * math.sqrt(math.factorial(N_ELECTRONS))
            / float(np.prod(normalizations[list(occupied)]))
        )
    norm = np.linalg.norm(result)
    if norm == 0.0:
        raise RuntimeError("Laughlin coefficient reconstruction is empty")
    return result / norm


def _one_body_between(
    source_basis: tuple[int, ...],
    target_basis: tuple[int, ...],
    orbital_matrix: np.ndarray,
) -> np.ndarray:
    target_index = {
        state: index for index, state in enumerate(target_basis)
    }
    result = np.zeros(
        (len(target_basis), len(source_basis)), dtype=np.complex128
    )
    for column, state in enumerate(source_basis):
        for source_orbital in range(TWO_Q + 1):
            removed = apply_annihilation(state, source_orbital)
            if removed is None:
                continue
            intermediate, first_sign = removed
            for target_orbital in range(TWO_Q + 1):
                value = orbital_matrix[target_orbital, source_orbital]
                if abs(value) < 1.0e-15:
                    continue
                created = apply_creation(intermediate, target_orbital)
                if created is None:
                    continue
                final, second_sign = created
                row = target_index.get(final)
                if row is not None:
                    result[row, column] += (
                        first_sign * second_sign * value
                    )
    return result


@cache
def _sector_generators(basis: tuple[int, ...]) -> tuple[np.ndarray, ...]:
    space = FockSpace(
        n_orbitals=TWO_Q + 1,
        n_particles=N_ELECTRONS,
        states=basis,
        index={state: index for index, state in enumerate(basis)},
    )
    return tuple(
        scalar_generator_pair(space, TWO_Q, rank) for rank in RAW_RANKS
    )


@cache
def _mother(
    magnetic_number: int,
    basis: tuple[int, ...],
) -> np.ndarray:
    zero_basis = fixed_m_basis(N_ELECTRONS, TWO_Q, 0.0)
    laughlin = _laughlin_coefficients(zero_basis)
    if magnetic_number == 0:
        density = _one_body_between(
            zero_basis,
            basis,
            canonical_tensor(TWO_Q, 2, 0),
        )
    else:
        density = _one_body_between(
            zero_basis,
            basis,
            canonical_tensor(TWO_Q, 2, magnetic_number),
        )
    tower = density @ laughlin
    norm = np.linalg.norm(tower)
    if norm == 0.0:
        raise RuntimeError(f"empty tower mother for M={magnetic_number}")
    return tower / norm


@cache
def _ground_mother(basis: tuple[int, ...]) -> np.ndarray:
    return _laughlin_coefficients(basis)


def _complex_vector(payload: dict[str, Any]) -> np.ndarray:
    return np.asarray(payload["real"]) + 1.0j * np.asarray(payload["imag"])


def _candidate(
    mother: np.ndarray,
    generators: list[np.ndarray],
    coefficients: np.ndarray,
    architecture: dict[str, Any],
) -> np.ndarray:
    mean = np.asarray(architecture["centering_mean"], dtype=np.float64)
    whitening = np.asarray(architecture["whitening"], dtype=np.float64)
    raw_weights = coefficients @ whitening
    identity_weight = 1.0 - coefficients @ (whitening @ mean)
    vector = identity_weight * mother
    for weight, generator in zip(raw_weights, generators, strict=True):
        vector = vector + weight * (generator @ mother)
    norm = np.linalg.norm(vector)
    if norm == 0.0:
        raise RuntimeError("zero D+0 candidate")
    return vector / norm


def _fidelity(left: np.ndarray, right: np.ndarray) -> float:
    return float(abs(np.vdot(left, right)) ** 2)


def _span_fidelity(
    exact: np.ndarray,
    mother: np.ndarray,
    generators: list[np.ndarray],
) -> tuple[float, int]:
    columns = np.column_stack(
        [mother] + [generator @ mother for generator in generators]
    )
    left, singular_values, _ = np.linalg.svd(columns, full_matrices=False)
    retained = singular_values > singular_values[0] * 1.0e-12
    basis = left[:, retained]
    fidelity = float(np.linalg.norm(basis.T.conj() @ exact) ** 2)
    return min(1.0, max(0.0, fidelity)), int(np.count_nonzero(retained))


def _load_inputs(
    dispatch: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    dependency = load_json(require_artifact(dispatch["prerequisites"][0]))
    architecture = load_json(require_artifact(dependency["architecture"]))
    checkpoints = [
        load_json(require_artifact(reference))
        for reference in dependency["checkpoints"]
    ]
    return dependency, architecture, checkpoints


def _ed_sector_result(
    magnetic_number: int,
    integrals: np.ndarray,
) -> tuple[dict[str, Any], dict[str, Any]]:
    basis, hamiltonian, l_squared = _sector(magnetic_number, integrals)
    energy, state, diagnostics = _lowest_l_state(
        hamiltonian, l_squared, 2
    )
    results: dict[str, Any] = {
        "m_sector": magnetic_number,
        "basis_dimension": len(basis),
        "l2_energy": energy,
    }
    if magnetic_number == 0:
        ground_energy, _, ground_diagnostics = _lowest_l_state(
            hamiltonian, l_squared, 0
        )
        results["ground_energy"] = ground_energy
        diagnostics["ground"] = ground_diagnostics
    diagnostics["state_norm"] = float(np.linalg.norm(state))
    diagnostics["hamiltonian_hermiticity_residual"] = float(
        np.max(np.abs(hamiltonian - hamiltonian.T.conj()))
    )
    return results, diagnostics


def _overlap_result(
    integrals: np.ndarray,
    architecture: dict[str, Any],
    checkpoints: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    sector_cache = {
        magnetic_number: _sector(magnetic_number, integrals)
        for magnetic_number in range(-2, 3)
    }
    exact: dict[int, tuple[float, np.ndarray]] = {}
    for magnetic_number, (_, hamiltonian, l_squared) in sector_cache.items():
        energy, vector, _ = _lowest_l_state(hamiltonian, l_squared, 2)
        exact[magnetic_number] = (energy, vector)
    zero_basis, zero_hamiltonian, zero_l_squared = sector_cache[0]
    ed_ground_energy, ed_ground, _ = _lowest_l_state(
        zero_hamiltonian, zero_l_squared, 0
    )
    records = []
    for checkpoint in sorted(checkpoints, key=lambda item: item["seed"]):
        ground_generators = _sector_generators(zero_basis)
        ground = _candidate(
            _ground_mother(zero_basis),
            ground_generators,
            _complex_vector(checkpoint["ground_coefficients"]),
            architecture,
        )
        ground_energy = float(
            np.real(ground.conj() @ zero_hamiltonian @ ground)
        )
        tower_fidelities = []
        tower_energies = []
        for magnetic_number in range(-2, 3):
            basis, hamiltonian, _ = sector_cache[magnetic_number]
            tower = _candidate(
                _mother(magnetic_number, basis),
                _sector_generators(basis),
                _complex_vector(checkpoint["tower_coefficients"]),
                architecture,
            )
            tower_fidelities.append(
                _fidelity(exact[magnetic_number][1], tower)
            )
            tower_energies.append(
                float(np.real(tower.conj() @ hamiltonian @ tower))
            )
        tower_energy = float(np.mean(tower_energies))
        records.append(
            {
                "seed": checkpoint["seed"],
                "ground_fidelity": _fidelity(ed_ground, ground),
                "tower_fidelity_mean": float(np.mean(tower_fidelities)),
                "tower_fidelity_by_m": {
                    str(m): value
                    for m, value in zip(
                        range(-2, 3), tower_fidelities, strict=True
                    )
                },
                "ground_energy": ground_energy,
                "tower_energy": tower_energy,
                "gap": tower_energy - ground_energy,
            }
        )
    ed_tower_energy = float(
        np.mean([exact[m][0] for m in range(-2, 3)])
    )
    ed_gap = ed_tower_energy - ed_ground_energy
    mean_gap = float(np.mean([record["gap"] for record in records]))
    results = {
        "ed_ground_energy": ed_ground_energy,
        "ed_tower_energy": ed_tower_energy,
        "ed_gap": ed_gap,
        "checkpoint_records": records,
        "ground_fidelity_mean": float(
            np.mean([record["ground_fidelity"] for record in records])
        ),
        "tower_fidelity_mean": float(
            np.mean(
                [record["tower_fidelity_mean"] for record in records]
            )
        ),
        "dplus_gap_mean": mean_gap,
        "gap_absolute_error": abs(mean_gap - ed_gap),
        "seed_aggregation": "arithmetic-mean-of-three-pre-frozen-seeds",
    }
    diagnostics = {
        "checkpoint_count": len(records),
        "multiplet_splitting": float(
            max(exact[m][0] for m in exact)
            - min(exact[m][0] for m in exact)
        ),
    }
    return results, diagnostics


def _span_result(
    integrals: np.ndarray,
) -> tuple[dict[str, Any], dict[str, Any]]:
    zero_basis, zero_hamiltonian, zero_l_squared = _sector(0, integrals)
    _, exact_ground, _ = _lowest_l_state(
        zero_hamiltonian, zero_l_squared, 0
    )
    ground_mother = _ground_mother(zero_basis)
    ground_generators = _sector_generators(zero_basis)
    ground_fidelity, ground_rank = _span_fidelity(
        exact_ground, ground_mother, ground_generators
    )
    tower_values = {}
    tower_ranks = {}
    for magnetic_number in range(-2, 3):
        basis, hamiltonian, l_squared = _sector(
            magnetic_number, integrals
        )
        _, exact_tower, _ = _lowest_l_state(
            hamiltonian, l_squared, 2
        )
        fidelity, rank = _span_fidelity(
            exact_tower,
            _mother(magnetic_number, basis),
            _sector_generators(basis),
        )
        tower_values[str(magnetic_number)] = fidelity
        tower_ranks[str(magnetic_number)] = rank
    return (
        {
            "ground_span_fidelity": ground_fidelity,
            "tower_span_fidelity_mean": float(
                np.mean(list(tower_values.values()))
            ),
            "tower_span_fidelity_by_m": tower_values,
            "krylov_depth": 1,
            "generator_ranks": list(RAW_RANKS),
        },
        {
            "ground_span_rank": ground_rank,
            "tower_span_rank_by_m": tower_ranks,
        },
    )


def _slurm_record(started: float) -> dict[str, Any]:
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not os.environ.get("SLURM_JOB_ID") or not visible:
        raise RuntimeError("Phase 7 worker requires a Slurm GPU allocation")
    return {
        "job_id": os.environ["SLURM_JOB_ID"],
        "cluster_name": os.environ.get("SLURM_CLUSTER_NAME", "hpccube-xh5"),
        "node_list": os.environ.get("SLURM_NODELIST", "unknown"),
        "partition": os.environ.get("SLURM_JOB_PARTITION", "unknown"),
        "gpu_devices": [part for part in visible.split(",") if part],
        "cpus_per_task": int(os.environ.get("SLURM_CPUS_PER_TASK", "1")),
        "memory_mb": int(
            os.environ.get("SLURM_MEM_PER_NODE")
            or os.environ.get("SLURM_MEM_PER_CPU")
            or "1"
        ),
        "elapsed_seconds": time.monotonic() - started,
        "exit_code": 0,
    }


def run_task(
    *,
    repo_root: Path,
    dispatch_path: Path,
    task_id: str,
    run_dir: Path,
    integrals_path: Path,
) -> None:
    started = time.monotonic()
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    dispatch = load_json(dispatch_path)
    validate_dispatch(dispatch)
    revision = require_clean_revision(repo_root)
    if revision != dispatch["source_revision"]:
        raise RuntimeError("worker source revision differs from dispatch")
    tasks = {task["task_id"]: task for task in dispatch["tasks"]}
    task = tasks[task_id]
    expected_dir = (
        Path(dispatch["run_root"]) / task["run_dir"]
    ).resolve()
    if run_dir.resolve() != expected_dir:
        raise RuntimeError("worker run directory differs from dispatch")
    _, architecture, checkpoints = _load_inputs(dispatch)
    integrals = np.load(integrals_path)["integrals"]
    if task["kind"] == "ed-sector":
        results, diagnostics = _ed_sector_result(
            int(task["m_sector"]), integrals
        )
    elif task["kind"] == "overlap":
        results, diagnostics = _overlap_result(
            integrals, architecture, checkpoints
        )
    else:
        results, diagnostics = _span_result(integrals)
    if task["kind"] == "ed-sector":
        task_gates = {
            "sector_energy": bool(
                np.isfinite(results["l2_energy"])
                and (
                    "ground_energy" not in results
                    or np.isfinite(results["ground_energy"])
                )
            ),
            "sector_normalization": (
                abs(diagnostics["state_norm"] - 1.0) < 1.0e-10
            ),
            "symmetry_readback": (
                abs(diagnostics["l2_expectation"] - 6.0) < 1.0e-8
                and diagnostics["l2_variance"] < 1.0e-7
                and diagnostics["eigen_residual"] < 1.0e-8
                and diagnostics["hamiltonian_hermiticity_residual"]
                < 1.0e-10
            ),
            "slurm_evidence": True,
        }
    elif task["kind"] == "overlap":
        fidelities = [
            results["ground_fidelity_mean"],
            results["tower_fidelity_mean"],
        ]
        task_gates = {
            "ground_overlap": bool(
                np.isfinite(fidelities[0])
                and 0.0 <= fidelities[0] <= 1.0 + 1.0e-10
            ),
            "tower_overlap": bool(
                np.isfinite(fidelities[1])
                and 0.0 <= fidelities[1] <= 1.0 + 1.0e-10
            ),
            "gap_comparison": bool(
                np.isfinite(results["ed_gap"])
                and np.isfinite(results["dplus_gap_mean"])
                and np.isfinite(results["gap_absolute_error"])
            ),
            "slurm_evidence": True,
        }
    else:
        task_gates = {
            "ground_span_ceiling": bool(
                np.isfinite(results["ground_span_fidelity"])
                and 0.0
                <= results["ground_span_fidelity"]
                <= 1.0 + 1.0e-10
            ),
            "tower_span_ceiling": bool(
                np.isfinite(results["tower_span_fidelity_mean"])
                and 0.0
                <= results["tower_span_fidelity_mean"]
                <= 1.0 + 1.0e-10
            ),
            "slurm_evidence": True,
        }
    if not all(task_gates.values()):
        raise RuntimeError(f"Phase 7 domain integrity gate failed: {task_gates}")
    domain = {
        "schema_version": DOMAIN_VERSION,
        "task_id": task_id,
        "kind": task["kind"],
        "source_revision": revision,
        "n_electrons": N_ELECTRONS,
        "two_q": TWO_Q,
        "hamiltonian_convention": (
            "pair_only_chord-route_d_plus_orbital_gauge"
        ),
        "results": results,
        "diagnostics": diagnostics,
        "gates": task_gates,
        "passed": True,
    }
    schema_path = MODULE_ROOT / "phase7-domain.schema.json"
    schema = load_json(schema_path)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    ).validate(domain)
    domain_path = run_dir / "domain-certificate.json"
    write_json(domain_path, domain)
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    for path in (stdout_path, stderr_path):
        if not path.exists():
            path.touch()
    certificate = {
        "schema_version": TASK_VERSION,
        "stage": "phase7",
        "task_id": task_id,
        "kind": task["kind"],
        "run_dir": str(run_dir.resolve()),
        "source_revision": revision,
        "git_dirty": False,
        "started_at_utc": started_at,
        "finished_at_utc": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(),
        "input_artifacts": [
            {
                "path": reference["path"],
                "sha256": reference["sha256"],
            }
            for reference in dispatch["prerequisites"]
        ]
        + [artifact(integrals_path)],
        "slurm": _slurm_record(started),
        "logs": {
            "stdout": artifact(stdout_path),
            "stderr": artifact(stderr_path),
        },
        "domain_certificate": {
            **artifact(domain_path),
            "schema_path": str(schema_path.resolve()),
            "schema_sha256": sha256_file(schema_path),
            "schema_valid": True,
        },
        "checkpoint": None,
        "gates": task_gates,
        "passed": True,
    }
    validate_payload(certificate, "task-certificate.schema.json")
    write_json(run_dir / "task-certificate.json", certificate)


def finalize(
    *,
    dispatch_path: Path,
    stage_gate_path: Path,
) -> dict[str, Any]:
    dispatch = load_json(dispatch_path)
    validate_dispatch(dispatch)
    domains = {
        task["task_id"]: load_json(
            Path(dispatch["run_root"])
            / task["run_dir"]
            / "domain-certificate.json"
        )
        for task in dispatch["tasks"]
    }
    overlap = domains["overlap"]["results"]
    span = domains["span-ceiling"]["results"]
    mandatory = (
        overlap["gap_absolute_error"] <= 0.005
        and overlap["ground_fidelity_mean"] >= 0.95
        and overlap["tower_fidelity_mean"] >= 0.90
    )
    if mandatory:
        classification = "dplus0-sufficient"
    elif (
        span["ground_span_fidelity"] < 0.95
        or span["tower_span_fidelity_mean"] < 0.90
    ):
        classification = "expression-limited"
    else:
        classification = "optimization-failure"
    action = (
        "trigger-preregistered-D+1-D+2"
        if classification == "expression-limited"
        else "keep-D+0"
    )
    stage_gate = {
        "schema_version": STAGE_GATE_VERSION,
        "stage": "phase7",
        "source_revision": dispatch["source_revision"],
        "task_ids": [task["task_id"] for task in dispatch["tasks"]],
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "decision": {
            "kind": "phase7-capacity-decision",
            "benchmark_classification": classification,
            "capacity_action": action,
            "capacity_protocol_modified": False,
            "checkpoint_modified": False,
        },
        "passed": True,
    }
    validate_payload(stage_gate, "stage-gate.schema.json")
    write_json(stage_gate_path, stage_gate)
    return stage_gate


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    authorize_parser = subparsers.add_parser("authorize")
    authorize_parser.add_argument("--repo-root", required=True, type=Path)
    authorize_parser.add_argument("--run-root", required=True, type=Path)
    authorize_parser.add_argument("--run-id", required=True)
    authorize_parser.add_argument("--architecture", required=True, type=Path)
    authorize_parser.add_argument(
        "--checkpoint", required=True, action="append", type=Path
    )
    authorize_parser.add_argument(
        "--capacity-protocol", required=True, type=Path
    )
    prepare_parser = subparsers.add_parser("prepare-integrals")
    prepare_parser.add_argument("--output", required=True, type=Path)
    remediation_parser = subparsers.add_parser(
        "authorize-remediation"
    )
    remediation_parser.add_argument(
        "--repo-root", required=True, type=Path
    )
    remediation_parser.add_argument(
        "--run-root", required=True, type=Path
    )
    remediation_parser.add_argument("--run-id", required=True)
    remediation_parser.add_argument(
        "--baseline-phase7-aggregate", required=True, type=Path
    )
    remediation_parser.add_argument(
        "--remediation-certificate", required=True, type=Path
    )
    remediation_parser.add_argument(
        "--remediation-readback", required=True, type=Path
    )
    remediation_parser.add_argument(
        "--architecture", required=True, type=Path
    )
    remediation_parser.add_argument(
        "--checkpoint", required=True, action="append", type=Path
    )
    remediation_parser.add_argument(
        "--capacity-protocol", required=True, type=Path
    )
    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--repo-root", required=True, type=Path)
    worker_parser.add_argument("--dispatch", required=True, type=Path)
    worker_parser.add_argument("--task-id", required=True)
    worker_parser.add_argument("--run-dir", required=True, type=Path)
    worker_parser.add_argument("--integrals", required=True, type=Path)
    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--dispatch", required=True, type=Path)
    finalize_parser.add_argument("--stage-gate", required=True, type=Path)
    arguments = parser.parse_args()
    if arguments.command == "authorize":
        payload = authorize(
            repo_root=arguments.repo_root.resolve(),
            run_root=arguments.run_root.resolve(),
            run_id=arguments.run_id,
            architecture_path=arguments.architecture.resolve(),
            checkpoint_paths=[
                path.resolve() for path in arguments.checkpoint
            ],
            capacity_protocol_path=arguments.capacity_protocol.resolve(),
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif arguments.command == "prepare-integrals":
        prepare_integrals(arguments.output.resolve())
    elif arguments.command == "authorize-remediation":
        payload = authorize_remediation(
            repo_root=arguments.repo_root.resolve(),
            run_root=arguments.run_root.resolve(),
            run_id=arguments.run_id,
            baseline_phase7_aggregate_path=(
                arguments.baseline_phase7_aggregate.resolve()
            ),
            remediation_certificate_path=(
                arguments.remediation_certificate.resolve()
            ),
            remediation_readback_path=(
                arguments.remediation_readback.resolve()
            ),
            architecture_path=arguments.architecture.resolve(),
            checkpoint_paths=[
                path.resolve() for path in arguments.checkpoint
            ],
            capacity_protocol_path=(
                arguments.capacity_protocol.resolve()
            ),
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif arguments.command == "worker":
        run_task(
            repo_root=arguments.repo_root.resolve(),
            dispatch_path=arguments.dispatch.resolve(),
            task_id=arguments.task_id,
            run_dir=arguments.run_dir.resolve(),
            integrals_path=arguments.integrals.resolve(),
        )
    else:
        payload = finalize(
            dispatch_path=arguments.dispatch.resolve(),
            stage_gate_path=arguments.stage_gate.resolve(),
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
