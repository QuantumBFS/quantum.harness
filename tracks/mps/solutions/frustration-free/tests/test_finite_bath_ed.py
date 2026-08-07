from __future__ import annotations

import copy
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import stat

import numpy as np
import pytest
from scipy.linalg import expm


SOLUTION_DIR = Path(__file__).parents[1]


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SOLUTION_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bath = _load_module("challenge_81_bath", "bath.py")
chain = _load_module("challenge_81_chain_mapping", "chain_mapping.py")
ed = _load_module("challenge_81_finite_bath_ed", "finite_bath_ed.py")

QN_TASK4_MAX_BATH = int(os.environ.get("QN_TASK4_MAX_BATH", "2"))
if QN_TASK4_MAX_BATH not in range(1, 7):
    raise ValueError("QN_TASK4_MAX_BATH must be between 1 and 6")


def _bath_artifact(*, n_bath=1, gamma=0.0, bandwidth=1.0):
    return bath.make_bath_artifact(
        gamma=gamma,
        bandwidth=bandwidth,
        n_bath=n_bath,
        frequency_grid=[-bandwidth, 0.0, bandwidth],
    )


def _spinless_sector_hamiltonian(one_particle, particle_count):
    n_orbitals = one_particle.shape[0]
    basis = [
        sum(1 << orbital for orbital in occupied)
        for occupied in itertools.combinations(range(n_orbitals), particle_count)
    ]
    positions = {state: index for index, state in enumerate(basis)}
    hamiltonian = np.zeros((len(basis), len(basis)))
    for source_index, source in enumerate(basis):
        for annihilate in range(n_orbitals):
            if not source & (1 << annihilate):
                continue
            after_annihilation = source ^ (1 << annihilate)
            annihilation_sign = (
                -1.0
                if (source & ((1 << annihilate) - 1)).bit_count() & 1
                else 1.0
            )
            for create in range(n_orbitals):
                if after_annihilation & (1 << create):
                    continue
                target = after_annihilation | (1 << create)
                creation_sign = (
                    -1.0
                    if (after_annihilation & ((1 << create) - 1)).bit_count() & 1
                    else 1.0
                )
                hamiltonian[positions[target], source_index] += (
                    one_particle[create, annihilate]
                    * annihilation_sign
                    * creation_sign
                )
    return hamiltonian, basis


def _fixed_sector_spectrum(one_particle, interaction, n_up, n_down):
    up_hamiltonian, up_basis = _spinless_sector_hamiltonian(
        one_particle, n_up
    )
    down_hamiltonian, down_basis = _spinless_sector_hamiltonian(
        one_particle, n_down
    )
    hamiltonian = np.kron(up_hamiltonian, np.eye(len(down_basis)))
    hamiltonian += np.kron(np.eye(len(up_basis)), down_hamiltonian)
    for up_index, up_state in enumerate(up_basis):
        if not up_state & 1:
            continue
        for down_index, down_state in enumerate(down_basis):
            if down_state & 1:
                index = up_index * len(down_basis) + down_index
                hamiltonian[index, index] += interaction
    return np.linalg.eigvalsh(hamiltonian)


def _full_fock_sector_spectrum(hamiltonian, n_bath, n_up, n_down):
    n_spatial = n_bath + 1
    states = [
        state
        for state in range(1 << (2 * n_spatial))
        if sum((state >> (2 * orbital)) & 1 for orbital in range(n_spatial))
        == n_up
        and sum(
            (state >> (2 * orbital + 1)) & 1
            for orbital in range(n_spatial)
        )
        == n_down
    ]
    return np.linalg.eigvalsh(hamiltonian[np.ix_(states, states)])


def _noninteracting_thermal_observables(one_particle, beta, tau):
    eigenvalues, eigenvectors = np.linalg.eigh(one_particle)
    occupations = 1.0 / (1.0 + np.exp(beta * eigenvalues))
    fermi = (eigenvectors * occupations) @ eigenvectors.T
    impurity_occupancy = float(fermi[0, 0])
    identity = np.eye(one_particle.shape[0])
    green = [
        -float((expm(-tau_value * one_particle) @ (identity - fermi))[0, 0])
        for tau_value in tau
    ]
    return {
        "logZ": 2.0
        * float(np.sum(np.logaddexp(0.0, -beta * eigenvalues))),
        "occupancy": {
            "up": impurity_occupancy,
            "down": impurity_occupancy,
            "total": 2.0 * impurity_occupancy,
        },
        "double_occupancy": impurity_occupancy**2,
        "green_function": {
            "up": green,
            "down": green,
            "average": green,
        },
    }


@pytest.mark.parametrize("n_bath", range(1, QN_TASK4_MAX_BATH + 1))
def test_one_particle_star_and_chain_are_unitarily_equivalent(n_bath):
    star = _bath_artifact(n_bath=n_bath, gamma=0.13, bandwidth=1.2)
    mapping = chain.derive_chain_mapping(star)
    epsilon_d, mu = -0.31, 0.07
    star_h = ed.build_one_particle_hamiltonian(
        bath_artifact=star, epsilon_d=epsilon_d, mu=mu
    )
    chain_h = ed.build_one_particle_hamiltonian(
        bath_artifact=star,
        chain_mapping_artifact=mapping,
        bath_representation="chain",
        epsilon_d=epsilon_d,
        mu=mu,
    )
    Q = np.asarray(mapping["payload"]["Q"])
    transform = np.zeros((n_bath + 1, n_bath + 1))
    transform[0, 0] = 1.0
    transform[1:, 1:] = Q

    assert chain_h == pytest.approx(transform.T @ star_h @ transform, abs=3e-12)
    assert np.linalg.eigvalsh(chain_h) == pytest.approx(
        np.linalg.eigvalsh(star_h), abs=3e-12
    )


@pytest.mark.parametrize("n_bath", range(1, QN_TASK4_MAX_BATH + 1))
@pytest.mark.parametrize("interaction", [0.0, 0.83])
def test_star_and_chain_one_up_one_down_sector_spectra_match(
    n_bath, interaction
):
    star = _bath_artifact(n_bath=n_bath, gamma=0.13, bandwidth=1.2)
    mapping = chain.derive_chain_mapping(star)
    common = {"bath_artifact": star, "epsilon_d": -0.31, "mu": 0.07}
    star_h = ed.build_one_particle_hamiltonian(**common)
    chain_h = ed.build_one_particle_hamiltonian(
        **common,
        bath_representation="chain",
        chain_mapping_artifact=mapping,
    )

    assert _fixed_sector_spectrum(
        chain_h, interaction, 1, 1
    ) == pytest.approx(
        _fixed_sector_spectrum(star_h, interaction, 1, 1), abs=5e-12
    )


