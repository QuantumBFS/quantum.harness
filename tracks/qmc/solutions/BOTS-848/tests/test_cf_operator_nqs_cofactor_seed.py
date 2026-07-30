from __future__ import annotations

import numpy as np
import pytest

from scalable_v1.routes.cf_operator_nqs.cofactor_seed import (
    cofactor_seed_family_amplitudes,
)
from scalable_v1.routes.cf_operator_nqs.seeds import JKCFSeedFamily


def _configs(n_electrons: int) -> np.ndarray:
    rng = np.random.default_rng(848 + n_electrons)
    values = rng.normal(size=(2, n_electrons, 2)) + 1j * rng.normal(
        size=(2, n_electrons, 2)
    )
    return values / np.linalg.norm(values, axis=-1, keepdims=True)


@pytest.mark.parametrize("n_electrons", range(2, 9))
def test_cofactor_family_matches_direct_jk_determinants(n_electrons: int) -> None:
    family = JKCFSeedFamily(
        n_electrons=n_electrons,
        two_q=3 * (n_electrons - 1),
    )
    configs = _configs(n_electrons)
    tower = family.generate_multiplet()
    expected = np.column_stack(
        (
            family.ground_state().amplitude(configs),
            *(tower[m].amplitude(configs) for m in range(-2, 3)),
        )
    )

    actual = np.stack(
        [cofactor_seed_family_amplitudes(family, config) for config in configs]
    )

    np.testing.assert_allclose(
        actual,
        expected,
        rtol=1.0e-12,
        atol=1.0e-300,
    )


def test_cofactor_family_rejects_wrong_shape() -> None:
    family = JKCFSeedFamily(n_electrons=2, two_q=3)

    with pytest.raises(ValueError, match="shape"):
        cofactor_seed_family_amplitudes(
            family,
            np.ones((2, 3), dtype=np.complex128),
        )
