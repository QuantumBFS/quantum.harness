#!/usr/bin/env python3
"""Finite-torus Shastry-Sutherland ED oracle.

This script is deliberately separate from the infinite-volume SDP. It checks
the model geometry and normalization and supplies finite-size comparison data;
its gaps are not certified bulk-gap bounds.
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import scipy
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import eigsh

SCHEMA_VERSION = "shastry-sutherland-finite-torus-ed-v1"
GENERATOR = "scripts/shastry_sutherland_ed.py"


def site_id(x: int, y: int, lx: int) -> int:
    return y * lx + x


def dimer_partner(x: int, y: int, lx: int, ly: int) -> tuple[int, int]:
    if x % 2 == 0:
        raw = (x - 1, y + 1) if y % 2 == 0 else (x + 1, y + 1)
    else:
        raw = (x - 1, y - 1) if y % 2 == 0 else (x + 1, y - 1)
    return raw[0] % lx, raw[1] % ly


def validate_periodic_dimer_covering(lx: int, ly: int) -> None:
    for y in range(ly):
        for x in range(lx):
            partner = dimer_partner(x, y, lx, ly)
            if dimer_partner(*partner, lx, ly) != (x, y):
                raise RuntimeError("periodic dimer partner map is not involutive")


def shastry_sutherland_bonds(
    lx: int,
    ly: int,
    g: float,
) -> list[tuple[int, int, float, str]]:
    if lx < 4 or ly < 4 or lx % 2 or ly % 2:
        raise ValueError("periodic dimensions must be even and at least four")
    validate_periodic_dimer_covering(lx, ly)

    bonds: dict[tuple[int, int, str], tuple[int, int, float, str]] = {}
    for y in range(ly):
        for x in range(lx):
            i = site_id(x, y, lx)
            for nx, ny in (((x + 1) % lx, y), (x, (y + 1) % ly)):
                j = site_id(nx, ny, lx)
                key = (min(i, j), max(i, j), "square")
                bonds[key] = (*key[:2], g, "square")

            px, py = dimer_partner(x, y, lx, ly)
            j = site_id(px, py, lx)
            key = (min(i, j), max(i, j), "dimer")
            bonds[key] = (*key[:2], 1.0, "dimer")

    result = sorted(bonds.values(), key=lambda bond: (bond[3], bond[0], bond[1]))
    nsites = lx * ly
    if sum(kind == "dimer" for *_, kind in result) != nsites // 2:
        raise RuntimeError("dimer covering does not contain N/2 bonds")
    if sum(kind == "square" for *_, kind in result) != 2 * nsites:
        raise RuntimeError("square torus does not contain 2N bonds")
    return result


def fixed_popcount_basis(nsites: int, nup: int) -> list[int]:
    return [
        sum(1 << site for site in occupied)
        for occupied in combinations(range(nsites), nup)
    ]


def sector_hamiltonian(
    nsites: int,
    nup: int,
    bonds: list[tuple[int, int, float, str]],
):
    basis = fixed_popcount_basis(nsites, nup)
    index = {state: position for position, state in enumerate(basis)}
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []

    for column, state in enumerate(basis):
        diagonal = 0.0
        for i, j, coupling, _ in bonds:
            bit_i = (state >> i) & 1
            bit_j = (state >> j) & 1
            diagonal += coupling * (0.25 if bit_i == bit_j else -0.25)
            if bit_i != bit_j:
                target = state ^ (1 << i) ^ (1 << j)
                rows.append(index[target])
                columns.append(column)
                values.append(coupling / 2.0)
        rows.append(column)
        columns.append(column)
        values.append(diagonal)

    matrix = coo_matrix(
        (values, (rows, columns)),
        shape=(len(basis), len(basis)),
        dtype=np.float64,
    ).tocsr()
    matrix.sum_duplicates()
    return matrix


def lowest_levels(matrix, count: int, tolerance: float) -> tuple[np.ndarray, float]:
    if not 1 <= count < matrix.shape[0]:
        raise ValueError("level count must lie between one and dimension minus one")
    initial_vector = np.arange(1, matrix.shape[0] + 1, dtype=np.float64)
    initial_vector /= np.linalg.norm(initial_vector)
    values, vectors = eigsh(
        matrix,
        k=count,
        which="SA",
        tol=tolerance,
        v0=initial_vector,
        return_eigenvectors=True,
    )
    order = np.argsort(values)
    values = values[order]
    ground_vector = vectors[:, order[0]]
    residual = np.linalg.norm(matrix @ ground_vector - values[0] * ground_vector)
    return values, float(residual)


def run_oracle(
    lx: int,
    ly: int,
    g: float,
    levels: int = 4,
    tolerance: float = 1e-11,
) -> dict[str, object]:
    nsites = lx * ly
    bonds = shastry_sutherland_bonds(lx, ly, g)
    sector_results: dict[str, object] = {}

    for total_sz, nup in ((0, nsites // 2), (1, nsites // 2 + 1)):
        matrix = sector_hamiltonian(nsites, nup, bonds)
        values, residual = lowest_levels(matrix, levels, tolerance)
        sector_results[str(total_sz)] = {
            "dimension": matrix.shape[0],
            "nnz": matrix.nnz,
            "lowest_energies": [float(value) for value in values],
            "ground_residual": residual,
        }

    ground_energy = sector_results["0"]["lowest_energies"][0]
    triplet_energy = sector_results["1"]["lowest_energies"][0]
    result = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "model": "shastry-sutherland",
        "boundary": "periodic-torus",
        "normalization": "J_dimer=1; H=sum J_ij S_i dot S_j",
        "lx": lx,
        "ly": ly,
        "sites": nsites,
        "g": g,
        "dimer_bonds": sum(kind == "dimer" for *_, kind in bonds),
        "square_bonds": sum(kind == "square" for *_, kind in bonds),
        "sectors": sector_results,
        "ground_energy_sz0": ground_energy,
        "energy_per_site_sz0": ground_energy / nsites,
        "lowest_energy_sz1": triplet_energy,
        "finite_torus_sz1_gap": triplet_energy - ground_energy,
        "bulk_bound_claim": False,
        "eigensolver": {
            "method": "scipy.sparse.linalg.eigsh",
            "levels_requested_per_sector": levels,
            "tolerance": tolerance,
            "initial_vector": "normalized [1,2,...,dimension]",
        },
        "runtime": {
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
        },
    }
    if g == 0.0:
        exact_check = (
            abs(result["energy_per_site_sz0"] + 3.0 / 8.0) <= 1e-12
            and abs(result["finite_torus_sz1_gap"] - 1.0) <= 1e-12
        )
        result["exact_g0_check"] = exact_check
        if not exact_check:
            raise RuntimeError("g=0 exact dimer calibration failed")
    return result


def write_result(path: Path, result: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lx", type=int, default=4)
    parser.add_argument("--ly", type=int, default=4)
    parser.add_argument("--g", type=float, required=True)
    parser.add_argument("--levels", type=int, default=4)
    parser.add_argument("--tolerance", type=float, default=1e-11)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_oracle(args.lx, args.ly, args.g, args.levels, args.tolerance)
    if args.output is not None:
        write_result(args.output, result)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.output is None:
        print(result)


if __name__ == "__main__":
    main()
