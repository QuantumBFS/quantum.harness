from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct

import matplotlib
import matplotlib.figure
import matplotlib.pyplot as plt
import numpy as np
import pytest

import qcontrol.figures as figures_module
from qcontrol.analysis import (
    BootstrapInterval,
    MethodSummary,
    MetricAvailability,
    PairedSummary,
    ProbabilityEstimate,
    StratumKey,
    StratumSummary,
    Summary,
    TrajectoryBand,
)
from qcontrol.artifacts import canonical_json_bytes
from qcontrol.figures import FigureError, render_publication_figures


matplotlib.use("Agg", force=True)

METHODS = ("full", "model_hessian", "oracle", "random")
FILENAMES = (
    "queries_vs_dimension.png",
    "advantage_vs_gap.png",
    "subspace_rotation_and_floor.png",
    "rank_invariant_d2_d4.png",
    "failure_case.png",
)
GOLDEN_PNG_SHA256 = {
    "queries_vs_dimension.png": (
        "f114f76ec10dd5068bd1a3e0994778069a3a2ad7e187f477cd4ba0b8f10a90da"
    ),
    "advantage_vs_gap.png": (
        "738d875c86d779ccdfb65d5b37d227c5c3bf01c54f51428861b158ff9edecccf"
    ),
    "subspace_rotation_and_floor.png": (
        "2588603ade7d3ef501f1c46e1ee4649a1ad6b126ce20ebf6525540a003336f27"
    ),
    "rank_invariant_d2_d4.png": (
        "f3d613ae09f9ec9f9e9a623d132b52a85f8c2cb94c5f8eba564da64612fe4de2"
    ),
    "failure_case.png": (
        "fe004c0ecf459c618d1a84d63a938161b5747af0c6b5f9e5e75fdbc4c45c6d57"
    ),
}


def _interval(estimate: float, *, seed: int = 7) -> BootstrapInterval:
    return BootstrapInterval(
        estimate=estimate,
        low=estimate - 0.1,
        high=estimate + 0.1,
        confidence=0.95,
        samples=20,
        seed=seed,
    )


def _probability(value: float, numerator: int) -> ProbabilityEstimate:
    # These are fixture intervals; production strictness is checked by canonical
    # round-tripping, so use exact Wilson bounds from the public constructor path.
    from qcontrol.analysis import success_probability

    trials = [
        {
            "certified": index < numerator,
            "first_certified_query": 2 if index < numerator else None,
            "provisional_crossings": [2] if index < numerator else [],
        }
        for index in range(4)
    ]
    estimate = success_probability(trials)
    assert estimate.value == value
    return estimate


def _method(
    name: str,
    *,
    dimension: int,
    query: int,
    success_numerator: int,
    attained: float,
    rank: int,
    gap: float,
) -> MethodSummary:
    probability = _probability(success_numerator / 4, success_numerator)
    trajectory = TrajectoryBand(
        median=(0.4, 0.2, 0.1),
        low=(0.35, 0.15, 0.08),
        high=(0.45, 0.25, 0.12),
        confidence=0.95,
        samples=20,
        seed=7,
    )
    return MethodSummary(
        method=name,
        trial_count=4,
        failure_count=4 - success_numerator,
        success_probability=probability,
        conditional_first_certified_queries=(query,) * success_numerator,
        censored_first_certified_queries=(query,) * success_numerator
        + (40,) * (4 - success_numerator),
        total_shots=4 * query * 1_000,
        total_shots_by_trial=(query * 1_000,) * 4,
        median_best_observed_infidelity_trajectory=(0.4, 0.2, 0.1),
        metric_availability=MetricAvailability("available", None),
        principal_angle_availability=MetricAvailability("available", None),
        exact_infidelity_trajectory=trajectory,
        median_attained_infidelity_upper_bound=attained,
        median_principal_angles=tuple(
            0.02 * (index + 1) + gap for index in range(dimension)
        ),
        median_model_effective_ranks=(float(rank),) * 3,
        median_truth_effective_ranks=(float(rank),) * 3,
        median_signed_eigenvalue_gaps=tuple(
            ((-1.0) ** index) * gap for index in range(dimension)
        ),
    )


