import jax.numpy as jnp
import pytest
from jax.ad_checkpoint import checkpoint_name

from vqetape.spatial_programs import build_spatial_energy
from vqetape.spec import SpatialProgramConfig, TFIMVQESpec
from vqetape.tape import profile_saved_residuals
from vqetape.tn_program import plan_contraction
from vqetape.tn_template import build_expectation_template
from vqetape.tn_template import build_mpo_expectation_template
from vqetape.tn_vqe import build_tn_energy


def test_profile_saved_residuals_accounts_for_bytes_and_sources():
    def objective(value):
        hidden = checkpoint_name(
            jnp.sin(value),
            "hidden",
        )
        return jnp.sum(hidden * hidden)

    argument = jnp.ones((4,), dtype=jnp.float32)
    profile = profile_saved_residuals(objective, argument)

    assert profile.total_bytes > 0
    assert profile.recomputable_bytes > 0
    assert profile.bytes_by_name()["hidden"] == 16
    assert sum(profile.bytes_by_category().values()) == profile.total_bytes


def test_residual_profile_serializes_without_full_records_by_default():
    profile = profile_saved_residuals(lambda value: jnp.sum(value**2), jnp.ones(3))

    payload = profile.to_dict()

    assert payload["residual_count"] == len(profile.records)
    assert payload["total_bytes"] == profile.total_bytes
    assert "records" not in payload
    assert len(profile.to_dict(include_records=True)["records"]) == len(
        profile.records
    )


@pytest.mark.parametrize(
    "spec",
    [
        TFIMVQESpec(nqubits=2, depth=1),
        TFIMVQESpec(nqubits=3, depth=2),
    ],
)
@pytest.mark.parametrize(
    "gate_representation",
    ["dense", "operator_schmidt"],
)
@pytest.mark.parametrize(
    "hamiltonian_representation",
    ["pauli_sum", "mpo"],
)
def test_named_tape_controls_logical_residual_budget(
    spec,
    gate_representation,
    hamiltonian_representation,
):
    template = (
        build_expectation_template(
            spec,
            gate_representation=gate_representation,
        )
        if hamiltonian_representation == "pauli_sum"
        else build_mpo_expectation_template(
            spec,
            gate_representation=gate_representation,
        )
    )
    program = plan_contraction(template, "greedy")
    all_names = tuple(
        f"contract:{step_index}:elements{step.output_elements}:{component}"
        for step_index, step in enumerate(program.steps)
        for component in ("real", "imag")
    )
    theta = jnp.zeros(spec.parameter_shape, dtype=jnp.float32)
    default_energy, _, _ = build_tn_energy(
        spec,
        path_strategy="greedy",
        remat_policy="none",
        explicit_path=program.path,
        gate_representation=gate_representation,
        hamiltonian_representation=hamiltonian_representation,
    )
    empty_energy, _, _ = build_tn_energy(
        spec,
        path_strategy="greedy",
        remat_policy="named",
        explicit_path=program.path,
        save_names=(),
        gate_representation=gate_representation,
        hamiltonian_representation=hamiltonian_representation,
    )
    full_energy, _, _ = build_tn_energy(
        spec,
        path_strategy="greedy",
        remat_policy="named",
        explicit_path=program.path,
        save_names=all_names,
        gate_representation=gate_representation,
        hamiltonian_representation=hamiltonian_representation,
    )

    default_bytes = profile_saved_residuals(default_energy, theta).total_bytes
    empty_bytes = profile_saved_residuals(empty_energy, theta).total_bytes
    full_bytes = profile_saved_residuals(full_energy, theta).total_bytes

    assert empty_bytes < full_bytes < default_bytes


def test_schmidt_lowering_eliminates_dense_diag_residuals():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    theta = jnp.zeros(spec.parameter_shape, dtype=jnp.float32)
    profiles = {}
    for gate_representation in ("dense", "operator_schmidt"):
        energy, _, _ = build_tn_energy(
            spec,
            path_strategy="greedy",
            remat_policy="none",
            gate_representation=gate_representation,
        )
        profiles[gate_representation] = profile_saved_residuals(
            energy,
            theta,
        )

    assert profiles["dense"].bytes_by_category().get("jitted:_diag", 0) > 0
    assert (
        profiles["operator_schmidt"]
        .bytes_by_category()
        .get("jitted:_diag", 0)
        == 0
    )


def test_mpo_removes_repeated_circuit_gate_residuals():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    theta = jnp.zeros(spec.parameter_shape, dtype=jnp.float32)
    profiles = {}
    for hamiltonian_representation in ("pauli_sum", "mpo"):
        energy, _, _ = build_tn_energy(
            spec,
            path_strategy="greedy",
            remat_policy="none",
            hamiltonian_representation=hamiltonian_representation,
        )
        profiles[hamiltonian_representation] = profile_saved_residuals(
            energy,
            theta,
        )

    assert profiles["mpo"].total_bytes < profiles["pauli_sum"].total_bytes
    assert (
        profiles["mpo"].bytes_by_category().get("jitted:_diag", 0)
        < profiles["pauli_sum"]
        .bytes_by_category()
        .get("jitted:_diag", 0)
    )


@pytest.mark.parametrize(
    "config",
    [
        SpatialProgramConfig("greedy", "default"),
        SpatialProgramConfig("greedy", "remat"),
        SpatialProgramConfig(
            "greedy",
            "segmented",
            segment_length=2,
        ),
        SpatialProgramConfig(
            "greedy",
            "explicit",
            block_width=3,
        ),
        SpatialProgramConfig(
            "greedy",
            "default",
            symmetry="z2-reference",
        ),
        SpatialProgramConfig(
            "greedy",
            "default",
            symmetry="z2-native",
        ),
    ],
)
def test_spatial_adjoint_residual_profiles_are_structured(config):
    spec = TFIMVQESpec(nqubits=8, depth=1)
    theta = jnp.zeros(spec.parameter_shape, dtype=jnp.float32)
    profile = profile_saved_residuals(
        build_spatial_energy(spec, config),
        theta,
    )

    assert profile.records
    assert profile.total_bytes > 0
    assert profile.recomputable_bytes >= 0
    assert sum(profile.bytes_by_category().values()) == profile.total_bytes


def test_explicit_spatial_residual_profile_has_fixed_path_control():
    spec = TFIMVQESpec(nqubits=12, depth=1)
    theta = jnp.zeros(spec.parameter_shape, dtype=jnp.float32)
    profiles = {
        adjoint: profile_saved_residuals(
            build_spatial_energy(
                spec,
                SpatialProgramConfig(
                    "greedy",
                    adjoint,
                    block_width=3,
                ),
            ),
            theta,
        )
        for adjoint in ("default", "explicit")
    }

    assert profiles["default"].total_bytes > 0
    assert profiles["explicit"].total_bytes > 0
