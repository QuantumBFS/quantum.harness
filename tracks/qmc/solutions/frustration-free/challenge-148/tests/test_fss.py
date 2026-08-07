from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from challenge148.fss import (
    _load_validated_cell,
    analyze_coarse_points,
    analyze_extended_production_roots,
    binder_summary,
    bootstrap_binder_chains,
    compare_beta_ratios,
    find_sign_change_bracket,
    load_validated_extension_root,
)
from challenge148.extension import build_directed_extension_plan
from challenge148.provenance import canonical_json
from challenge148.statistics import jackknife_binder


def test_binder_summary_aggregates_primitive_moments_not_per_bin_ratios():
    m2 = np.array([0.20, 0.24, 0.18, 0.23, 0.21, 0.19, 0.22, 0.17])
    m4 = np.array([0.08, 0.10, 0.07, 0.095, 0.085, 0.075, 0.09, 0.065])

    summary = binder_summary(m2, m4)

    assert summary == jackknife_binder(m2, m4)
    assert summary["raw_plugin_mean"] == pytest.approx(m2.mean() ** 2 / m4.mean())
    assert summary["raw_plugin_mean"] != pytest.approx(
        np.mean(m2**2 / m4), abs=1e-12
    )


def test_binder_jackknife_retains_m2_m4_covariance():
    m2 = np.array([0.18, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32])
    m4 = 0.30 * m2 + np.array(
        [0.030, 0.028, 0.031, 0.027, 0.032, 0.026, 0.033, 0.025]
    )

    summary = binder_summary(m2, m4)
    leave = ((m2.sum() - m2) / 7) ** 2 / ((m4.sum() - m4) / 7)
    covariance_aware = np.sqrt(7 / 8 * np.sum((leave - leave.mean()) ** 2))

    assert summary["standard_error"] == pytest.approx(covariance_aware)


def test_complete_chain_bootstrap_never_splices_bins_between_chains():
    chains = [
        (np.full(8, 1.0), np.full(8, 2.0)),
        (np.full(8, 3.0), np.full(8, 6.0)),
    ]

    samples = bootstrap_binder_chains(chains, replicates=64, seed=148)

    possible = {0.5, 1.0, 1.5}
    assert set(np.round(samples, 12)) <= possible
    assert len(set(np.round(samples, 12))) > 1


def test_complete_chain_bootstrap_rejects_single_replicate():
    chains = [
        (np.full(8, 1.0), np.full(8, 2.0)),
        (np.full(8, 3.0), np.full(8, 6.0)),
    ]

    with pytest.raises(ValueError, match="at least two"):
        bootstrap_binder_chains(chains, replicates=1, seed=148)


def test_sign_change_bracket_is_exact_and_accepts_exact_zero():
    bracket = find_sign_change_bracket(
        [4.70, 4.75, 4.80], [0.10, -0.02, -0.08]
    )
    assert bracket == {"lower_field": 4.70, "upper_field": 4.75}

    exact = find_sign_change_bracket([2.10, 2.15, 2.20], [0.1, 0.0, -0.1])
    assert exact == {"lower_field": 2.15, "upper_field": 2.15}


def test_sign_change_bracket_rejects_absent_or_ambiguous_brackets():
    with pytest.raises(ValueError, match="no sign-change"):
        find_sign_change_bracket([1.0, 2.0, 3.0], [0.3, 0.2, 0.1])
    with pytest.raises(ValueError, match="multiple sign-change"):
        find_sign_change_bracket([1.0, 2.0, 3.0, 4.0], [0.2, -0.1, 0.1, -0.2])


def test_beta_ratio_comparison_reports_overlap_and_shift():
    comparison = compare_beta_ratios(
        {
            1: {"lower_field": 4.70, "upper_field": 4.80},
            2: {"lower_field": 4.75, "upper_field": 4.85},
        }
    )

    assert comparison == {
        "beta_ratios": [1, 2],
        "consistent": True,
        "overlap": {"lower_field": 4.75, "upper_field": 4.80},
        "midpoint_shift": pytest.approx(0.05),
    }


