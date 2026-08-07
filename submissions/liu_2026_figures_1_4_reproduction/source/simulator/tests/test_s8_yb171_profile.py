"""S8 acceptance tests for generic Doppler and the Yb-171 data profile."""

from __future__ import annotations

import math

import pytest
import qutip as qt

from cs_tweezer_sim import (
    ConstantPulse,
    Delay,
    ExperimentProgram,
    OpticalWavevectorComponent,
    Play,
    StochasticScopeEngine,
    doppler_t2_us,
    effective_wavevector_magnitude_rad_per_m,
    liu_2026_yb171_doppler_model,
    liu_2026_yb171_four_level_profile,
    single_photon_effective_wavevector_rad_per_m,
    two_photon_effective_wavevector_rad_per_m,
)
from cs_tweezer_sim.qutip_multilevel_backend import QutipMultilevelBackend
from cs_tweezer_sim.stochastic import (
    ATOMIC_MASS_KG,
    thermal_velocity_sigma_m_per_s,
)
from cs_tweezer_sim.yb_profiles import (
    LIU_2026_RYDBERG_LIFETIME_US,
    LIU_2026_RYDBERG_RABI_RAD_PER_US,
    LIU_2026_RYDBERG_WAVELENGTH_NM,
    LIU_2026_TEMPERATURE_UK,
    YB171_ATOMIC_MASS_U,
    YB171_MASS_KG,
)


def _population(state: qt.Qobj, basis: qt.Qobj) -> float:
    density = qt.ket2dm(state) if state.isket else state
    return float(qt.expect(basis * basis.dag(), density).real)


def test_effective_wavevector_is_species_independent_and_legacy_compatible() -> None:
    wavelength_nm = LIU_2026_RYDBERG_WAVELENGTH_NM
    expected_single = 2.0 * math.pi / (wavelength_nm * 1e-9)
    assert single_photon_effective_wavevector_rad_per_m(
        wavelength_nm
    ) == pytest.approx(expected_single, rel=1e-15)

    wavelengths = (459.4459, 1040.03)
    generic = effective_wavevector_magnitude_rad_per_m(
        (
            OpticalWavevectorComponent(
                wavelengths[0], (0.0, 0.0, 2.0)
            ),
            OpticalWavevectorComponent(
                wavelengths[1], (0.0, 0.0, -3.0)
            ),
        )
    )
    assert two_photon_effective_wavevector_rad_per_m(
        wavelengths
    ) == pytest.approx(generic, rel=1e-15)


def test_yb171_single_photon_doppler_matches_analytic_coherence_time() -> None:
    wavevector = single_photon_effective_wavevector_rad_per_m(
        LIU_2026_RYDBERG_WAVELENGTH_NM
    )
    sigma_velocity = thermal_velocity_sigma_m_per_s(
        LIU_2026_TEMPERATURE_UK,
        mass_kg=YB171_MASS_KG,
    )
    expected_t2_us = math.sqrt(2.0) / (wavevector * sigma_velocity) * 1e6
    actual_t2_us = doppler_t2_us(
        LIU_2026_TEMPERATURE_UK,
        mass_kg=YB171_MASS_KG,
        effective_wavevector_rad_per_m=wavevector,
    )
    assert actual_t2_us == pytest.approx(expected_t2_us, rel=1e-15)
    assert YB171_MASS_KG == pytest.approx(
        YB171_ATOMIC_MASS_U * ATOMIC_MASS_KG,
        rel=1e-15,
    )

    model = liu_2026_yb171_doppler_model()
    engine = StochasticScopeEngine(model.blocks(1), seed=20260730)
    engine.begin_iteration()
    engine.begin_shot()
    context = model.context(engine, 1)
    assert context.level_energy_offsets_rad_per_us[
        (0, "r")
    ] == pytest.approx(
        context.level_energy_offsets_rad_per_us[(0, "r_prime")],
        abs=0.0,
    )


