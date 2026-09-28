import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_iterated_full_diffusion_audit_fails_closed_at_boundary_counterterm():
    payload = json.loads(
        (ROOT / "docs/iterated_full_diffusion_limit_audit.json").read_text()
    )
    assert len(payload["outer_rows"]) == 3
    assert len(payload["finite_field_rows"]) == 3
    gates = payload["gates"]
    assert gates["fixed_finite_string_weight_vanishes_quadratically"] is True
    assert gates["cross_is_subleading_Oh_in_tested_iterated_sequence"] is False
    assert gates["diagonal_reduction_is_a_proved_identity"] is False
    assert gates["supplement_eq16_eligible_for_D1_extraction"] is False
    assert gates["uniform_u_outer_certificate_superseded"] is True
    assert gates["u_over_xi_boundary_layer_resolved"] is True
    assert gates["regulated_xi_boundary_counterterm_derived"] is False
    assert gates["constant_D1_existence_certified"] is False
    assert gates["physical_D1_certified"] is False