def _point(
    lattice: str,
    beta_ratio: int,
    length: int,
    field: float,
    binder: float,
) -> dict[str, object]:
    m2 = np.linspace(0.20, 0.27, 8)
    m4 = m2.mean() ** 2 / binder + np.linspace(-0.002, 0.002, 8)
    return {
        "lattice": lattice,
        "beta_ratio": beta_ratio,
        "length": length,
        "field": field,
        "chains": [
            {"m2": m2.tolist(), "m4": m4.tolist()},
            {"m2": (m2 + 0.001).tolist(), "m4": (m4 + 0.001).tolist()},
        ],
    }


def _combined_points(*, bracket_mode: str = "single") -> tuple[
    list[dict[str, object]], list[dict[str, object]]
]:
    centers = {"triangular": 4.76811, "honeycomb": 2.1325}
    directed = {
        ("triangular", 1, "4<->6"): {0.97, 0.98},
        ("triangular", 2, "6<->8"): {1.02, 1.03},
        ("honeycomb", 1, "6<->8"): {0.97, 0.98},
    }
    base_points: list[dict[str, object]] = []
    extension_points: list[dict[str, object]] = []
    for lattice, center in centers.items():
        for beta_ratio in (1, 2):
            for length in (4, 6, 8):
                for factor in (0.99, 1.00, 1.01):
                    slope = factor - 1.005
                    binder = (
                        0.65 + 0.01 * length
                        if bracket_mode == "none"
                        else 0.65 + 0.02 * length * slope
                    )
                    base_points.append(
                        _point(lattice, beta_ratio, length, center * factor, binder)
                    )
    for (lattice, beta_ratio, pair), factors in directed.items():
        center = centers[lattice]
        lengths = tuple(int(value) for value in pair.split("<->"))
        threshold = 0.985 if max(factors) < 1.0 else 1.015
        for length in lengths:
            for factor in sorted(factors):
                slope = factor - threshold
                if bracket_mode == "none":
                    slope = 1.0
                elif bracket_mode == "multiple":
                    slope = -1.0 if factor == min(factors) else 1.0
                binder = 0.65 + 0.02 * length * slope
                extension_points.append(
                    _point(lattice, beta_ratio, length, center * factor, binder)
                )
    return base_points, extension_points


def _plan(digest: str) -> dict[str, object]:
    return {"plan_sha256": digest}


def _bindings(prefix: str, count: int) -> list[dict[str, object]]:
    return [
        {"cell_id": f"{prefix}-{index}", "sha256": "b" * 64}
        for index in range(count)
    ]


def test_extended_analysis_merges_only_directed_coordinates_and_hashes_output(
    monkeypatch: pytest.MonkeyPatch,
):
    base_points, extension_points = _combined_points()
    monkeypatch.setattr(
        "challenge148.fss.load_validated_production_root",
        lambda root: (_plan("a" * 64), base_points, _bindings("base", 72)),
    )
    monkeypatch.setattr(
        "challenge148.fss.load_validated_extension_root",
        lambda root: (_plan("c" * 64), extension_points, _bindings("extension", 24)),
    )

    result = analyze_extended_production_roots(
        Path("/base"), Path("/extension"), bootstrap_replicates=32
    )

    assert result["stage"] == "QMC_SSE coarse localization"
    assert result["plan_sha256"] == "a" * 64
    assert result["extension_plan_sha256"] == "c" * 64
    assert len(result["input_bindings"]) == 96
    assert len(result["binder_summaries"]) == 48
    assert len(result["crossing_brackets"]) == 8
    assert result["refinement"]["lengths"] == [8, 12, 16, 20]
    assert "not a final two-code verdict" in result["refinement"]["interpretation"]
    fields_by_series = {
        (item["lattice"], item["beta_ratio"], item["size_pair"]): len(
            item["binder_differences"]
        )
        for item in result["crossing_brackets"]
    }
    assert fields_by_series[("triangular", 1, "4<->6")] == 5
    assert fields_by_series[("triangular", 2, "6<->8")] == 5
    assert fields_by_series[("honeycomb", 1, "6<->8")] == 5
    assert set(fields_by_series.values()) == {3, 5}
    centers = {"triangular": 4.76811, "honeycomb": 2.1325}
    factor_grid = {
        (item["lattice"], item["beta_ratio"], item["size_pair"]): [
            round(point["field"] / centers[item["lattice"]], 2)
            for point in item["binder_differences"]
        ]
        for item in result["crossing_brackets"]
    }
    assert factor_grid[("triangular", 1, "4<->6")] == [
        0.97,
        0.98,
        0.99,
        1.00,
        1.01,
    ]
    assert factor_grid[("triangular", 2, "6<->8")] == [
        0.99,
        1.00,
        1.01,
        1.02,
        1.03,
    ]
    assert factor_grid[("honeycomb", 1, "6<->8")] == [
        0.97,
        0.98,
        0.99,
        1.00,
        1.01,
    ]
    assert all(
        factors == [0.99, 1.00, 1.01]
        for series, factors in factor_grid.items()
        if series
        not in {
            ("triangular", 1, "4<->6"),
            ("triangular", 2, "6<->8"),
            ("honeycomb", 1, "6<->8"),
        }
    )
    unsigned = copy.deepcopy(result)
    digest = unsigned.pop("analysis_sha256")
    assert digest == hashlib.sha256(canonical_json(unsigned)).hexdigest()


