from __future__ import annotations

import hashlib
import importlib.util
import math
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[6]
RESULTS = REPO_ROOT / "results/challenge-194"
SOLUTION = Path(__file__).resolve().parents[1]
GENERATOR = SOLUTION / "scripts/generate_report_figures.py"

EXPECTED_FILE_HASHES = {
    "approval": "29dc5d04fd18728ee46fffe90c70d98caa61032005974f354e2b4e0e6018a7ab",
    "p0_analysis": "44083701db692304cd3aa054c8a9488b75674cead7cd6bf479c0a203cc1fa10b",
    "extension_protocol": "e363a60f842b11b32972c7a68ec1c5f237741bc45bc79ab8bf93f51f6760d84d",
    "extension_analysis": "d8fdd60a6de83cf3818349d4440f49f4a38bb5acd7fff1dab9b56ded4da913e5",
    "combined_analysis": "6c38e3e18a4577da41bc70c5610b5449e0316b1588291cb178e437099fb78929",
    "brackets": "7a84d545b4526d94aa6f93ca4f0d264dcf01e518f2f9b04383921634786c9962",
}


def source_paths() -> dict[str, Path]:
    if not RESULTS.is_dir():
        pytest.skip("gitignored results/challenge-194 evidence root is unavailable")
    return {
        "approval": SOLUTION / "pilot_correctness_approval.json",
        "p0_analysis": RESULTS / "p0_analysis.json",
        "extension_protocol": RESULTS / "p0_extension_v1_protocol.json",
        "extension_analysis": RESULTS / "p0_extension_v1_analysis.json",
        "combined_analysis": RESULTS / "p0_combined_analysis_v2.json",
        "brackets": RESULTS / "p0_combined_brackets_v2.json",
    }


def load_module():
    spec = importlib.util.spec_from_file_location("generate_report_figures", GENERATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def independent_marks(rows, kappas, lengths):
    q_marks = []
    crossing_marks = []
    for index in range(len(kappas) - 1):
        q_diff = [
            rows[(lengths[0], kappas[endpoint])]["means"]["q_g"]
            - rows[(lengths[1], kappas[endpoint])]["means"]["q_g"]
            for endpoint in (index, index + 1)
        ]
        q_marks.append(min(q_diff) <= 0.0 <= max(q_diff))
        crossing_marks.append(
            any(
                min(
                    rows[(length, kappas[index])]["means"]["four_sector_crossing"],
                    rows[(length, kappas[index + 1])]["means"]["four_sector_crossing"],
                )
                <= 0.25
                and max(
                    rows[(length, kappas[index])]["means"]["four_sector_crossing"],
                    rows[(length, kappas[index + 1])]["means"]["four_sector_crossing"],
                )
                >= 0.75
                for length in lengths
            )
        )
    return q_marks, crossing_marks


def test_authenticates_all_sources_and_embedded_identities():
    module = load_module()
    paths = source_paths()
    evidence = module.load_evidence(paths)

    assert evidence.file_hashes == EXPECTED_FILE_HASHES
    assert evidence.embedded_hashes == module.EXPECTED_EMBEDDED_HASHES
    for key, expected in EXPECTED_FILE_HASHES.items():
        assert hashlib.sha256(paths[key].read_bytes()).hexdigest() == expected


def test_rejects_changed_authenticated_source(tmp_path):
    module = load_module()
    paths = source_paths()
    changed = tmp_path / "combined.json"
    changed.write_bytes(paths["combined_analysis"].read_bytes() + b" ")
    paths["combined_analysis"] = changed

    with pytest.raises(ValueError, match="SHA256"):
        module.load_evidence(paths)


def test_extracts_required_rows_uncertainties_and_selector_marks():
    module = load_module()
    evidence = module.load_evidence(source_paths())

    assert tuple(evidence.panels) == ((0.9).hex(), (1.0).hex())
    for panel in evidence.panels.values():
        assert panel.lengths == (16384, 262144)
        assert tuple(sorted(panel.kappas, key=float.fromhex)) == panel.kappas
        for kappa in panel.kappas:
            assert float.fromhex(kappa).hex() == kappa
            for length in panel.lengths:
                row = panel.rows[(length, kappa)]
                for observable in ("q_g", "four_sector_crossing"):
                    assert observable in row["means"]
                    error = row["standard_errors"][observable]
                    assert math.isfinite(error) and error >= 0.0
        q_marks, crossing_marks = independent_marks(
            panel.rows, panel.kappas, panel.lengths
        )
        assert panel.q_marks == tuple(q_marks)
        assert panel.crossing_marks == tuple(crossing_marks)
        assert not any(q and c for q, c in zip(q_marks, crossing_marks))
        assert panel.status == "requires_p0_extension"
        assert panel.reason == "no_nonzero_interval_marked_by_both_estimators"


def test_svg_contains_accessibility_labels_sources_and_boundaries():
    module = load_module()
    evidence = module.load_evidence(source_paths())
    selector = module.render_selector_svg(evidence).decode()
    workflow = module.render_workflow_svg(
        evidence,
        (
            "scripts/analyze_pilot.py",
            "src/long_range_percolation/pilot_extension.py",
        ),
    ).decode()

    for svg in (selector, workflow):
        assert "<title>" in svg and "<desc>" in svg
        assert "SHA256" in svg
    for text in (
        "sigma = 0.9",
        "sigma = 1.0",
        "Q_G",
        "four-sector",
        "± 1 standard error",
        "共同标记区间：无",
        "p0_combined_analysis_v2.json",
        "p0_combined_brackets_v2.json",
        "exploratory selector evidence",
    ):
        assert text in selector
    for text in (
        "P0",
        "extension v1",
        "96",
        "P1",
        "未发布",
        "未运行",
        "extension-v2",
        "不属于本报告证据链",
    ):
        assert text in workflow


def test_rendering_is_byte_deterministic():
    module = load_module()
    evidence = module.load_evidence(source_paths())
    dirty = ("scripts/analyze_pilot.py",)

    assert module.render_selector_svg(evidence) == module.render_selector_svg(evidence)
    assert module.render_workflow_svg(evidence, dirty) == module.render_workflow_svg(
        evidence, dirty
    )


def test_write_outputs_is_no_clobber(tmp_path):
    module = load_module()
    outputs = {"a.svg": b"same"}
    module.write_outputs(tmp_path, outputs)
    module.write_outputs(tmp_path, outputs)
    assert (tmp_path / "a.svg").read_bytes() == b"same"

    with pytest.raises(FileExistsError, match="refusing to replace"):
        module.write_outputs(tmp_path, {"a.svg": b"different"})
    assert (tmp_path / "a.svg").read_bytes() == b"same"