@pytest.mark.parametrize(
    "n_bath", range(1, min(QN_TASK4_MAX_BATH, 3) + 1)
)
@pytest.mark.parametrize("interaction", [0.0, 0.83])
def test_star_and_chain_full_hamiltonians_match_in_every_sector(
    n_bath, interaction
):
    star = _bath_artifact(n_bath=n_bath, gamma=0.13, bandwidth=1.2)
    mapping = chain.derive_chain_mapping(star)
    common = {
        "bath_artifact": star,
        "U": interaction,
        "epsilon_d": -0.31,
        "mu": 0.07,
    }
    star_h = ed.build_hamiltonian(**common)
    chain_h = ed.build_hamiltonian(
        **common,
        bath_representation="chain",
        chain_mapping_artifact=mapping,
    )
    for n_up in range(n_bath + 2):
        for n_down in range(n_bath + 2):
            assert _full_fock_sector_spectrum(
                chain_h, n_bath, n_up, n_down
            ) == pytest.approx(
                _full_fock_sector_spectrum(
                    star_h, n_bath, n_up, n_down
                ),
                abs=5e-12,
            )


def test_geometry_selection_fails_closed():
    star = _bath_artifact(n_bath=2, gamma=0.13, bandwidth=1.2)
    mapping = chain.derive_chain_mapping(star)
    other_star = _bath_artifact(n_bath=3, gamma=0.13, bandwidth=1.2)
    wrong_mapping = chain.derive_chain_mapping(other_star)

    with pytest.raises(ValueError, match="requires.*mapping"):
        ed.build_one_particle_hamiltonian(
            bath_artifact=star, bath_representation="chain"
        )
    with pytest.raises(ValueError, match="cannot consume.*mapping"):
        ed.build_one_particle_hamiltonian(
            bath_artifact=star,
            bath_representation="direct_star",
            chain_mapping_artifact=mapping,
        )
    with pytest.raises(ValueError, match="source bath"):
        ed.build_one_particle_hamiltonian(
            bath_artifact=star,
            bath_representation="chain",
            chain_mapping_artifact=wrong_mapping,
        )
    with pytest.raises(ValueError, match="bath_representation"):
        ed.build_one_particle_hamiltonian(
            bath_artifact=star, bath_representation="tree"
        )


def test_solver_and_oracle_bind_explicit_chain_geometry(tmp_path):
    star = _bath_artifact(n_bath=2, gamma=0.13, bandwidth=1.2)
    mapping = chain.derive_chain_mapping(star)
    common = {
        "bath_artifact": star,
        "chain_mapping_artifact": mapping,
        "bath_representation": "chain",
        "U": 0.83,
        "epsilon_d": -0.31,
        "mu": 0.07,
        "beta": 1.3,
        "tau": [0.0, 1.3],
    }
    result = ed.solve_finite_bath(**common)
    artifact = ed.make_oracle_artifact(**common)
    written = ed.write_oracle_json(tmp_path / "chain-oracle.json", **common)

    assert result["bath_representation"] == "chain"
    assert result["chain_mapping_sha256"] == mapping["sha256"]
    assert artifact["payload"]["parameters"]["bath_representation"] == "chain"
    assert artifact["payload"]["mapping_input"] == mapping
    assert artifact["payload"]["mapping_input_sha256"] == mapping["sha256"]
    assert ed.verify_oracle_artifact(artifact) is None
    assert written == artifact


@pytest.mark.parametrize("n_bath", range(1, QN_TASK4_MAX_BATH + 1))
def test_star_and_chain_thermal_observables_and_green_match(n_bath):
    star = _bath_artifact(n_bath=n_bath, gamma=0.17, bandwidth=1.1)
    mapping = chain.derive_chain_mapping(star)
    beta = 2.3
    tau = [0.0, beta / 4.0, beta / 2.0, 3.0 * beta / 4.0, beta]
    common = {
        "bath_artifact": star,
        "epsilon_d": -0.29,
        "mu": 0.06,
    }
    direct = _noninteracting_thermal_observables(
        ed.build_one_particle_hamiltonian(**common), beta, tau
    )
    transformed = _noninteracting_thermal_observables(
        ed.build_one_particle_hamiltonian(
            **common,
            bath_representation="chain",
            chain_mapping_artifact=mapping,
        ),
        beta,
        tau,
    )

    assert transformed["logZ"] == pytest.approx(direct["logZ"], abs=5e-12)
    assert transformed["occupancy"] == pytest.approx(
        direct["occupancy"], abs=5e-12
    )
    assert transformed["double_occupancy"] == pytest.approx(
        direct["double_occupancy"], abs=5e-12
    )
    assert 0.0 < tau[1] < tau[2] < tau[3] < beta
    for result in (direct, transformed):
        for spin in ("up", "down"):
            occupation = result["occupancy"][spin]
            green = result["green_function"][spin]
            assert green[0] == pytest.approx(-(1.0 - occupation), abs=5e-12)
            assert green[-1] == pytest.approx(-occupation, abs=5e-12)
        for spin in ("up", "down", "average"):
            assert transformed["green_function"][spin] == pytest.approx(
                direct["green_function"][spin], abs=5e-12
            )


@pytest.mark.parametrize(
    "n_bath", range(1, min(QN_TASK4_MAX_BATH, 3) + 1)
)
def test_interacting_star_and_chain_thermal_observables_and_green_match(n_bath):
    star = _bath_artifact(n_bath=n_bath, gamma=0.17, bandwidth=1.1)
    mapping = chain.derive_chain_mapping(star)
    beta = 2.3
    tau = [0.0, beta / 4.0, beta / 2.0, 3.0 * beta / 4.0, beta]
    common = {
        "bath_artifact": star,
        "U": 0.8,
        "epsilon_d": -0.29,
        "mu": 0.06,
        "beta": beta,
        "tau": tau,
    }
    direct = ed.solve_finite_bath(**common)
    transformed = ed.solve_finite_bath(
        **common,
        bath_representation="chain",
        chain_mapping_artifact=mapping,
    )

    assert transformed["logZ"] == pytest.approx(direct["logZ"], abs=5e-12)
    assert transformed["occupancy"] == pytest.approx(
        direct["occupancy"], abs=5e-12
    )
    assert transformed["double_occupancy"] == pytest.approx(
        direct["double_occupancy"], abs=5e-12
    )
    assert direct["bath_representation"] == "direct_star"
    assert direct["chain_mapping_sha256"] is None
    assert transformed["bath_representation"] == "chain"
    assert transformed["chain_mapping_sha256"] == mapping["sha256"]
    assert 0.0 < tau[1] < tau[2] < tau[3] < beta
    for result in (direct, transformed):
        for spin in ("up", "down"):
            occupation = result["occupancy"][spin]
            green = result["green_function"][spin]
            assert green[0] == pytest.approx(-(1.0 - occupation), abs=5e-12)
            assert green[-1] == pytest.approx(-occupation, abs=5e-12)
        for spin in ("up", "down", "average"):
            assert transformed["green_function"][spin] == pytest.approx(
                direct["green_function"][spin], abs=5e-12
            )


