from __future__ import annotations

import json
from pathlib import Path

import jsonschema

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_D_PLUS_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_phase6c_symmetry_schema_pins_all_continuous_gates() -> None:
    schema = json.loads(
        (ROUTE_D_PLUS_ROOT / "symmetry.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    gates = schema["properties"]["gates"]["properties"]
    assert set(gates) == {
        "lll_homogeneity",
        "exchange",
        "scalarity",
        "ladder",
        "finite_rotation",
    }
    assert all(value["const"] is True for value in gates.values())
    assert (
        schema["properties"]["rotation_convention"]["const"]
        == "Phi_2(RX)=D2(R)@Phi_2(X)"
    )


def test_phase6c_verifier_recomputes_checkpoint_symmetry() -> None:
    source = (ROUTE_D_PLUS_ROOT / "symmetry.py").read_text(
        encoding="utf-8"
    )
    assert "ground_raw_channels(configuration)" in source
    assert "tower_raw_channels(configuration)" in source
    assert "scale**TWO_Q" in source
    assert "rotation_matrix(4, rotation_vector) @ tower_value" in source
    assert "_ladder_error()" in source
