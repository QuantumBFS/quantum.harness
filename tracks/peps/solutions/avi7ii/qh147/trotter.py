from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm

from .model import site_index

X = np.array([[0.0, 1.0], [1.0, 0.0]])
Z = np.array([[1.0, 0.0], [0.0, -1.0]])


@dataclass(frozen=True)
class Gate:
    sites: tuple[int, ...]
    matrix: np.ndarray
    label: str
    weight: float


def _bond_layers(
    lx: int,
    ly: int,
) -> tuple[tuple[tuple[int, int], ...], ...]:
    hx = tuple(
        tuple(
            (site_index(x, y, ly), site_index(x + 1, y, ly))
            for x in range(parity, lx - 1, 2)
            for y in range(ly)
        )
        for parity in (0, 1)
    )
    vy = tuple(
        tuple(
            (site_index(x, y, ly), site_index(x, y + 1, ly))
            for x in range(lx)
            for y in range(parity, ly - 1, 2)
        )
        for parity in (0, 1)
    )
    return hx + vy


def second_order_gates(
    lx: int,
    ly: int,
    *,
    j: float,
    h: float,
    delta_beta: float,
) -> tuple[Gate, ...]:
    layers = _bond_layers(lx, ly)
    sequence: list[Gate] = []
    bond_op = np.kron(Z, Z)
    for layer_index, bonds in enumerate(layers):
        for sites in bonds:
            sequence.append(
                Gate(
                    sites,
                    expm(0.5 * delta_beta * j * bond_op).reshape(2, 2, 2, 2),
                    f"bond-{layer_index}",
                    0.5,
                )
            )
    for site in range(lx * ly):
        sequence.append(
            Gate((site,), expm(delta_beta * h * X), "field", 1.0)
        )
    for layer_index, bonds in reversed(tuple(enumerate(layers))):
        for sites in bonds:
            sequence.append(
                Gate(
                    sites,
                    expm(0.5 * delta_beta * j * bond_op).reshape(2, 2, 2, 2),
                    f"bond-{layer_index}",
                    0.5,
                )
            )
    return tuple(sequence)


def _embed(op: np.ndarray, sites: tuple[int, ...], nsites: int) -> np.ndarray:
    dim = 1 << nsites
    out = np.zeros((dim, dim), dtype=np.float64)
    op_matrix = op.reshape(1 << len(sites), 1 << len(sites))
    for state in range(dim):
        local_in = sum(
            ((state >> site) & 1) << k for k, site in enumerate(sites)
        )
        for local_out in range(1 << len(sites)):
            target = state
            for k, site in enumerate(sites):
                target = (target & ~(1 << site)) | (
                    ((local_out >> k) & 1) << site
                )
            out[target, state] += op_matrix[local_out, local_in]
    return out


def dense_trotter_step(
    lx: int,
    ly: int,
    *,
    j: float,
    h: float,
    delta_beta: float,
) -> np.ndarray:
    result = np.eye(1 << (lx * ly))
    for gate in second_order_gates(
        lx,
        ly,
        j=j,
        h=h,
        delta_beta=delta_beta,
    ):
        result = _embed(gate.matrix, gate.sites, lx * ly) @ result
    return result
