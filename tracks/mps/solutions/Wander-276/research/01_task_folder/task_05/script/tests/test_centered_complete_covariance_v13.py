from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from lgeth.full_wick_ustat import ResponseFactors
from run_centered_complete_covariance_v13 import (
    MOORE_CHECKPOINT_ROOT,
    OUTPUT_PATH,
    analyze_model,
    canonical_scientific_json,
    frozen_center_whiten_split,
)


def _frame(ambient: int = 6, rank: int = 2) -> np.ndarray:
    values = np.zeros((ambient, rank), dtype=complex)
    values[:rank] = np.eye(rank)
    return values


def _synthetic_samples(*, shift: np.ndarray | None = None) -> tuple[ResponseFactors, ...]:
    rng = np.random.default_rng(2026081713)
    fluctuations = rng.normal(size=(24, 2, 6, 2)) + 1j * rng.normal(
        size=(24, 2, 6, 2)
    )
    offset = np.zeros((2, 6, 2), dtype=complex) if shift is None else shift
    return tuple(
        ResponseFactors(frame=_frame(), channels=fluctuations[index] + offset)
        for index in range(24)
    )


def test_output_and_checkpoints_are_additive_v13_paths() -> None:
    assert "paper1_prb_v13" in OUTPUT_PATH.parts
    assert "paper1_prb_v13" in MOORE_CHECKPOINT_ROOT.parts
    assert "moore_read_v9" not in MOORE_CHECKPOINT_ROOT.parts
    assert OUTPUT_PATH.name == "centered_complete_covariance_v13.json"


def test_frozen_centering_removes_an_arbitrary_nonzero_mean() -> None:
    rng = np.random.default_rng(71)
    shift = 3.0 * (
        rng.normal(size=(2, 6, 2)) + 1j * rng.normal(size=(2, 6, 2))
    )
    unshifted = frozen_center_whiten_split(
        _synthetic_samples(),
        tuple(range(12)),
        tuple(range(12, 24)),
        population_mean=np.zeros((2, 6, 2), dtype=complex),
        mean_provenance="synthetic_exact_zero",
    )
    shifted = frozen_center_whiten_split(
        _synthetic_samples(shift=shift),
        tuple(range(12)),
        tuple(range(12, 24)),
        population_mean=shift,
        mean_provenance="synthetic_exact_shift",
    )

    for left, right in zip(
        unshifted.inference_samples, shifted.inference_samples, strict=True
    ):
        assert np.allclose(left.channels, right.channels, atol=3e-13, rtol=3e-13)
    assert shifted.audit["population_mean_relative_rms"] > 0.8
    assert shifted.audit["centering_not_estimated_from_training_panels"] is True
    assert shifted.audit["training_whitened_gram_identity_error"] < 2e-12

    unshifted_result = analyze_model(
        _synthetic_samples(),
        model_id="unshifted",
        population_mean=np.zeros((2, 6, 2), dtype=complex),
        mean_provenance="synthetic_exact_zero",
    )
    shifted_result = analyze_model(
        _synthetic_samples(shift=shift),
        model_id="shifted",
        population_mean=shift,
        mean_provenance="synthetic_exact_shift",
    )
    corrected_unshifted = unshifted_result[
        "centered_whitened_complete_cumulant"
    ]["primary"]["summary"]
    corrected_shifted = shifted_result[
        "centered_whitened_complete_cumulant"
    ]["primary"]["summary"]
    assert corrected_shifted["directional_estimate"] == pytest.approx(
        corrected_unshifted["directional_estimate"], abs=3e-13, rel=3e-13
    )
    assert corrected_shifted["normalized_cumulant_norm"] == pytest.approx(
        corrected_unshifted["normalized_cumulant_norm"], abs=3e-13, rel=3e-13
    )
    raw_unshifted = unshifted_result["raw_v12_residual"]["summary"]
    raw_shifted = shifted_result["raw_v12_residual"]["summary"]
    assert abs(
        raw_shifted["directional_estimate"]
        - raw_unshifted["directional_estimate"]
    ) > 0.1


def test_training_channel_gram_is_identity_on_registered_support() -> None:
    split = frozen_center_whiten_split(
        _synthetic_samples(),
        tuple(range(12)),
        tuple(range(12, 24)),
        population_mean=np.zeros((2, 6, 2), dtype=complex),
        mean_provenance="synthetic_exact_zero",
    )

    assert split.audit["support_rank"] == 2
    assert split.audit["training_count"] == 12
    assert split.audit["inference_count"] == 12
    assert split.audit["training_whitened_gram_identity_error"] < 2e-12