@pytest.mark.parametrize(
    ("mode", "message"),
    [("none", "no sign-change"), ("multiple", "multiple sign-change")],
)
def test_extended_analysis_fails_closed_when_any_series_has_invalid_bracket(
    monkeypatch: pytest.MonkeyPatch, mode: str, message: str
):
    base_points, extension_points = _combined_points(bracket_mode=mode)
    monkeypatch.setattr(
        "challenge148.fss.load_validated_production_root",
        lambda root: (_plan("a" * 64), base_points, _bindings("base", 72)),
    )
    monkeypatch.setattr(
        "challenge148.fss.load_validated_extension_root",
        lambda root: (_plan("c" * 64), extension_points, _bindings("extension", 24)),
    )

    with pytest.raises(ValueError, match=message):
        analyze_extended_production_roots(
            Path("/base"), Path("/extension"), bootstrap_replicates=2
        )


def test_extended_analysis_rejects_overlapping_base_and_extension_coordinate(
    monkeypatch: pytest.MonkeyPatch,
):
    base_points, extension_points = _combined_points()
    extension_points[0]["field"] = base_points[0]["field"]
    extension_points[0]["lattice"] = base_points[0]["lattice"]
    extension_points[0]["beta_ratio"] = base_points[0]["beta_ratio"]
    extension_points[0]["length"] = base_points[0]["length"]
    monkeypatch.setattr(
        "challenge148.fss.load_validated_production_root",
        lambda root: (_plan("a" * 64), base_points, _bindings("base", 72)),
    )
    monkeypatch.setattr(
        "challenge148.fss.load_validated_extension_root",
        lambda root: (_plan("c" * 64), extension_points, _bindings("extension", 24)),
    )

    with pytest.raises(ValueError, match="overlap"):
        analyze_extended_production_roots(
            Path("/base"), Path("/extension"), bootstrap_replicates=2
        )


def test_coarse_analysis_separates_lattice_beta_and_size_pairs_and_hashes_output():
    points = []
    for lattice, center in (("triangular", 4.75), ("honeycomb", 2.15)):
        fields = [center - 0.05, center, center + 0.05]
        for beta_ratio in (1, 2):
            for field_index, field in enumerate(fields):
                for length, slope in ((4, 0.00), (6, 0.02), (8, 0.04)):
                    binder = 0.70 - 0.03 * field_index + slope * (1 - field_index)
                    points.append(
                        _point(lattice, beta_ratio, length, field, binder)
                    )

    result = analyze_coarse_points(
        points,
        plan_sha256="a" * 64,
        input_bindings=[{"cell_id": f"cell-{index}", "sha256": "b" * 64}
                        for index in range(72)],
        bootstrap_replicates=64,
        bootstrap_seed=148,
    )

    assert result["stage"] == "QMC_SSE coarse localization"
    assert len(result["binder_summaries"]) == 36
    assert {
        (item["lattice"], item["beta_ratio"], item["size_pair"])
        for item in result["crossing_brackets"]
    } == {
        (lattice, ratio, pair)
        for lattice in ("triangular", "honeycomb")
        for ratio in (1, 2)
        for pair in ("4<->6", "6<->8")
    }
    assert result["refinement"]["lengths"][-1] >= 20
    unsigned = copy.deepcopy(result)
    digest = unsigned.pop("analysis_sha256")
    assert digest == hashlib.sha256(canonical_json(unsigned)).hexdigest()
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def _load_analysis_cli():
    script = Path(__file__).resolve().parents[1] / "scripts" / "analyze.py"
    specification = importlib.util.spec_from_file_location("challenge148_analyze", script)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_analysis_cli_passes_validated_root_and_publishes_hash_bound_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    module = _load_analysis_cli()
    production_root = tmp_path / "production"
    output = tmp_path / "analysis.json"
    analysis = {"analysis_sha256": "c" * 64, "stage": "QMC_SSE coarse localization"}
    calls = []

    def analyze(root, *, bootstrap_replicates, bootstrap_seed):
        calls.append(("analyze", root, bootstrap_replicates, bootstrap_seed))
        return analysis

    def write(path, value):
        calls.append(("write", path, value))

    monkeypatch.setattr(module, "analyze_production_root", analyze)
    monkeypatch.setattr(module, "write_analysis_artifact", write)

    assert module.main(
        [
            "--production-root",
            str(production_root),
            "--output",
            str(output),
            "--bootstrap-replicates",
            "64",
            "--bootstrap-seed",
            "9",
        ]
    ) == 0
    assert calls == [
        ("analyze", production_root.resolve(), 64, 9),
        ("write", output.resolve(), analysis),
    ]
    assert capsys.readouterr().out == (
        "stage: QMC_SSE coarse localization\n"
        f"analysis_sha256: {'c' * 64}\n"
        f"artifact: {output.resolve()}\n"
    )