def test_chain_oracle_verifier_replays_embedded_complete_mapping():
    star = _bath_artifact(n_bath=2, gamma=0.17, bandwidth=1.1)
    mapping = chain.derive_chain_mapping(star)
    artifact = ed.make_oracle_artifact(
        bath_artifact=star,
        chain_mapping_artifact=mapping,
        bath_representation="chain",
        U=0.8,
        epsilon_d=-0.29,
        mu=0.06,
        beta=2.3,
        tau=[0.0, 0.37, 1.41, 2.3],
    )

    assert artifact["payload"]["mapping_input"] == mapping
    assert artifact["payload"]["mapping_input"] is not mapping
    assert artifact["payload"]["mapping_input_sha256"] == mapping["sha256"]
    assert ed.verify_oracle_artifact(artifact) is None

    corrupted = copy.deepcopy(artifact)
    corrupted_mapping = corrupted["payload"]["mapping_input"]
    corrupted_mapping["payload"]["Q"][0][0] += 0.01
    _rehash(corrupted_mapping)
    corrupted["payload"]["mapping_input_sha256"] = corrupted_mapping["sha256"]
    _rehash(corrupted)
    with pytest.raises(ValueError, match="mapping"):
        ed.verify_oracle_artifact(corrupted)


def test_internal_consumed_bath_call_defaults_to_validated_direct_star_geometry():
    star = _bath_artifact(n_bath=2, gamma=0.13, bandwidth=1.2)
    consumed = {
        "epsilon": star["payload"]["epsilon"],
        "V": star["payload"]["V"],
        "n_bath": star["payload"]["parameters"]["n_bath"],
    }
    common = {
        "U": 0.83,
        "epsilon_d": -0.31,
        "mu": 0.07,
        "beta": 1.3,
        "tau": [0.0, 1.3],
        "max_dimension": ed.MAX_DENSE_DIMENSION,
        "max_dense_bytes": ed.MAX_DENSE_BYTES,
    }

    internal = ed._solve_consumed_bath(consumed_bath=consumed, **common)
    public = ed.solve_finite_bath(bath_artifact=star, **common)

    assert internal["bath_representation"] == "direct_star"
    assert internal["chain_mapping_sha256"] is None
    assert internal["logZ"] == pytest.approx(public["logZ"], abs=2e-13)
    assert internal["occupancy"] == pytest.approx(
        public["occupancy"], abs=2e-13
    )
    assert internal["green_function"] == pytest.approx(
        public["green_function"], abs=2e-13
    )


def test_dense_guard_runs_before_many_body_geometry_construction(monkeypatch):
    star = _bath_artifact(n_bath=6, gamma=0.13, bandwidth=1.2)

    def fail_if_geometry_is_constructed(*_args, **_kwargs):
        raise AssertionError("geometry constructed before dense guard")

    monkeypatch.setattr(
        ed, "_geometry_from_consumed", fail_if_geometry_is_constructed
    )
    with pytest.raises(ValueError, match="dimension"):
        ed.solve_finite_bath(
            bath_artifact=star,
            U=0.83,
            beta=1.0,
            tau=[0.0, 1.0],
        )


@pytest.mark.parametrize("location", ["payload", "parameters"])
def test_rehashed_unknown_geometry_schema_claim_is_rejected(location):
    artifact = ed.make_oracle_artifact(
        bath_artifact=_bath_artifact(n_bath=1, gamma=0.13),
        U=0.83,
        beta=1.0,
        tau=[0.0, 1.0],
    )
    target = (
        artifact["payload"]
        if location == "payload"
        else artifact["payload"]["parameters"]
    )
    target["unknown_geometry_claim"] = "unsupported"
    _rehash(artifact)

    with pytest.raises(ValueError, match="keys"):
        ed.verify_oracle_artifact(artifact)


def test_ed_independently_validates_authoritative_model_conventions():
    assert ed.MODEL_DEFINITION["parameters"]["U"] == 0.8
    assert ed.MODEL_DEFINITION["conventions"]["hamiltonian"] == (
        ed.HAMILTONIAN_CONVENTION
    )
    assert ed.MODEL_DEFINITION["conventions"]["green_function"] == (
        ed.GREEN_FUNCTION_CONVENTION
    )


def _canonical_json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _rehash(artifact):
    artifact["sha256"] = hashlib.sha256(
        _canonical_json(artifact["payload"])
    ).hexdigest()
    return artifact


def test_jordan_wigner_operators_obey_canonical_anticommutation():
    n_modes = 4
    identity = np.eye(1 << n_modes)
    zero = np.zeros_like(identity)
    annihilators = [
        ed.fermion_annihilation(n_modes=n_modes, mode=mode)
        for mode in range(n_modes)
    ]

    for left in range(n_modes):
        for right in range(n_modes):
            anti_aa = (
                annihilators[left] @ annihilators[right]
                + annihilators[right] @ annihilators[left]
            )
            anti_adag = (
                annihilators[left] @ annihilators[right].T
                + annihilators[right].T @ annihilators[left]
            )
            assert anti_aa == pytest.approx(zero, abs=0.0)
            assert anti_adag == pytest.approx(
                identity if left == right else zero, abs=0.0
            )


def test_hamiltonian_is_hermitian_and_has_exact_hybridization_signs():
    coupling = 0.37
    hamiltonian = ed.build_hamiltonian(
        epsilon=[0.2],
        V=[coupling],
        U=0.0,
        epsilon_d=0.0,
        mu=0.0,
    )

    assert hamiltonian == pytest.approx(hamiltonian.T, abs=0.0)
    # d_up^dagger c_up has a positive sign without lower occupied spectators.
    assert hamiltonian[0b0001, 0b0100] == pytest.approx(coupling)
    # Occupied d_down lies between d_up and c_up in canonical mode order.
    assert hamiltonian[0b0011, 0b0110] == pytest.approx(-coupling)
    assert hamiltonian[0b0110, 0b0011] == pytest.approx(-coupling)
    # The corresponding spin-down hop has no intervening occupied mode here.
    assert hamiltonian[0b0010, 0b1000] == pytest.approx(coupling)