def test_missing_or_ill_conditioned_support_fails_closed() -> None:
    samples = _synthetic_samples()
    singular = tuple(
        ResponseFactors(
            frame=sample.frame,
            channels=np.stack([sample.channels[0], sample.channels[0]]),
        )
        for sample in samples
    )

    with pytest.raises(RuntimeError, match="ill-conditioned channel support"):
        frozen_center_whiten_split(
            singular,
            tuple(range(12)),
            tuple(range(12, 24)),
            population_mean=np.zeros((2, 6, 2), dtype=complex),
            mean_provenance="synthetic_exact_zero",
        )
    with pytest.raises(RuntimeError, match="exactly 24 panels"):
        frozen_center_whiten_split(
            samples[:-1],
            tuple(range(12)),
            tuple(range(12, 23)),
            population_mean=np.zeros((2, 6, 2), dtype=complex),
            mean_provenance="synthetic_exact_zero",
        )

    with pytest.raises(RuntimeError, match="population mean provenance"):
        frozen_center_whiten_split(
            samples,
            tuple(range(12)),
            tuple(range(12, 24)),
            population_mean=np.zeros((2, 6, 2), dtype=complex),
            mean_provenance="",
        )


def test_primary_inference_uses_exactly_twelve_units_and_labels_cannot_alias() -> None:
    result = analyze_model(
        _synthetic_samples(),
        model_id="synthetic",
        population_mean=np.zeros((2, 6, 2), dtype=complex),
        mean_provenance="synthetic_exact_zero",
    )

    assert set(result) == {
        "model_id",
        "response_sign_provenance",
        "raw_v12_residual",
        "centered_whitened_complete_cumulant",
    }
    raw = result["raw_v12_residual"]
    corrected = result["centered_whitened_complete_cumulant"]
    assert raw["statistic"] == "uncentered_unwhitened_raw_moment_residual"
    assert corrected["statistic"] == "centered_whitened_complete_cumulant"
    assert raw["statistic"] != corrected["statistic"]
    assert corrected["primary"]["summary"]["realization_count"] == 12
    assert corrected["primary"]["claim_eligible"] is True
    assert corrected["primary"]["gate_for_claim"] is None
    assert "nominal_positive_directional_gate" in corrected["primary"]
    assert corrected["reverse_descriptive"]["claim_eligible"] is False
    assert corrected["reverse_descriptive"]["inferential_role"] == (
        "descriptive_replication_not_pooled"
    )


def test_scientific_payload_serialization_is_deterministic() -> None:
    first_result = analyze_model(
        _synthetic_samples(),
        model_id="synthetic",
        population_mean=np.zeros((2, 6, 2), dtype=complex),
        mean_provenance="synthetic_exact_zero",
    )
    second_result = analyze_model(
        _synthetic_samples(),
        model_id="synthetic",
        population_mean=np.zeros((2, 6, 2), dtype=complex),
        mean_provenance="synthetic_exact_zero",
    )

    first = canonical_scientific_json({"models": {"synthetic": first_result}})
    second = canonical_scientific_json({"models": {"synthetic": second_result}})

    assert first == second
    assert json.loads(first)["models"]["synthetic"]["model_id"] == "synthetic"


def test_canonical_output_uses_exact_population_means_and_familywise_gate() -> None:
    payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))

    assert payload["protocol"]["entrywise_mean"] == (
        "exact_registered_finite_ensemble_population_mean"
    )
    assert payload["protocol"]["primary_case_family_size"] == 5
    assert payload["protocol"]["familywise_method"] == "Bonferroni"
    assert payload["protocol"]["finite_sample_reference"] == "Student_t"
    assert payload["protocol"]["student_t_degrees_of_freedom"] == 11
    assert payload["protocol"]["family_alpha"] == pytest.approx(0.05)
    assert payload["protocol"]["per_case_alpha"] == pytest.approx(0.01)
    assert payload["corrected_primary_positive_directional_gate"] == {
        "lattice_susy_m1": False,
        "lattice_susy_m2": False,
        "lattice_susy_m3": False,
        "moore_read_N4": False,
        "moore_read_N6": True,
    }
    for model in payload["models"].values():
        primary = model["centered_whitened_complete_cumulant"]["primary"]
        audit = primary["transform_audit"]
        assert audit["population_mean_exact_for_registered_finite_ensemble"] is True
        assert audit["centering_not_estimated_from_training_panels"] is True
        assert primary["familywise_method"] == (
            "Bonferroni_over_registered_primary_cases_with_Student_t11"
        )
        assert primary["student_t_degrees_of_freedom"] == 11
    assert payload["models"]["moore_read_N6"][
        "centered_whitened_complete_cumulant"
    ]["primary"]["familywise_one_sided_interval_low"] > 0.0
