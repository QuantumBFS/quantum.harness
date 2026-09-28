from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_local_counterterm_audit_rejects_frequency_selective_stability() -> None:
    payload = json.loads(
        (ROOT / "docs/mori_uv_local_counterterm_audit.json").read_text()
    )
    assert payload["uses_target_trajectory"] is False
    assert payload["uses_target_a_or_D"] is False
    assert len(payload["cutoffs"]) == 5
    assert [row["fourier_points"] for row in payload["cutoffs"]] == [8, 12, 16, 20, 24]
    # Quadratic subtraction happens to stabilize z=.2, but not z=.1.  The
    # fail-closed gate must not cherry-pick that single frequency.
    quadratic = payload["orders"][2]
    assert quadratic["probes"][1]["cutoff_stability_pass"] is True
    assert quadratic["probes"][0]["cutoff_stability_pass"] is False
    assert quadratic["all_probe_frequencies_stable"] is False
    assert payload["gates"]["some_single_local_order_stabilizes_all_probes"] is False
    assert payload["gates"]["finite_local_counterterm_uv_matching_complete"] is False
    assert payload["gates"]["physical_F1_perp_certified"] is False
