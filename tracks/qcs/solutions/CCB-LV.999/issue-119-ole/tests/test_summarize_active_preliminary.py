import importlib.util
from pathlib import Path
import sys

import pytest


OLE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = OLE_ROOT / "scripts" / "summarize_active_preliminary.py"


def _module():
    spec = importlib.util.spec_from_file_location("summarize_active_preliminary", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _record(chi: int, seed: int, value: float) -> dict:
    return {
        "status": "success",
        "params": {"chi": chi, "seed": seed, "delta": "0.15"},
        "result": {"sample_value": value},
    }


def test_summary_keeps_available_and_three_chi_matched_samples_distinct():
    """Breaks if missing seeds are silently treated as a balanced χ sweep."""
    module = _module()
    records = [
        _record(64, 1, 0.1),
        _record(64, 2, 0.2),
        _record(64, 3, 0.3),
        _record(128, 1, 0.4),
        _record(128, 2, 0.5),
        _record(192, 1, 0.7),
        _record(192, 3, 0.9),
    ]

    summary = module.summarize(records)

    assert summary["available"]["64"]["n"] == 3
    assert summary["available"]["128"]["n"] == 2
    assert summary["available"]["192"]["n"] == 2
    assert summary["three_chi_common_seeds"] == [1]
    assert summary["matched"]["64"]["mean"] == pytest.approx(0.1)
    assert summary["matched"]["128"]["mean"] == pytest.approx(0.4)
    assert summary["matched"]["192"]["mean"] == pytest.approx(0.7)
    assert summary["paired_drift"]["64_to_128"]["mean"] == pytest.approx(0.3)
    assert summary["paired_drift"]["128_to_192"]["mean"] == pytest.approx(0.3)


def test_external_anchors_preserve_instance_and_normalization_labels():
    """Breaks if raw, rescaled, or baseline references can be plotted as one series."""
    module = _module()

    anchors = module.external_anchors()

    assert anchors["active_public_bp_raw_chi512"] == {
        "instance": "49x1296",
        "normalization": "raw",
        "method": "BP-TN",
        "chi": 512,
        "value": pytest.approx(0.88157984),
    }
    assert anchors["active_public_bp_rescaled_chi512"]["normalization"] == (
        "delta0_rescaled"
    )
    assert anchors["active_ibm_rescaled"]["interval"] == pytest.approx(
        [0.649, 0.662]
    )
    assert anchors["baseline_current_bp_raw_chi512"]["instance"] == "49x648"
