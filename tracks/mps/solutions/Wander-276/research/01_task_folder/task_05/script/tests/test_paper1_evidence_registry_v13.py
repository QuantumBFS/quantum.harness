from __future__ import annotations

import json
import math
import shutil
import stat
import sys
from copy import deepcopy
from pathlib import Path

import pytest

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from build_paper1_evidence_registry_v13 import (
    OPTIONAL_SOURCE_PATHS,
    REQUIRED_SOURCE_PATHS,
    SOURCE_PATHS,
    build_registry,
    write_registry_atomic,
)
from make_paper1_prb_assets_v13 import (
    render_evidence_matrix,
    render_model_table,
    render_results,
)


REPO = Path(__file__).resolve().parents[4]


def _copy_sources(destination: Path, source_root: Path = REPO) -> None:
    for relative_path in REQUIRED_SOURCE_PATHS.values():
        source = source_root / relative_path
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def test_registry_keeps_missing_cells_explicit() -> None:
    payload = build_registry(REPO)

    assert set(payload) == {
        "sources",
        "models",
        "observables",
        "gates",
        "claims",
        "source_hashes",
    }
    assert payload["models"]["laughlin"]["centered_complete_covariance_v13"] is False
    assert payload["models"]["susy_syk"]["centered_complete_covariance_v13"] is False
    assert payload["models"]["moore_read"]["production_complete"] is False
    assert payload["models"]["lattice_susy"]["production_complete"] is False
    assert payload["models"]["xcube"]["role"] == "exact_structured_control"
    assert payload["claims"]["asymptotic_geometric_eth"] is False
    assert payload["claims"]["universal_geometric_eth"] is False
    assert payload["claims"]["thermalization"] is False
    assert payload["claims"]["lyapunov_behavior"] is False
    assert len(payload["source_hashes"]) == 11
    assert all(len(value) == 64 for value in payload["source_hashes"].values())
    historical = payload["sources"]["protected_scaling_inference_v4"]
    assert historical["available"] is False
    assert historical["reason"] == "not_tracked_in_delivery_branch"
    assert "sha256" not in historical
    assert payload["observables"]["protected_fourth_moment"] == {
        "available": False,
        "reason": "not_tracked_in_delivery_branch",
    }
    centered_source = payload["sources"]["centered_complete_covariance_v13"]
    assert centered_source["available"] is True
    assert centered_source["checks_pass"] is True


def test_registry_separates_raw_v12_from_centered_full_r4_v13() -> None:
    payload = build_registry(REPO)
    raw = payload["observables"]["raw_uncentered_moment_residual_v12"]
    full = payload["observables"]["centered_whitened_full_r4_v13"]

    assert raw["statistic"] == "raw_uncentered_moment_residual"
    assert raw["claim_eligible"] is False
    assert raw["raw_v12_recomputed_numerically_consistent"] is True
    assert raw["protocol"]["realization_count"] == 24
    assert set(raw["cases"]) == {
        "moore_read_N4",
        "moore_read_N6",
        "lattice_susy_m1",
        "lattice_susy_m2",
        "lattice_susy_m3",
    }
    assert full["statistic"] == "centered_whitened_complete_cumulant"
    assert full["notation"] == "R4^{full}"
    assert full["source_observed_primary_gate_by_case"] == {
        "lattice_susy_m1": False,
        "lattice_susy_m2": False,
        "lattice_susy_m3": False,
        "moore_read_N4": False,
        "moore_read_N6": True,
    }
    assert full["claim_eligible"] is True
    assert full["claim_gate_by_case"] == full[
        "source_observed_primary_gate_by_case"
    ]
    assert full["inference_status"] == "finite_rank_exact_population_mean_familywise"
    assert all(
        case["primary"]["summary"]["realization_count"] == 12
        for case in full["cases"].values()
    )
    assert all(
        case["primary"]["claim_eligible"] is True
        for case in full["cases"].values()
    )
    assert full["cases"]["moore_read_N6"]["primary"][
        "source_observed_gate"
    ] is True
    assert all(
        case["reverse_descriptive"]["claim_eligible"] is False
        and case["reverse_descriptive"]["gate_for_claim"] is None
        for case in full["cases"].values()
    )
    for model in payload["models"].values():
        assert "complete_covariance_gate" not in model
        assert "complete_covariance_v12" not in model


