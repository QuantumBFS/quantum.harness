"""Finite-temperature exact diagonalization for the m=3 DQMC oracle."""

from __future__ import annotations

import numpy as np

from .algebra import kron_sum
from .dqmc import DQMCConfig, make_one_body_model
from .fock import basis_states, d_gamma, many_body_hamiltonian


def thermal_m3(config: DQMCConfig) -> dict[str, float]:
    if config.m != 3:
        raise ValueError("full thermal ED is restricted to m=3")
    model = make_one_body_model(config)
    hamiltonian, basis, q_ops = many_body_hamiltonian(
        config.m,
        model.k,
        model.channels,
        model.couplings,
    )
    dense = hamiltonian.toarray()
    energies, vectors = np.linalg.eigh(dense)
    shifted = energies - energies[0]
    weights = np.exp(-config.beta * shifted)
    probabilities = weights / np.sum(weights)
    number_diagonal = np.asarray(
        [int(state).bit_count() for state in basis], dtype=np.float64
    )
    number_per_eigenstate = np.sum(
        np.abs(vectors) ** 2 * number_diagonal[:, None], axis=0
    )
    q_square_by_channel = []
    for q_operator in q_ops:
        transformed = q_operator @ vectors
        q_square_by_channel.append(
            np.sum(np.abs(transformed) ** 2, axis=0)
        )
    modes = config.m * config.m
    q_a = sum(q_ops[index] for index in model.group_a)
    q_b = sum(q_ops[index] for index in model.group_b)
    qa_transformed = q_a @ vectors
    qb_transformed = q_b @ vectors
    nematic = d_gamma(kron_sum(model.nematic), basis)
    nematic_transformed = nematic @ vectors
    qa2 = np.sum(np.abs(qa_transformed) ** 2, axis=0)
    qb2 = np.sum(np.abs(qb_transformed) ** 2, axis=0)
    nematic2 = np.sum(np.abs(nematic_transformed) ** 2, axis=0)
    return {
        "energy": float(np.dot(probabilities, energies)),
        "density": float(
            np.dot(probabilities, number_per_eigenstate) / modes
        ),
        "q_a_sq": float(
            np.dot(probabilities, qa2) / (len(model.group_a) * modes)
        ),
        "q_b_sq": float(
            np.dot(probabilities, qb2) / (len(model.group_b) * modes)
        ),
        "q_combined": float(
            0.5
            * (
                np.dot(probabilities, qa2) / (len(model.group_a) * modes)
                + np.dot(probabilities, qb2) / (len(model.group_b) * modes)
            )
        ),
        "nematic_sq": float(np.dot(probabilities, nematic2) / (modes * modes)),
        "partition_shifted": float(np.sum(weights)),
        "hilbert_dimension": len(basis),
    }
