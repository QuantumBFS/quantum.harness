import numpy as np

from oracle.symmetric_oddcycle_full_fock import (
    cross_perturbed_initial,
    preconditioned_problem,
)


def test_grade24_preconditioner_and_cross_perturbation_are_full_rank():
    atoms, base, split, grades = preconditioned_problem(known="24")
    assert grades == (0, 2, 4, 5, 1, 3)
    assert all(atom.shape == (32, 32) for atom in atoms)
    assert split == 17
    assert np.linalg.matrix_rank(base) == 32
    perturbed = cross_perturbed_initial(
        base,
        split=split,
        epsilon=1.0e-4,
        rng=np.random.default_rng(121),
    )
    assert np.linalg.matrix_rank(perturbed) == 32
    assert not np.array_equal(perturbed, base)