def test_analysis_cli_uses_directed_mode_when_extension_root_is_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    module = _load_analysis_cli()
    base_root = tmp_path / "base"
    extension_root = tmp_path / "extension"
    output = tmp_path / "analysis.json"
    analysis = {"analysis_sha256": "c" * 64, "stage": "QMC_SSE coarse localization"}
    calls = []

    def analyze(base, extension, *, bootstrap_replicates, bootstrap_seed):
        calls.append((base, extension, bootstrap_replicates, bootstrap_seed))
        return analysis

    monkeypatch.setattr(module, "analyze_extended_production_roots", analyze)
    monkeypatch.setattr(module, "write_analysis_artifact", lambda path, value: None)

    assert module.main(
        [
            "--production-root",
            str(base_root),
            "--extension-root",
            str(extension_root),
            "--output",
            str(output),
            "--bootstrap-replicates",
            "32",
        ]
    ) == 0
    assert calls == [(base_root.resolve(), extension_root.resolve(), 32, 148)]


def test_analysis_cli_directed_failure_preserves_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    module = _load_analysis_cli()
    output = tmp_path / "analysis.json"
    sentinel = b'{"immutable":"sentinel"}\n'
    output.write_bytes(sentinel)

    def analyze(*args, **kwargs):
        raise ValueError("multiple sign-change brackets")

    monkeypatch.setattr(module, "analyze_extended_production_roots", analyze)

    assert module.main(
        [
            "--production-root",
            str(tmp_path / "base"),
            "--extension-root",
            str(tmp_path / "extension"),
            "--output",
            str(output),
            "--bootstrap-replicates",
            "2",
        ]
    ) == 1
    assert output.read_bytes() == sentinel


