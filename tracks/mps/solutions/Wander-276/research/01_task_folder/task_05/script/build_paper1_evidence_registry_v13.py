#!/usr/bin/env python3
"""Build the fail-closed evidence registry for Paper I.

The registry is an additive v13 view of immutable v2--v12 outputs.  It does
not promote prose to evidence: positive entries are copied only from explicit
machine-readable checks or registered branches in the source artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


OUTPUT_PREFIX = Path("01_task_folder/task_05/script/output")
REQUIRED_SOURCE_PATHS: dict[str, Path] = {
    "spectral_silence_v2": OUTPUT_PREFIX / "spectral_silence_v2.json",
    "matrix_element_geometric_eth_v3": (
        OUTPUT_PREFIX / "matrix_element_geometric_eth_v3.json"
    ),
    "topological_holonomy_v3": OUTPUT_PREFIX / "topological_holonomy_v3.json",
    "continuum_lll_replication_inference_v6": (
        OUTPUT_PREFIX / "continuum_lll_replication_inference_v6.json"
    ),
    "susy_hodge_v7_N14_inference": (
        OUTPUT_PREFIX / "susy_hodge_v7_N14_inference.json"
    ),
    "moore_read_pilot_v9": (
        OUTPUT_PREFIX / "moore_read_v9/moore_read_pilot_v9.json"
    ),
    "lattice_susy_pilot_v10": (
        OUTPUT_PREFIX / "lattice_susy_v10/lattice_susy_pilot_v10.json"
    ),
    "xcube_geometric_control_v11": (
        OUTPUT_PREFIX / "xcube_v11/xcube_geometric_control_v11.json"
    ),
    "cross_complete_covariance_v12": (
        OUTPUT_PREFIX / "cross_complete_covariance_v12.json"
    ),
    "cross_mechanism_geometric_eth_v12": (
        OUTPUT_PREFIX / "cross_mechanism_geometric_eth_v12.json"
    ),
    "centered_complete_covariance_v13": (
        OUTPUT_PREFIX
        / "paper1_prb_v13/centered_complete_covariance_v13.json"
    ),
}
OPTIONAL_SOURCE_PATHS: dict[str, Path] = {
    "protected_scaling_inference_v4": (
        OUTPUT_PREFIX / "protected_scaling_inference_v4.json"
    ),
}
SOURCE_PATHS: dict[str, Path] = REQUIRED_SOURCE_PATHS | OPTIONAL_SOURCE_PATHS

SOURCE_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "spectral_silence_v2": ("all_checks_pass", "checks", "physical_case"),
    "matrix_element_geometric_eth_v3": ("checks", "cases", "result_branch"),
    "topological_holonomy_v3": ("checks", "sizes", "result_branch"),
    "protected_scaling_inference_v4": ("checks", "cases", "claim_boundary"),
    "continuum_lll_replication_inference_v6": (
        "checks",
        "branch",
        "claim_boundary",
        "scores",
    ),
    "susy_hodge_v7_N14_inference": (
        "passed",
        "checks",
        "selected_branch",
    ),
    "moore_read_pilot_v9": ("all_checks_pass", "cases"),
    "lattice_susy_pilot_v10": ("all_checks_pass", "cases"),
    "xcube_geometric_control_v11": ("all_checks_pass", "cases"),
    "cross_complete_covariance_v12": (
        "all_checks_pass",
        "cases",
        "protocol",
    ),
    "cross_mechanism_geometric_eth_v12": (
        "all_checks_pass",
        "claim_status",
        "complete_covariance_missing",
        "established",
        "models",
        "not_established",
        "production_missing",
        "response_convention",
        "selected_branch",
    ),
    "centered_complete_covariance_v13": (
        "claim_boundary",
        "corrected_primary_positive_directional_gate",
        "models",
        "protocol",
        "schema",
        "scientific_payload_sha256",
        "source_hashes",
        "version",
    ),
}

MODEL_NAMES = ("laughlin", "susy_syk", "moore_read", "lattice_susy", "xcube")
CENTERED_CASES = (
    "lattice_susy_m1",
    "lattice_susy_m2",
    "lattice_susy_m3",
    "moore_read_N4",
    "moore_read_N6",
)
CENTERED_SOURCE_GATES = {
    "lattice_susy_m1": False,
    "lattice_susy_m2": False,
    "lattice_susy_m3": False,
    "moore_read_N4": False,
    "moore_read_N6": True,
}
RESPONSE_SIGN_PROVENANCE = {
    "kato_projector_derivative": "X_a=-Q[Q(H-E0)Q]^-1Q(dH)P",
    "source_registry_unsigned_resolvent": "Q(H-E0)^-1Q(dH)P",
    "stored_channel_interpretation": (
        "stored_channels=-X_a_when_source_omits_Kato_minus"
    ),
    "even_contractions_invariant_under_global_channel_sign": True,
}


def load_json(path: Path, required: tuple[str, ...] = ()) -> dict[str, Any]:
    """Load a JSON object and reject missing files, malformed data, or keys."""

    if not path.is_file():
        raise RuntimeError(f"missing required evidence source: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid evidence source: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"evidence source is not a JSON object: {path}")
    missing = tuple(key for key in required if key not in payload)
    if missing:
        raise RuntimeError(f"{path} missing required keys: {', '.join(missing)}")
    return payload


def sha256_file(path: Path) -> str:
    """Return the hexadecimal SHA-256 digest of *path*."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RuntimeError(f"cannot hash evidence source: {path}: {exc}") from exc
    return digest.hexdigest()


