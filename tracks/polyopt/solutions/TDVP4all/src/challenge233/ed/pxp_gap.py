import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import platform
import time

import numpy as np
import quspin
import scipy
from quspin.operators import hamiltonian

from challenge233.basis.pxp import build_constrained_basis


@dataclass(frozen=True)
class SpectrumPoint:
    size: int
    detuning: float
    basis_dimension: int
    eigenvalues: tuple[float, ...]
    gap: float
    residual_norms: tuple[float, ...]
    hermiticity_max_abs: float
    matrix_nnz: int
    wall_seconds: float


def build_pxp_hamiltonian(size: int, detuning: float):
    basis = build_constrained_basis(size)
    rabi_terms = [[1.0, site] for site in range(size)]
    detuning_terms = [[-0.5 * detuning, site] for site in range(size)]
    operator = hamiltonian(
        [["x", rabi_terms], ["z", detuning_terms]],
        [],
        basis=basis,
        dtype=np.float64,
        check_herm=False,
        check_symm=False,
        check_pcon=False,
    )
    energy_shift = -0.5 * detuning * size
    return operator, energy_shift


def solve_low_spectrum(
    size: int,
    detuning: float,
    eigenpairs: int = 4,
    tolerance: float = 1e-12,
    random_seed: int = 233,
) -> SpectrumPoint:
    started_at = time.perf_counter()
    operator, energy_shift = build_pxp_hamiltonian(size, detuning)
    basis_dimension = operator.Ns
    if not 2 <= eigenpairs < basis_dimension:
        raise ValueError(
            "eigenpairs must satisfy 2 <= eigenpairs < basis dimension"
        )

    initial_vector = np.random.default_rng(random_seed).standard_normal(
        basis_dimension
    )
    unshifted_eigenvalues, eigenvectors = operator.eigsh(
        k=eigenpairs,
        which="SA",
        tol=tolerance,
        maxiter=max(1000, 50 * basis_dimension),
        v0=initial_vector,
    )
    order = np.argsort(unshifted_eigenvalues)
    unshifted_eigenvalues = unshifted_eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    eigenvalues = unshifted_eigenvalues + energy_shift

    residual_norms = tuple(
        float(
            np.linalg.norm(
                operator.dot(eigenvectors[:, index])
                - unshifted_eigenvalues[index] * eigenvectors[:, index]
            )
        )
        for index in range(eigenpairs)
    )
    sparse_matrix = operator.tocsr()
    antihermitian = sparse_matrix - sparse_matrix.getH()
    hermiticity_max_abs = (
        float(np.max(np.abs(antihermitian.data)))
        if antihermitian.nnz
        else 0.0
    )

    return SpectrumPoint(
        size=size,
        detuning=detuning,
        basis_dimension=basis_dimension,
        eigenvalues=tuple(float(value) for value in eigenvalues),
        gap=float(eigenvalues[1] - eigenvalues[0]),
        residual_norms=residual_norms,
        hermiticity_max_abs=hermiticity_max_abs,
        matrix_nnz=sparse_matrix.nnz,
        wall_seconds=time.perf_counter() - started_at,
    )