def test_analysis_cli_rejects_single_bootstrap_replicate_before_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    module = _load_analysis_cli()
    called = False

    def analyze(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(module, "analyze_production_root", analyze)

    with pytest.raises(SystemExit) as exc_info:
        module.main(
            [
                "--production-root",
                str(tmp_path / "production"),
                "--output",
                str(tmp_path / "analysis.json"),
                "--bootstrap-replicates",
                "1",
            ]
        )

    assert exc_info.value.code == 2
    assert not called


def test_analysis_cli_no_bracket_exits_nonzero_without_creating_or_altering_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    module = _load_analysis_cli()
    points = []
    for lattice, center in (("triangular", 4.75), ("honeycomb", 2.15)):
        for beta_ratio in (1, 2):
            for field_index, field in enumerate(
                [center - 0.05, center, center + 0.05]
            ):
                for length in (4, 6, 8):
                    points.append(
                        _point(
                            lattice,
                            beta_ratio,
                            length,
                            field,
                            0.60 + 0.01 * length - 0.02 * field_index,
                        )
                    )

    def analyze(root, *, bootstrap_replicates, bootstrap_seed):
        return analyze_coarse_points(
            points,
            plan_sha256="a" * 64,
            input_bindings=[
                {"cell_id": f"cell-{index}", "sha256": "b" * 64}
                for index in range(72)
            ],
            bootstrap_replicates=bootstrap_replicates,
            bootstrap_seed=bootstrap_seed,
        )

    monkeypatch.setattr(module, "analyze_production_root", analyze)
    missing_output = tmp_path / "missing.json"
    existing_output = tmp_path / "existing.json"
    existing_payload = b'{"immutable":"sentinel"}\n'
    existing_output.write_bytes(existing_payload)

    for output in (missing_output, existing_output):
        assert module.main(
            [
                "--production-root",
                str(tmp_path / "production"),
                "--output",
                str(output),
                "--bootstrap-replicates",
                "2",
            ]
        ) == 1

    assert not missing_output.exists()
    assert existing_output.read_bytes() == existing_payload
    errors = capsys.readouterr().err
    assert errors.count("no sign-change bracket") == 2


def test_real_run_cell_completed_evidence_is_accepted_with_live_snapshot_binding(
    tmp_path: Path,
):
    from test_run_cell import (
        _fake_executable,
        _load_runner,
        _plan_fixture,
    )

    runner = _load_runner()
    plan_path, plan = _plan_fixture(tmp_path)
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable, semantic_output=True)
    cell_root = runner.run_cell(plan_path, 0, executable, timeout=5)

    records, binding = _load_validated_cell(
        tmp_path, plan, plan["cells"][0], 0
    )

    assert len(records) == 16
    assert binding["cell_id"] == plan["cells"][0]["cell_id"]
    assert binding["semantic_snapshot_sha256"] == json.loads(
        next((cell_root / "completed-evidence").iterdir()).joinpath(
            "completion.json"
        ).read_text()
    )["semantic_snapshot_sha256"]


def _extension_plan_fixture(root: Path) -> dict[str, object]:
    preregistration = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "preregistration"
            / "directed-extension-v1.json"
        ).read_text()
    )
    plan = build_directed_extension_plan(
        preregistration,
        {
            "adapter": "QMC_SSE",
            "source_hash": "a" * 64,
            "build_hash": "b" * 64,
        },
        root,
    )
    (root / "plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return plan


def test_extension_loader_requires_exactly_24_cells_and_reuses_cell_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plan = _extension_plan_fixture(tmp_path)
    cells_root = tmp_path / "cells"
    for cell in plan["cells"]:
        (cells_root / cell["cell_id"]).mkdir(parents=True)
    calls = []

    def load(root, loaded_plan, cell, cell_index):
        calls.append((root, loaded_plan, cell, cell_index))
        return (
            [
                {"m2_sum": 20.0 + index, "m4_sum": 10.0 + index, "sample_count": 100}
                for index in range(2)
            ],
            {"cell_id": cell["cell_id"], "sha256": "d" * 64},
        )

    monkeypatch.setattr("challenge148.fss._load_validated_cell", load)
    loaded_plan, points, bindings = load_validated_extension_root(tmp_path)

    assert loaded_plan == plan
    assert len(calls) == 24
    assert len(points) == 12
    assert all(len(point["chains"]) == 2 for point in points)
    assert len(bindings) == 24

    (cells_root / "unexpected").mkdir()
    with pytest.raises(ValueError, match="exactly the 24 planned cells"):
        load_validated_extension_root(tmp_path)


def test_extension_loader_rejects_modified_completed_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from test_run_cell import _fake_executable, _load_runner

    plan = _extension_plan_fixture(tmp_path)
    cells_root = tmp_path / "cells"
    for cell in plan["cells"]:
        (cells_root / cell["cell_id"]).mkdir(parents=True)
    runner = _load_runner()
    monkeypatch.setattr(
        runner,
        "validate_plan",
        __import__(
            "challenge148.extension", fromlist=["validate_directed_extension_plan"]
        ).validate_directed_extension_plan,
    )
    executable = tmp_path / "qmc-sse"
    _fake_executable(executable, semantic_output=True)
    first_cell = runner.run_cell(tmp_path / "plan.json", 0, executable, timeout=5)
    evidence = next((first_cell / "completed-evidence").iterdir())
    completion = evidence / "completion.json"
    completion.write_bytes(completion.read_bytes() + b" ")

    with pytest.raises(ValueError, match="cell completion|canonical"):
        load_validated_extension_root(tmp_path)
