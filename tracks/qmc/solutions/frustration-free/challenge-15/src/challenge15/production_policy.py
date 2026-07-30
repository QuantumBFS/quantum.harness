"""Code-owned immutable policy for Challenge 15 production execution."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Mapping


JSONValue = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]

ARTIFACT_SCHEMAS = (
    "challenge15.production-policy.v1",
    "challenge15.source-manifest.v1",
    "challenge15.allowed-runtime.v1",
    "challenge15.runtime-attestation-set.v1",
    "challenge15.runtime-set-copies.v1",
    "challenge15.runtime-set-publication-receipt.v1",
    "challenge15.attestation-bootstrap-transfer.v1",
    "challenge15.cluster-profile.v1",
    "challenge15.production-oracle.v1",
    "challenge15.chiral-response.v1",
    "challenge15.seed-owner.v1",
    "challenge15.rank-extension.v1",
    "challenge15.rank-extension-decision.v1",
    "challenge15.training-attempt.v1",
    "challenge15.training-snapshot.v1",
    "challenge15.training-generation.v1",
    "challenge15.recovery-receipt.v1",
    "challenge15.resource-override.v1",
    "challenge15.identity-map.v1",
    "challenge15.submission-receipt.v1",
    "challenge15.orchestration-state-key.v1",
    "challenge15.orchestration-attempt-intent.v1",
    "challenge15.orchestration-transition.v1",
    "challenge15.orchestration-state-manifest.v1",
    "challenge15.state-manifest-backup-receipt.v1",
    "challenge15.output-promotion.v1",
    "challenge15.export-bundle.v1",
    "challenge15.import-bundle.v1",
    "challenge15.transfer-receipt.v1",
    "challenge15.dry-run-receipt.v1",
    "challenge15.deployment-receipt.v1",
    "challenge15.exact-evaluation-shard.v1",
    "challenge15.coordinate-evaluation-shard.v1",
    "challenge15.evaluation-receipt.v1",
    "challenge15.size-result.v1",
    "challenge15.reduction-receipt.v1",
    "challenge15.reduction-finalization.v1",
    "challenge15.terminal-selection.v1",
    "challenge15.cross-size-manifest.v1",
    "challenge15.final-report.v1",
    "challenge15.report-receipt.v1",
)

RUNTIME_ROLES = ("training", "coordinate", "oracle", "exact", "reducer")
IMMUTABLE_INPUT_SCHEMAS = (
    "challenge15.production-vmc-config.v1",
    "challenge15.fixed-schedule.v1",
)

_POLICY: dict[str, JSONValue] = {
    "physics": {
        "two_q_formula": "3*(N-1)",
        "interaction": "chord-coulomb-distance",
        "energy_unit": "E_C",
        "sectors": [0, 2],
    },
    "model": {
        "shared_parameter_tree": True,
        "carriers": "exact-M=0",
        "projector": "exact-angular-momentum",
        "determinant_indexed_trainable_arrays": False,
    },
    "estimator": {
        "gradient": "score_covariance_finite_chain",
        "sampling_variance_label": "bare-potential",
        "prohibited_variance_label": "Var(H_LLL)",
    },
    "seed_policy": {
        "seeds": [0, 1, 2, 3, 4],
        "complete_coverage_at_every_rank": True,
        "identical_paired_seed_sets": True,
        "minimum_accepted_final_rank_seeds": 4,
    },
    "rank_policy": {
        "initial_rank": 1,
        "growth": "consecutive-doubling",
        "required_rank_doublings": 2,
        "energy_change_plus_2sigma_max_ec": 1e-4,
        "gap_change_plus_2sigma_relative_max": 0.002,
        "overlap_change_max": 1e-3,
        "allowed_nonroot_reasons": [
            "scheduled_initial_ladder",
            "rank_convergence_pending",
        ],
    },
    "exact_acceptance": {
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
    },
    "vmc_diagnostics": {
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
    },
    "artifact_schemas": list(ARTIFACT_SCHEMAS),
    "immutable_input_schemas": list(IMMUTABLE_INPUT_SCHEMAS),
    "runtime_roles": list(RUNTIME_ROLES),
    "transfer_policy": {
        "publication": "create-only",
        "partial_paths": "unique-content-addressed",
        "existing_destination": "hard-fail",
        "approved_roots_only": True,
        "verify_before_atomic_rename": True,
    },
    "finalization_policy": {
        "expected_rank_versioned": True,
        "provisional_create_only": True,
        "terminal_selection_create_only": True,
        "accepted_only_terminal_selection": True,
    },
    "claim_policy": {
        "prerequisite_order": [6, 7, 8],
        "missing_or_failed_gates": "pending",
        "accepted_claim": (
            "Production accepted for finite-size lowest-L=2 sector gaps at "
            "N=6,7,8 only; no chiral response or thermodynamic-limit claim is made."
        ),
        "pending_claim": "Production pending; no N=6..8 production claim is made.",
        "prohibited_claims": ["chirality", "thermodynamic-limit", "scalability"],
    },
}


def production_policy() -> Mapping[str, JSONValue]:
    """Return a detached copy of the sole canonical production policy payload."""

    return deepcopy(_POLICY)


def policy_sha256() -> str:
    """Return SHA256 of canonical policy payload bytes."""

    encoded = json.dumps(
        _POLICY,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