def test_interacting_hybridized_hamiltonian_matches_independent_basis_construction():
    epsilon_d = -0.31
    epsilon_bath = 0.27
    coupling = 0.19
    interaction = 0.83
    chemical_potential = -0.07
    expected = np.zeros((16, 16))

    def apply_annihilation(state, mode):
        if not state & (1 << mode):
            return None
        parity = sum((state >> lower) & 1 for lower in range(mode))
        return state ^ (1 << mode), (-1.0) ** parity

    def apply_creation(state, mode):
        if state & (1 << mode):
            return None
        parity = sum((state >> lower) & 1 for lower in range(mode))
        return state | (1 << mode), (-1.0) ** parity

    for source in range(16):
        occupations = [(source >> mode) & 1 for mode in range(4)]
        expected[source, source] = (
            (epsilon_d - chemical_potential)
            * (occupations[0] + occupations[1])
            + interaction * occupations[0] * occupations[1]
            + (epsilon_bath - chemical_potential)
            * (occupations[2] + occupations[3])
        )
        for impurity_mode, bath_mode in ((0, 2), (1, 3)):
            for annihilate_mode, create_mode in (
                (bath_mode, impurity_mode),
                (impurity_mode, bath_mode),
            ):
                first = apply_annihilation(source, annihilate_mode)
                if first is None:
                    continue
                intermediate, first_sign = first
                second = apply_creation(intermediate, create_mode)
                if second is None:
                    continue
                target, second_sign = second
                expected[target, source] += (
                    coupling * first_sign * second_sign
                )

    actual = ed.build_hamiltonian(
        epsilon=[epsilon_bath],
        V=[coupling],
        U=interaction,
        epsilon_d=epsilon_d,
        mu=chemical_potential,
    )
    assert actual == pytest.approx(expected, abs=0.0)


def test_atomic_limit_matches_analytic_thermal_trace_and_green_function():
    U = 0.8
    epsilon_d = -0.23
    beta = 3.1
    tau = [0.0, 0.4, 1.7, beta]
    result = ed.solve_finite_bath(
        bath_artifact=_bath_artifact(),
        U=U,
        epsilon_d=epsilon_d,
        beta=beta,
        tau=tau,
    )

    impurity_energies = np.array(
        [0.0, epsilon_d, epsilon_d, 2.0 * epsilon_d + U]
    )
    impurity_weights = np.exp(-beta * impurity_energies)
    z_impurity = float(np.sum(impurity_weights))
    # The n_bath=1 bath has epsilon=0 and two free spin modes.
    expected_z = 4.0 * z_impurity
    expected_n_spin = float(
        (impurity_weights[1] + impurity_weights[3]) / z_impurity
    )
    expected_double = float(impurity_weights[3] / z_impurity)
    expected_green = [
        -(
            math.exp(-value * epsilon_d)
            + math.exp(
                -(beta - value) * epsilon_d
                - value * (2.0 * epsilon_d + U)
            )
        )
        / z_impurity
        for value in tau
    ]

    assert result["Z"] == pytest.approx(expected_z, rel=2e-14)
    assert result["logZ"] == pytest.approx(math.log(expected_z), abs=2e-14)
    assert result["occupancy"] == pytest.approx(
        {
            "up": expected_n_spin,
            "down": expected_n_spin,
            "total": 2.0 * expected_n_spin,
        },
        abs=2e-14,
    )
    assert result["double_occupancy"] == pytest.approx(expected_double, abs=2e-14)
    assert result["green_function"]["up"] == pytest.approx(
        expected_green, abs=2e-14
    )
    assert result["green_function"]["down"] == pytest.approx(
        expected_green, abs=2e-14
    )
    assert result["green_function"]["average"] == pytest.approx(
        expected_green, abs=2e-14
    )


def test_infinite_temperature_limit_uses_full_fock_space():
    result = ed.solve_finite_bath(
        bath_artifact=_bath_artifact(n_bath=2, gamma=0.2),
        U=0.8,
        beta=0.0,
        tau=[0.0],
    )

    assert result["Z"] == 64.0
    assert result["logZ"] == pytest.approx(math.log(64.0))
    assert result["occupancy"] == pytest.approx(
        {"up": 0.5, "down": 0.5, "total": 1.0}
    )
    assert result["double_occupancy"] == pytest.approx(0.25)
    assert result["green_function"]["average"] == pytest.approx([-0.5])


def test_noninteracting_result_matches_independent_one_particle_fermi_matrix():
    beta = 2.4
    epsilon_d = -0.17
    tau = np.array([0.0, 0.2, 1.1, beta])
    artifact = _bath_artifact(n_bath=2, gamma=0.13, bandwidth=1.2)
    epsilon = np.asarray(artifact["payload"]["epsilon"])
    coupling = np.asarray(artifact["payload"]["V"])
    one_particle = np.diag(np.concatenate(([epsilon_d], epsilon)))
    one_particle[0, 1:] = coupling
    one_particle[1:, 0] = coupling
    eigenvalues, eigenvectors = np.linalg.eigh(one_particle)
    fermi = eigenvectors @ np.diag(
        1.0 / (1.0 + np.exp(beta * eigenvalues))
    ) @ eigenvectors.T
    n_spin = float(fermi[0, 0])
    expected_green = [
        -float((expm(-value * one_particle) @ (np.eye(3) - fermi))[0, 0])
        for value in tau
    ]
    expected_logz = 2.0 * float(
        np.sum(np.logaddexp(0.0, -beta * eigenvalues))
    )

    result = ed.solve_finite_bath(
        bath_artifact=artifact,
        U=0.0,
        epsilon_d=epsilon_d,
        beta=beta,
        tau=tau.tolist(),
    )

    assert result["logZ"] == pytest.approx(expected_logz, abs=3e-13)
    assert result["Z"] == pytest.approx(math.exp(expected_logz), rel=3e-13)
    assert result["occupancy"]["up"] == pytest.approx(n_spin, abs=3e-13)
    assert result["occupancy"]["down"] == pytest.approx(n_spin, abs=3e-13)
    assert result["double_occupancy"] == pytest.approx(n_spin**2, abs=3e-13)
    assert result["green_function"]["up"] == pytest.approx(
        expected_green, abs=3e-13
    )
    assert result["green_function"]["down"] == pytest.approx(
        expected_green, abs=3e-13
    )


