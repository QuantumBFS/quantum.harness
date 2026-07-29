"""Six-mode overlap screen for Fock--CP/Choi candidate cones."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import combinations
import json
import sys
import time
from typing import Sequence

import numpy as np
from scipy.linalg import null_space

from oracle.fock_basis import exact_to_numpy, quadratic_term
from oracle.fock_cp import (
    fock_tensorization_order,
    liouville_to_choi,
)
from oracle.klein_hodge import (
    embed_contiguous_even_gate,
    klein_hodge_gate,
    overlap_klein_circuit,
)


_MODES = 6
_RING_EDGES = (
    (0, 1),
    (0, 3),
    (1, 2),
    (2, 3),
    (2, 5),
    (3, 4),
    (4, 5),
)
_DIAGONAL_EDGES = ((0, 2), (1, 3), (2, 4), (3, 5))
_BRIDGE_EDGES = ((0, 4), (1, 5))


@dataclass(frozen=True)
class FockCPDirection:
    label: str
    kind: str
    i: int
    j: int
    bridge: bool
    fock_generator: np.ndarray


@dataclass(frozen=True)
class FockCPScreenResult:
    transform: str
    family: str
    mask: str
    ket_modes: tuple[int, ...]
    basis_dimension: int
    hp_dimension: int
    conditional_span_rank: int
    drift_dimension: int
    surviving_bridge_labels: tuple[str, ...]
    maximum_bridge_hp_projection: float
    best_conditional_minimum: float | None
    sampled_ccp_directions: int
    sampled_bridge_ccp_directions: int
    sampled_dissipative_bridge_ccp_directions: int


@lru_cache(maxsize=None)
def support_edges(mask: str) -> tuple[tuple[int, int], ...]:
    masks = {
        "rings": _RING_EDGES,
        "rings-bridges": _RING_EDGES + _BRIDGE_EDGES,
        "rings-diagonals-bridges": (
            _RING_EDGES + _DIAGONAL_EDGES + _BRIDGE_EDGES
        ),
    }
    try:
        return tuple(sorted(masks[mask]))
    except KeyError as error:
        raise ValueError(f"unknown support mask: {mask}") from error


@lru_cache(maxsize=None)
def quadratic_directions(
    *,
    family: str,
    mask: str,
) -> tuple[FockCPDirection, ...]:
    if family not in ("number-conserving", "bdg"):
        raise ValueError(f"unknown quadratic family: {family}")

    directions: list[FockCPDirection] = []
    for index in range(_MODES):
        directions.append(
            FockCPDirection(
                label=f"n{index}",
                kind="hop",
                i=index,
                j=index,
                bridge=False,
                fock_generator=exact_to_numpy(
                    quadratic_term(_MODES, "hop", index, index)
                ),
            )
        )
    for i, j in support_edges(mask):
        is_bridge = (i, j) in _BRIDGE_EDGES
        for left, right in ((i, j), (j, i)):
            directions.append(
                FockCPDirection(
                    label=f"h{left}<-{right}",
                    kind="hop",
                    i=left,
                    j=right,
                    bridge=is_bridge,
                    fock_generator=exact_to_numpy(
                        quadratic_term(_MODES, "hop", left, right)
                    ),
                )
            )
        if family == "bdg":
            for kind, prefix in (
                ("pair_create", "pc"),
                ("pair_annihilate", "pa"),
            ):
                directions.append(
                    FockCPDirection(
                        label=f"{prefix}{i},{j}",
                        kind=kind,
                        i=i,
                        j=j,
                        bridge=is_bridge,
                        fock_generator=exact_to_numpy(
                            quadratic_term(_MODES, kind, i, j)
                        ),
                    )
                )
    return tuple(sorted(directions, key=lambda direction: direction.label))


@lru_cache(maxsize=None)
def candidate_transform(name: str) -> np.ndarray:
    if name == "identity":
        return np.eye(1 << _MODES)
    if name == "overlap-klein":
        return exact_to_numpy(overlap_klein_circuit())
    if name.startswith("klein:"):
        sequence_text = name.removeprefix("klein:")
        try:
            sequence = tuple(int(value) for value in sequence_text.split(","))
        except ValueError as error:
            raise ValueError(f"invalid Klein circuit: {name}") from error
        if not sequence or any(start not in (0, 1, 2) for start in sequence):
            raise ValueError(f"invalid Klein circuit: {name}")
        result = np.eye(1 << _MODES)
        for start in sequence:
            result = _embedded_klein_gate(start) @ result
        return result
    raise ValueError(f"unknown Fock transform: {name}")


@lru_cache(maxsize=3)
def _embedded_klein_gate(start: int) -> np.ndarray:
    return exact_to_numpy(
        embed_contiguous_even_gate(
            klein_hodge_gate(),
            start=start,
            total_modes=_MODES,
        )
    )


def klein_circuit_catalog(*, maximum_depth: int = 2) -> tuple[str, ...]:
    if maximum_depth < 0:
        raise ValueError("maximum_depth must be nonnegative")
    names = ["identity"]
    frontier = [()]
    for _ in range(maximum_depth):
        frontier = [
            (*prefix, start)
            for prefix in frontier
            for start in (0, 1, 2)
        ]
        names.extend(
            "klein:" + ",".join(str(start) for start in sequence)
            for sequence in frontier
        )
    return tuple(names)


@lru_cache(maxsize=1)
def all_tensorizations() -> tuple[tuple[int, ...], ...]:
    return tuple(combinations(range(_MODES), _MODES // 2))


def _real_linear_nullspace(
    matrices: Sequence[np.ndarray],
    *,
    relative_tolerance: float,
) -> np.ndarray:
    columns = []
    for matrix in matrices:
        antihermitian = matrix - matrix.conj().T
        columns.append(
            np.concatenate(
                (antihermitian.real.ravel(), antihermitian.imag.ravel())
            )
        )
    constraints = np.column_stack(columns)
    _, singular_values, right_vectors = np.linalg.svd(
        constraints,
        full_matrices=False,
    )
    threshold = (
        relative_tolerance * singular_values[0]
        if singular_values.size and singular_values[0] > 0.0
        else relative_tolerance
    )
    rank = int(np.count_nonzero(singular_values > threshold))
    return right_vectors[rank:].conj().T


@lru_cache(maxsize=1)
def _conditional_basis(operator_dimension: int) -> np.ndarray:
    identity_vector = np.eye(operator_dimension, dtype=complex).reshape(
        -1,
        order="F",
    )
    identity_vector /= np.linalg.norm(identity_vector)
    return null_space(identity_vector.conj().reshape(1, -1))


def _matrix_span_rank(
    matrices: Sequence[np.ndarray],
    *,
    relative_tolerance: float,
) -> int:
    if not matrices:
        return 0
    columns = [
        np.concatenate((matrix.real.ravel(), matrix.imag.ravel()))
        for matrix in matrices
    ]
    values = np.linalg.svd(
        np.column_stack(columns),
        compute_uv=False,
    )
    if not values.size or values[0] <= relative_tolerance:
        return 0
    return int(np.count_nonzero(values > relative_tolerance * values[0]))


@lru_cache(maxsize=None)
def _transformed_generators(
    transform_name: str,
    family: str,
    mask: str,
) -> tuple[np.ndarray, ...]:
    transform = candidate_transform(transform_name)
    inverse = transform.T
    if not np.allclose(transform @ inverse, np.eye(transform.shape[0]), atol=1e-12):
        inverse = np.linalg.inv(transform)
    return tuple(
        transform @ direction.fock_generator @ inverse
        for direction in quadratic_directions(family=family, mask=mask)
    )


def analyze_tensorization(
    *,
    transform_name: str,
    family: str,
    mask: str,
    ket_modes: Sequence[int],
    samples: int = 256,
    seed: int = 0,
    relative_tolerance: float = 1e-10,
) -> FockCPScreenResult:
    if samples < 0:
        raise ValueError("samples must be nonnegative")
    directions = quadratic_directions(family=family, mask=mask)
    transformed_generators = _transformed_generators(
        transform_name,
        family,
        mask,
    )
    order = fock_tensorization_order(modes=_MODES, ket_modes=ket_modes)
    liouville_generators = [
        generator[np.ix_(order, order)]
        for generator in transformed_generators
    ]
    choi_generators = [
        liouville_to_choi(generator, operator_dimension=8)
        for generator in liouville_generators
    ]
    hp_nullspace = _real_linear_nullspace(
        choi_generators,
        relative_tolerance=relative_tolerance,
    )
    hp_dimension = hp_nullspace.shape[1]
    surviving_bridge_labels = tuple(
        direction.label
        for index, direction in enumerate(directions)
        if direction.bridge
        and float(np.linalg.norm(hp_nullspace[index, :]))
        > relative_tolerance
    )
    maximum_bridge_hp_projection = max(
        (
            float(np.linalg.norm(hp_nullspace[index, :]))
            for index, direction in enumerate(directions)
            if direction.bridge
        ),
        default=0.0,
    )

    complement = _conditional_basis(8)
    conditional_generators = [
        complement.conj().T
        @ (0.5 * (choi + choi.conj().T))
        @ complement
        for choi in choi_generators
    ]
    conditional_hp_basis = [
        sum(
            hp_nullspace[index, column] * conditional_generators[index]
            for index in range(len(directions))
        )
        for column in range(hp_dimension)
    ]
    conditional_rank = _matrix_span_rank(
        conditional_hp_basis,
        relative_tolerance=relative_tolerance,
    )
    drift_dimension = hp_dimension - conditional_rank

    coefficient_samples: list[np.ndarray] = []
    for column in range(hp_dimension):
        coefficient_samples.append(hp_nullspace[:, column])
        coefficient_samples.append(-hp_nullspace[:, column])
    rng = np.random.default_rng(seed)
    for _ in range(samples):
        coordinates = rng.standard_normal(hp_dimension)
        norm = float(np.linalg.norm(coordinates))
        if norm > 0.0:
            coefficient_samples.append(hp_nullspace @ (coordinates / norm))

    sampled_ccp = 0
    sampled_bridge_ccp = 0
    sampled_dissipative_bridge_ccp = 0
    best_minimum: float | None = None
    bridge_indices = tuple(
        index for index, direction in enumerate(directions) if direction.bridge
    )
    for coefficients in coefficient_samples:
        conditional = sum(
            coefficients[index] * conditional_generators[index]
            for index in range(len(directions))
        )
        conditional = 0.5 * (conditional + conditional.conj().T)
        conditional_norm = float(np.linalg.norm(conditional))
        if conditional_norm <= relative_tolerance:
            minimum = 0.0
        else:
            minimum = float(np.linalg.eigvalsh(conditional)[0])
            scaled_minimum = minimum / conditional_norm
            if best_minimum is None or scaled_minimum > best_minimum:
                best_minimum = scaled_minimum
        is_ccp = minimum >= -relative_tolerance * max(1.0, conditional_norm)
        if not is_ccp:
            continue
        sampled_ccp += 1
        bridge_norm = float(np.linalg.norm(coefficients[list(bridge_indices)]))
        if bridge_norm > relative_tolerance:
            sampled_bridge_ccp += 1
            if conditional_norm > relative_tolerance:
                sampled_dissipative_bridge_ccp += 1

    return FockCPScreenResult(
        transform=transform_name,
        family=family,
        mask=mask,
        ket_modes=tuple(int(mode) for mode in ket_modes),
        basis_dimension=len(directions),
        hp_dimension=hp_dimension,
        conditional_span_rank=conditional_rank,
        drift_dimension=drift_dimension,
        surviving_bridge_labels=surviving_bridge_labels,
        maximum_bridge_hp_projection=maximum_bridge_hp_projection,
        best_conditional_minimum=best_minimum,
        sampled_ccp_directions=sampled_ccp,
        sampled_bridge_ccp_directions=sampled_bridge_ccp,
        sampled_dissipative_bridge_ccp_directions=(
            sampled_dissipative_bridge_ccp
        ),
    )


def run_screen(
    *,
    transforms: Sequence[str],
    family: str,
    mask: str,
    samples: int,
    seed: int,
    show_progress: bool = False,
) -> tuple[FockCPScreenResult, ...]:
    results = []
    for transform in transforms:
        started = time.monotonic()
        for offset, ket_modes in enumerate(all_tensorizations()):
            results.append(
                analyze_tensorization(
                    transform_name=transform,
                    family=family,
                    mask=mask,
                    ket_modes=ket_modes,
                    samples=samples,
                    seed=seed + offset,
                )
            )
        if show_progress:
            transform_results = results[-len(all_tensorizations()) :]
            bridge_cells = sum(
                bool(result.surviving_bridge_labels)
                for result in transform_results
            )
            print(
                (
                    f"completed {transform}: cells={len(transform_results)} "
                    f"hp_bridge_cells={bridge_cells} "
                    f"seconds={time.monotonic() - started:.2f}"
                ),
                file=sys.stderr,
                flush=True,
            )
    return tuple(results)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="screen six-mode Fock tensorizations for conditional CP cones"
    )
    parser.add_argument(
        "--transform",
        action="append",
        dest="transforms",
    )
    parser.add_argument(
        "--klein-depth",
        type=int,
        help="screen the complete contiguous Klein circuit catalog to this depth",
    )
    parser.add_argument(
        "--family",
        choices=("number-conserving", "bdg"),
        default="number-conserving",
    )
    parser.add_argument(
        "--mask",
        choices=("rings", "rings-bridges", "rings-diagonals-bridges"),
        default="rings-bridges",
    )
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--seed", type=int, default=20260729)
    arguments = parser.parse_args()
    if arguments.klein_depth is not None and arguments.transforms:
        parser.error("--klein-depth and --transform cannot be combined")
    transforms = (
        klein_circuit_catalog(maximum_depth=arguments.klein_depth)
        if arguments.klein_depth is not None
        else arguments.transforms or ["identity", "overlap-klein"]
    )
    started = time.monotonic()
    results = run_screen(
        transforms=transforms,
        family=arguments.family,
        mask=arguments.mask,
        samples=arguments.samples,
        seed=arguments.seed,
        show_progress=True,
    )
    print(
        json.dumps(
            {
                "schema_version": 1,
                "family": arguments.family,
                "mask": arguments.mask,
                "samples_per_tensorization": arguments.samples,
                "seed": arguments.seed,
                "runtime_seconds": time.monotonic() - started,
                "results": [asdict(result) for result in results],
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
