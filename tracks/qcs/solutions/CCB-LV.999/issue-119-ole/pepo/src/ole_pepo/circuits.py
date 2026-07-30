"""Immutable circuit profiles for the issue-119 PEPO calculations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .qasm import OLEProtocol, read_validated_qasm


@dataclass(frozen=True, slots=True)
class CircuitProfile:
    name: str
    qasm_relative_path: str
    qasm_sha256: str
    qasm_bytes: int
    expected_layers: int
    expected_cz: int
    observable_sites: tuple[int, ...]
    oracle_run_name: str
    source_qasm3_sha256: str | None = None
    canonical_equal_to_source_qasm3: bool | None = None
    expected_register_size: int = 156
    expected_active_sites: int = 49
    perturbation_angle: float = 0.3
    perturbation_count: int = 24


_CIRCUITS = {
    "baseline": CircuitProfile(
        name="baseline",
        qasm_relative_path="inputs/49Q_OLE_circuit_L_3_b_0.25_delta0.15.qasm",
        qasm_sha256=(
            "1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455"
        ),
        qasm_bytes=150686,
        expected_layers=73,
        expected_cz=648,
        observable_sites=(52, 59, 72),
        oracle_run_name="issue119-pepo-small-oracle",
    ),
    "active": CircuitProfile(
        name="active",
        qasm_relative_path="inputs/49Q_OLE_circuit_L_6_b_0.25_delta0.15.qasm",
        qasm_sha256=(
            "d237a273c7cc233e9d64039ad06613af17eb472b19bda12f4ce458b9c4541645"
        ),
        qasm_bytes=297926,
        expected_layers=145,
        expected_cz=1296,
        observable_sites=(52, 59, 72),
        oracle_run_name="issue119-pepo-active-small-oracle",
        source_qasm3_sha256=(
            "3748e2c026c118f9d6c7499093ea43e41a45251b6bf8d3adb6fb056f718f6cc0"
        ),
        canonical_equal_to_source_qasm3=True,
    ),
}


def get_circuit_profile(name: str) -> CircuitProfile:
    """Resolve one explicitly named immutable circuit profile."""
    try:
        return _CIRCUITS[name]
    except KeyError as error:
        choices = ", ".join(sorted(_CIRCUITS))
        raise ValueError(f"unknown circuit {name!r}; expected one of: {choices}") from error


def load_circuit_protocol(profile: CircuitProfile, ole_root: str | Path) -> OLEProtocol:
    """Load a profile and reject any structural drift before numerical work."""
    root = Path(ole_root)
    protocol = read_validated_qasm(
        root / profile.qasm_relative_path,
        profile.qasm_sha256,
        profile.qasm_bytes,
    )
    checks = {
        "register size": (protocol.register_size, profile.expected_register_size),
        "active sites": (len(protocol.active_sites), profile.expected_active_sites),
        "layers": (len(protocol.layers), profile.expected_layers),
        "barriers": (protocol.barrier_count, profile.expected_layers),
        "CZ gates": (
            sum(gate.name == "cz" for gate in protocol.gates),
            profile.expected_cz,
        ),
        "perturbation gates": (
            sum(
                gate.name == "rz"
                and gate.angle is not None
                and np.isclose(
                    gate.angle,
                    profile.perturbation_angle,
                    atol=8 * np.finfo(float).eps,
                    rtol=0,
                )
                for gate in protocol.gates
            ),
            profile.perturbation_count,
        ),
    }
    for label, (actual, expected) in checks.items():
        if actual != expected:
            raise ValueError(
                f"{profile.name} circuit {label} changed: expected {expected}, got {actual}"
            )
    return protocol
