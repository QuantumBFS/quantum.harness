#!/usr/bin/env python3
"""Compare a tiny TeNPy purification run with dense exact dynamics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.linalg import expm


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research_dataset import load_research_dataset


def _embedded(operator: np.ndarray, site: int, length: int) -> np.ndarray:
    result = np.asarray([[1.0 + 0.0j]])
    identity = np.eye(2, dtype=complex)
    for index in range(length):
        result = np.kron(result, operator if index == site else identity)
    return result


def dense_j1_j2_operators(
    *,
    length: int,
    coupling: float,
    delta: float,
    j2: float,
) -> tuple[np.ndarray, list[np.ndarray], list[np.ndarray]]:
    """Build the dense Hamiltonian, physical-cut currents, and local Sz.

    A physical cut current contains every range-one and range-two XY bond
    crossing that cut.  Consequently the returned operators obey the exact
    lattice continuity identity site by site.
    """

    length = int(length)
    if length < 2:
        raise ValueError("Dense chain length must be at least two")
    values = np.asarray([coupling, delta, j2], dtype=float)
    if np.any(~np.isfinite(values)):
        raise ValueError("Hamiltonian parameters must be finite")

    sp = np.asarray([[0.0, 1.0], [0.0, 0.0]], dtype=complex)
    sm = sp.T.conj()
    sx = 0.5 * (sp + sm)
    sy = (sp - sm) / (2.0j)
    sz = np.diag([0.5, -0.5]).astype(complex)
    sx_ops = [_embedded(sx, site, length) for site in range(length)]
    sy_ops = [_embedded(sy, site, length) for site in range(length)]
    sz_ops = [_embedded(sz, site, length) for site in range(length)]

    dimension = 2**length
    hamiltonian = np.zeros((dimension, dimension), dtype=complex)
    cut_currents = [
        np.zeros_like(hamiltonian) for _ in range(length - 1)
    ]
    for site in range(length - 1):
        hamiltonian += -coupling * (
            sx_ops[site] @ sx_ops[site + 1]
            + sy_ops[site] @ sy_ops[site + 1]
            + delta * sz_ops[site] @ sz_ops[site + 1]
        )
        current = -coupling * (
            sx_ops[site] @ sy_ops[site + 1]
            - sy_ops[site] @ sx_ops[site + 1]
        )
        cut_currents[site] += current
    for site in range(length - 2):
        hamiltonian += -j2 * (
            sx_ops[site] @ sx_ops[site + 2]
            + sy_ops[site] @ sy_ops[site + 2]
            + sz_ops[site] @ sz_ops[site + 2]
        )
        current = -j2 * (
            sx_ops[site] @ sy_ops[site + 2]
            - sy_ops[site] @ sx_ops[site + 2]
        )
        cut_currents[site] += current
        cut_currents[site + 1] += current
    return hamiltonian, cut_currents, sz_ops


def _dense_reference(path: Path) -> dict[str, object]:
    dataset = load_research_dataset(path)
    if (
        dataset.m is None
        or dataset.current is None
        or dataset.czz is None
        or dataset.fcs_gamma is None
        or dataset.fcs_logZ is None
    ):
        raise ValueError("Dataset must contain m, current, Czz, and FCS")
    length = dataset.x.size
    if length > 10:
        raise ValueError("Dense validation is restricted to L <= 10")

    J = float(dataset.metadata["J"])
    delta = float(dataset.metadata["delta"])
    j2 = float(dataset.metadata.get("J2", 0.0))
    hamiltonian, currents, sz_ops = dense_j1_j2_operators(
        length=length,
        coupling=J,
        delta=delta,
        j2=j2,
    )

    rho0 = np.asarray([[1.0 + 0.0j]])
    for value in dataset.m[0]:
        rho0 = np.kron(
            rho0,
            np.diag([0.5 + float(value), 0.5 - float(value)]),
        )
    rho0 /= np.trace(rho0)
    q_right = sum(sz_ops[length // 2 :])
    center = length // 2

    exact_m: list[np.ndarray] = []
    exact_current: list[np.ndarray] = []
    exact_czz: list[np.ndarray] = []
    exact_logz: list[np.ndarray] = []
    for time in dataset.t:
        unitary = expm(-1j * hamiltonian * float(time))
        rho = unitary @ rho0 @ unitary.conj().T
        magnetization = np.asarray(
            [np.trace(rho @ operator) for operator in sz_ops],
            dtype=complex,
        )
        exact_m.append(np.real(magnetization))
        exact_current.append(
            np.real(
                np.asarray(
                    [np.trace(rho @ operator) for operator in currents],
                    dtype=complex,
                )
            )
        )
        exact_czz.append(
            np.real(
                np.asarray(
                    [
                        np.trace(rho @ sz_ops[center] @ operator)
                        - magnetization[center] * magnetization[index]
                        for index, operator in enumerate(sz_ops)
                    ],
                    dtype=complex,
                )
            )
        )
        logz = []
        for gamma in dataset.fcs_gamma:
            plus = expm(1j * float(gamma) * q_right)
            minus = plus.conj().T
            characteristic = np.trace(
                rho0
                @ unitary.conj().T
                @ plus
                @ unitary
                @ minus
            )
            logz.append(np.log(characteristic))
        exact_logz.append(np.asarray(logz))

    exact_m_array = np.stack(exact_m)
    exact_current_array = np.stack(exact_current)
    exact_czz_array = np.stack(exact_czz)
    exact_logz_array = np.stack(exact_logz)
    errors = {
        "magnetization_max_abs": float(
            np.max(np.abs(dataset.m - exact_m_array))
        ),
        "current_max_abs": float(
            np.max(np.abs(dataset.current - exact_current_array))
        ),
        "czz_max_abs": float(
            np.max(np.abs(dataset.czz - exact_czz_array))
        ),
        "fcs_logZ_max_abs": float(
            np.max(np.abs(dataset.fcs_logZ - exact_logz_array))
        ),
    }
    thresholds = {
        "magnetization_max_abs": 2e-7,
        "current_max_abs": 2e-7,
        "czz_max_abs": 2e-7,
        "fcs_logZ_max_abs": 2e-7,
    }
    checks = {
        name: errors[name] < threshold
        for name, threshold in thresholds.items()
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "input": str(path.resolve()),
        "L": length,
        "times": [float(value) for value in dataset.t],
        "hamiltonian": (
            "-J sum_nn(SxSx+SySy+Delta SzSz) "
            "-J2 sum_nnn(SxSx+SySy+SzSz), open boundary"
        ),
        "errors": errors,
        "thresholds": thresholds,
        "checks": checks,
    }


def _report(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# TeNPy versus dense exact dynamics",
            "",
            f"**Status:** `{summary['status']}`",
            "",
            f"- chain length: `{summary['L']}`",
            f"- saved times: `{summary['times']}`",
            f"- Hamiltonian: `{summary['hamiltonian']}`",
            "",
            "| Observable | max absolute error | threshold |",
            "|---|---:|---:|",
            *[
                f"| {name} | {summary['errors'][name]:.6e} | "
                f"{summary['thresholds'][name]:.6e} |"
                for name in summary["errors"]
            ],
            "",
            "This independently constructs the full density matrix and dense "
            "unitary. It checks the Hamiltonian sign, current operator, "
            "connected correlation, purification dynamics, and counting-field "
            "ordering together.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "exact_reference_smoke.npz",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "exact_validation",
    )
    args = parser.parse_args()
    summary = _dense_reference(args.input)
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    (args.outdir / "REPORT.md").write_text(_report(summary))
    print(json.dumps(summary, ensure_ascii=False))
    if summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
