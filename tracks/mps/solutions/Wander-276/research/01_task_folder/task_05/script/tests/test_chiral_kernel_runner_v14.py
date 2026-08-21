"""Prospective sealing and execution contracts for chiral kernels."""

from __future__ import annotations

import hashlib
import json
import stat
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from run_chiral_kernel_geometric_eth_v14 import (
    BASES_PER_SIZE,
    BRANCH_PRECEDENCE,
    CLASS_SEEDS,
    DEVELOPMENT_SIZES,
    TANGENT_CLASSES,
    TANGENTS_PER_BASE,
    VALIDATION_SIZES,
    _complete_standardized_fourth_cumulant,
    run_sealed_validation,
    validate_prediction_seal,
)
from seal_chiral_kernel_prediction_v14 import seal_prediction


REPO = Path(__file__).resolve().parents[4]


def test_complete_fourth_cumulant_proper_complex_gaussian_oracle() -> None:
    rng = np.random.default_rng(14_004_101)
    sample = (
        rng.standard_normal(500_000) + 1j * rng.standard_normal(500_000)
    ) / 2.0**0.5

    cumulant, variance, normalized_pseudocovariance = (
        _complete_standardized_fourth_cumulant(sample)
    )

    assert variance == pytest.approx(1.0, abs=8e-3)
    assert normalized_pseudocovariance < 8e-3
    assert cumulant == pytest.approx(0.0, abs=3e-2)


