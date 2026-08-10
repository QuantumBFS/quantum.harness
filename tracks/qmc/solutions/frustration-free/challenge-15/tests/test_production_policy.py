from __future__ import annotations

import copy
from pathlib import Path
import subprocess

import pytest

from challenge15.production_policy import (
    ARTIFACT_SCHEMAS,
    policy_sha256,
    production_policy,
)
from challenge15.production_schema import payload_sha256
from challenge15.provenance import SOURCE_PATTERNS, build_source_manifest


def test_policy_is_canonical_complete_and_not_mutable():
    first = production_policy()
    second = production_policy()

    assert first == second
    assert first is not second
    assert list(first) == [
        "physics",
        "model",
        "estimator",
        "seed_policy",
        "rank_policy",
        "exact_acceptance",
        "vmc_diagnostics",
        "artifact_schemas",
        "immutable_input_schemas",
        "runtime_roles",
        "transfer_policy",
        "finalization_policy",
        "claim_policy",
    ]
    assert first["immutable_input_schemas"] == [
        "challenge15.production-vmc-config.v1",
        "challenge15.fixed-schedule.v1",
    ]
    assert first["seed_policy"]["seeds"] == [0, 1, 2, 3, 4]
    assert first["rank_policy"]["required_rank_doublings"] == 2
    assert first["vmc_diagnostics"]["minimum_effective_sample_size"] == 1000
    assert first["vmc_diagnostics"]["maximum_split_rhat"] == 1.01
    assert first["runtime_roles"] == [
        "training",
        "coordinate",
        "oracle",
        "exact",
        "reducer",
    ]
    assert set(first["artifact_schemas"]) == set(ARTIFACT_SCHEMAS)

    first["seed_policy"]["seeds"].append(99)
    assert production_policy()["seed_policy"]["seeds"] == [0, 1, 2, 3, 4]


def test_policy_digest_is_payload_digest_and_sensitive_to_acceptance_changes():
    policy = production_policy()
    changed = copy.deepcopy(policy)
    changed["vmc_diagnostics"]["maximum_split_rhat"] = 1.02

    assert policy_sha256() == payload_sha256(policy)
    assert payload_sha256(changed) != policy_sha256()


def test_policy_encodes_every_design_section_12_gate_exactly():
    policy = production_policy()

    assert policy["exact_acceptance"] == {
        "hilbert_space": {
            "car_and_pauli_identities_exact": True,
            "multiplicity_dimension_identity": "dim(M_L)=dim(H_M=L)-dim(H_M=L+1)",
            "irrep_completeness_identity": "sum_L((2L+1)*dim(M_L))=binomial(2Q+1,N)",
            "intertwiner_orthonormality_defect_max": 1e-12,
        },
        "gauge_rotation": {
            "generator_intertwiner_relative_residual_max": 1e-11,
            "finite_rotation_relative_residual_max": 1e-10,
            "chart_product_gauge_phase_relative_residual_max": 1e-10,
            "su2_central_element_exact": True,
        },
        "hamiltonian": {
            "relative_hermiticity_defect_max": 1e-13,
            "independent_coulomb_matrix_and_spectrum_error_max_ec": 1e-11,
            "lz_l2_relative_commutator_residual_max": 1e-10,
            "eigenpair_residual_max": 1e-10,
        },
        "nqs": {
            "minimum_passing_seeds": 4,
            "configured_seed_count": 5,
            "joint_sector_conditioned_single_parameter_tree": True,
            "determinant_or_multiplicity_scaled_trainable_arrays_forbidden": True,
            "carrier_antisymmetric_holomorphic_exact_degree_2q": True,
            "unprojected_mz_residual_max": 1e-12,
            "gauss_legendre_exactness": "2*n_beta-1>=L_max+L",
            "periodic_alpha_exactness": "n_alpha>=2*L_max+1",
            "quadrature_normalized_amplitude_energy_symmetry_change_max": 1e-11,
            "required_consecutive_rank_doublings": 2,
            "sector_energy_change_plus_2sigma_max_ec": 1e-4,
            "gap_change_plus_2sigma_relative_max": 0.002,
            "paired_covariance_required": True,
            "projected_span_relative_threshold": 1e-10,
            "projected_span_singular_values_required": True,
            "projected_span_numerical_rank_required": True,
            "completeness_claim_requires_rank_equals_dim_m_l": True,
            "incomplete_span_claim_basis": "energy-and-overlap-convergence-only",
            "exact_overlap_change_max": 1e-3,
            "exact_sum_energy_error_max_ec": 1e-4,
            "exact_sum_energy_error_max_gap_fraction": 0.01,
            "gap_ed_relative_error_max": 0.01,
            "gap_combined_standard_errors_max": 2.0,
            "exact_overlap_min": 0.99,
            "per_state_gates_required": True,
        },
        "response": {
            "rank_two_tensor_commutator_residual_max": 1e-10,
            "adjoint_relation_residual_max": 1e-12,
            "spectral_sum_rule_weight_min": 0.99,
            "chirality_requires_resolved_unnormalized_contrast": True,
            "monopole_reversal_interchange_required": True,
        },
    }


