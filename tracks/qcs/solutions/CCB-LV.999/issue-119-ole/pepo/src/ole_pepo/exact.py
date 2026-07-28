"""Independent NumPy dense oracle for small audited OLE protocols."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from .qasm import OLEProtocol, QASMGate, crop_protocol


SEVEN_SITE_ORACLE = frozenset({33, 39, 53, 52, 51, 50, 49})
SEVEN_SITE_OBSERVABLE = (52,)
_SEVEN_SITE_EDGES = frozenset(
    {
        (33, 39),
        (39, 53),
        (52, 53),
        (51, 52),
        (50, 51),
        (49, 50),
    }
)


def dense_gate_matrix(gate: QASMGate) -> np.ndarray:
    """Return an analytic dense matrix without using the PEPO gate path."""
    if gate.name == "rx":
        if gate.angle is None:
            raise ValueError("parameterized gate 'rx' requires an angle")
        half_angle = gate.angle / 2
        return np.array(
            [
                [np.cos(half_angle), -1j * np.sin(half_angle)],
                [-1j * np.sin(half_angle), np.cos(half_angle)],
            ],
            dtype=np.complex128,
        )
    if gate.name == "rz":
        if gate.angle is None:
            raise ValueError("parameterized gate 'rz' requires an angle")
        half_angle = gate.angle / 2
        return np.diag([np.exp(-1j * half_angle), np.exp(1j * half_angle)]).astype(
            np.complex128
        )
    if gate.angle is not None:
        raise ValueError(f"fixed gate {gate.name!r} does not accept an angle")
    if gate.name == "s":
        return np.diag([1.0, 1.0j]).astype(np.complex128)
    if gate.name == "sdg":
        return np.diag([1.0, -1.0j]).astype(np.complex128)
    if gate.name == "sx":
        return 0.5 * np.array(
            [[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]], dtype=np.complex128
        )
    if gate.name == "sxdg":
        return 0.5 * np.array(
            [[1 - 1j, 1 + 1j], [1 + 1j, 1 - 1j]], dtype=np.complex128
        )
    if gate.name == "cz":
        return np.diag([1.0, 1.0, 1.0, -1.0]).astype(np.complex128)
    raise ValueError(f"unsupported dense gate matrix: {gate.name!r}")


def _left_apply(
    unitary: np.ndarray,
    gate: np.ndarray,
    targets: tuple[int, ...],
    nsites: int,
) -> np.ndarray:
    untouched = tuple(i for i in range(nsites) if i not in targets)
    permutation = targets + untouched + tuple(range(nsites, 2 * nsites))
    inverse = np.argsort(permutation)
    tensor = unitary.reshape((2,) * (2 * nsites)).transpose(permutation)
    front = tensor.reshape(2 ** len(targets), -1)
    updated = (gate @ front).reshape((2,) * (2 * nsites))
    return updated.transpose(inverse).reshape(unitary.shape)


def _site_order(protocol: OLEProtocol, site_order: tuple[int, ...] | None) -> tuple[int, ...]:
    sites = protocol.active_sites if site_order is None else tuple(site_order)
    if len(set(sites)) != len(sites):
        raise ValueError("site_order contains duplicate physical labels")
    missing = set(protocol.active_sites).difference(sites)
    if missing:
        raise ValueError(f"site_order omits active physical labels: {sorted(missing)}")
    return sites


def dense_unitary(
    protocol: OLEProtocol,
    site_order: tuple[int, ...] | None = None,
    max_sites: int = 12,
) -> np.ndarray:
    """Evolve an OLE protocol as a small dense unitary in physical-label order."""
    sites = _site_order(protocol, site_order)
    if len(sites) > max_sites:
        raise ValueError(
            f"dense protocol has {len(sites)} sites, exceeding max_sites={max_sites}"
        )
    positions = {site: position for position, site in enumerate(sites)}
    dimension = 2 ** len(sites)
    unitary = np.eye(dimension, dtype=np.complex128)
    for gate in protocol.gates:
        try:
            targets = tuple(positions[site] for site in gate.qubits)
        except KeyError as error:
            raise ValueError(f"gate uses a site missing from site_order: {error.args[0]}") from error
        unitary = _left_apply(unitary, dense_gate_matrix(gate), targets, len(sites))
    return unitary


def pauli_product_dense(
    site_order: tuple[int, ...], observable_sites: tuple[int, ...]
) -> np.ndarray:
    """Build Z on ``observable_sites`` and I on every other ordered site."""
    sites = tuple(site_order)
    if len(set(sites)) != len(sites):
        raise ValueError("site_order contains duplicate physical labels")
    unknown = set(observable_sites).difference(sites)
    if unknown:
        raise ValueError(f"observable_sites are absent from site_order: {sorted(unknown)}")
    observable_set = frozenset(observable_sites)
    product = np.array([[1.0]], dtype=np.complex128)
    for site in sites:
        factor = (
            np.array([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)
            if site in observable_set
            else np.eye(2, dtype=np.complex128)
        )
        product = np.kron(product, factor)
    return product


def normalized_ole_dense(
    protocol: OLEProtocol, observable_sites: tuple[int, ...]
) -> complex:
    """Compute the normalized infinite-temperature OLE trace exactly."""
    site_order = protocol.active_sites
    unitary = dense_unitary(protocol, site_order=site_order)
    observable = pauli_product_dense(site_order, observable_sites)
    evolved = unitary.conj().T @ observable @ unitary
    value = np.trace(observable @ evolved) / (2 ** len(site_order))
    return complex(value)


def seven_site_oracle_protocol(
    full_protocol: OLEProtocol, delta_zero: bool = False
) -> OLEProtocol:
    """Crop the audited seven-site OLE fixture and optionally set δ to zero."""
    cropped = crop_protocol(full_protocol, SEVEN_SITE_ORACLE)
    edges = frozenset(
        tuple(sorted(gate.qubits)) for gate in cropped.gates if gate.name == "cz"
    )
    if edges != _SEVEN_SITE_EDGES:
        raise ValueError(f"unexpected seven-site CZ edges: {sorted(edges)}")
    perturbations = tuple(
        gate
        for gate in cropped.gates
        if gate.name == "rz"
        and gate.angle is not None
        and np.isclose(gate.angle, 0.3, atol=8 * np.finfo(float).eps, rtol=0)
    )
    if len(perturbations) != 2 or {gate.qubits for gate in perturbations} != {
        (33,),
        (49,),
    }:
        raise ValueError("seven-site crop must contain rz(0.3) perturbations on 33 and 49")
    if not delta_zero:
        return cropped
    perturbation_ids = {gate.gate_index for gate in perturbations}
    return replace(
        cropped,
        layers=tuple(
            tuple(
                replace(gate, angle=0.0)
                if gate.gate_index in perturbation_ids
                else gate
                for gate in layer
            )
            for layer in cropped.layers
        ),
    )
