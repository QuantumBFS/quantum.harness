import pytest
import hashlib
import json
from types import MappingProxyType

from analysis.data_io import LoadedRun
from analysis.entanglement import fit_entropy_arc
from analysis.phase import classify_angle, locate_bracket, write_refinement_request
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