def run_sweep(
    sizes,
    detunings,
    output_directory,
    eigenpairs: int = 4,
    tolerance: float = 1e-12,
    random_seed: int = 233,
):
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    sizes = list(sizes)
    detunings = list(detunings)
    rows = []
    for size in sizes:
        for detuning in detunings:
            point = solve_low_spectrum(
                size=size,
                detuning=detuning,
                eigenpairs=eigenpairs,
                tolerance=tolerance,
                random_seed=random_seed,
            )
            row = {
                "size": point.size,
                "detuning": point.detuning,
                "basis_dimension": point.basis_dimension,
                "gap": point.gap,
                "max_residual": max(point.residual_norms),
                "hermiticity_max_abs": point.hermiticity_max_abs,
                "matrix_nnz": point.matrix_nnz,
                "wall_seconds": point.wall_seconds,
            }
            for index, eigenvalue in enumerate(point.eigenvalues):
                row[f"e{index}"] = eigenvalue
            for index, residual in enumerate(point.residual_norms):
                row[f"residual_{index}"] = residual
            rows.append(row)

    fieldnames = [
        "size",
        "detuning",
        "basis_dimension",
        *(f"e{index}" for index in range(eigenpairs)),
        "gap",
        *(f"residual_{index}" for index in range(eigenpairs)),
        "max_residual",
        "hermiticity_max_abs",
        "matrix_nnz",
        "wall_seconds",
    ]
    with (output_directory / "ed-gap.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    project_root = Path(__file__).resolve().parents[3]
    trusted_basis = (
        project_root
        / "external"
        / "1d-basis"
        / "pxpbasis.py"
    )
    source_paths = (
        "src/challenge233/basis/pxp.py",
        "src/challenge233/ed/pxp_gap.py",
    )
    basis_state_files = {}
    for size in sizes:
        states_path = output_directory / f"basis-states-N{size:04d}.npy"
        np.save(states_path, build_constrained_basis(size).states)
        basis_state_files[str(size)] = {
            "path": states_path.name,
            "count": build_constrained_basis(size).Ns,
            "sha256": hashlib.sha256(states_path.read_bytes()).hexdigest(),
        }
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "hamiltonian": (
            "H_N(delta)=sum_i P_{i-1} X_i P_{i+1}"
            "-delta sum_i n_i"
        ),
        "rabi_coefficient": 1.0,
        "detuning_sign": "-delta",
        "projectors": {
            "P": "|0><0|=(I-Z)/2",
            "n": "|1><1|=(I+Z)/2",
        },
        "boundary": "periodic",
        "local_state_convention": "0=down, 1=up",
        "blockade_constraint": "n_i n_{i+1}=0",
        "symmetry_sector": "full constrained Hilbert space",
        "target_gap": "E_1-E_0, all momenta",
        "sizes": sizes,
        "detunings": detunings,
        "solver": {
            "package": "QuSpin",
            "version": quspin.__version__,
            "method": "eigsh",
            "which": "SA",
            "eigenpairs": eigenpairs,
            "tolerance": tolerance,
            "random_seed": random_seed,
            "dtype": "float64",
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "thread_environment": {
                variable: os.environ.get(variable)
                for variable in (
                    "OMP_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "OPENBLAS_NUM_THREADS",
                )
            },
        },
        "trusted_basis_path": "external/1d-basis/pxpbasis.py",
        "trusted_basis_sha256": hashlib.sha256(
            trusted_basis.read_bytes()
        ).hexdigest(),
        "source_file_sha256": {
            relative_path: hashlib.sha256(
                (project_root / relative_path).read_bytes()
            ).hexdigest()
            for relative_path in source_paths
        },
        "basis_state_files": basis_state_files,
        "data_file": "ed-gap.csv",
        "data_sha256": hashlib.sha256(
            (output_directory / "ed-gap.csv").read_bytes()
        ).hexdigest(),
        "point_count": len(rows),
    }
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return rows


def _inclusive_decimal_grid(start: str, stop: str, step: str) -> list[float]:
    start_decimal = Decimal(start)
    stop_decimal = Decimal(stop)
    step_decimal = Decimal(step)
    if step_decimal <= 0:
        raise ValueError("detuning step must be positive")
    if stop_decimal < start_decimal:
        raise ValueError("detuning maximum must not be below minimum")

    values = []
    value = start_decimal
    while value <= stop_decimal:
        values.append(float(value))
        value += step_decimal
    if Decimal(str(values[-1])) != stop_decimal:
        raise ValueError("detuning step must land exactly on the maximum")
    return values


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Sparse QuSpin ED oracle for the periodic blockaded PXP chain"
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--min-size", type=int, default=4)
    parser.add_argument("--max-size", type=int, default=20)
    parser.add_argument("--detuning-min", default="0")
    parser.add_argument("--detuning-max", default="1")
    parser.add_argument("--detuning-step", default="0.1")
    parser.add_argument("--eigenpairs", type=int, default=4)
    parser.add_argument("--tolerance", type=float, default=1e-12)
    parser.add_argument("--random-seed", type=int, default=233)
    arguments = parser.parse_args(argv)

    if arguments.min_size < 4 or arguments.max_size < arguments.min_size:
        parser.error("sizes must satisfy 4 <= min-size <= max-size")

    detunings = _inclusive_decimal_grid(
        arguments.detuning_min,
        arguments.detuning_max,
        arguments.detuning_step,
    )
    sizes = list(range(arguments.min_size, arguments.max_size + 1))
    rows = run_sweep(
        sizes=sizes,
        detunings=detunings,
        output_directory=arguments.output_dir,
        eigenpairs=arguments.eigenpairs,
        tolerance=arguments.tolerance,
        random_seed=arguments.random_seed,
    )
    print(f"completed {len(rows)} ED points in {arguments.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
