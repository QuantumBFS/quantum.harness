#!/usr/bin/env python3
"""Compute the root-response Jacobi crossover through active rank 800."""

from __future__ import annotations

import argparse
import json
import platform
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from lgeth.channels import root_response_partition
from lgeth.jacobi import jacobi_parameters, sample_jacobi_wishart
from lgeth.statistics import bulk_gap_ratio_per_spectrum, histogram_l1


VERSION = "v1"
ALGORITHM_VERSION = 1
REGISTERED_CASES = (
    (8, 2_000),
    (10, 2_000),
    (12, 2_000),
    (14, 1_000),
    (16, 1_000),
    (18, 500),
    (20, 250),
)
RESPONSE_ENTRY_CEILING = 1_200_000


@dataclass(frozen=True)
class ResponseAssembler:
    """Sparse lookup for a root-space one-body response block."""

    D: int
    M: int
    row: np.ndarray
    column: np.ndarray
    destination: np.ndarray
    source: np.ndarray
    population: np.ndarray

    def channel(self, tangent: np.ndarray) -> np.ndarray:
        values = self.population * tangent[self.destination, self.source]
        matrix = np.zeros((self.D, self.M), dtype=float)
        np.add.at(matrix, (self.row, self.column), values)
        return matrix


def build_response_assembler(partition) -> ResponseAssembler:
    """Precompute the nonzero one-body representation map."""

    target_column = {
        int(basis_index): column
        for column, basis_index in enumerate(
            partition.descendant_external
        )
    }
    state_index = {
        state: index for index, state in enumerate(partition.states)
    }
    rows: list[int] = []
    columns: list[int] = []
    destinations: list[int] = []
    sources: list[int] = []
    populations: list[int] = []
    for row, basis_index in enumerate(partition.zero_modes):
        state = partition.states[int(basis_index)]
        for source, population in enumerate(state):
            if population == 0:
                continue
            for destination in range(len(state)):
                if destination == source:
                    continue
                updated = list(state)
                updated[source] -= 1
                updated[destination] += 1
                target_index = state_index[tuple(updated)]
                column = target_column.get(target_index)
                if column is not None:
                    rows.append(row)
                    columns.append(column)
                    destinations.append(destination)
                    sources.append(source)
                    populations.append(population)
    return ResponseAssembler(
        D=len(partition.zero_modes),
        M=len(partition.descendant_external),
        row=np.asarray(rows, dtype=np.int32),
        column=np.asarray(columns, dtype=np.int32),
        destination=np.asarray(destinations, dtype=np.int16),
        source=np.asarray(sources, dtype=np.int16),
        population=np.asarray(populations, dtype=float),
    )


def _random_symmetric_tangent(
    rng: np.random.Generator,
    orbitals: int,
) -> np.ndarray:
    upper = rng.integers(
        -16,
        17,
        size=(orbitals, orbitals),
        dtype=np.int64,
    )
    tangent = np.triu(upper, 1)
    tangent += tangent.T
    np.fill_diagonal(
        tangent,
        rng.integers(-16, 17, size=orbitals, dtype=np.int64),
    )
    return tangent.astype(float)


