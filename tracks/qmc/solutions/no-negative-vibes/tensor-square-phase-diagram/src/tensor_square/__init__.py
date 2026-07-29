"""Tensor-square phase-diagram research code."""

from .algebra import (
    exterior_square,
    kron_sum,
    tensor_square_weight_direct,
    tensor_square_weight_eigenvalues,
    tensor_square_weight_factorized,
)
from .fock import (
    basis_states,
    d_gamma,
    many_body_hamiltonian,
    normal_ordered_q_square,
)

__all__ = [
    "basis_states",
    "d_gamma",
    "exterior_square",
    "kron_sum",
    "many_body_hamiltonian",
    "normal_ordered_q_square",
    "tensor_square_weight_direct",
    "tensor_square_weight_eigenvalues",
    "tensor_square_weight_factorized",
]
