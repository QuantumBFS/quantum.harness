from __future__ import annotations

import numpy as np
import pytest

from scalable_v1.routes.cf_operator_nqs.coordinate_action import (
    evaluate_seed_and_actions,
)
from scalable_v1.routes.cf_operator_nqs.jax_action import (
    build_family_action_kernel,
)
from scalable_v1.routes.cf_operator_nqs.seeds import JKCFSeedFamily


def _configs(*, seed: int, batch: int, n_electrons: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    values = rng.normal(size=(batch, n_electrons, 2)) + 1j * rng.normal(
        size=(batch, n_electrons, 2)
    )
    return values / np.linalg.norm(values, axis=-1, keepdims=True)


@pytest.mark.parametrize("n_electrons", (2, 3))
def test_jax_family_action_matches_pairjet_reference(n_electrons: int) -> None:
    family = JKCFSeedFamily(
        n_electrons=n_electrons,
        two_q=3 * (n_electrons - 1),
    )
    configs = _configs(
        seed=1848 + n_electrons,
        batch=1,
        n_electrons=n_electrons,
    )
    kernel = build_family_action_kernel(
        family,
        platform="cpu",
        sector="family",
    )

    raw_seeds, raw_actions = kernel(configs)
    raw_seeds.block_until_ready()
    seeds = np.asarray(raw_seeds)
    actions = np.asarray(raw_actions)

    tower = family.generate_multiplet()
    states = (
        family.ground_state(),
        *(tower[m] for m in range(-2, 3)),
    )
    ells = tuple(ell for ell in (2, 3, 4) if ell <= family.two_q)
    expected = [
        evaluate_seed_and_actions(state, configs, ells=ells) for state in states
    ]
    for sector, (expected_seed, expected_action) in enumerate(expected):
        np.testing.assert_allclose(
            seeds[:, sector],
            expected_seed,
            rtol=1.0e-10,
            atol=1.0e-300,
        )
        np.testing.assert_allclose(
            actions[:, sector],
            expected_action,
            rtol=1.0e-10,
            atol=1.0e-11,
        )
    assert seeds.dtype == np.complex128
    assert actions.dtype == np.complex128


@pytest.mark.parametrize(
    ("sector", "seed_count"),
    (("l0", 1), ("l2", 5), ("family", 6)),
)
def test_jax_kernel_sector_shapes(sector: str, seed_count: int) -> None:
    family = JKCFSeedFamily(n_electrons=2, two_q=3)
    configs = _configs(seed=2848, batch=2, n_electrons=2)

    seeds, actions = build_family_action_kernel(
        family,
        platform="cpu",
        sector=sector,
    )(configs)

    assert seeds.shape == (2, seed_count)
    assert actions.shape == (2, seed_count, 2)


def test_jax_action_rejects_missing_platform() -> None:
    family = JKCFSeedFamily(n_electrons=2, two_q=3)

    with pytest.raises(RuntimeError, match="platform"):
        build_family_action_kernel(
            family,
            platform="not-a-platform",
            sector="family",
        )
