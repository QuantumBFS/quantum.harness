"""Stage-3A evidence for the pinned RBIM fermionic baseline."""

from __future__ import annotations

import math
from pathlib import Path
import subprocess
from typing import Any

import numpy as np

from .conventions import NISHIMORI_PC, nishimori_coupling
from .exact import BondFields, row_transfer_amplitude
from .rbim import fermionic_log_partition


def _write_bonds(
    path: Path,
    vertical: np.ndarray,
    horizontal: np.ndarray,
    coupling: float,
    qr_interval: int,
) -> None:
    lines = [
        f"{vertical.shape[0]} {vertical.shape[1]} "
        f"{coupling:.17g} {qr_interval}"
    ]
    lines.extend(" ".join(str(int(value)) for value in row) for row in vertical)
    lines.extend(" ".join(str(int(value)) for value in row) for row in horizontal)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_stage3a_metrics(
    upstream_driver: str | Path,
    scratch: str | Path,
    upstream_smoke: str | Path,
) -> dict[str, Any]:
    coupling = nishimori_coupling(NISHIMORI_PC)
    rng = np.random.default_rng(2026072703)
    scratch_path = Path(scratch)
    scratch_path.mkdir(parents=True, exist_ok=True)

    exact_errors: list[float] = []
    upstream_errors: list[float] = []
    interval_errors: list[float] = []
    orthogonality_errors: list[float] = []

    for sample in range(64):
        vertical = rng.choice((-1, 1), size=(5, 4)).astype(np.int8)
        horizontal = rng.choice((-1, 1), size=(4, 4)).astype(np.int8)
        fields = BondFields(
            s_horizontal=vertical,
            s_vertical=horizontal,
        )
        sign, exact_log = row_transfer_amplitude(fields, coupling)
        if sign != 1:
            raise AssertionError("positive RBIM partition acquired negative sign")
        internal, orthogonality = fermionic_log_partition(
            vertical,
            horizontal,
            coupling,
            qr_interval=1,
        )
        exact_errors.append(abs(internal - exact_log))
        orthogonality_errors.append(orthogonality)

        if sample < 16:
            bond_path = scratch_path / f"bonds-{sample:03d}.txt"
            _write_bonds(bond_path, vertical, horizontal, coupling, 1)
            process = subprocess.run(
                [str(upstream_driver), str(bond_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            upstream_log = float(process.stdout.strip().splitlines()[-1])
            upstream_errors.append(abs(internal - upstream_log))

    for _ in range(1_000):
        vertical = rng.choice((-1, 1), size=(12, 6)).astype(np.int8)
        horizontal = rng.choice((-1, 1), size=(11, 6)).astype(np.int8)
        interval_one, error_one = fermionic_log_partition(
            vertical,
            horizontal,
            coupling,
            qr_interval=1,
        )
        interval_five, error_five = fermionic_log_partition(
            vertical,
            horizontal,
            coupling,
            qr_interval=5,
        )
        interval_errors.append(abs(interval_one - interval_five))
        orthogonality_errors.extend((error_one, error_five))

    smoke_path = Path(upstream_smoke)
    smoke_log0 = smoke_path / "logZ0_raw_data.bin"
    smoke_log1 = smoke_path / "logZ1_raw_data.bin"
    expected_smoke_values = 4
    smoke_values0 = np.fromfile(smoke_log0, dtype=np.float64)
    smoke_values1 = np.fromfile(smoke_log1, dtype=np.float64)
    smoke_finite = bool(
        smoke_values0.size == expected_smoke_values
        and smoke_values1.size == expected_smoke_values
        and np.all(np.isfinite(smoke_values0))
        and np.all(np.isfinite(smoke_values1))
    )

    metrics: dict[str, Any] = {
        "p": NISHIMORI_PC,
        "coupling": coupling,
        "exact_spin_samples": len(exact_errors),
        "exact_spin_max_logZ_absolute_error": max(exact_errors),
        "upstream_fixed_driver_samples": len(upstream_errors),
        "upstream_fixed_driver_max_logZ_absolute_error": max(upstream_errors),
        "qr_interval_samples": len(interval_errors),
        "qr_interval_1_vs_5_max_logZ_absolute_error": max(interval_errors),
        "qr_interval_absolute_tolerance": 5.0e-10,
        "maximum_orthogonality_error": max(orthogonality_errors),
        "upstream_smoke_logZ0_values": smoke_values0.tolist(),
        "upstream_smoke_logZ1_values": smoke_values1.tolist(),
        "upstream_smoke_binary_interface_finite": smoke_finite,
    }
    gates = {
        "spin_transfer_matches_fermionic": bool(max(exact_errors) < 2.0e-10),
        "fixed_upstream_matches_internal": bool(max(upstream_errors) < 2.0e-10),
        "qr_intervals_1_and_5_match": bool(max(interval_errors) < 5.0e-10),
        "orthogonality_below_1e_minus_10": bool(
            max(orthogonality_errors) < 1.0e-10
        ),
        "upstream_binary_interface_reproduced": smoke_finite,
    }
    metrics["gates"] = gates
    metrics["all_gates_passed"] = all(gates.values())
    if not math.isfinite(metrics["coupling"]):
        raise FloatingPointError("non-finite Nishimori coupling")
    return metrics