def test_registry_records_response_minus_sign_provenance_and_claim_scope() -> None:
    payload = build_registry(REPO)
    response = payload["observables"]["centered_whitened_full_r4_v13"][
        "response_sign_provenance"
    ]

    assert response["stored_channel_interpretation"] == (
        "stored_channels=-X_a_when_source_omits_Kato_minus"
    )
    assert response["even_contractions_invariant_under_global_channel_sign"] is True
    assert payload["claims"]["centered_full_r4_positive_only_moore_read_N6"] is True
    assert payload["claims"]["centered_full_r4_positive_claim"] is True
    assert payload["claims"]["centered_full_r4_population_mean_audit_complete"] is True
    assert payload["claims"]["centered_full_r4_moore_read_N4"] is False
    assert payload["claims"]["centered_full_r4_lattice_susy_m1_m2_m3"] is False
    assert payload["claims"]["strongest_statistical_scope"] == (
        "finite_rank_domain_limited_moore_read_N6_only"
    )
    assert payload["claims"]["asymptotic_geometric_eth"] is False
    assert payload["claims"]["universal_geometric_eth"] is False


def test_registry_fails_closed_when_a_required_source_is_missing(tmp_path: Path) -> None:
    _copy_sources(tmp_path)
    (tmp_path / REQUIRED_SOURCE_PATHS["spectral_silence_v2"]).unlink()

    with pytest.raises(RuntimeError, match="missing required evidence source"):
        build_registry(tmp_path)


def test_centered_v13_is_required_and_its_payload_hash_is_verified(
    tmp_path: Path,
) -> None:
    _copy_sources(tmp_path)
    centered = tmp_path / REQUIRED_SOURCE_PATHS["centered_complete_covariance_v13"]
    centered.unlink()
    with pytest.raises(RuntimeError, match="missing required evidence source"):
        build_registry(tmp_path)

    _copy_sources(tmp_path)
    payload = json.loads(centered.read_text(encoding="utf-8"))
    payload["corrected_primary_positive_directional_gate"]["moore_read_N4"] = True
    centered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="scientific payload hash"):
        build_registry(tmp_path)


def test_registry_rejects_false_source_check(tmp_path: Path) -> None:
    _copy_sources(tmp_path)
    source = tmp_path / REQUIRED_SOURCE_PATHS["spectral_silence_v2"]
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["all_checks_pass"] = False
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="failed its registered checks"):
        build_registry(tmp_path)


def test_registry_rejects_contradictory_production_flags(tmp_path: Path) -> None:
    _copy_sources(tmp_path)
    source = tmp_path / REQUIRED_SOURCE_PATHS["cross_mechanism_geometric_eth_v12"]
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["models"]["moore_read"]["production_complete"] = True
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="contradictory production flag"):
        build_registry(tmp_path)


def test_registry_rejects_absent_claim_boundary(tmp_path: Path) -> None:
    _copy_sources(tmp_path)
    source = tmp_path / REQUIRED_SOURCE_PATHS["cross_mechanism_geometric_eth_v12"]
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload.pop("not_established")
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="missing required keys.*not_established"):
        build_registry(tmp_path)


def test_atomic_writer_round_trips_registry(tmp_path: Path) -> None:
    payload = build_registry(REPO)
    destination = tmp_path / "nested" / "registry.json"

    write_registry_atomic(payload, destination)

    assert json.loads(destination.read_text(encoding="utf-8")) == payload
    assert stat.S_IMODE(destination.stat().st_mode) == 0o644
    assert not list(destination.parent.glob(f".{destination.name}.*.tmp"))


def test_checked_in_registry_matches_builder() -> None:
    generated = (
        REPO
        / "01_task_folder/task_05/script/output/paper1_prb_v13/evidence_registry_v13.json"
    )

    assert json.loads(generated.read_text(encoding="utf-8")) == build_registry(REPO)


def test_optional_historical_source_is_never_read_outside_repo(tmp_path: Path) -> None:
    _copy_sources(tmp_path)
    optional = tmp_path / OPTIONAL_SOURCE_PATHS["protected_scaling_inference_v4"]
    assert not optional.exists()

    payload = build_registry(tmp_path)

    assert payload["sources"]["protected_scaling_inference_v4"]["available"] is False
    assert "protected_scaling_inference_v4" not in payload["source_hashes"]