def test_particle_hole_symmetric_bath_has_unit_impurity_occupancy():
    result = ed.solve_finite_bath(
        bath_artifact=_bath_artifact(n_bath=2, gamma=0.2),
        U=0.8,
        beta=7.0,
        tau=[0.0, 3.5, 7.0],
    )

    assert result["occupancy"]["total"] == pytest.approx(1.0, abs=2e-13)


def test_particle_hole_symmetric_bath_green_function_is_tau_reflection_symmetric():
    beta = 6.0
    tau = [0.0, 0.7, 2.1, 3.0, 3.9, 5.3, beta]
    result = ed.solve_finite_bath(
        bath_artifact=_bath_artifact(n_bath=2, gamma=0.2),
        U=0.8,
        beta=beta,
        tau=tau,
    )

    for spin in ("up", "down", "average"):
        assert result["green_function"][spin] == pytest.approx(
            list(reversed(result["green_function"][spin])), abs=3e-13
        )


def test_green_function_endpoints_and_spin_symmetry():
    beta = 4.3
    result = ed.solve_finite_bath(
        bath_artifact=_bath_artifact(n_bath=2, gamma=0.17),
        U=0.8,
        beta=beta,
        tau=[0.0, beta / 2.0, beta],
    )

    for spin in ("up", "down"):
        occupancy = result["occupancy"][spin]
        green = result["green_function"][spin]
        assert green[0] == pytest.approx(-(1.0 - occupancy), abs=2e-13)
        assert green[-1] == pytest.approx(-occupancy, abs=2e-13)
    assert result["occupancy"]["up"] == pytest.approx(
        result["occupancy"]["down"], abs=2e-13
    )
    assert result["green_function"]["up"] == pytest.approx(
        result["green_function"]["down"], abs=2e-13
    )
    assert result["green_function"]["average"] == pytest.approx(
        result["green_function"]["up"], abs=2e-13
    )


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"U": True}, "U"),
        ({"U": math.nan}, "U"),
        ({"epsilon_d": math.inf}, "epsilon_d"),
        ({"mu": True}, "mu"),
        ({"beta": True}, "beta"),
        ({"beta": -0.1}, "beta"),
        ({"tau": [0.0, math.nan]}, "tau"),
        ({"tau": [0.0, True]}, "tau"),
        ({"tau": [0.4, 0.3]}, "nondecreasing"),
        ({"tau": [-0.1, 0.2]}, r"\[0, beta\]"),
        ({"tau": [0.0, 2.1]}, r"\[0, beta\]"),
        ({"max_dimension": True}, "max_dimension"),
        ({"max_dimension": 3.5}, "max_dimension"),
    ],
)
def test_solver_rejects_invalid_scalar_and_tau_inputs(kwargs, match):
    arguments = {
        "bath_artifact": _bath_artifact(),
        "U": 0.8,
        "beta": 2.0,
        "tau": [0.0, 2.0],
    }
    arguments.update(kwargs)
    with pytest.raises((TypeError, ValueError), match=match):
        ed.solve_finite_bath(**arguments)


def test_hamiltonian_rejects_malformed_arrays_and_unsafe_dimension():
    invalid = [
        {"epsilon": [0.0, math.nan], "V": [0.1, 0.2]},
        {"epsilon": [0.0, True], "V": [0.1, 0.2]},
        {"epsilon": [0.0], "V": [0.1, 0.2]},
        {"epsilon": [0.0], "V": [-0.1]},
        {"epsilon": [0.0], "V": [0.1 + 0.2j]},
    ]
    for kwargs in invalid:
        with pytest.raises((TypeError, ValueError)):
            ed.build_hamiltonian(
                **kwargs, U=0.8, epsilon_d=-0.4, mu=0.0
            )

    with pytest.raises(ValueError, match="dimension"):
        ed.solve_finite_bath(
            bath_artifact=_bath_artifact(n_bath=6, gamma=0.1),
            U=0.8,
            beta=1.0,
            tau=[0.0, 1.0],
        )


def test_dense_memory_guard_is_conservative_and_enforced_at_boundary():
    dimension = 16
    estimate = ed.estimate_dense_peak_memory_bytes(dimension)

    assert estimate >= 12 * 8 * dimension**2
    assert ed.build_hamiltonian(
        epsilon=[0.0],
        V=[0.0],
        U=0.8,
        max_dense_bytes=estimate,
    ).shape == (dimension, dimension)
    with pytest.raises(ValueError, match="memory"):
        ed.build_hamiltonian(
            epsilon=[0.0],
            V=[0.0],
            U=0.8,
            max_dense_bytes=estimate - 1,
        )
    with pytest.raises((TypeError, ValueError), match="max_dense_bytes"):
        ed.build_hamiltonian(
            epsilon=[0.0],
            V=[0.0],
            U=0.8,
            max_dense_bytes=True,
        )


def test_solver_rejects_tampered_or_wrong_convention_bath_artifact():
    tampered = _bath_artifact()
    tampered["payload"]["epsilon"][0] = 9.0
    with pytest.raises(ValueError, match="bath.*SHA256"):
        ed.solve_finite_bath(
            bath_artifact=tampered, U=0.8, beta=1.0, tau=[0.0, 1.0]
        )

    wrong_convention = _bath_artifact()
    wrong_convention["payload"]["conventions"]["hybridization"] = "different"
    wrong_convention["sha256"] = hashlib.sha256(
        _canonical_json(wrong_convention["payload"])
    ).hexdigest()
    with pytest.raises(ValueError, match="conventions.*unsupported"):
        ed.solve_finite_bath(
            bath_artifact=wrong_convention,
            U=0.8,
            beta=1.0,
            tau=[0.0, 1.0],
        )