def test_liu_profile_is_data_only_and_has_complete_provenance() -> None:
    config = liu_2026_yb171_four_level_profile()
    assert config.profile_name == "liu-2026-yb171-four-level-effective"
    assert tuple(level.name for level in config.model.levels) == (
        "0",
        "1",
        "r",
        "r_prime",
        "erasure",
    )
    couplings = config.channels["rydberg_302"].transition_couplings
    assert tuple(item.transition for item in couplings) == (
        "1_r",
        "0_r_prime",
    )
    assert tuple(item.relative_rabi for item in couplings) == (
        1.0 + 0.0j,
        1.0 + 0.0j,
    )
    assert not config.model.pair_interactions

    evidence_kinds = {item.evidence_kind for item in config.provenance}
    assert {"reference", "reported", "assumption"} <= evidence_kinds
    parameters = {item.parameter for item in config.provenance}
    assert {
        "atomic_mass",
        "rydberg_wavelength",
        "rydberg_rabi",
        "rydberg_splitting",
        "rydberg_lifetime",
        "temperature",
        "shared_rydberg_relative_rabi",
        "effective_in_subspace_decay_partition",
        "profile_channel_command_limits",
    } <= parameters
    assert all(item.source and item.locator and item.unit for item in config.provenance)
    assert {
        "rf_max_rabi_rad_per_us",
        "rf_max_abs_detuning_rad_per_us",
        "rydberg_max_rabi_rad_per_us",
        "rydberg_max_abs_detuning_rad_per_us",
    } <= config.nominal_controls.keys()

    scanned = liu_2026_yb171_four_level_profile(
        rydberg_splitting_rad_per_us=0.5,
        include_effective_rydberg_decay=False,
        effective_out_of_computational_decay_fraction=0.8,
    )
    scanned_provenance = {
        item.parameter: item for item in scanned.provenance
    }
    assert scanned_provenance["rydberg_splitting"].evidence_kind == "configured"
    assert (
        scanned_provenance[
            "out_of_computational_lifetime_error_fraction"
        ].evidence_kind
        == "configured"
    )
    with pytest.raises(ValueError):
        liu_2026_yb171_four_level_profile(
            include_effective_rydberg_decay=False,
            effective_out_of_computational_decay_fraction=1.1,
        )


def test_shared_302nm_actuator_drives_both_transitions() -> None:
    config = liu_2026_yb171_four_level_profile(
        n_atoms=1,
        rydberg_splitting_rad_per_us=0.0,
        include_effective_rydberg_decay=False,
    )
    backend = QutipMultilevelBackend(config)
    pi_pulse = ExperimentProgram(
        (
            Play(
                "rydberg_302",
                (0,),
                ConstantPulse(
                    math.pi / LIU_2026_RYDBERG_RABI_RAD_PER_US,
                    LIU_2026_RYDBERG_RABI_RAD_PER_US,
                ),
            ),
        ),
        "yb171-shared-302nm-pi",
    )
    from_one = backend.simulate(
        pi_pulse,
        initial_state=backend.computational_basis_state("1"),
    ).state
    from_zero = backend.simulate(
        pi_pulse,
        initial_state=backend.computational_basis_state("0"),
    ).state
    assert backend.outcome_probabilities(from_one)["R"] > 1.0 - 1e-8
    assert backend.outcome_probabilities(from_zero)["R'"] > 1.0 - 1e-8


def test_effective_lifetime_has_correct_total_rate_and_survival() -> None:
    config = liu_2026_yb171_four_level_profile(n_atoms=1)
    for source in ("r", "r_prime"):
        total_rate = sum(
            decay.rate_per_us
            for decay in config.model.decays
            if decay.source_level == source
        )
        assert total_rate == pytest.approx(
            1.0 / LIU_2026_RYDBERG_LIFETIME_US,
            rel=1e-15,
        )

    backend = QutipMultilevelBackend(config)
    state = backend.simulate(
        ExperimentProgram(
            (Delay(LIU_2026_RYDBERG_LIFETIME_US),),
            "yb171-one-lifetime",
        ),
        initial_state=backend.local_level_product_state(("r",)),
    ).state
    rydberg = backend.local_level_product_state(("r",))
    assert _population(state, rydberg) == pytest.approx(
        math.exp(-1.0),
        abs=1e-7,
    )
