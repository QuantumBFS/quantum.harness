import pytest
import hashlib
import json
from types import MappingProxyType

from analysis.data_io import LoadedRun
from analysis.entanglement import fit_entropy_arc
from analysis.phase import (
    PhaseEvidence,
    classify_angle,
    locate_bracket,
    select_candidate,
    write_refinement_request,
)
from test_entanglement import arc_points


MODELS = ("constant", "log", "log2", "log_log2", "page_log_log2")


def evidence(phi_pi: float, kind: str):
    fits = {
        width: fit_entropy_arc(arc_points(kind), MODELS)
        for width in (8, 12, 16)
    }
    return classify_angle(phi_pi, fits)


def test_phase_evidence_requires_three_persistent_widths():
    assert evidence(0.18, "constant").phase == "insulator"
    assert evidence(0.22, "log_log2").phase == "metal"
    two_widths = {
        width: fit_entropy_arc(arc_points("constant"), MODELS)
        for width in (8, 12)
    }
    assert classify_angle(0.1, two_widths).phase == "inconclusive"


def test_bracket_requires_opposite_phase_evidence():
    bracket = locate_bracket(
        [evidence(0.18, "insulator" if False else "constant"), evidence(0.22, "log_log2")]
    )
    assert bracket.lower_phi_pi == pytest.approx(0.18)
    assert bracket.upper_phi_pi == pytest.approx(0.22)

    with pytest.raises(ValueError, match="phase change"):
        locate_bracket([evidence(0.18, "constant"), evidence(0.22, "constant")])


def test_refinement_request_is_atomically_written_and_hashed(tmp_path):
    manifest = {"schema_version": 1, "artifact_sha256": {}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    loaded = LoadedRun(
        run_dir=tmp_path,
        manifest=MappingProxyType(manifest),
        streams=MappingProxyType({}),
    )

    request_path = write_refinement_request(loaded, {})
    payload = request_path.read_bytes()
    updated = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert json.loads(payload)["status"] == "inconclusive"
    assert updated["artifact_sha256"]["processed/refinement_request.json"] == (
        hashlib.sha256(payload).hexdigest()
    )


def test_refinement_resume_preserves_the_stage_already_frozen_in_manifest(tmp_path):
    refinement = {
        "name": "diii-refine",
        "theta_pi": 0.45,
        "phi_pi": [0.30, 0.31, 0.32],
        "widths": [8, 12, 16, 20, 24, 28, 32],
        "streams": 8,
        "burn_in_layers_per_width": 16,
        "measurement_layers_per_width": 96,
        "block_layers_per_width": 8,
    }
    manifest = {
        "schema_version": 1,
        "config": {"stages": [{"name": "diii-locator"}, refinement]},
        "artifact_sha256": {},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    processed = tmp_path / "processed"
    processed.mkdir()
    (processed / "refinement_request.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "exploratory",
                "stage": "diii-refine",
                "theta_pi": 0.45,
                "phi_pi": [0.28, 0.29, 0.30],
                "widths": [8, 12, 16, 20, 24, 28, 32],
                "streams": 8,
                "burn_in_layers_per_width": 16,
                "measurement_layers_per_width": 96,
                "block_layers_per_width": 8,
            }
        ),
        encoding="utf-8",
    )
    loaded = LoadedRun(
        run_dir=tmp_path,
        manifest=MappingProxyType(manifest),
        streams=MappingProxyType({}),
    )

    request_path = write_refinement_request(loaded, {})
    request = json.loads(request_path.read_text(encoding="utf-8"))

    assert request["status"] == "exploratory"
    assert request["phi_pi"] == [0.30, 0.31, 0.32]
    assert request["widths"] == refinement["widths"]


def test_candidate_selection_prefers_a_strict_bracket_and_lower_tie_angle():
    selection = select_candidate(
        [
            PhaseEvidence(0.18, "insulator", (8, 12, 16), 0.8),
            PhaseEvidence(0.22, "metal", (8, 12, 16), 0.9),
        ]
    )
    assert selection.status == "bracketed"
    assert selection.lower_phi_pi == pytest.approx(0.18)
    assert selection.upper_phi_pi == pytest.approx(0.22)
    assert selection.candidate_phi_pi == pytest.approx(0.18)
    assert selection.reasons == ()


def test_candidate_selection_falls_back_to_largest_score_change_deterministically():
    selection = select_candidate(
        [
            PhaseEvidence(0.16, "inconclusive", (8, 12, 16), 0.10),
            PhaseEvidence(0.18, "inconclusive", (8, 12, 16), 0.15),
            PhaseEvidence(0.20, "inconclusive", (8, 12, 16), 0.55),
            PhaseEvidence(0.22, "inconclusive", (8, 12, 16), 0.60),
        ]
    )
    assert selection.status == "exploratory"
    assert (selection.lower_phi_pi, selection.upper_phi_pi) == pytest.approx((0.18, 0.20))
    assert selection.candidate_phi_pi == pytest.approx(0.18)
    assert selection.reasons == ("diii_transition_not_bracketed",)

    tie = select_candidate(
        [
            PhaseEvidence(0.16, "inconclusive", (8, 12, 16), 0.10),
            PhaseEvidence(0.18, "inconclusive", (8, 12, 16), 0.30),
            PhaseEvidence(0.20, "inconclusive", (8, 12, 16), 0.10),
        ]
    )
    assert (tie.lower_phi_pi, tie.upper_phi_pi) == pytest.approx((0.16, 0.18))