def test_bath_schema_and_semantic_provenance_are_strictly_validated():
    unsupported = _bath_artifact()
    unsupported["payload"]["schema_version"] = 999
    unsupported["payload"]["provenance"]["schema_version"] = 999
    _rehash(unsupported)
    with pytest.raises(ValueError, match="schema"):
        ed.solve_finite_bath(
            bath_artifact=unsupported, U=0.8, beta=1.0, tau=[0.0, 1.0]
        )

    wrong_schema_type = _bath_artifact()
    wrong_schema_type["payload"]["schema_version"] = 2.0
    wrong_schema_type["payload"]["provenance"]["schema_version"] = 2.0
    _rehash(wrong_schema_type)
    with pytest.raises((TypeError, ValueError), match="schema"):
        ed.solve_finite_bath(
            bath_artifact=wrong_schema_type,
            U=0.8,
            beta=1.0,
            tau=[0.0, 1.0],
        )

    malformed = _bath_artifact()
    malformed["payload"]["provenance"]["module"] = "not-bath"
    _rehash(malformed)
    with pytest.raises(ValueError, match="provenance"):
        ed.solve_finite_bath(
            bath_artifact=malformed, U=0.8, beta=1.0, tau=[0.0, 1.0]
        )

    missing = _bath_artifact()
    del missing["payload"]["provenance"]["numpy_version"]
    _rehash(missing)
    with pytest.raises(ValueError, match="provenance"):
        ed.solve_finite_bath(
            bath_artifact=missing, U=0.8, beta=1.0, tau=[0.0, 1.0]
        )


def test_stored_bath_arrays_are_consumed_without_refitting(monkeypatch):
    artifact = _bath_artifact(n_bath=2, gamma=0.13, bandwidth=1.2)
    stored_epsilon = artifact["payload"]["epsilon"]
    stored_coupling = artifact["payload"]["V"]
    beta = 2.2
    epsilon_d = 0.14

    def fail_if_refitted(*_args, **_kwargs):
        raise AssertionError("oracle consumption must not refit the bath")

    monkeypatch.setattr(
        ed._BATH_MODULE,
        "discretize_semicircular_bath",
        fail_if_refitted,
    )
    monkeypatch.setattr(
        ed._BATH_MODULE,
        "make_bath_artifact",
        fail_if_refitted,
    )

    one_particle = np.diag([epsilon_d, *stored_epsilon])
    one_particle[0, 1:] = stored_coupling
    one_particle[1:, 0] = stored_coupling
    eigenvalues, eigenvectors = np.linalg.eigh(one_particle)
    fermi = eigenvectors @ np.diag(
        1.0 / (1.0 + np.exp(beta * eigenvalues))
    ) @ eigenvectors.T

    result = ed.solve_finite_bath(
        bath_artifact=artifact,
        U=0.0,
        epsilon_d=epsilon_d,
        beta=beta,
        tau=[0.0, beta],
    )
    oracle = ed.make_oracle_artifact(
        bath_artifact=artifact,
        U=0.0,
        epsilon_d=epsilon_d,
        beta=beta,
        tau=[0.0, beta],
    )

    assert result["occupancy"]["up"] == pytest.approx(fermi[0, 0], abs=3e-13)
    assert oracle["payload"]["bath"]["epsilon"] == stored_epsilon
    assert oracle["payload"]["bath"]["V"] == stored_coupling


def test_oracle_artifact_is_deterministic_complete_and_integrity_checked():
    bath_input = _bath_artifact(n_bath=2, gamma=0.1)
    arguments = {
        "bath_artifact": bath_input,
        "U": 0.8,
        "beta": 3.0,
        "tau": [0.0, 1.5, 3.0],
    }
    first = ed.make_oracle_artifact(**arguments)
    second = ed.make_oracle_artifact(**arguments)

    assert first == second
    assert first["sha256"] == hashlib.sha256(
        _canonical_json(first["payload"])
    ).hexdigest()
    payload = first["payload"]
    assert payload["schema_version"] == ed.SCHEMA_VERSION
    assert payload["parameters"]["epsilon_d"] == pytest.approx(-0.4)
    assert payload["parameters"]["mu"] == 0.0
    assert payload["parameters"]["grand_canonical"] is True
    assert payload["parameters"]["bath_representation"] == "direct_star"
    assert payload["bath_input_sha256"] == bath_input["sha256"]
    assert payload["bath_input"] == bath_input
    assert payload["mapping_input"] is None
    assert payload["mapping_input_sha256"] is None
    assert payload["mode_order"] == [
        "d_up",
        "d_down",
        "c1_up",
        "c1_down",
        "c2_up",
        "c2_down",
    ]
    assert payload["tau"] == arguments["tau"]
    assert payload["observables"]["occupancy"]["total"] == pytest.approx(1.0)
    assert payload["provenance"]["module"] == "finite_bath_ed"
    assert payload["resources"]["hilbert_dimension"] == 64
    assert payload["resources"]["dense_peak_memory_estimate_bytes"] == (
        ed.estimate_dense_peak_memory_bytes(64)
    )
    assert "O(D^3)" in payload["resources"]["diagonalization_cost"]
    assert "fixed locked runtime" in payload["conventions"][
        "deterministic_serialization"
    ]
    assert payload["conventions"]["coupling_gauge"] == (
        "V_k is real and nonnegative: V_k = sqrt(weight_k / pi)"
    )
    assert ed.verify_oracle_artifact(first) is None

    first["payload"]["observables"]["occupancy"]["up"] = 123.0
    with pytest.raises(ValueError, match="SHA256"):
        ed.verify_oracle_artifact(first)


def test_low_temperature_overflow_uses_nullable_partition_status_and_valid_json(
    tmp_path,
):
    destination = tmp_path / "low-temperature-oracle.json"
    artifact = ed.write_oracle_json(
        destination,
        bath_artifact=_bath_artifact(),
        U=0.0,
        epsilon_d=-100.0,
        beta=10.0,
        tau=[0.0, 5.0, 10.0],
    )
    observables = artifact["payload"]["observables"]

    assert observables["logZ"] > math.log(np.finfo(np.float64).max)
    assert math.isfinite(observables["logZ"])
    assert observables["Z"] is None
    assert observables["Z_status"] == "overflow"
    assert json.loads(_canonical_json(artifact)) == artifact
    assert json.loads(destination.read_text(encoding="utf-8")) == artifact
    assert ed.verify_oracle_artifact(artifact) is None