def test_complete_fourth_cumulant_improper_real_gaussian_oracle() -> None:
    rng = np.random.default_rng(14_004_201)
    sample = rng.standard_normal(500_000).astype(complex)

    cumulant, variance, normalized_pseudocovariance = (
        _complete_standardized_fourth_cumulant(sample)
    )
    centered = sample - sample.mean()
    legacy_proper_only = float(
        np.mean(abs(centered) ** 4) / (2.0 * variance**2) - 1.0
    )

    assert variance == pytest.approx(1.0, abs=8e-3)
    assert normalized_pseudocovariance == pytest.approx(1.0, abs=1e-12)
    assert cumulant == pytest.approx(0.0, abs=4e-2)
    assert legacy_proper_only > 0.45


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _channel_theory_fixture(path: Path) -> None:
    theory_source = (
        REPO
        / "01_task_folder/task_05/script/lgeth/geometric_eth_channel_theory.py"
    )
    payload = {
        "version": "v14",
        "schema": "geometric_eth_channel_theory_v14",
        "registered_channel_counts": [4, 8, 16, 32, 64],
        "maximum_relative_error": 0.04,
        "checks": {
            "exact_cumulant_additivity": True,
            "monte_carlo_relative_error": True,
            "scalar_commutant_audit": True,
        },
        "all_checks_pass": True,
        "source_hashes": {
            str(theory_source.relative_to(REPO)): _sha256(theory_source)
        },
    }
    unsigned = deepcopy(payload)
    encoded = (
        json.dumps(unsigned, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()
    payload["scientific_payload_sha256"] = hashlib.sha256(encoded).hexdigest()
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _sealed_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    theory = tmp_path / "channel_theory_v14.json"
    prediction = tmp_path / "chiral_prediction_v14.json"
    sidecar = tmp_path / "chiral_prediction_v14.sha256"
    outcomes = tmp_path / "chiral_outcomes_v14.json"
    _channel_theory_fixture(theory)
    seal_prediction(
        repo_root=REPO,
        channel_theory_path=theory,
        prediction_path=prediction,
        sidecar_path=sidecar,
        outcomes_path=outcomes,
        development_sizes=((4, 6), (6, 9)),
        development_base_count=3,
        tangent_count=4,
        strict_grid=False,
        sealed_utc="2026-08-21T03:00:00+00:00",
    )
    return prediction, sidecar, outcomes


def test_registered_grid_and_seed_isolation_are_frozen() -> None:
    assert DEVELOPMENT_SIZES == ((16, 24), (24, 36), (32, 48))
    assert VALIDATION_SIZES == ((48, 72), (64, 96), (96, 144))
    assert BASES_PER_SIZE == 64
    assert TANGENTS_PER_BASE == 16
    assert TANGENT_CLASSES == ("random", "local", "structured")
    assert BRANCH_PRECEDENCE == (
        "feasibility_failure",
        "random_channel_failure",
        "deformed_locality_class",
        "channel_law_validated",
    )
    all_seeds = [
        CLASS_SEEDS[kind][stream]
        for kind in TANGENT_CLASSES
        for stream in ("base", "tangent")
    ]
    assert len(all_seeds) == len(set(all_seeds))


def test_prediction_is_sealed_without_validation_outcome_leakage(
    tmp_path: Path,
) -> None:
    prediction_path, sidecar, _ = _sealed_fixture(tmp_path)
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    serialized = json.dumps(prediction, sort_keys=True).lower()

    assert prediction["registered_grid"]["development_sizes"] == [
        [16, 24],
        [24, 36],
        [32, 48],
    ]
    assert prediction["registered_grid"]["validation_sizes"] == [
        [48, 72],
        [64, 96],
        [96, 144],
    ]
    assert prediction["registered_grid"]["bases_per_size"] == 64
    assert prediction["registered_grid"]["tangents_per_base"] == 16
    assert prediction["branch_precedence"] == list(BRANCH_PRECEDENCE)
    primary = prediction["primary_prediction"]
    assert primary["statistic"] == (
        "N_eff_times_covariance_whitened_complete_standardized_fourth_cumulant"
    )
    assert primary["no_validation_refit_of_development_band_or_thresholds"] is True
    assert "at each base" in primary["observable_side_self_normalization"]
    assert "64 base means" in primary["estimator"]
    assert "all three" in primary["decision"]
    assert primary["bootstrap_intervals_are_reporting_only"] is True
    assert primary["bootstrap_intervals_do_not_expand_primary_band"] is True
    analysis = prediction["registered_analysis"]
    bootstrap = analysis["base_bootstrap"]
    assert bootstrap["master_seed"] == 20260821
    assert bootstrap["replicates"] == 10_000
    assert bootstrap["family_alpha"] == 0.05
    assert bootstrap["draws_per_replicate"] == 64
    assert bootstrap["lower_quantile"] == pytest.approx(0.05 / 6.0)
    assert bootstrap["upper_quantile"] == pytest.approx(1.0 - 0.05 / 6.0)
    assert bootstrap["class_order"] == list(TANGENT_CLASSES)
    assert bootstrap["size_order"] == [
        [48, 72],
        [64, 96],
        [96, 144],
    ]
    control = analysis["structured_control_separation"]
    assert control["eligible_classes"] == ["local", "structured"]
    assert control["minimum_disjoint_sizes"] == 2
    assert control["must_include_size"] == [96, 144]
    assert control["required_for_title_gate"] is True
    assert "interval_upper < band_lower" in control["strict_disjointness"]
    branches = analysis["branch_rules"]
    assert set(branches) == {
        "feasibility_failure",
        "random_channel_failure",
        "deformed_locality_class",
        "channel_law_validated",
    }
    assert prediction["source_hashes"]
    assert "observed_fourth_cumulant" not in serialized
    assert "validation_outcomes" not in serialized
    assert "selected_branch" not in serialized
    assert sidecar.read_text(encoding="utf-8").strip() == _sha256(prediction_path)
    assert stat.S_IMODE(prediction_path.stat().st_mode) == 0o644
    assert stat.S_IMODE(sidecar.stat().st_mode) == 0o644


def test_seal_refuses_when_outcome_file_already_exists(tmp_path: Path) -> None:
    theory = tmp_path / "channel_theory_v14.json"
    prediction = tmp_path / "chiral_prediction_v14.json"
    sidecar = tmp_path / "chiral_prediction_v14.sha256"
    outcomes = tmp_path / "chiral_outcomes_v14.json"
    _channel_theory_fixture(theory)
    outcomes.write_text('{"leak": true}\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match="outcome leakage"):
        seal_prediction(
            repo_root=REPO,
            channel_theory_path=theory,
            prediction_path=prediction,
            sidecar_path=sidecar,
            outcomes_path=outcomes,
            development_sizes=((4, 6),),
            development_base_count=2,
            tangent_count=3,
            strict_grid=False,
        )


def test_runner_refuses_changed_prediction_hash(tmp_path: Path) -> None:
    prediction, sidecar, _ = _sealed_fixture(tmp_path)
    payload = json.loads(prediction.read_text(encoding="utf-8"))
    payload["primary_prediction"]["simultaneous_band"]["upper"] += 0.1
    prediction.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="prediction SHA-256"):
        validate_prediction_seal(
            repo_root=REPO,
            prediction_path=prediction,
            sidecar_path=sidecar,
        )


def test_runner_refuses_changed_registered_source_hash(tmp_path: Path) -> None:
    prediction, sidecar, _ = _sealed_fixture(tmp_path)
    payload = json.loads(prediction.read_text(encoding="utf-8"))
    first = next(iter(payload["source_hashes"]))
    payload["source_hashes"][first] = "0" * 64
    unsigned = deepcopy(payload)
    unsigned.pop("scientific_payload_sha256")
    payload["scientific_payload_sha256"] = hashlib.sha256(
        (json.dumps(unsigned, indent=2, sort_keys=True) + "\n").encode()
    ).hexdigest()
    prediction.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sidecar.write_text(_sha256(prediction) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="registered source hash"):
        validate_prediction_seal(
            repo_root=REPO,
            prediction_path=prediction,
            sidecar_path=sidecar,
        )


def test_small_sealed_validation_is_deterministic_and_exact(tmp_path: Path) -> None:
    prediction, sidecar, outcomes = _sealed_fixture(tmp_path)
    first = run_sealed_validation(
        repo_root=REPO,
        prediction_path=prediction,
        sidecar_path=sidecar,
        output_path=outcomes,
        validation_sizes=((6, 9),),
        base_count=2,
        tangent_count=3,
        strict_grid=False,
        generated_utc="2026-08-21T04:00:00+00:00",
    )
    outcomes.unlink()
    second = run_sealed_validation(
        repo_root=REPO,
        prediction_path=prediction,
        sidecar_path=sidecar,
        output_path=outcomes,
        validation_sizes=((6, 9),),
        base_count=2,
        tangent_count=3,
        strict_grid=False,
        generated_utc="2026-08-21T04:00:00+00:00",
    )

    assert first == second
    assert first["prediction_sha256"] == _sha256(prediction)
    assert first["execution"]["mode"] == "test_fixture"
    assert first["checks"]["all_exact_index_gates_pass"] is True
    assert first["checks"]["class_seed_streams_disjoint"] is True
    assert first["checks"]["same_channel_count_all_classes"] is True
    assert first["all_checks_pass"] is True
    case = first["cases"]["n_b6_n_a9"]
    assert set(case["classes"]) == set(TANGENT_CLASSES)
    for record in case["classes"].values():
        assert len(record["safe_covariates"]) == 2
        assert len(record["outcome_tensors"]["effective_channel_number"]) == 2
        tensors = record["outcome_tensors"]
        assert all(
            len(row) == 3
            for row in tensors["complete_standardized_fourth_cumulant"]
        )
        assert all(len(row) == 3 for row in tensors["observable_variance"])
        assert all(
            len(row) == 3
            for row in tensors["normalized_pseudocovariance_magnitude"]
        )
        assert all(
            value > 0.0
            for row in tensors["observable_variance"]
            for value in row
        )
        assert all(
            0.0 <= value <= 1.0 + 1e-12
            for row in tensors["normalized_pseudocovariance_magnitude"]
            for value in row
        )
        assert all(
            safe["channel_whitening"]["rank"] == 3
            and safe["channel_whitening"]["identity_error"] < 1e-9
            for safe in record["safe_covariates"]
        )
    assert stat.S_IMODE(outcomes.stat().st_mode) == 0o644


def test_production_runner_rejects_reduced_grid(tmp_path: Path) -> None:
    prediction, sidecar, outcomes = _sealed_fixture(tmp_path)

    with pytest.raises(ValueError, match="sealed validation grid"):
        run_sealed_validation(
            repo_root=REPO,
            prediction_path=prediction,
            sidecar_path=sidecar,
            output_path=outcomes,
            validation_sizes=((6, 9),),
            base_count=2,
            tangent_count=3,
            strict_grid=True,
        )


def test_runner_rejects_outcome_timestamp_before_seal(tmp_path: Path) -> None:
    prediction, sidecar, outcomes = _sealed_fixture(tmp_path)

    with pytest.raises(RuntimeError, match="later than the prediction seal"):
        run_sealed_validation(
            repo_root=REPO,
            prediction_path=prediction,
            sidecar_path=sidecar,
            output_path=outcomes,
            validation_sizes=((6, 9),),
            base_count=2,
            tangent_count=3,
            strict_grid=False,
            generated_utc="2026-08-21T02:59:59+00:00",
        )