def production_summary(*, include_failure: bool = True) -> Summary:
    strata = []
    for system_name, hilbert_dimension, expected_rank in (
        ("one_qubit", 2, 3),
        ("two_qubit", 4, 15),
    ):
        for gap in (0.01, 0.02):
            for dimension in (1, 2):
                model_query = 5 + dimension
                model_success = 4
                attained = 5e-4
                if (
                    include_failure
                    and hilbert_dimension == 4
                    and gap == 0.02
                    and dimension == 2
                ):
                    model_query = 11
                    model_success = 2
                    attained = 2e-3
                values = {
                    "full": (10, 3),
                    "model_hessian": (model_query, model_success),
                    "oracle": (7 + dimension, 4),
                    "random": (12 + dimension, 2),
                }
                methods = tuple(
                    _method(
                        name,
                        dimension=dimension,
                        query=query,
                        success_numerator=successes,
                        attained=attained if name == "model_hessian" else 7e-4,
                        rank=expected_rank,
                        gap=gap,
                    )
                    for name, (query, successes) in sorted(values.items())
                )
                model = values["model_hessian"]
                pairs = tuple(
                    PairedSummary(
                        baseline=name,
                        pair_count=4,
                        cluster_count=4,
                        success_probability_difference=_interval(
                            model[1] / 4 - successes / 4
                        ),
                        censored_query_difference=_interval(query - model[0]),
                        total_shot_difference=_interval(
                            float((query - model[0]) * 1_000)
                        ),
                    )
                    for name, (query, successes) in sorted(values.items())
                    if name != "model_hessian"
                )
                strata.append(
                    StratumSummary(
                        key=StratumKey(
                            system_name=system_name,
                            hilbert_dimension=hilbert_dimension,
                            segments=3 if hilbert_dimension == 2 else 10,
                            amplitude_bound=4.0,
                            duration=1.0,
                            search_dimension=dimension,
                            gap=gap,
                            shots=1_000,
                        ),
                        methods=methods,
                        paired_differences=pairs,
                    )
                )
    return Summary(
        strata=tuple(sorted(strata, key=lambda item: item.key.sort_key())),
        bootstrap_confidence=0.95,
        bootstrap_samples=20,
        bootstrap_seed=7,
    )


def _replace_stratum(summary: Summary, target: StratumSummary) -> Summary:
    return replace(
        summary,
        strata=tuple(
            sorted(
                (
                    target
                    if item.key.sort_key() == target.key.sort_key()
                    else item
                    for item in summary.strata
                ),
                key=lambda item: item.key.sort_key(),
            )
        ),
    )


def _all_failure_summary() -> Summary:
    summary = production_summary()
    original = next(
        item
        for item in summary.strata
        if item.key.system_name == "one_qubit"
        and item.key.gap == 0.01
        and item.key.search_dimension == 1
    )
    methods = tuple(
        replace(
            item,
            failure_count=4,
            success_probability=_probability(0.0, 0),
            conditional_first_certified_queries=(),
            censored_first_certified_queries=(40, 40, 40, 40),
        )
        for item in original.methods
    )
    return _replace_stratum(summary, replace(original, methods=methods))


def _configuration_variant_summary() -> Summary:
    summary = production_summary()
    original = next(
        item
        for item in summary.strata
        if item.key.system_name == "one_qubit"
        and item.key.gap == 0.01
        and item.key.search_dimension == 1
    )
    variants = (
        replace(original, key=replace(original.key, duration=2.0)),
        replace(original, key=replace(original.key, segments=4)),
        replace(original, key=replace(original.key, amplitude_bound=5.0)),
    )
    return replace(
        summary,
        strata=tuple(
            sorted((*summary.strata, *variants), key=lambda item: item.key.sort_key())
        ),
    )


def _capture_figures(
    monkeypatch: pytest.MonkeyPatch,
) -> list[matplotlib.figure.Figure]:
    captured: list[matplotlib.figure.Figure] = []
    original = matplotlib.figure.Figure.savefig

    def recording_savefig(self, file, *args, **kwargs):
        captured.append(self)
        return original(self, file, *args, **kwargs)

    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", recording_savefig)
    return captured


def _method_line(axis, label: str):
    direct = next(
        (line for line in axis.lines if line.get_label() == label),
        None,
    )
    if direct is not None:
        return direct
    return next(
        container.lines[0]
        for container in axis.containers
        if container.get_label() == label and hasattr(container, "lines")
    )


def _confidence_band(axis, label: str):
    return next(item for item in axis.collections if item.get_label() == label)


def _band_y_bounds(axis, label: str) -> tuple[float, float]:
    band = _confidence_band(axis, label)
    y_values = np.concatenate([path.vertices[:, 1] for path in band.get_paths()])
    return float(np.min(y_values)), float(np.max(y_values))