def test_rehashed_semantic_oracle_corruption_is_rejected():
    base = ed.make_oracle_artifact(
        bath_artifact=_bath_artifact(n_bath=2, gamma=0.1),
        U=0.8,
        beta=3.0,
        tau=[0.0, 1.5, 3.0],
    )
    corruptions = []

    wrong_order = copy.deepcopy(base)
    wrong_order["payload"]["mode_order"][0:2] = ["d_down", "d_up"]
    corruptions.append(wrong_order)

    wrong_schema_type = copy.deepcopy(base)
    wrong_schema_type["payload"]["schema_version"] = float(ed.SCHEMA_VERSION)
    corruptions.append(wrong_schema_type)

    wrong_dimension = copy.deepcopy(base)
    wrong_dimension["payload"]["resources"]["hilbert_dimension"] = 32
    corruptions.append(wrong_dimension)

    wrong_endpoint = copy.deepcopy(base)
    wrong_endpoint["payload"]["observables"]["green_function"]["up"][0] = 0.0
    corruptions.append(wrong_endpoint)

    wrong_partition_status = copy.deepcopy(base)
    wrong_partition_status["payload"]["observables"]["Z"] = None
    corruptions.append(wrong_partition_status)

    broken_bath_link = copy.deepcopy(base)
    broken_bath_link["payload"]["bath_input"]["payload"]["epsilon"][0] = 99.0
    corruptions.append(broken_bath_link)

    nonnumeric_observable = copy.deepcopy(base)
    nonnumeric_observable["payload"]["observables"]["occupancy"]["up"] = "0.5"
    corruptions.append(nonnumeric_observable)

    for corrupted in corruptions:
        _rehash(corrupted)
        with pytest.raises((TypeError, ValueError)):
            ed.verify_oracle_artifact(corrupted)


@pytest.mark.parametrize(
    "claim",
    [
        "hamiltonian",
        "hybridization",
        "coupling_gauge",
        "fermion_mapping",
        "thermal_space",
        "green_function",
        "boltzmann_stabilization",
        "partition_overflow",
        "deterministic_serialization",
    ],
)
def test_rehashed_corruption_of_each_serialized_convention_is_rejected(claim):
    artifact = ed.make_oracle_artifact(
        bath_artifact=_bath_artifact(),
        U=0.8,
        beta=2.0,
        tau=[0.0, 1.0, 2.0],
    )
    artifact["payload"]["conventions"][claim] += " corrupted"
    _rehash(artifact)

    with pytest.raises(ValueError, match="convention"):
        ed.verify_oracle_artifact(artifact)


