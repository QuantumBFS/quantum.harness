from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib
import matplotlib.figure
import pytest

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


def test_hashes_are_deterministic_and_pngs_have_no_text_metadata(
    tmp_path: Path,
) -> None:
    first = _render(production_summary(), tmp_path / "first")
    second = _render(production_summary(), tmp_path / "second")

    assert [item.sha256 for item in first.figures] == [
        item.sha256 for item in second.figures
    ]
    for item in first.figures:
        payload = (tmp_path / "first" / item.filename).read_bytes()
        assert b"tEXt" not in payload
        assert b"tIME" not in payload


def test_selects_and_labels_real_failure_case(tmp_path: Path) -> None:
    manifest = _render(production_summary(), tmp_path)

    failure = next(
        item for item in manifest.figures if item.filename == "failure_case.png"
    )
    assert failure.panel_strata == (
        "two_qubit|d=4|k=2|gap=0.02|shots=1000",
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
