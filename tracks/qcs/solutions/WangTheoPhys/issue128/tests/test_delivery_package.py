from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.package_delivery import (  # noqa: E402
    EXPECTED,
    build_summary,
    canonical_json,
    render_summary_text,
    require_equal,
    write_delivery_files,
)


def test_build_summary_projects_frozen_certificate() -> None:
    summary = build_summary(ROOT)
    assert summary["schema_version"] == 1
    assert summary["benchmark"]["sites"] == 144
    assert summary["published_baseline"]["steps"] == 393
    assert summary["published_baseline"]["group_exponentials"] == 11_791
    assert summary["certified_result"]["steps"] == 97
    assert summary["certified_result"]["group_exponentials"] == 2_911
    assert summary["improvement"]["exact_ratio"] == [11_791, 2_911]
    assert summary["improvement"]["decimal"] == "4.050498110614909"
    assert summary["verification"]["d4_term_count"] == 75_324
    assert summary["verification"]["d4_group_count"] == 7_576
    assert summary["fivefold_followup"]["status"] == "not_certified"
    assert summary["fivefold_followup"]["d5_term_count"] == 605_832
    assert summary["fivefold_followup"]["d5_group_count"] == 123_106


def test_summary_keeps_outward_error_boundary() -> None:
    result = build_summary(ROOT)["certified_result"]
    assert result["error_upper_decimal_outward"] == "9.958938494314325e-7"
    assert result["previous_step_error_upper_decimal_outward"] == "1.050565873970784e-6"
    assert result["accepted_at_97"] is True
    assert result["rejected_at_96"] is True


def test_summary_binds_frozen_digests() -> None:
    sources = build_summary(ROOT)["sources"]
    assert sources["main_certificate"]["sha256"] == EXPECTED["certificate_sha256"]
    assert sources["d4_sidecar"]["sha256"] == EXPECTED["d4_sha256"]
    assert sources["d5_sidecar"]["sha256"] == EXPECTED["d5_sha256"]


def test_require_equal_rejects_drift() -> None:
    with pytest.raises(ValueError, match="candidate steps drift"):
        require_equal("candidate steps", 96, 97)


def test_text_marks_fivefold_unproved() -> None:
    text = render_summary_text(build_summary(ROOT))
    assert "CERTIFIED RESULT: 4.050498110614909x" in text
    assert "FIVEFOLD STATUS: NOT CERTIFIED" in text
    assert "No 78-step global error certificate is claimed or supplied." in text
    assert "certified 5x" not in text.lower()


def test_canonical_json_is_sorted_and_newline_terminated() -> None:
    assert canonical_json({"z": 1, "a": 2}) == '{\n  "a": 2,\n  "z": 1\n}\n'


def test_write_delivery_files_round_trips_summary(tmp_path: Path) -> None:
    summary = build_summary(ROOT)
    written = write_delivery_files(ROOT, tmp_path, capture=False)
    assert written == {tmp_path / "issue128-summary.json", tmp_path / "issue128-summary.txt"}
    assert json.loads((tmp_path / "issue128-summary.json").read_text()) == summary
    assert (tmp_path / "issue128-summary.txt").read_text().endswith("\n")