@pytest.mark.parametrize(
    ("claim", "corrupt"),
    [
        ("n_modes", lambda value: value + 2),
        ("hilbert_dimension", lambda value: value // 2),
        ("dense_peak_memory_estimate_bytes", lambda value: value + 1),
        ("dense_peak_memory_model", lambda value: value + " corrupted"),
        ("storage_cost", lambda value: value + " corrupted"),
        ("diagonalization_cost", lambda value: value + " corrupted"),
        ("enforced_max_dimension", lambda value: value // 2),
        ("enforced_max_dense_bytes", lambda value: value // 2),
    ],
)
def test_rehashed_corruption_of_each_serialized_resource_is_rejected(
    claim, corrupt
):
    artifact = ed.make_oracle_artifact(
        bath_artifact=_bath_artifact(),
        U=0.8,
        beta=2.0,
        tau=[0.0, 1.0, 2.0],
    )
    resources = artifact["payload"]["resources"]
    resources[claim] = corrupt(resources[claim])
    _rehash(artifact)

    with pytest.raises(ValueError, match="resource"):
        ed.verify_oracle_artifact(artifact)


def test_rehashed_unknown_resource_claim_is_rejected():
    artifact = ed.make_oracle_artifact(
        bath_artifact=_bath_artifact(),
        U=0.8,
        beta=2.0,
        tau=[0.0, 1.0, 2.0],
    )
    artifact["payload"]["resources"]["unvalidated_claim"] = "O(1)"
    _rehash(artifact)

    with pytest.raises(ValueError, match="resource"):
        ed.verify_oracle_artifact(artifact)


def test_rehashed_impossible_double_occupancy_lower_bound_is_rejected():
    artifact = ed.make_oracle_artifact(
        bath_artifact=_bath_artifact(),
        U=0.8,
        beta=2.0,
        tau=[0.0, 1.0, 2.0],
    )
    observables = artifact["payload"]["observables"]
    observables["occupancy"] = {"up": 0.8, "down": 0.8, "total": 1.6}
    observables["double_occupancy"] = 0.5
    observables["green_function"]["up"][0] = -0.2
    observables["green_function"]["down"][0] = -0.2
    observables["green_function"]["average"][0] = -0.2
    observables["green_function"]["up"][-1] = -0.8
    observables["green_function"]["down"][-1] = -0.8
    observables["green_function"]["average"][-1] = -0.8
    _rehash(artifact)

    with pytest.raises(ValueError, match="double occupancy"):
        ed.verify_oracle_artifact(artifact)


def test_rehashed_fabricated_interior_green_function_fails_scientific_verification():
    artifact = ed.make_oracle_artifact(
        bath_artifact=_bath_artifact(n_bath=2, gamma=0.1),
        U=0.8,
        beta=3.0,
        tau=[0.0, 1.0, 2.0, 3.0],
    )
    green = artifact["payload"]["observables"]["green_function"]
    for spin in ("up", "down", "average"):
        green[spin][1] += 0.01
        green[spin][2] += 0.01
    _rehash(artifact)

    with pytest.raises(ValueError, match="scientific"):
        ed.verify_oracle_artifact(artifact)


def test_writer_uses_public_scientific_verification_before_publication(
    tmp_path, monkeypatch
):
    destination = tmp_path / "oracle.json"
    fabricated = ed.make_oracle_artifact(
        bath_artifact=_bath_artifact(),
        U=0.8,
        beta=2.0,
        tau=[0.0, 1.0, 2.0],
    )
    green = fabricated["payload"]["observables"]["green_function"]
    for spin in ("up", "down", "average"):
        green[spin][1] += 0.01
    _rehash(fabricated)
    monkeypatch.setattr(
        ed, "make_oracle_artifact", lambda **_kwargs: fabricated
    )

    with pytest.raises(ValueError, match="scientific"):
        ed.write_oracle_json(
            destination,
            bath_artifact=_bath_artifact(),
            U=0.8,
            beta=2.0,
            tau=[0.0, 1.0, 2.0],
        )
    assert not destination.exists()


def test_artifact_construction_validates_bath_once_and_copies_caller_inputs(
    monkeypatch,
):
    bath_input = _bath_artifact(n_bath=2, gamma=0.1)
    tau = [0.0, 1.0, 2.0]
    calls = 0
    real_verify = ed._BATH_MODULE.verify_bath_artifact

    def recording_verify(value):
        nonlocal calls
        calls += 1
        return real_verify(value)

    monkeypatch.setattr(ed._BATH_MODULE, "verify_bath_artifact", recording_verify)
    artifact = ed.make_oracle_artifact(
        bath_artifact=bath_input, U=0.8, beta=2.0, tau=tau
    )
    snapshot = copy.deepcopy(artifact)

    bath_input["payload"]["epsilon"][0] = 123.0
    tau[1] = 0.25
    assert calls == 1
    assert artifact == snapshot
    assert ed.verify_oracle_artifact(artifact) is None


class _FailingWriteFile:
    def __init__(self, wrapped):
        self._wrapped = wrapped

    def __enter__(self):
        self._wrapped.__enter__()
        return self

    def __exit__(self, *args):
        return self._wrapped.__exit__(*args)

    @property
    def name(self):
        return self._wrapped.name

    def write(self, _payload):
        raise OSError("injected oracle write failure")

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


def test_oracle_publication_failure_preserves_destination_and_cleans_temporary(
    tmp_path, monkeypatch
):
    destination = tmp_path / "oracle.json"
    destination.write_bytes(b"existing oracle")
    real_named_temporary_file = ed.tempfile.NamedTemporaryFile

    def failing_named_temporary_file(*args, **kwargs):
        return _FailingWriteFile(real_named_temporary_file(*args, **kwargs))

    monkeypatch.setattr(
        ed.tempfile, "NamedTemporaryFile", failing_named_temporary_file
    )
    with pytest.raises(OSError, match="injected oracle write failure"):
        ed.write_oracle_json(
            destination,
            bath_artifact=_bath_artifact(),
            U=0.8,
            beta=2.0,
            tau=[0.0, 2.0],
        )

    assert destination.read_bytes() == b"existing oracle"
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize("existing", [False, True])
def test_pre_replace_failure_is_transactional_for_new_and_existing_destination(
    tmp_path, monkeypatch, existing
):
    destination = tmp_path / "oracle.json"
    if existing:
        destination.write_bytes(b"existing oracle")

    def failing_replace(_source, _target):
        raise OSError("injected pre-replace failure")

    monkeypatch.setattr(ed.os, "replace", failing_replace)
    with pytest.raises(OSError, match="injected pre-replace failure"):
        ed.write_oracle_json(
            destination,
            bath_artifact=_bath_artifact(),
            U=0.8,
            beta=2.0,
            tau=[0.0, 2.0],
        )

    if existing:
        assert destination.read_bytes() == b"existing oracle"
        assert list(tmp_path.iterdir()) == [destination]
    else:
        assert not destination.exists()
        assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("existing", [False, True])
def test_post_replace_directory_fsync_failure_rolls_back_transaction(
    tmp_path, monkeypatch, existing
):
    destination = tmp_path / "oracle.json"
    if existing:
        destination.write_bytes(b"existing oracle")

    calls = 0

    def failing_directory_fsync(_directory):
        nonlocal calls
        calls += 1
        target_call = 2 if existing else 1
        if calls == target_call:
            raise OSError("injected post-replace fsync failure")

    monkeypatch.setattr(ed, "_fsync_directory", failing_directory_fsync)
    with pytest.raises(OSError, match="injected post-replace fsync failure"):
        ed.write_oracle_json(
            destination,
            bath_artifact=_bath_artifact(),
            U=0.8,
            beta=2.0,
            tau=[0.0, 2.0],
        )

    if existing:
        assert destination.read_bytes() == b"existing oracle"
        assert list(tmp_path.iterdir()) == [destination]
    else:
        assert not destination.exists()
        assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("kind", ["directory", "symlink"])
def test_writer_rejects_unsupported_existing_destination_types(
    tmp_path, kind
):
    destination = tmp_path / "oracle.json"
    if kind == "directory":
        destination.mkdir()
    else:
        target = tmp_path / "target.json"
        target.write_bytes(b"target")
        destination.symlink_to(target)

    with pytest.raises(ValueError, match="regular file"):
        ed.write_oracle_json(
            destination,
            bath_artifact=_bath_artifact(),
            U=0.8,
            beta=2.0,
            tau=[0.0, 2.0],
        )


def test_existing_destination_rollback_restores_inode_metadata_and_hardlinks(
    tmp_path, monkeypatch
):
    destination = tmp_path / "oracle.json"
    external_link = tmp_path / "external.json"
    destination.write_bytes(b"existing oracle")
    os.chmod(destination, 0o640)
    timestamp_ns = 1_700_000_000_123_456_789
    os.utime(destination, ns=(timestamp_ns, timestamp_ns))
    os.link(destination, external_link)
    before = destination.stat()
    real_directory_fsync = ed._fsync_directory
    calls = 0

    def fail_publication_fsync(directory):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected publication directory fsync failure")
        return real_directory_fsync(directory)

    monkeypatch.setattr(ed, "_fsync_directory", fail_publication_fsync)
    with pytest.raises(
        OSError, match="injected publication directory fsync failure"
    ):
        ed.write_oracle_json(
            destination,
            bath_artifact=_bath_artifact(),
            U=0.8,
            beta=2.0,
            tau=[0.0, 2.0],
        )

    after = destination.stat()
    assert destination.read_bytes() == b"existing oracle"
    assert external_link.read_bytes() == b"existing oracle"
    assert after.st_ino == before.st_ino == external_link.stat().st_ino
    assert stat.S_IMODE(after.st_mode) == stat.S_IMODE(before.st_mode)
    assert after.st_mtime_ns == before.st_mtime_ns
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "external.json",
        "oracle.json",
    ]


def test_existing_destination_hardlink_backup_creation_and_deletion_are_fsynced(
    tmp_path, monkeypatch
):
    destination = tmp_path / "oracle.json"
    destination.write_bytes(b"existing oracle")
    linked = []
    fsynced_directories = []
    real_link = ed.os.link
    real_directory_fsync = ed._fsync_directory

    def recording_link(source, target, **kwargs):
        linked.append((Path(source), Path(target), kwargs))
        return real_link(source, target, **kwargs)

    def recording_directory_fsync(directory):
        fsynced_directories.append(Path(directory))
        return real_directory_fsync(directory)

    monkeypatch.setattr(ed.os, "link", recording_link)
    monkeypatch.setattr(ed, "_fsync_directory", recording_directory_fsync)
    ed.write_oracle_json(
        destination,
        bath_artifact=_bath_artifact(),
        U=0.8,
        beta=2.0,
        tau=[0.0, 2.0],
    )

    assert linked and linked[0][0] == destination
    assert linked[0][1].parent == destination.parent
    assert len(fsynced_directories) == 3
    assert fsynced_directories == [tmp_path, tmp_path, tmp_path]
    assert list(tmp_path.iterdir()) == [destination]
