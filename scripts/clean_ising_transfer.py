#!/usr/bin/env python3
"""Exact matrix-free row transfer operator for the clean 2D Ising model."""

import argparse
import csv
import math
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
from scipy.sparse.linalg import LinearOperator, eigsh


def critical_coupling():
    """Return the isotropic square-lattice Ising critical coupling."""
    return 0.5 * math.log(1.0 + math.sqrt(2.0))


def _periodic_row_energies(L):
    """Return sum_i sigma_i sigma_(i+1) for every bit-encoded row."""
    states = np.arange(1 << L, dtype=np.uint64)
    domain_walls = np.zeros(states.size, dtype=np.int16)
    for site in range(L):
        neighbor = (site + 1) % L
        different = ((states >> site) ^ (states >> neighbor)) & 1
        domain_walls += different.astype(np.int16)
    return L - 2 * domain_walls


class IsingTransferOperator(LinearOperator):
    """Symmetric clean-Ising transfer operator without dense materialization."""

    def __init__(self, L, kx, ktau):
        if L < 2:
            raise ValueError("L must be at least 2")
        self.L = int(L)
        self.dimension = 1 << self.L
        self.kx = float(kx)
        self.ktau = float(ktau)

        row_energies = _periodic_row_energies(self.L)
        self._dhalf = np.exp(0.5 * self.kx * row_energies)
        self._parallel = math.exp(self.ktau)
        self._antiparallel = math.exp(-self.ktau)
        super().__init__(dtype=np.dtype(np.float64), shape=(self.dimension, self.dimension))

    def _matvec(self, vector):
        vector = np.asarray(vector, dtype=np.float64).reshape(-1)
        if vector.size != self.dimension:
            raise ValueError(
                f"vector has size {vector.size}, expected {self.dimension}"
            )
        source = self._dhalf * vector
        target = np.empty_like(source)

        for site in range(self.L):
            stride = 1 << site
            source_blocks = source.reshape(-1, 2, stride)
            target_blocks = target.reshape(-1, 2, stride)
            lower = source_blocks[:, 0, :]
            upper = source_blocks[:, 1, :]
            target_blocks[:, 0, :] = (
                self._parallel * lower + self._antiparallel * upper
            )
            target_blocks[:, 1, :] = (
                self._antiparallel * lower + self._parallel * upper
            )
            source, target = target, source

        source *= self._dhalf
        return source

    def _matmat(self, matrix):
        """Apply the transfer operator to a block without column broadcasting."""
        matrix = np.asarray(matrix, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[0] != self.dimension:
            raise ValueError(
                f"matrix has shape {matrix.shape}, expected ({self.dimension}, k)"
            )
        block_size = matrix.shape[1]
        source = self._dhalf[:, None] * matrix
        target = np.empty_like(source)

        for site in range(self.L):
            stride = 1 << site
            source_blocks = source.reshape(-1, 2, stride, block_size)
            target_blocks = target.reshape(-1, 2, stride, block_size)
            lower = source_blocks[:, 0, :, :]
            upper = source_blocks[:, 1, :, :]
            target_blocks[:, 0, :, :] = (
                self._parallel * lower + self._antiparallel * upper
            )
            target_blocks[:, 1, :, :] = (
                self._antiparallel * lower + self._parallel * upper
            )
            source, target = target, source

        source *= self._dhalf[:, None]
        return source


def dominant_eigenpair(L, kx, ktau, tol=1e-11):
    """Return the leading matrix-free eigenvalue and its verified residual."""
    operator = IsingTransferOperator(L, kx, ktau)
    start_vector = np.ones(operator.dimension, dtype=np.float64)
    start_vector /= np.linalg.norm(start_vector)
    ncv = min(12, operator.dimension - 1)

    start = time.perf_counter()
    values, vectors = eigsh(
        operator,
        k=1,
        which="LA",
        v0=start_vector,
        ncv=ncv,
        tol=tol,
    )
    runtime_seconds = time.perf_counter() - start

    lambda0 = float(values[0])
    eigenvector = vectors[:, 0]
    residual_vector = operator @ eigenvector - lambda0 * eigenvector
    relative_residual = float(np.linalg.norm(residual_vector) / abs(lambda0))

    if not math.isfinite(lambda0) or lambda0 <= 0.0:
        raise RuntimeError(f"non-positive or non-finite leading eigenvalue at L={L}")
    if not math.isfinite(relative_residual) or relative_residual > 10.0 * tol:
        raise RuntimeError(
            f"unconverged leading eigenpair at L={L}: residual={relative_residual:.3e}"
        )

    log_lambda0 = math.log(lambda0)
    return {
        "L": int(L),
        "dimension": operator.dimension,
        "lambda0": lambda0,
        "log_lambda0": log_lambda0,
        "reduced_free_energy": -log_lambda0 / L,
        "relative_residual": relative_residual,
        "runtime_seconds": runtime_seconds,
    }


_CSV_FIELDS = (
    "L",
    "dimension",
    "lambda0",
    "log_lambda0",
    "reduced_free_energy",
    "relative_residual",
    "runtime_seconds",
)


def _write_raw_plot(results, path):
    inv_l2 = np.asarray([1.0 / item["L"] ** 2 for item in results])
    free_energy = np.asarray([item["reduced_free_energy"] for item in results])
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(inv_l2, free_energy, color="tab:blue")
    for x_value, y_value, item in zip(inv_l2, free_energy, results):
        ax.annotate(f"L={item['L']}", (x_value, y_value), xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("1 / L^2")
    ax.set_ylabel("-log(lambda0) / L")
    ax.set_title("Critical clean Ising leading eigenvalue (raw, no fit)")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def run_sizes(sizes, output_dir, tol=1e-11):
    """Solve requested widths, incrementally write CSV, and make a raw plot."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "values.csv"
    plot_path = output_dir / "leading_eigenvalues.png"
    k = critical_coupling()
    results = []

    with csv_path.open("w", newline="") as handle:
        csv.DictWriter(handle, fieldnames=_CSV_FIELDS).writeheader()

    for L in sizes:
        result = dominant_eigenpair(int(L), k, k, tol=tol)
        results.append(result)
        with csv_path.open("a", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS)
            writer.writerow(result)
            handle.flush()
        print(
            f"L={result['L']}: lambda0={result['lambda0']:.15g}, "
            f"residual={result['relative_residual']:.3e}, "
            f"runtime={result['runtime_seconds']:.3f}s",
            flush=True,
        )

    _write_raw_plot(results, plot_path)
    return results


def build_parser():
    parser = argparse.ArgumentParser(
        description="Compute clean-Ising leading transfer eigenvalues without fitting."
    )
    parser.add_argument("--sizes", nargs="+", type=int, required=True)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/clean_ising_transfer")
    )
    parser.add_argument("--tol", type=float, default=1e-11)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    run_sizes(args.sizes, args.output_dir, tol=args.tol)
    print(
        f"wrote {args.output_dir / 'values.csv'} and "
        f"{args.output_dir / 'leading_eigenvalues.png'}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
