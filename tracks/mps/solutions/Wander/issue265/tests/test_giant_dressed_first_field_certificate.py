import json
from pathlib import Path

from scripts.certify_giant_dressed_first_field import derive


ROOT = Path(__file__).resolve().parents[1]


def test_giant_dressed_first_field_certificate_is_reproducible() -> None:
    stored = json.loads(
        (ROOT / "docs/giant_dressed_first_field_certificate.json").read_text()
    )
    regenerated = derive()
    assert regenerated == stored
    gates = stored["gates"]
    assert gates["outer_dressed_kernel_complete"] is True
    assert gates["leading_residual_below_2e-8"] is True
    assert gates["first_order_spread_below_2e-3"] is True
    assert gates["full_diagonal_integrand_complete"] is False
    assert gates["fixed_string_inner_match_complete"] is False
    assert gates["physical_D1_certified"] is False