def test_latex_asset_rendering_is_deterministic_and_registry_derived() -> None:
    payload = build_registry(REPO)
    first = (
        render_results(payload),
        render_evidence_matrix(payload),
        render_model_table(payload),
    )
    second = (
        render_results(payload),
        render_evidence_matrix(payload),
        render_model_table(payload),
    )

    assert first == second
    assert r"\newcommand{\MooreReadNFourRank}{42}" in first[0]
    assert r"\newcommand{\MooreReadNSixRank}{120}" in first[0]
    assert r"\newcommand{\LatticeSusyMOneRank}{2}" in first[0]
    assert r"\newcommand{\LatticeSusyMTwoRank}{4}" in first[0]
    assert r"\newcommand{\LatticeSusyMThreeRank}{8}" in first[0]
    assert r"\newcommand{\MooreReadNFourFullRFourClaimStatus}{\text{not passed}}" in first[0]
    assert r"\newcommand{\MooreReadNSixFullRFourClaimStatus}{\text{passed}}" in first[0]
    assert r"\newcommand{\LatticeSusyMThreeFullRFourClaimStatus}{\text{not passed}}" in first[0]
    assert r"\newcommand{\MooreReadNSixFullRFourFamilywiseLower}{0.039160542}" in first[0]
    assert r"\newcommand{\FullRFourStudentTDegreesOfFreedom}{11}" in first[0]
    assert "RawMomentResidualEstimate" in first[0]
    assert "FullRFourDirectionalEstimate" in first[0]
    assert "TwoPairRFour" in first[0]
    assert "CovarianceEstimate" not in first[0]
    assert r"\newcommand{\StoredResponseChannelConvention}{\(\widetilde X_a=-X_a\)" in first[0]
    assert r"\newcommand{\EvenResponseContractionsSignInvariant}{\text{yes}}" in first[0]
    assert all("% source " in rendered for rendered in first)


def test_model_table_has_explicit_ensemble_and_production_cells() -> None:
    table = render_model_table(build_registry(REPO))
    rows = [line for line in table.splitlines() if "% MODELROW:" in line]

    assert len(rows) == 5
    for row in rows:
        assert "independent-ensemble=" in row
        assert "production=" in row
    assert r"three-body clustered FQH parent" in table
    assert r"\text{not tested}" in table
    assert r"42, 120" in table
    assert r"2, 4, 8" in table
    assert r"\(R_4^{\mathrm{full}}\), primary split" in table
    assert "N=4: not passed; N=6: passed (finite-rank)" in table
    assert "complete-covariance=" not in table


def test_lattice_susy_gate_language_does_not_imply_a_null_result() -> None:
    matrix = render_evidence_matrix(build_registry(REPO))

    assert "positive-direction gate not passed" in matrix
    assert "pilot null direction" not in matrix
    assert "this is not a Gaussianity claim" in matrix
    assert "raw, uncentered moment residual" in matrix
    assert "claim-ineligible" in matrix
    assert "N=4 gate does not pass and N=6 gate passes" in matrix
    assert "finite-rank N=6-only result" in matrix
    assert "reverse split is descriptive only" in matrix
    assert "does not provide asymptotic or universal evidence" in matrix
    assert "restricted to the registered finite-rank N=6 calculation" in matrix


def test_generated_latex_assets_match_renderers_and_have_no_forbidden_tokens() -> None:
    payload = build_registry(REPO)
    generated = REPO / "overleaf_sync/exactly_degenerate_quantum_chaos_prb/generated"
    expected = {
        "results_v13.tex": render_results(payload),
        "evidence_matrix_v13.tex": render_evidence_matrix(payload),
        "model_table_v13.tex": render_model_table(payload),
    }

    for filename, rendered in expected.items():
        path = generated / filename
        assert path.read_text(encoding="utf-8") == rendered
        assert stat.S_IMODE(path.stat().st_mode) == 0o644
        lowered = rendered.lower()
        assert "nan" not in lowered
        assert "unresolved-placeholder" not in lowered
        assert "inferred universal" not in lowered


def test_renderer_rejects_nonfinite_data_and_positive_forbidden_claims() -> None:
    payload = build_registry(REPO)
    with_nan = deepcopy(payload)
    with_nan["models"]["moore_read"]["cases"][0]["external_gap"] = math.nan
    with_forbidden_claim = deepcopy(payload)
    with_forbidden_claim["claims"]["asymptotic_geometric_eth"] = True

    with pytest.raises(RuntimeError, match="non-finite"):
        render_results(with_nan)
    with pytest.raises(RuntimeError, match="forbidden positive claim"):
        render_evidence_matrix(with_forbidden_claim)
