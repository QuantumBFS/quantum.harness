"""Minimal Hubbard--Stratonovich realization of the open-path TN class."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.linalg import expm


@dataclass(frozen=True)
class HubbardChainWeight:
    determinant_up: float
    determinant_down: float
    hs_prefactor: float

    @property
    def total(self) -> float:
        return self.hs_prefactor * self.determinant_up * self.determinant_down


@dataclass(frozen=True)
class SpinlessChainWeight:
    determinant: float
    hs_prefactor: float

    @property
    def total(self) -> float:
        return self.hs_prefactor * self.determinant


def hirsch_parameters(
    *,
    time_step: float,
    interaction: float,
) -> tuple[float, float]:
    """Return ``(lambda, C)`` for the repulsive discrete spin-channel HS rule."""

    if time_step <= 0.0:
        raise ValueError("time_step must be positive")
    if interaction < 0.0:
        raise ValueError("interaction must be nonnegative")
    coupling = math.acosh(math.exp(0.5 * time_step * interaction))
    prefactor = 0.5 * math.exp(-0.25 * time_step * interaction)
    return coupling, prefactor


def open_chain_kinetic_generator(
    *,
    sites: int,
    time_step: float,
    hopping: float,
    chemical_potential: float,
) -> np.ndarray:
    """Build ``-dt h_0`` for an open chain with ``h_0=-t adjacency-mu I``."""

    if sites < 1:
        raise ValueError("sites must be positive")
    if time_step <= 0.0:
        raise ValueError("time_step must be positive")
    if hopping < 0.0:
        raise ValueError("hopping must be nonnegative in the chosen fixed gauge")

    generator = np.eye(sites) * (time_step * chemical_potential)
    edge = time_step * hopping
    indices = np.arange(sites - 1)
    generator[indices, indices + 1] = edge
    generator[indices + 1, indices] = edge
    return generator


def slice_matrices(
    fields: np.ndarray,
    *,
    time_step: float,
    hopping: float,
    interaction: float,
    chemical_potential: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return symmetric-Trotter one-body matrices for one Ising HS slice."""

    spins = np.asarray(fields, dtype=float)
    if spins.ndim != 1 or not np.all(np.isin(spins, (-1.0, 1.0))):
        raise ValueError("fields must be a one-dimensional array of +/-1")

    coupling, _ = hirsch_parameters(
        time_step=time_step,
        interaction=interaction,
    )
    kinetic = open_chain_kinetic_generator(
        sites=spins.size,
        time_step=time_step,
        hopping=hopping,
        chemical_potential=chemical_potential,
    )
    half_kinetic = expm(0.5 * kinetic)
    up = half_kinetic @ np.diag(np.exp(coupling * spins)) @ half_kinetic
    down = half_kinetic @ np.diag(np.exp(-coupling * spins)) @ half_kinetic
    return up, down


def configuration_weight(
    field_history: np.ndarray,
    *,
    time_step: float,
    hopping: float,
    interaction: float,
    chemical_potential: float,
) -> HubbardChainWeight:
    """Evaluate one finite-temperature DQMC configuration on an open chain."""

    history = np.asarray(field_history, dtype=float)
    if history.ndim != 2 or history.shape[0] < 1 or history.shape[1] < 1:
        raise ValueError("field_history must have shape (slices, sites)")

    product_up = np.eye(history.shape[1])
    product_down = np.eye(history.shape[1])
    for fields in history:
        slice_up, slice_down = slice_matrices(
            fields,
            time_step=time_step,
            hopping=hopping,
            interaction=interaction,
            chemical_potential=chemical_potential,
        )
        product_up = product_up @ slice_up
        product_down = product_down @ slice_down

    _, one_site_prefactor = hirsch_parameters(
        time_step=time_step,
        interaction=interaction,
    )
    hs_prefactor = one_site_prefactor ** history.size
    determinant_up = float(np.linalg.det(np.eye(history.shape[1]) + product_up))
    determinant_down = float(
        np.linalg.det(np.eye(history.shape[1]) + product_down)
    )
    return HubbardChainWeight(
        determinant_up=determinant_up,
        determinant_down=determinant_down,
        hs_prefactor=hs_prefactor,
    )


def spinless_slice_matrix(
    bond_fields: np.ndarray,
    *,
    time_step: float,
    hopping: float,
    interaction: float,
    chemical_potential: float,
) -> np.ndarray:
    """Build one slice for the repulsive spinless open-chain ``t-V`` model."""

    fields = np.asarray(bond_fields, dtype=float)
    if fields.ndim != 1 or fields.size < 1:
        raise ValueError("bond_fields must be a nonempty one-dimensional array")
    if not np.all(np.isin(fields, (-1.0, 1.0))):
        raise ValueError("bond_fields must contain only +/-1")

    coupling, _ = hirsch_parameters(
        time_step=time_step,
        interaction=interaction,
    )
    sites = fields.size + 1
    kinetic = open_chain_kinetic_generator(
        sites=sites,
        time_step=time_step,
        hopping=hopping,
        chemical_potential=chemical_potential,
    )
    diagonal_field = np.zeros(sites)
    diagonal_field[:-1] += coupling * fields
    diagonal_field[1:] -= coupling * fields
    half_kinetic = expm(0.5 * kinetic)
    return (
        half_kinetic
        @ np.diag(np.exp(diagonal_field))
        @ half_kinetic
    )


def spinless_configuration_weight(
    field_history: np.ndarray,
    *,
    time_step: float,
    hopping: float,
    interaction: float,
    chemical_potential: float,
) -> SpinlessChainWeight:
    """Evaluate one finite-temperature configuration of an open ``t-V`` chain."""

    history = np.asarray(field_history, dtype=float)
    if history.ndim != 2 or history.shape[0] < 1 or history.shape[1] < 1:
        raise ValueError("field_history must have shape (slices, bonds)")

    sites = history.shape[1] + 1
    product_matrix = np.eye(sites)
    for fields in history:
        product_matrix = product_matrix @ spinless_slice_matrix(
            fields,
            time_step=time_step,
            hopping=hopping,
            interaction=interaction,
            chemical_potential=chemical_potential,
        )

    _, one_bond_prefactor = hirsch_parameters(
        time_step=time_step,
        interaction=interaction,
    )
    determinant = float(np.linalg.det(np.eye(sites) + product_matrix))
    return SpinlessChainWeight(
        determinant=determinant,
        hs_prefactor=one_bond_prefactor ** history.size,
    )