def test_every_acceptance_leaf_changes_policy_digest():
    baseline = production_policy()

    def leaves(value, path=()):
        if isinstance(value, dict):
            for key, nested in value.items():
                yield from leaves(nested, (*path, key))
        else:
            yield path, value

    for path, value in leaves(baseline["exact_acceptance"]):
        changed = copy.deepcopy(baseline)
        target = changed["exact_acceptance"]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = not value if isinstance(value, bool) else f"{value}-changed"
        assert payload_sha256(changed) != policy_sha256(), path


def test_policy_encodes_exact_update_and_statistical_gates():
    assert production_policy()["vmc_diagnostics"] == {
        "minimum_retained_values_per_sector": 2,
        "minimum_chains_per_sector": 4,
        "minimum_effective_sample_size": 1000,
        "maximum_split_rhat": 1.01,
        "optimize_total_acceptance_rate_min": 0.20,
        "optimize_total_acceptance_rate_max": 0.80,
        "evaluation_local_acceptance_rate_min": 0.20,
        "evaluation_local_acceptance_rate_max": 0.80,
        "evaluation_total_acceptance_rate_min": 0.20,
        "evaluation_total_acceptance_rate_max": 0.80,
        "require_autocorrelation_converged_for": ["E0", "E2", "paired_gap"],
        "require_effective_sample_size_for": ["E0", "E2", "paired_gap"],
        "require_split_rhat_for": ["E0", "E2", "paired_gap"],
        "require_finite_update_values": [
            "amplitudes",
            "potentials",
            "scores",
            "gradients",
            "parameters",
            "optimizer_values",
            "estimates",
        ],
        "require_finite_evaluation_values": [
            "estimates",
            "errors",
            "intervals",
            "covariances",
        ],
        "confidence_interval_must_contain_estimate": True,
        "invalid_update_stops_attempt": True,
    }


def test_source_manifest_covers_every_tracked_executable_and_test_input():
    root = Path(__file__).parents[1]
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", *SOURCE_PATTERNS],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    expected = {path for path in tracked if path}

    manifest = build_source_manifest(root)

    assert set(manifest.members) == expected
    assert all(len(digest) == 64 for digest in manifest.members.values())
    assert manifest.policy_sha256 == policy_sha256()


def test_source_manifest_clean_check_rejects_dirty_file_outside_source_patterns(
    tmp_path,
):
    (tmp_path / "README.md").write_text("clean\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "README.md"],
        check=True,
    )
    subprocess.run(
        [
            "git", "-C", str(tmp_path),
            "-c", "user.name=Test",
            "-c", "user.email=test@example.invalid",
            "commit", "-qm", "fixture",
        ],
        check=True,
    )
    (tmp_path / "README.md").write_text("dirty\n")

    with pytest.raises(ValueError, match="clean"):
        build_source_manifest(tmp_path, require_clean=True)