def _require_registered_checks(source_id: str, payload: dict[str, Any]) -> None:
    has_summary = False
    if "all_checks_pass" in payload and payload["all_checks_pass"] is not True:
        raise RuntimeError(f"source {source_id} failed its registered checks")
    if payload.get("all_checks_pass") is True:
        has_summary = True
    if "passed" in payload and payload["passed"] is not True:
        raise RuntimeError(f"source {source_id} failed its registered checks")
    if payload.get("passed") is True:
        has_summary = True
    checks = payload.get("checks")
    if checks is not None:
        if not isinstance(checks, dict) or not checks:
            raise RuntimeError(f"source {source_id} has no registered checks")
        has_summary = True
        failed = sorted(key for key, value in checks.items() if value is not True)
        if failed:
            raise RuntimeError(
                f"source {source_id} failed its registered checks: {', '.join(failed)}"
            )
    if not has_summary:
        raise RuntimeError(f"source {source_id} has no registered checks")


def _validate_centered_covariance_source(payload: dict[str, Any]) -> None:
    """Validate the additive centered source without promoting its pilot gate."""

    if payload["version"] != "v13" or payload["schema"] != (
        "paper1_centered_complete_covariance_v13"
    ):
        raise RuntimeError("unexpected centered covariance schema or version")
    unsigned = deepcopy(payload)
    registered_hash = unsigned.pop("scientific_payload_sha256")
    encoded = (
        json.dumps(
            unsigned,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != registered_hash:
        raise RuntimeError("centered covariance scientific payload hash mismatch")

    protocol = payload["protocol"]
    if (
        protocol.get("panel_count") != 24
        or protocol.get("primary_training_indices") != list(range(12))
        or protocol.get("primary_inference_indices") != list(range(12, 24))
        or protocol.get("complete_wick_pairings") != 3
        or protocol.get("entrywise_mean")
        != "exact_registered_finite_ensemble_population_mean"
        or protocol.get("family_alpha") != 0.05
        or protocol.get("familywise_method") != "Bonferroni"
        or protocol.get("finite_sample_reference") != "Student_t"
        or protocol.get("student_t_degrees_of_freedom") != 11
        or protocol.get("primary_case_family_size") != 5
        or protocol.get("per_case_alpha") != 0.01
        or protocol.get("reverse_split_role")
        != "descriptive_replication_not_pooled"
    ):
        raise RuntimeError("centered covariance split protocol is contradictory")
    if set(payload["models"]) != set(CENTERED_CASES):
        raise RuntimeError("centered covariance case grid is incomplete")
    if payload["corrected_primary_positive_directional_gate"] != (
        CENTERED_SOURCE_GATES
    ):
        raise RuntimeError("centered covariance source gate grid is contradictory")

    for case_id in CENTERED_CASES:
        case = payload["models"][case_id]
        if case.get("model_id") != case_id:
            raise RuntimeError(f"centered covariance model identity mismatch: {case_id}")
        if case.get("response_sign_provenance") != RESPONSE_SIGN_PROVENANCE:
            raise RuntimeError(f"centered covariance response sign mismatch: {case_id}")
        raw = case.get("raw_v12_residual", {})
        if (
            raw.get("statistic") != "uncentered_unwhitened_raw_moment_residual"
            or raw.get("claim_eligible") is not False
        ):
            raise RuntimeError(f"raw v12 residual label is unsafe: {case_id}")
        centered = case.get("centered_whitened_complete_cumulant", {})
        if centered.get("statistic") != "centered_whitened_complete_cumulant":
            raise RuntimeError(f"centered statistic label is missing: {case_id}")
        primary = centered.get("primary", {})
        reverse = centered.get("reverse_descriptive", {})
        if (
            primary.get("inferential_role") != "primary_frozen_12_12_split"
            or primary.get("claim_eligible") is not True
            or primary.get("gate_for_claim") != CENTERED_SOURCE_GATES[case_id]
            or primary.get("summary", {}).get("realization_count") != 12
            or primary.get("summary", {}).get("pairing_count") != 3
            or primary.get("family_alpha") != 0.05
            or primary.get("per_case_alpha") != 0.01
            or primary.get("familywise_method")
            != "Bonferroni_over_registered_primary_cases_with_Student_t11"
        ):
            raise RuntimeError(f"centered primary split is contradictory: {case_id}")
        if (
            reverse.get("inferential_role")
            != "descriptive_replication_not_pooled"
            or reverse.get("claim_eligible") is not False
            or reverse.get("gate_for_claim") is not None
            or reverse.get("summary", {}).get("realization_count") != 12
            or reverse.get("summary", {}).get("pairing_count") != 3
        ):
            raise RuntimeError(f"centered reverse split is not descriptive: {case_id}")
        for fold_name, fold in (("primary", primary), ("reverse", reverse)):
            checks = fold.get("summary", {}).get("checks")
            if not isinstance(checks, dict) or not checks or not all(checks.values()):
                raise RuntimeError(
                    f"centered covariance {fold_name} checks failed: {case_id}"
                )
        audit = primary.get("transform_audit", {})
        if (
            audit.get("population_mean_exact_for_registered_finite_ensemble")
            is not True
            or audit.get("centering_not_estimated_from_training_panels") is not True
            or not audit.get("population_mean_provenance")
        ):
            raise RuntimeError(
                f"centered population-mean provenance is incomplete: {case_id}"
            )
        familywise_lower = primary.get("familywise_one_sided_interval_low")
        if not isinstance(familywise_lower, (int, float)) or not math.isfinite(
            familywise_lower
        ):
            raise RuntimeError(f"centered familywise interval is missing: {case_id}")
        if primary["gate_for_claim"] is not (familywise_lower > 0.0):
            raise RuntimeError(f"centered familywise gate is contradictory: {case_id}")


def _validate_cross_boundary(
    cross: dict[str, Any], covariance: dict[str, Any]
) -> None:
    models = cross["models"]
    if set(models) != set(MODEL_NAMES):
        raise RuntimeError("cross-mechanism model registry is incomplete")

    production_missing = set(cross["production_missing"])
    expected_production_missing = {
        name for name, model in models.items() if model.get("production_complete") is False
    }
    if production_missing != expected_production_missing:
        raise RuntimeError("contradictory production flag in cross-mechanism source")

    covariance_missing = set(cross["complete_covariance_missing"])
    expected_covariance_missing = {
        name
        for name, model in models.items()
        if model.get("complete_covariance_computed") is False
    }
    if covariance_missing != expected_covariance_missing:
        raise RuntimeError("contradictory complete-covariance flag in cross-mechanism source")

    expected_covariance_cases = {
        "moore_read_N4",
        "moore_read_N6",
        "lattice_susy_m1",
        "lattice_susy_m2",
        "lattice_susy_m3",
    }
    if set(covariance["cases"]) != expected_covariance_cases:
        raise RuntimeError("complete-covariance case grid is incomplete or contradictory")

    required_negative_claims = {
        "asymptotic Geometric ETH",
        "cross-mechanism universality of a scaling law",
        "complete-covariance inference from independent Hamiltonian or disorder realizations for Moore--Read or lattice SUSY",
        "Moore--Read N=8 production result",
    }
    if not required_negative_claims.issubset(set(cross["not_established"])):
        raise RuntimeError("cross-mechanism source is missing a registered claim boundary")
    if cross["selected_branch"] != "domain_limited_geometric_eth":
        raise RuntimeError("unexpected cross-mechanism registered branch")

    required_positive_results = {
        "exact degeneracy and projector-motion audits pass in all opened models",
        "X-cube coefficient reweighting has exactly zero geometry",
        "X-cube local isospectral transport has scalar curvature and zero connected variance",
        "Moore--Read N=4 and N=6 have positive fixed-direction complete-covariance panel cumulants",
        "lattice-SUSY complete-covariance panel cumulants do not pass the fixed positive-direction gate at m=1,2,3",
    }
    if not required_positive_results.issubset(set(cross["established"])):
        raise RuntimeError("cross-mechanism source is missing a registered positive result")


def _validate_embedded_hashes(
    payloads: dict[str, dict[str, Any]], source_hashes: dict[str, str]
) -> None:
    cross = payloads["cross_mechanism_geometric_eth_v12"]
    source_for_model = {
        "laughlin": "continuum_lll_replication_inference_v6",
        "susy_syk": "susy_hodge_v7_N14_inference",
        "moore_read": "moore_read_pilot_v9",
        "lattice_susy": "lattice_susy_pilot_v10",
        "xcube": "xcube_geometric_control_v11",
    }
    for model_name, source_id in source_for_model.items():
        embedded = cross["models"][model_name].get("source", {}).get("sha256")
        if embedded != source_hashes[source_id]:
            raise RuntimeError(f"source hash contradiction for model {model_name}")
    covariance_hash = cross.get("complete_covariance_source", {}).get("sha256")
    if covariance_hash != source_hashes["cross_complete_covariance_v12"]:
        raise RuntimeError("source hash contradiction for complete covariance")


def _validate_raw_residual_consistency(
    raw_v12: dict[str, Any], centered_v13: dict[str, Any]
) -> None:
    for case_id in CENTERED_CASES:
        registered = centered_v13["models"][case_id]["raw_v12_residual"]
        expected = raw_v12["cases"][case_id]
        observed = registered["summary"]
        exact_fields = (
            "ambient_dimension",
            "fiber_rank",
            "label_count",
            "pairing_count",
            "positive_directional_gate",
            "realization_count",
            "unordered_pair_count",
        )
        numeric_fields = (
            "directional_estimate",
            "normalized_cumulant_norm",
            "one_sided_interval_low",
            "one_sided_p_value",
            "standard_error",
            "z_score",
        )
        exact_match = all(observed[field] == expected[field] for field in exact_fields)
        numeric_match = all(
            math.isclose(
                float(observed[field]),
                float(expected[field]),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            for field in numeric_fields
        )
        expected_oracle = expected.get("oracle_relative_error")
        observed_oracle = observed.get("oracle_relative_error")
        oracle_match = (
            expected_oracle is None
            and observed_oracle is None
            or isinstance(expected_oracle, (int, float))
            and isinstance(observed_oracle, (int, float))
            and math.isclose(
                float(observed_oracle),
                float(expected_oracle),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        )
        checks_match = observed.get("checks") == expected.get("checks")
        if not (exact_match and numeric_match and oracle_match and checks_match):
            raise RuntimeError(
                f"raw v12 residual contradicts centered source: {case_id}"
            )


def _model_registry(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cross_models = payloads["cross_mechanism_geometric_eth_v12"]["models"]
    centered = payloads["centered_complete_covariance_v13"]
    continuum = payloads["continuum_lll_replication_inference_v6"]
    matrix_elements = payloads["matrix_element_geometric_eth_v3"]

    models: dict[str, Any] = {}
    for name in MODEL_NAMES:
        source_model = cross_models[name]
        raw_available = source_model["complete_covariance_computed"]
        if name in {"moore_read", "lattice_susy"}:
            centered_available: bool | str = True
            case_prefix = "moore_read_" if name == "moore_read" else "lattice_susy_"
            source_gates = {
                case_id: centered["corrected_primary_positive_directional_gate"][
                    case_id
                ]
                for case_id in CENTERED_CASES
                if case_id.startswith(case_prefix)
            }
        elif name == "xcube":
            centered_available = "not_applicable_exact_control"
            source_gates = {}
        else:
            centered_available = False
            source_gates = {}
        models[name] = {
            "mechanism": source_model["mechanism"],
            "role": source_model["role"],
            "production_complete": source_model["production_complete"],
            "raw_uncentered_moment_residual_v12": raw_available,
            "raw_uncentered_moment_residual_claim_eligible": False,
            "centered_complete_covariance_v13": centered_available,
            "centered_source_observed_gate_by_case": source_gates,
            "centered_claim_gate_by_case": deepcopy(source_gates),
            "centered_claim_eligible": centered_available is True,
            "independent_ensemble_complete": False,
            "source_unsigned_response_convention": source_model[
                "response_convention"
            ],
            "response_sign_provenance": deepcopy(RESPONSE_SIGN_PROVENANCE),
        }

    models["laughlin"].update(
        {
            "role": "finite_size_stochastic_geometry",
            "reported_branch": continuum["branch"],
            "matrix_element_ranks": [case["rank"] for case in matrix_elements["cases"]],
            "continuum_connected_excess_by_size": deepcopy(
                cross_models["laughlin"]["connected_excess_by_size"]
            ),
        }
    )
    models["susy_syk"].update(
        {
            "role": "finite_size_stochastic_geometry",
            "reported_branch": cross_models["susy_syk"]["reported_branch"],
            "N14_observed_medians": deepcopy(
                cross_models["susy_syk"]["N14_observed_medians"]
            ),
        }
    )
    models["moore_read"].update(
        {
            "role": "finite_size_stochastic_geometry",
            "cases": deepcopy(cross_models["moore_read"]["cases"]),
        }
    )
    models["lattice_susy"].update(
        {
            "role": "finite_size_structured_geometry",
            "cases": deepcopy(cross_models["lattice_susy"]["cases"]),
        }
    )
    models["xcube"].update(
        {
            "role": "exact_structured_control",
            "independent_ensemble_complete": "not_applicable_exact_control",
            "coefficient_curvature": cross_models["xcube"]["coefficient_curvature"],
            "transport_curvature_eigenvalue": cross_models["xcube"][
                "transport_curvature_eigenvalue"
            ],
            "transport_connected_variance": cross_models["xcube"][
                "transport_connected_variance"
            ],
        }
    )
    return models


def _centered_case_registry(
    centered_source: dict[str, Any], case_id: str
) -> dict[str, Any]:
    """Copy a centered case and retain the audited finite-rank gate boundary."""

    source_case = centered_source["models"][case_id][
        "centered_whitened_complete_cumulant"
    ]
    primary = deepcopy(source_case["primary"])
    primary["source_observed_gate"] = primary["gate_for_claim"]
    primary["source_claim_eligible"] = primary["claim_eligible"]
    primary["inference_status"] = "finite_rank_exact_population_mean_familywise"
    reverse = deepcopy(source_case["reverse_descriptive"])
    return {
        "primary": primary,
        "reverse_descriptive": reverse,
    }


def build_registry(repo_root: Path) -> dict[str, Any]:
    """Build and validate the Paper I registry from a repository root."""

    root = Path(repo_root).resolve()
    payloads: dict[str, dict[str, Any]] = {}
    source_hashes: dict[str, str] = {}
    sources: dict[str, Any] = {}

    for source_id, relative_path in REQUIRED_SOURCE_PATHS.items():
        path = root / relative_path
        payload = load_json(path, SOURCE_REQUIRED_KEYS[source_id])
        if source_id == "centered_complete_covariance_v13":
            _validate_centered_covariance_source(payload)
        else:
            _require_registered_checks(source_id, payload)
        digest = sha256_file(path)
        payloads[source_id] = payload
        source_hashes[source_id] = digest
        sources[source_id] = {
            "path": relative_path.as_posix(),
            "available": True,
            "sha256": digest,
            "checks_pass": True,
            "version": payload.get("version"),
        }

    for source_id, relative_path in OPTIONAL_SOURCE_PATHS.items():
        # The v4 scaling file is mentioned in the historical plan but is not
        # tracked on this delivery branch.  Its absence is evidence metadata,
        # never a zero-valued observable or a failed/positive scientific gate.
        sources[source_id] = {
            "path": relative_path.as_posix(),
            "available": False,
            "reason": "not_tracked_in_delivery_branch",
            "version": "v4",
        }

    cross = payloads["cross_mechanism_geometric_eth_v12"]
    covariance = payloads["cross_complete_covariance_v12"]
    centered_covariance = payloads["centered_complete_covariance_v13"]
    _validate_cross_boundary(cross, covariance)
    _validate_embedded_hashes(payloads, source_hashes)
    _validate_raw_residual_consistency(covariance, centered_covariance)
    models = _model_registry(payloads)

    spectral = payloads["spectral_silence_v2"]
    matrix_elements = payloads["matrix_element_geometric_eth_v3"]
    topology = payloads["topological_holonomy_v3"]

    observables = {
        "spectral_silence": {
            "exact_energy_silence": spectral["checks"]["exact_energy_silence"],
            "kernel_bandwidth": spectral["physical_case"]["kernel_bandwidth"],
            "external_gap": spectral["physical_case"]["external_gap"],
            "fiber_rank": spectral["physical_case"]["D"],
        },
        "matrix_element_geometry": {
            "registered_branch": matrix_elements["result_branch"],
            "descriptive_slope_per_particle": matrix_elements[
                "descriptive_slope_per_particle"
            ],
            "cases": deepcopy(matrix_elements["cases"]),
        },
        "protected_fourth_moment": {
            "available": False,
            "reason": "not_tracked_in_delivery_branch",
        },
        "raw_uncentered_moment_residual_v12": {
            "statistic": "raw_uncentered_moment_residual",
            "source_label": "uncentered_unwhitened_raw_moment_residual",
            "notation": "raw_moment_residual",
            "claim_eligible": False,
            "raw_v12_recomputed_numerically_consistent": True,
            "recomputation_note": (
                "v13 deterministic recomputation agrees with v12 within "
                "rtol=atol=1e-12 after exact structural checks"
            ),
            "protocol": deepcopy(covariance["protocol"]),
            "cases": deepcopy(covariance["cases"]),
        },
        "centered_whitened_full_r4_v13": {
            "statistic": "centered_whitened_complete_cumulant",
            "notation": "R4^{full}",
            "claim_eligible": True,
            "inference_status": "finite_rank_exact_population_mean_familywise",
            "claim_boundary": (
                "The registered familywise gate is finite-rank and model/case "
                "specific; it is not asymptotic or universal evidence."
            ),
            "protocol": deepcopy(centered_covariance["protocol"]),
            "source_observed_primary_gate_by_case": deepcopy(
                centered_covariance[
                    "corrected_primary_positive_directional_gate"
                ]
            ),
            "claim_gate_by_case": deepcopy(
                centered_covariance[
                    "corrected_primary_positive_directional_gate"
                ]
            ),
            "reverse_split_role": "descriptive_replication_not_pooled",
            "response_sign_provenance": deepcopy(RESPONSE_SIGN_PROVENANCE),
            "cases": {
                case_id: _centered_case_registry(centered_covariance, case_id)
                for case_id in CENTERED_CASES
            },
        },
        "topological_holonomy": {
            "registered_branch": topology["result_branch"],
            "sizes": deepcopy(topology["sizes"]),
        },
    }

    gates = {
        "production_complete_by_model": {
            name: models[name]["production_complete"] for name in MODEL_NAMES
        },
        "raw_uncentered_moment_residual_v12_by_model": {
            name: models[name]["raw_uncentered_moment_residual_v12"]
            for name in MODEL_NAMES
        },
        "centered_full_r4_v13_available_by_model": {
            name: models[name]["centered_complete_covariance_v13"]
            for name in MODEL_NAMES
        },
        "centered_full_r4_v13_source_observed_by_case": deepcopy(
            centered_covariance["corrected_primary_positive_directional_gate"]
        ),
        "centered_full_r4_v13_claim_gate_by_case": {
            case_id: centered_covariance[
                "corrected_primary_positive_directional_gate"
            ][case_id]
            for case_id in CENTERED_CASES
        },
        "centered_full_r4_v13_claim_eligible": True,
        "centered_full_r4_v13_inference_status": (
            "finite_rank_exact_population_mean_familywise"
        ),
        "independent_ensemble_complete_by_model": {
            name: models[name]["independent_ensemble_complete"] for name in MODEL_NAMES
        },
        "selected_cross_mechanism_branch": cross["selected_branch"],
        "claim_status": cross["claim_status"],
        "all_registered_source_checks_pass": True,
    }

    established = set(cross["established"])
    not_established = set(cross["not_established"])
    claims = {
        "exact_degeneracy_with_informative_geometry": (
            "exact degeneracy and projector-motion audits pass in all opened models"
            in established
        ),
        "finite_size_mechanism_dependent_geometric_statistics": (
            cross["selected_branch"] == "domain_limited_geometric_eth"
        ),
        "domain_limited_geometric_eth": (
            cross["selected_branch"] == "domain_limited_geometric_eth"
        ),
        "centered_full_r4_positive_only_moore_read_N6": True,
        "centered_full_r4_positive_claim": True,
        "centered_full_r4_population_mean_audit_complete": True,
        "centered_full_r4_moore_read_N4": False,
        "centered_full_r4_lattice_susy_m1_m2_m3": False,
        "strongest_statistical_scope": (
            "finite_rank_domain_limited_moore_read_N6_only"
        ),
        "asymptotic_geometric_eth": (
            "asymptotic Geometric ETH" not in not_established
        ),
        "universal_geometric_eth": (
            "cross-mechanism universality of a scaling law" not in not_established
        ),
        "cross_mechanism_universal_scaling": (
            "cross-mechanism universality of a scaling law" not in not_established
        ),
        "independent_model_operator_class_established": (
            "complete-covariance inference from independent Hamiltonian or disorder realizations for Moore--Read or lattice SUSY"
            not in not_established
        ),
        "thermalization": False,
        "lyapunov_behavior": False,
        "moore_read_N8_production_result": (
            "Moore--Read N=8 production result" not in not_established
        ),
        "registered_not_established": sorted(
            set(cross["not_established"])
            | {
                "asymptotic or universal extension of the finite-rank "
                "Moore--Read N=6 centered/full-R4 result"
            }
        ),
    }

    return {
        "sources": sources,
        "models": models,
        "observables": observables,
        "gates": gates,
        "claims": claims,
        "source_hashes": source_hashes,
    }


def write_registry_atomic(payload: dict[str, Any], destination: Path) -> None:
    """Serialize *payload* to *destination* without exposing a partial file."""

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    destination = (
        repo_root
        / "01_task_folder/task_05/script/output/paper1_prb_v13/evidence_registry_v13.json"
    )
    write_registry_atomic(build_registry(repo_root), destination)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
