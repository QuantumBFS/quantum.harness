from __future__ import annotations

from fractions import Fraction

import numpy as np
from scipy.linalg import expm

from .algebra import to_dense
from .hamiltonian import four_matching_fragments, fragment_from_bonds
from .higher_order import fourth_order_suzuki_stages
from .lattice import SquareLattice
# A short outward-rounded summary of the schema-v3 bound at N=144, r=116.
# The exact rational value remains in certificates/issue128-certificate.json.
REFINED_BOUND_N144 = Fraction(973, 10**9)
REFINED_STEPS = 116


def small_exact_crosscheck(
    length: int,
    tolerance: Fraction,
) -> dict[str, object]:
    if length == 2:
        groups = (
            ((0, 1), (2, 3)),
            ((0, 1), (2, 3)),
            ((0, 2), (1, 3)),
            ((0, 2), (1, 3)),
        )
        fragments = tuple(fragment_from_bonds(group) for group in groups)
        n_sites = 4
    else:
        lattice = SquareLattice(length)
        fragments = four_matching_fragments(lattice)
        n_sites = lattice.n_sites
    matrices = [to_dense(fragment, n_sites) for fragment in fragments]
    hamiltonian = sum(matrices, np.zeros_like(matrices[0]))
    steps = REFINED_STEPS
    delta = 1 / steps
    one_step = np.eye(1 << n_sites, dtype=np.complex128)
    for stage in fourth_order_suzuki_stages(4):
        one_step = one_step @ expm(
            -1j * float(stage.coefficient) * delta * matrices[stage.fragment_index]
        )
    approximation = np.linalg.matrix_power(one_step, steps)
    exact = expm(-1j * hamiltonian)
    error = float(np.linalg.norm(approximation - exact, ord=2))
    bound = float(REFINED_BOUND_N144 * Fraction(n_sites, 144))
    return {
        "length": length,
        "n_sites": n_sites,
        "model_note": (
            "degenerate 2x2 periodic algebra sanity check for schema-v3 r=116"
            if length == 2
            else "periodic square lattice"
        ),
        "steps": steps,
        "empirical_operator_norm_error": error,
        "certified_upper_bound": bound,
        "requested_tolerance": float(tolerance),
        "bound_dominates_empirical_error": bound >= error,
        "bound_meets_tolerance": bound <= float(tolerance),
    }