def qr_normalized_curvature(
    channel_v: np.ndarray,
    channel_w: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Return row isometry and normalized-curvature spectrum by thin QR."""

    doubled = np.concatenate([channel_v, channel_w], axis=1)
    q, triangular = np.linalg.qr(doubled.T, mode="reduced")
    diagonal = np.abs(np.diag(triangular))
    condition_indicator = float(np.min(diagonal) / np.max(diagonal))
    if condition_indicator <= 1e-12:
        raise RuntimeError("root-response channel lost active rank")
    rows = q.T
    M = channel_v.shape[1]
    plus = rows[:, :M]
    minus = rows[:, M:]
    omega = 1j * (
        plus @ minus.T - minus @ plus.T
    )
    spectrum = np.linalg.eigvalsh(
        0.5 * (omega + omega.conj().T)
    )
    return rows, spectrum, condition_indicator


def _row_diagnostics(rows: np.ndarray, M: int) -> tuple[float, float]:
    weights = np.sum(rows * rows, axis=0)
    rank = float(rows.shape[0])
    effective = rank * rank / float(np.sum(weights * weights))
    participation = effective / rows.shape[1]
    polarization = abs(
        float(np.sum(weights[:M]) - np.sum(weights[M:])) / rank
    )
    return participation, polarization


def _strip_atoms(
    spectra: np.ndarray,
    plus_atoms: int,
    minus_atoms: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    labels = np.zeros_like(spectra, dtype=bool)
    maximum_residual = 0.0
    if minus_atoms:
        labels[:, :minus_atoms] = True
        labels[:, -plus_atoms:] = True
        maximum_residual = max(
            float(np.max(np.abs(spectra[:, :minus_atoms] + 1.0))),
            float(np.max(np.abs(spectra[:, -plus_atoms:] - 1.0))),
        )
    interior = spectra[~labels].reshape(
        spectra.shape[0],
        spectra.shape[1] - plus_atoms - minus_atoms,
    )
    return interior, labels, maximum_residual


def _checkpoint_paths(directory: Path, n: int) -> tuple[Path, Path]:
    return directory / f"n{n}_v1.json", directory / f"n{n}_v1.npz"


def _computed_case(
    n: int,
    samples: int,
    checkpoint_dir: Path,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    json_path, npz_path = _checkpoint_paths(checkpoint_dir, n)
    if json_path.exists() and npz_path.exists():
        result = json.loads(json_path.read_text(encoding="utf-8"))
        if (
            result.get("algorithm_version") == ALGORITHM_VERSION
            and result.get("samples") == samples
            and result.get("status") == "computed"
        ):
            with np.load(npz_path) as arrays:
                return result, {key: arrays[key] for key in arrays.files}
    started = time.perf_counter()
    partition = root_response_partition(3, n)
    assembler = build_response_assembler(partition)
    D, M = assembler.D, assembler.M
    parameters = jacobi_parameters(D, M)
    count = int(samples)
    spectra = np.empty((count, D), dtype=np.float32)
    participation = np.empty(count, dtype=np.float32)
    polarization = np.empty(count, dtype=np.float32)
    condition_indicator = np.empty(count, dtype=np.float32)
    seed_block = np.empty(count, dtype=np.int16)
    frame_pair_count = min(count // 2, 64 if D <= 352 else 24)
    frame_overlaps = np.empty(frame_pair_count, dtype=np.float32)
    previous = None
    pair = 0
    blocks = min(8, count)
    child_sequences = np.random.SeedSequence(
        20260728300 + n
    ).spawn(blocks)
    index_blocks = np.array_split(np.arange(count), blocks)
    for block, indices in enumerate(index_blocks):
        rng = np.random.default_rng(child_sequences[block])
        for sample in indices:
            tangent_v = _random_symmetric_tangent(rng, n)
            tangent_w = _random_symmetric_tangent(rng, n)
            channel_v = assembler.channel(tangent_v)
            channel_w = assembler.channel(tangent_w)
            rows, values, indicator = qr_normalized_curvature(
                channel_v,
                channel_w,
            )
            spectra[sample] = values
            condition_indicator[sample] = indicator
            participation[sample], polarization[sample] = _row_diagnostics(
                rows,
                M,
            )
            seed_block[sample] = block
            if pair < frame_pair_count:
                if sample % 2 == 0:
                    previous = rows
                elif previous is not None:
                    frame_overlaps[pair] = np.linalg.norm(
                        previous @ rows.T
                    ) ** 2
                    pair += 1
                    previous = None
        print(
            f"root n={n}, D={D}, block {block + 1}/{blocks}: "
            f"{indices[-1] + 1}/{count}",
            flush=True,
        )
    interior, atom_labels, atom_residual = _strip_atoms(
        spectra,
        parameters.plus_atoms,
        parameters.minus_atoms,
    )
    reference_full, reference_interior, reference_atom_labels = (
        sample_jacobi_wishart(
            D,
            M,
            count,
            seed=20260728400 + n,
        )
    )
    physical_ratios = bulk_gap_ratio_per_spectrum(interior)
    reference_ratios = bulk_gap_ratio_per_spectrum(reference_interior)
    density_l1 = histogram_l1(
        interior,
        reference_interior,
        np.linspace(-1.0, 1.0, 161),
    )
    arrays = {
        "full_spectra": spectra,
        "interior_spectra": interior.astype(np.float32),
        "atom_labels": atom_labels,
        "reference_full_spectra": reference_full.astype(np.float32),
        "reference_interior_spectra": reference_interior.astype(
            np.float32
        ),
        "reference_atom_labels": reference_atom_labels,
        "gap_ratios": physical_ratios.astype(np.float32),
        "reference_gap_ratios": reference_ratios.astype(np.float32),
        "seed_block": seed_block,
        "participation": participation,
        "polarization": polarization,
        "frame_overlaps": frame_overlaps,
        "condition_indicator": condition_indicator,
    }
    result = {
        "algorithm_version": ALGORITHM_VERSION,
        "status": "computed",
        "N": 3,
        "n": n,
        "D": D,
        "M": M,
        "samples": count,
        "ambient_hilbert_dimension": len(partition.states),
        "response_entries": D * 2 * M,
        "response_nonzero_terms": int(assembler.row.size),
        "interior_dimension": parameters.interior_dimension,
        "plus_atoms_per_matrix": parameters.plus_atoms,
        "minus_atoms_per_matrix": parameters.minus_atoms,
        "observed_plus_atoms_per_matrix": int(
            np.mean(np.sum(atom_labels[:, -parameters.plus_atoms :], axis=1))
        )
        if parameters.plus_atoms
        else 0,
        "observed_minus_atoms_per_matrix": int(
            np.mean(np.sum(atom_labels[:, : parameters.minus_atoms], axis=1))
        )
        if parameters.minus_atoms
        else 0,
        "maximum_atom_residual": atom_residual,
        "mean_gap_ratio": float(np.mean(physical_ratios)),
        "reference_mean_gap_ratio": float(np.mean(reference_ratios)),
        "gap_ratio_difference": abs(
            float(np.mean(physical_ratios))
            - float(np.mean(reference_ratios))
        ),
        "interior_density_l1": density_l1,
        "mean_participation": float(np.mean(participation)),
        "mean_polarization": float(np.mean(polarization)),
        "mean_frame_overlap": float(np.mean(frame_overlaps)),
        "minimum_condition_indicator": float(
            np.min(condition_indicator)
        ),
        "seed_blocks": blocks,
        "frame_pairs": frame_pair_count,
        "runtime_seconds": time.perf_counter() - started,
    }
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(npz_path, **arrays)
    return result, arrays


def run(
    output_json: Path,
    output_npz: Path,
    cases: tuple[tuple[int, int], ...] = REGISTERED_CASES,
    response_entry_ceiling: int = RESPONSE_ENTRY_CEILING,
) -> dict[str, Any]:
    """Run registered cases with per-size resumable checkpoints."""

    started = time.perf_counter()
    checkpoint_dir = (
        output_npz.parent / f"{output_npz.stem}_checkpoints"
    )
    case_results: list[dict[str, Any]] = []
    saved_arrays: dict[str, np.ndarray] = {}
    for n, samples in cases:
        partition = root_response_partition(3, n)
        D = len(partition.zero_modes)
        M = len(partition.descendant_external)
        entries = D * 2 * M
        if entries > int(response_entry_ceiling):
            result = {
                "status": "resource_rejected",
                "N": 3,
                "n": n,
                "D": D,
                "M": M,
                "samples": int(samples),
                "response_entries": entries,
                "response_entry_ceiling": int(response_entry_ceiling),
            }
            arrays = {}
        else:
            result, arrays = _computed_case(
                n,
                int(samples),
                checkpoint_dir,
            )
        case_results.append(result)
        for key, value in arrays.items():
            saved_arrays[f"n{n}_{key}"] = value
    computed = [case for case in case_results if case["status"] == "computed"]
    registered = tuple(cases) == REGISTERED_CASES
    checks = {
        "registered_dimensions_match": all(
            (case["D"], case["M"])
            == {
                8: (16, 80),
                10: (50, 140),
                12: (112, 216),
                14: (210, 308),
                16: (352, 416),
                18: (546, 540),
                20: (800, 680),
            }[case["n"]]
            for case in case_results
        ),
        "statuses_explicit": all(
            case["status"] in {"computed", "resource_rejected"}
            for case in case_results
        ),
        "registered_run_has_no_rejections": (
            not registered
            or all(case["status"] == "computed" for case in case_results)
        ),
        "registered_sample_counts_unchanged": (
            not registered
            or all(
                case["samples"] == samples
                for case, (_, samples) in zip(
                    case_results,
                    REGISTERED_CASES,
                    strict=True,
                )
            )
        ),
        "atom_counts_match_intersection_theorem": all(
            case["observed_plus_atoms_per_matrix"]
            == max(case["D"] - case["M"], 0)
            and case["observed_minus_atoms_per_matrix"]
            == max(case["D"] - case["M"], 0)
            for case in computed
        ),
        "atom_residual_below_tolerance": all(
            case["maximum_atom_residual"] < 2e-5 for case in computed
        ),
    }
    result = {
        "schema_version": 1,
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "registered_cases": [
            {"n": n, "samples": samples}
            for n, samples in REGISTERED_CASES
        ],
        "response_entry_ceiling": int(response_entry_ceiling),
        "cases": case_results,
        "checks": checks,
        "all_checks_pass": bool(all(checks.values())),
        "runtime_seconds": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_npz.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(output_npz, **saved_arrays)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("output/rank_scaling_v1.json"),
    )
    parser.add_argument(
        "--output-npz",
        type=Path,
        default=Path("output/rank_scaling_v1.npz"),
    )
    args = parser.parse_args()
    result = run(args.output_json, args.output_npz)
    print(json.dumps(result, indent=2))
    if not result["all_checks_pass"]:
        raise SystemExit("rank-scaling audit failed")


if __name__ == "__main__":
    main()
