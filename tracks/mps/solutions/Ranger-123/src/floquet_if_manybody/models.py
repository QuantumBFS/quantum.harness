"""Hamiltonians for the open-boundary driven transverse-field Ising model."""

from __future__ import annotations

import numpy as np

from .config import ModelConfig
from .operators import ComplexMatrix, collective_operator, product_operator


def coupling_operator(config: ModelConfig) -> ComplexMatrix:
    return collective_operator("z", config.n, config.eta)


def drive_operator(config: ModelConfig) -> ComplexMatrix:
    return collective_operator("z", config.n, config.drive_eta)


def ising_hamiltonian(config: ModelConfig) -> ComplexMatrix:
    dimension = 2**config.n
    hamiltonian = np.zeros((dimension, dimension), dtype=np.complex128)
    for site in range(config.n - 1):
        hamiltonian -= config.j * product_operator({site: "z", site + 1: "z"}, config.n)
    hamiltonian += (config.omega / 2) * collective_operator("x", config.n)
    if config.counterterm:
        s = coupling_operator(config)
        hamiltonian += config.counterterm_strength * (s @ s)
    return hamiltonian


def driven_hamiltonian(config: ModelConfig, time: float) -> ComplexMatrix:
    return np.asarray(
        ising_hamiltonian(config)
        + config.drive_amplitude
        * np.cos(config.drive_frequency * time)
        * drive_operator(config),
        dtype=np.complex128,
    )
