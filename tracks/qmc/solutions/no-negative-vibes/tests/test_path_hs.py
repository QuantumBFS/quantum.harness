from __future__ import annotations

from itertools import product
import math

import numpy as np

from oracle.path_hs import (
    configuration_weight,
    hirsch_parameters,
    spinless_configuration_weight,
)


def test_hirsch_rule_for_all_local_occupations() -> None:
    time_step = 0.2
    interaction = 3.0
    coupling, prefactor = hirsch_parameters(
        time_step=time_step,
        interaction=interaction,
    )

    for occupation_up, occupation_down in product((0, 1), repeat=2):
        exact = math.exp(
            -time_step
            * interaction
            * (occupation_up - 0.5)
            * (occupation_down - 0.5)
        )
        decoupled = prefactor * sum(
            math.exp(
                coupling
                * field
                * (occupation_up - occupation_down)
            )
            for field in (-1.0, 1.0)
        )
        assert math.isclose(exact, decoupled, rel_tol=1e-14, abs_tol=1e-14)


def test_all_small_open_chain_hs_configurations_are_positive() -> None:
    slices = 3
    sites = 3
    minimum_up = math.inf
    minimum_down = math.inf
    minimum_total = math.inf

    for flattened_fields in product((-1.0, 1.0), repeat=slices * sites):
        history = np.asarray(flattened_fields).reshape(slices, sites)
        weight = configuration_weight(
            history,
            time_step=0.25,
            hopping=1.0,
            interaction=4.0,
            chemical_potential=0.7,
        )
        minimum_up = min(minimum_up, weight.determinant_up)
        minimum_down = min(minimum_down, weight.determinant_down)
        minimum_total = min(minimum_total, weight.total)

    assert minimum_up >= 1.0 - 1e-12
    assert minimum_down >= 1.0 - 1e-12
    assert minimum_total > 0.0


def test_bond_hirsch_rule_for_repulsive_spinless_interaction() -> None:
    time_step = 0.2
    interaction = 3.0
    coupling, prefactor = hirsch_parameters(
        time_step=time_step,
        interaction=interaction,
    )

    for occupation_left, occupation_right in product((0, 1), repeat=2):
        exact = math.exp(
            -time_step
            * interaction
            * (occupation_left - 0.5)
            * (occupation_right - 0.5)
        )
        decoupled = prefactor * sum(
            math.exp(
                coupling
                * field
                * (occupation_left - occupation_right)
            )
            for field in (-1.0, 1.0)
        )
        assert math.isclose(exact, decoupled, rel_tol=1e-14, abs_tol=1e-14)


def test_all_small_spinless_t_v_configurations_are_positive() -> None:
    slices = 4
    bonds = 3
    minimum_determinant = math.inf
    minimum_total = math.inf

    for flattened_fields in product((-1.0, 1.0), repeat=slices * bonds):
        history = np.asarray(flattened_fields).reshape(slices, bonds)
        weight = spinless_configuration_weight(
            history,
            time_step=0.2,
            hopping=1.0,
            interaction=3.0,
            chemical_potential=0.7,
        )
        minimum_determinant = min(minimum_determinant, weight.determinant)
        minimum_total = min(minimum_total, weight.total)

    assert minimum_determinant >= 1.0 - 1e-12
    assert minimum_total > 0.0