def _png_chunks(payload: bytes) -> tuple[str, ...]:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    chunks: list[str] = []
    offset = 8
    while offset < len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk = payload[offset + 4 : offset + 8].decode("ascii")
        chunks.append(chunk)
        offset += length + 12
        if chunk == "IEND":
            assert offset == len(payload)
            break
    return tuple(chunks)


def _fixture_stratum_id(stratum: StratumSummary) -> str:
    key = stratum.key
    return (
        f"system={key.system_name}|d={key.hilbert_dimension}|"
        f"segments={key.segments}|amplitude_bound={key.amplitude_bound:g}|"
        f"duration={key.duration:g}|k={key.search_dimension}|gap={key.gap:g}|"
        f"shots={'exact' if key.shots is None else key.shots}"
    )


def _render(summary: Summary, output: Path):
    return render_publication_figures(
        summary,
        output,
        source="strict Summary fixture",
        config="production fixture",
        run_id="fixture-001",
    )


def test_renders_five_closed_nonempty_publication_figures_and_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: dict[str, matplotlib.figure.Figure] = {}
    original = matplotlib.figure.Figure.savefig

    def recording_savefig(self, file, *args, **kwargs):
        saved[Path(file).name if not hasattr(file, "write") else f"buffer-{len(saved)}"] = self
        return original(self, file, *args, **kwargs)

    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", recording_savefig)
    manifest = _render(production_summary(), tmp_path)

    assert tuple(item.filename for item in manifest.figures) == FILENAMES
    assert all((tmp_path / name).stat().st_size > 0 for name in FILENAMES)
    assert (tmp_path / "figure_manifest.json").is_file()
    assert manifest.summary_sha256 == hashlib.sha256(
        canonical_json_bytes(production_summary().canonical_dict())
    ).hexdigest()
    figures = list(saved.values())
    assert figures
    for figure in figures:
        assert figure.axes
        assert all(axis.has_data() for axis in figure.axes)
        assert all(axis.get_xlabel() and axis.get_ylabel() for axis in figure.axes)
        assert figure._suptitle is not None


