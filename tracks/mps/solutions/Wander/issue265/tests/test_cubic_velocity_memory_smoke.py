from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cubic_velocity_smoke_is_positive_and_fail_closed() -> None:
    payload = json.loads(
        (ROOT / "docs/cubic_velocity_memory_h025_1string_smoke.json").read_text()
    )
    assert payload["uses_target_trajectory"] is False
    assert payload["uses_target_a_or_D"] is False
    assert payload["operator"]["dimension"] == 16
    assert payload["scope"]["first_nonzero_cubic_velocity_memory_W2_evaluated"] is True
    assert payload["scope"]["wrapped_cubic_aliases_removed"] is True
    assert payload["scope"]["fixed_fourier_spacing_has_fixed_spatial_cell_length"] is True
    assert payload["scope"]["full_string_zero_field_limit_complete"] is False
    assert payload["scope"]["microscopic_mori_uv_matching_complete"] is False
    assert payload["scope"]["physical_F1_perp_claimed"] is False
    lengths = [row["spatial_cell_length"] for row in payload["rows"]]
    assert max(lengths) - min(lengths) < 1.0e-12
    assert all(row["zero_time_nonnegative"] for row in payload["rows"])
    assert all(row["integral_to_maximum_time"] > 0.0 for row in payload["rows"])