def test_axes_expose_required_definitions_scales_legends_and_methods(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    figures: list[matplotlib.figure.Figure] = []
    original = matplotlib.figure.Figure.savefig

    def recording_savefig(self, file, *args, **kwargs):
        figures.append(self)
        return original(self, file, *args, **kwargs)

    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", recording_savefig)
    _render(production_summary(), tmp_path)

    text = "\n".join(
        [
            *(axis.get_xlabel() for figure in figures for axis in figure.axes),
            *(axis.get_ylabel() for figure in figures for axis in figure.axes),
            *(
                label.get_text()
                for figure in figures
                for axis in figure.axes
                for label in axis.get_legend().get_texts()
                if axis.get_legend() is not None
            ),
        ]
    )
    for label in ("Full space", "Random", "Oracle", "Model Hessian"):
        assert label in text
    assert "optimizer queries" in text
    assert "success probability" in text
    assert "normalized gap" in text
    assert "radians" in text
    assert "relative threshold" in text
    assert any(
        axis.get_yscale() == "log" and "infidelity" in axis.get_ylabel().lower()
        for figure in figures
        for axis in figure.axes
    )
    assert all(
        axis.get_yscale() != "log" or "infidelity" in axis.get_ylabel().lower()
        for figure in figures
        for axis in figure.axes
    )
    assert all(figure.texts for figure in figures)


def test_artifacts_match_golden_hashes_canonical_manifest_and_png_contract(
    tmp_path: Path,
) -> None:
    summary = production_summary()
    first_directory = tmp_path / "first"
    second_directory = tmp_path / "second"
    first = _render(summary, first_directory)
    with matplotlib.rc_context({"font.family": "monospace"}):
        second = _render(summary, second_directory)

    assert matplotlib.get_backend().lower() == "agg"
    assert {item.filename: item.sha256 for item in first.figures} == (
        GOLDEN_PNG_SHA256
    )
    assert first.summary_sha256 == hashlib.sha256(
        canonical_json_bytes(summary.canonical_dict())
    ).hexdigest()
    assert first.source == "strict Summary fixture"
    assert first.config == "production fixture"
    assert first.run_id == "fixture-001"
    assert first.matplotlib_version == matplotlib.__version__
    assert first.numpy_version == np.__version__
    expected_strata = {_fixture_stratum_id(item) for item in summary.strata}
    for entry in first.figures[:4]:
        assert set(entry.panel_strata) == expected_strata
    assert first.figures[4].panel_strata == (
        "system=two_qubit|d=4|segments=10|amplitude_bound=4|"
        "duration=1|k=2|gap=0.02|shots=1000",
    )

    first_manifest = (first_directory / "figure_manifest.json").read_bytes()
    assert first_manifest == canonical_json_bytes(first.canonical_dict())
    assert json.loads(first_manifest) == first.canonical_dict()
    assert first_manifest == (
        second_directory / "figure_manifest.json"
    ).read_bytes()
    assert first == second

    for entry in first.figures:
        first_payload = (first_directory / entry.filename).read_bytes()
        second_payload = (second_directory / entry.filename).read_bytes()
        assert first_payload == second_payload
        assert hashlib.sha256(first_payload).hexdigest() == entry.sha256
        chunks = _png_chunks(first_payload)
        assert chunks[0] == "IHDR"
        assert chunks[-1] == "IEND"
        assert chunks.count("IHDR") == chunks.count("IEND") == 1
        assert "IDAT" in chunks
        assert set(chunks) <= {"IHDR", "IDAT", "IEND"}


def test_selects_and_labels_real_failure_case(tmp_path: Path) -> None:
    manifest = _render(production_summary(), tmp_path)

    failure = next(
        item for item in manifest.figures if item.filename == "failure_case.png"
    )
    assert failure.panel_strata == (
        "system=two_qubit|d=4|segments=10|amplitude_bound=4|"
        "duration=1|k=2|gap=0.02|shots=1000",
    )
    assert failure.failure_reason is not None
    assert "restricted attained infidelity" in failure.failure_reason


def test_fails_precisely_when_no_real_failure_exists(tmp_path: Path) -> None:
    with pytest.raises(FigureError, match="no qualifying production failure"):
        _render(production_summary(include_failure=False), tmp_path)
    assert not list(tmp_path.glob("*.png"))


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda payload: payload["strata"][0]["methods"].pop(
                next(
                    index
                    for index, method in enumerate(
                        payload["strata"][0]["methods"]
                    )
                    if method["method"] == "model_hessian"
                )
            ),
            "required methods",
        ),
        (
            lambda payload: payload["strata"][0]["methods"][0].update(
                {
                    "metric_availability": {
                        "state": "unavailable",
                        "reason": "missing",
                    },
                    "principal_angle_availability": {
                        "state": "unavailable",
                        "reason": "missing",
                    },
                    "exact_infidelity_trajectory": None,
                    "median_attained_infidelity_upper_bound": None,
                    "median_model_effective_ranks": None,
                    "median_principal_angles": None,
                    "median_signed_eigenvalue_gaps": None,
                    "median_truth_effective_ranks": None,
                }
            ),
            "production metrics",
        ),
    ),
)
def test_rejects_missing_methods_or_metrics(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    payload = production_summary().canonical_dict()
    mutation(payload)
    payload["strata"][0]["methods"].sort(key=lambda item: item["method"])
    summary = Summary.from_canonical_dict(payload)

    with pytest.raises(FigureError, match=message):
        _render(summary, tmp_path)
    assert not list(tmp_path.glob("*.png"))


def test_rejects_noncanonical_summary_instance(tmp_path: Path) -> None:
    valid = production_summary()
    malformed = Summary(
        strata=tuple(reversed(valid.strata)),
        bootstrap_confidence=valid.bootstrap_confidence,
        bootstrap_samples=valid.bootstrap_samples,
        bootstrap_seed=valid.bootstrap_seed,
    )

    with pytest.raises(FigureError, match="strict canonical Summary"):
        _render(malformed, tmp_path)


def test_primary_query_series_uses_censored_failures_and_all_failure_point(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    figures = _capture_figures(monkeypatch)
    manifest = _render(_all_failure_summary(), tmp_path)
    query_figure = figures[FILENAMES.index("queries_vs_dimension.png")]
    query_axis, success_axis = next(
        (query_figure.axes[index], query_figure.axes[index + 1])
        for index in range(0, len(query_figure.axes), 2)
        if "one_qubit" in query_figure.axes[index].get_title()
        and "gap=0.01" in query_figure.axes[index].get_title()
    )

    model_query = _method_line(query_axis, "Model Hessian")
    model_success = _method_line(success_axis, "Model Hessian")
    assert model_query.get_xdata().tolist() == [1, 2]
    assert model_query.get_ydata().tolist() == [40.0, 7.0]
    assert model_success.get_ydata().tolist() == [0.0, 1.0]
    model_errors = next(
        container
        for container in query_axis.containers
        if container.get_label() == "Model Hessian"
    )
    segments = model_errors.lines[2][0].get_segments()
    assert segments[0].tolist() == [[1.0, 40.0], [1.0, 40.0]]
    success_errors = next(
        container
        for container in success_axis.containers
        if container.get_label() == "Model Hessian"
    )
    assert success_errors.lines[2][0].get_segments()[0].tolist() == [
        [1.0, 0.0],
        [1.0, _probability(0.0, 0).high],
    ]
    random_query = _method_line(query_axis, "Random")
    assert random_query.get_ydata().tolist() == [40.0, 27.0]
    random_errors = next(
        container
        for container in query_axis.containers
        if container.get_label() == "Random"
    )
    assert random_errors.lines[2][0].get_segments()[1].tolist() == [
        [2.0, 14.0],
        [2.0, 40.0],
    ]
    assert "budget-censored median" in query_axis.get_ylabel()
    assert manifest.figures[0].panel_strata


def test_full_control_configuration_separates_panels_and_manifest_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    figures = _capture_figures(monkeypatch)
    manifest = _render(_configuration_variant_summary(), tmp_path)
    query_figure = figures[FILENAMES.index("queries_vs_dimension.png")]
    query_entry = manifest.figures[0]

    assert manifest.source == "strict Summary fixture"
    assert manifest.config == "production fixture"
    assert manifest.run_id == "fixture-001"
    assert len(query_figure.axes) == 14
    assert len(query_entry.panel_strata) == len(set(query_entry.panel_strata))
    assert any("segments=4" in item for item in query_entry.panel_strata)
    assert any("amplitude_bound=5" in item for item in query_entry.panel_strata)
    assert any("duration=2" in item for item in query_entry.panel_strata)
    assert all(
        all(
            field in item
            for field in (
                "system=",
                "d=",
                "segments=",
                "amplitude_bound=",
                "duration=",
                "k=",
                "gap=",
                "shots=",
            )
        )
        for item in query_entry.panel_strata
    )


def test_exact_artist_data_and_method_styles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    figures = _capture_figures(monkeypatch)
    _render(production_summary(), tmp_path)
    by_title = {
        figure._suptitle.get_text().splitlines()[0]: figure
        for figure in figures
    }
    advantage = by_title[
        "Paired Model-Hessian advantage versus normalized gap"
    ]
    subspace = by_title[
        "Target-k subspace rotation and restricted fidelity floor"
    ]
    rank = by_title["d=2 and d=4 Hessian rank invariants"]
    failure = next(
        figure
        for title, figure in by_title.items()
        if title.startswith("Observed production failure:")
    )
    advantage_axes = {
        "query": next(
            axis
            for axis in advantage.axes
            if "one_qubit" in axis.get_title()
            and "k=1" in axis.get_title()
            and "query advantage" in axis.get_ylabel()
        ),
        "shot": next(
            axis
            for axis in advantage.axes
            if "one_qubit" in axis.get_title()
            and "k=1" in axis.get_title()
            and "shot advantage" in axis.get_ylabel()
        ),
        "success": next(
            axis
            for axis in advantage.axes
            if "one_qubit" in axis.get_title()
            and "k=1" in axis.get_title()
            and "success advantage" in axis.get_ylabel()
        ),
    }
    assert _method_line(
        advantage_axes["query"], "Full space"
    ).get_ydata().tolist() == [
        4.0,
        4.0,
    ]
    assert _method_line(
        advantage_axes["shot"], "Full space"
    ).get_ydata().tolist() == [
        4000.0,
        4000.0,
    ]
    assert _method_line(
        advantage_axes["success"], "Full space"
    ).get_ydata().tolist() == [
        0.25,
        0.25,
    ]
    assert _band_y_bounds(
        advantage_axes["query"], "Full space confidence interval"
    ) == (
        3.9,
        4.1,
    )
    assert _band_y_bounds(
        advantage_axes["shot"], "Full space confidence interval"
    ) == (
        3999.9,
        4000.1,
    )
    assert _band_y_bounds(
        advantage_axes["success"], "Full space confidence interval"
    ) == (
        0.15,
        0.35,
    )

    k2_angles = next(
        axis
        for axis in subspace.axes
        if "one_qubit" in axis.get_title()
        and "k=2" in axis.get_title()
        and "principal angles" in axis.get_ylabel()
    )
    for method in ("Full space", "Model Hessian", "Oracle", "Random"):
        assert _method_line(k2_angles, f"{method} θ1").get_xdata().tolist() == [
            0.0025,
            0.005,
        ]
        assert _method_line(k2_angles, f"{method} θ1").get_ydata().tolist() == [
            0.03,
            0.04,
        ]
        assert _method_line(k2_angles, f"{method} θ2").get_ydata().tolist() == [
            0.05,
            0.06,
        ]

    summary = production_summary()
    for stratum in summary.strata:
        identity = _fixture_stratum_id(stratum)
        rank_axis = next(
            axis
            for axis in rank.axes
            if axis.get_title() == identity
            and "effective Hessian rank" in axis.get_ylabel()
        )
        gap_axis = next(
            axis
            for axis in rank.axes
            if axis.get_title() == identity
            and "signed leading" in axis.get_ylabel()
        )
        expected_rank = 3.0 if stratum.key.hilbert_dimension == 2 else 15.0
        for label in (
            "Model Hessian model rank",
            "Model Hessian truth rank",
        ):
            assert _method_line(rank_axis, label).get_xdata().tolist() == [
                1e-6,
                1e-8,
                1e-10,
            ]
            assert _method_line(rank_axis, label).get_ydata().tolist() == [
                expected_rank,
                expected_rank,
                expected_rank,
            ]
        reference = f"Expected invariant rank {int(expected_rank)}"
        assert list(_method_line(rank_axis, reference).get_ydata()) == [
            expected_rank,
            expected_rank,
        ]
        expected_gaps = [
            ((-1.0) ** index) * stratum.key.gap
            for index in range(stratum.key.search_dimension)
        ]
        signed_gap = _method_line(
            gap_axis,
            "Model Hessian signed leading gaps",
        )
        assert signed_gap.get_xdata().tolist() == list(
            range(1, stratum.key.search_dimension + 1)
        )
        assert signed_gap.get_ydata().tolist() == expected_gaps

    expected_failure_values = {
        "right-censored first certified query": 25.5,
        "total optimizer + validation shots": 11000.0,
        "success probability within budget": 0.5,
        "restricted infidelity": 0.002,
    }
    for ylabel, expected_value in expected_failure_values.items():
        axis = next(
            item for item in failure.axes if ylabel in item.get_ylabel()
        )
        assert _method_line(
            axis,
            "Model Hessian",
        ).get_ydata().item() == expected_value

    expected = {
        "Full space": ("#000000", "s", "-"),
        "Model Hessian": ("#0072B2", "o", "-"),
        "Oracle": ("#009E73", "^", "--"),
        "Random": ("#E69F00", "D", ":"),
    }
    for figure in figures:
        for axis in figure.axes:
            labeled_lines = [
                (line, line.get_label())
                for line in axis.lines
            ]
            labeled_lines.extend(
                (container.lines[0], container.get_label())
                for container in axis.containers
                if hasattr(container, "lines")
            )
            for line, label in labeled_lines:
                method = next(
                    (
                        name
                        for name in expected
                        if label == name
                        or label.startswith(f"{name} ")
                    ),
                    None,
                )
                if method is None:
                    continue
                color, marker, linestyle = expected[method]
                assert line.get_color().lower() == color.lower()
                assert line.get_marker() == marker
                assert line.get_linestyle() == linestyle

def test_builder_exception_closes_only_new_figures_and_restores_rc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = plt.figure()
    before_numbers = plt.get_fignums()
    before_rc = {
        "axes.grid": matplotlib.rcParams["axes.grid"],
        "font.size": matplotlib.rcParams["font.size"],
    }

    def broken_builder(summary, caption):
        plt.figure()
        raise RuntimeError("intentional builder failure")

    monkeypatch.setattr(figures_module, "_queries_figure", broken_builder)
    try:
        with pytest.raises(RuntimeError, match="intentional builder failure"):
            _render(production_summary(), tmp_path)
        assert plt.get_fignums() == before_numbers
        assert {
            "axes.grid": matplotlib.rcParams["axes.grid"],
            "font.size": matplotlib.rcParams["font.size"],
        } == before_rc
        assert plt.fignum_exists(existing.number)
    finally:
        plt.close(existing)
