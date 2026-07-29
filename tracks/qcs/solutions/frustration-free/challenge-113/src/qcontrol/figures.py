from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import struct
import zlib

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from qcontrol.analysis import AnalysisError, MethodSummary, StratumSummary, Summary
from qcontrol.artifacts import canonical_json_bytes


class FigureError(ValueError):
    """A strict production Summary cannot support the required figures."""


@dataclass(frozen=True, slots=True)
class FigureManifestEntry:
    filename: str
    panel_strata: tuple[str, ...]
    sha256: str
    failure_reason: str | None = None

    def canonical_dict(self) -> dict[str, object]:
        return {
            "failure_reason": self.failure_reason,
            "filename": self.filename,
            "panel_strata": list(self.panel_strata),
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class FigureManifest:
    summary_sha256: str
    matplotlib_version: str
    numpy_version: str
    figures: tuple[FigureManifestEntry, ...]
    schema_version: int = 1

    def canonical_dict(self) -> dict[str, object]:
        return {
            "figures": [item.canonical_dict() for item in self.figures],
            "matplotlib_version": self.matplotlib_version,
            "numpy_version": self.numpy_version,
            "schema_version": self.schema_version,
            "summary_sha256": self.summary_sha256,
        }


_METHODS = ("full", "model_hessian", "oracle", "random")
_BASELINES = ("full", "oracle", "random")
_RANK_THRESHOLDS = (1e-6, 1e-8, 1e-10)
_TARGET_INFIDELITY = 1.0 - 0.999
_STYLES = {
    "full": {"color": "#000000", "marker": "s", "linestyle": "-"},
    "model_hessian": {"color": "#0072B2", "marker": "o", "linestyle": "-"},
    "oracle": {"color": "#009E73", "marker": "^", "linestyle": "--"},
    "random": {"color": "#E69F00", "marker": "D", "linestyle": ":"},
}
_DISPLAY = {
    "full": "Full space",
    "model_hessian": "Model Hessian",
    "oracle": "Oracle",
    "random": "Random",
}
_FILENAMES = (
    "queries_vs_dimension.png",
    "advantage_vs_gap.png",
    "subspace_rotation_and_floor.png",
    "rank_invariant_d2_d4.png",
    "failure_case.png",
)
_RC = {
    "axes.grid": True,
    "axes.grid.axis": "y",
    "axes.spines.right": False,
    "axes.spines.top": False,
    "font.size": 8,
    "figure.dpi": 120,
    "savefig.dpi": 120,
}


def _strict_summary(summary: Summary) -> Summary:
    if not isinstance(summary, Summary):
        raise FigureError("figures require a strict canonical Summary instance")
    try:
        parsed = Summary.from_canonical_dict(summary.canonical_dict())
    except (AnalysisError, TypeError, ValueError) as error:
        raise FigureError(f"figures require a strict canonical Summary: {error}") from error
    if parsed != summary:
        raise FigureError("figures require a strict canonical Summary")
    for stratum in summary.strata:
        names = tuple(item.method for item in stratum.methods)
        if set(names) != set(_METHODS):
            missing = sorted(set(_METHODS) - set(names))
            extra = sorted(set(names) - set(_METHODS))
            raise FigureError(
                "required methods are incomplete "
                f"(missing={missing}, unexpected={extra}) in {_stratum_id(stratum)}"
            )
        paired = {item.baseline for item in stratum.paired_differences}
        if paired != set(_BASELINES):
            raise FigureError(
                f"required paired methods are incomplete in {_stratum_id(stratum)}"
            )
        for method in stratum.methods:
            if (
                method.metric_availability.state != "available"
                or method.principal_angle_availability.state != "available"
                or method.exact_infidelity_trajectory is None
                or method.median_attained_infidelity_upper_bound is None
                or method.median_principal_angles is None
                or method.median_model_effective_ranks is None
                or method.median_truth_effective_ranks is None
                or method.median_signed_eigenvalue_gaps is None
            ):
                raise FigureError(
                    "required production metrics are unavailable for "
                    f"{method.method!r} in {_stratum_id(stratum)}"
                )
            if not method.conditional_first_certified_queries:
                raise FigureError(
                    "required certified-query metric is unavailable for "
                    f"{method.method!r} in {_stratum_id(stratum)}"
                )
    dimensions = {item.key.hilbert_dimension for item in summary.strata}
    if not {2, 4}.issubset(dimensions):
        raise FigureError("rank figure requires production strata for d=2 and d=4")
    return parsed


def _stratum_id(stratum: StratumSummary) -> str:
    key = stratum.key
    shots = "exact" if key.shots is None else str(key.shots)
    return (
        f"{key.system_name}|d={key.hilbert_dimension}|k={key.search_dimension}|"
        f"gap={key.gap:g}|shots={shots}"
    )


def _method(stratum: StratumSummary, name: str) -> MethodSummary:
    return next(item for item in stratum.methods if item.method == name)


def _caption(summary: Summary, source: str, config: str, run_id: str) -> str:
    trials = sum(method.trial_count for stratum in summary.strata for method in stratum.methods)
    clusters = sum(
        pair.cluster_count
        for stratum in summary.strata
        for pair in stratum.paired_differences
    )
    return (
        f"Source: {source} | config: {config} | run: {run_id} | "
        f"method-stratum samples n={trials}; paired clusters n={clusters}; "
        f"{summary.bootstrap_confidence:.0%} intervals, "
        f"{summary.bootstrap_samples} bootstrap samples"
    )


def _finish_figure(figure: matplotlib.figure.Figure, caption: str) -> None:
    figure.text(0.01, 0.006, caption, ha="left", va="bottom", fontsize=6)
    figure.tight_layout(rect=(0.0, 0.035, 1.0, 0.965))


def _groups(
    strata: Iterable[StratumSummary],
    key: Callable[[StratumSummary], tuple[object, ...]],
) -> tuple[tuple[tuple[object, ...], tuple[StratumSummary, ...]], ...]:
    grouped: dict[tuple[object, ...], list[StratumSummary]] = {}
    for stratum in strata:
        grouped.setdefault(key(stratum), []).append(stratum)
    return tuple(
        (group, tuple(sorted(items, key=lambda item: item.key.sort_key())))
        for group, items in sorted(grouped.items(), key=lambda item: repr(item[0]))
    )


def _axes_grid(
    rows: int,
    columns: int,
    *,
    width: float,
    height: float,
) -> tuple[matplotlib.figure.Figure, np.ndarray]:
    figure, axes = plt.subplots(
        rows,
        columns,
        figsize=(width * columns, height * rows),
        squeeze=False,
    )
    return figure, axes


def _bootstrap_median(
    values: Sequence[int],
    summary: Summary,
    identity: str,
) -> tuple[float, float, float]:
    data = np.asarray(values, dtype=np.float64)
    digest = hashlib.sha256(
        canonical_json_bytes([summary.bootstrap_seed, identity])
    ).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    selected = data[
        rng.integers(
            0,
            data.size,
            size=(summary.bootstrap_samples, data.size),
        )
    ]
    estimates = np.median(selected, axis=1)
    alpha = (1.0 - summary.bootstrap_confidence) / 2.0
    low, high = np.quantile(estimates, [alpha, 1.0 - alpha])
    return float(np.median(data)), float(low), float(high)


def _plot_interval_series(
    axis: matplotlib.axes.Axes,
    x: Sequence[float],
    center: Sequence[float],
    low: Sequence[float],
    high: Sequence[float],
    method: str,
    *,
    label: str | None = None,
) -> None:
    style = _STYLES[method]
    axis.plot(x, center, label=label or _DISPLAY[method], **style)
    axis.fill_between(x, low, high, color=style["color"], alpha=0.16)


def _queries_figure(
    summary: Summary,
    caption: str,
) -> tuple[matplotlib.figure.Figure, tuple[str, ...]]:
    groups = _groups(
        summary.strata,
        lambda item: (
            item.key.system_name,
            item.key.hilbert_dimension,
            item.key.gap,
            item.key.shots,
        ),
    )
    figure, axes = _axes_grid(len(groups), 2, width=4.2, height=2.7)
    panel_strata: list[str] = []
    for row, (_, strata) in enumerate(groups):
        panel_strata.extend(_stratum_id(item) for item in strata)
        x = [item.key.search_dimension for item in strata]
        for name in _METHODS:
            query_rows = [
                _bootstrap_median(
                    _method(item, name).conditional_first_certified_queries,
                    summary,
                    f"{_stratum_id(item)}:{name}:conditional-query",
                )
                for item in strata
            ]
            _plot_interval_series(
                axes[row, 0],
                x,
                [item[0] for item in query_rows],
                [item[1] for item in query_rows],
                [item[2] for item in query_rows],
                name,
            )
            probabilities = [_method(item, name).success_probability for item in strata]
            _plot_interval_series(
                axes[row, 1],
                x,
                [item.value for item in probabilities],
                [item.low for item in probabilities],
                [item.high for item in probabilities],
                name,
            )
        key = strata[0].key
        facet = (
            f"{key.system_name}, d={key.hilbert_dimension}, gap={key.gap:g}, "
            f"shots={'exact' if key.shots is None else key.shots}"
        )
        axes[row, 0].set_title(facet)
        axes[row, 1].set_title(facet)
        axes[row, 0].set_xlabel("search dimension k [basis directions]")
        axes[row, 1].set_xlabel("search dimension k [basis directions]")
        axes[row, 0].set_ylabel(
            "first independently certified optimizer queries [count]"
        )
        axes[row, 1].set_ylabel("success probability within budget [fraction]")
        axes[row, 1].set_ylim(-0.03, 1.03)
        axes[row, 0].legend()
        axes[row, 1].legend()
    figure.suptitle("Certified query cost and success versus search dimension")
    _finish_figure(figure, caption)
    return figure, tuple(panel_strata)


def _advantage_figure(
    summary: Summary,
    caption: str,
) -> tuple[matplotlib.figure.Figure, tuple[str, ...]]:
    groups = _groups(
        summary.strata,
        lambda item: (
            item.key.system_name,
            item.key.hilbert_dimension,
            item.key.search_dimension,
            item.key.shots,
        ),
    )
    figure, axes = _axes_grid(len(groups), 3, width=3.8, height=2.7)
    panel_strata: list[str] = []
    metrics = (
        ("censored_query_difference", "paired query advantage\nbaseline − model [queries]"),
        ("total_shot_difference", "paired shot advantage\nbaseline − model [shots]"),
        (
            "success_probability_difference",
            "paired success advantage\nmodel − baseline [probability]",
        ),
    )
    for row, (_, strata) in enumerate(groups):
        panel_strata.extend(_stratum_id(item) for item in strata)
        x = [abs(item.key.gap) / item.key.amplitude_bound for item in strata]
        for baseline in _BASELINES:
            pairs = [
                next(
                    item
                    for item in stratum.paired_differences
                    if item.baseline == baseline
                )
                for stratum in strata
            ]
            for column, (field, _) in enumerate(metrics):
                intervals = [getattr(item, field) for item in pairs]
                _plot_interval_series(
                    axes[row, column],
                    x,
                    [item.estimate for item in intervals],
                    [item.low for item in intervals],
                    [item.high for item in intervals],
                    baseline,
                )
        key = strata[0].key
        facet = (
            f"{key.system_name}, d={key.hilbert_dimension}, "
            f"k={key.search_dimension}, "
            f"shots={'exact' if key.shots is None else key.shots}"
        )
        for column, (_, ylabel) in enumerate(metrics):
            axes[row, column].axhline(0.0, color="#666666", linewidth=0.8)
            axes[row, column].set_title(facet)
            axes[row, column].set_xlabel(
                "normalized gap |device gap| / amplitude bound [dimensionless]"
            )
            axes[row, column].set_ylabel(ylabel)
            axes[row, column].legend()
    figure.suptitle("Paired Model-Hessian advantage versus normalized gap")
    _finish_figure(figure, caption)
    return figure, tuple(panel_strata)


def _positive_log_values(values: Sequence[float]) -> tuple[np.ndarray, float]:
    data = np.asarray(values, dtype=np.float64)
    positive = data[data > 0.0]
    epsilon = (
        float(np.min(positive)) / 10.0
        if positive.size
        else float(np.finfo(np.float64).tiny)
    )
    return np.maximum(data, epsilon), epsilon


def _subspace_figure(
    summary: Summary,
    caption: str,
) -> tuple[matplotlib.figure.Figure, tuple[str, ...]]:
    groups = _groups(
        summary.strata,
        lambda item: (
            item.key.system_name,
            item.key.hilbert_dimension,
            item.key.search_dimension,
            item.key.shots,
        ),
    )
    figure, axes = _axes_grid(len(groups), 2, width=4.4, height=2.7)
    panel_strata: list[str] = []
    for row, (_, strata) in enumerate(groups):
        panel_strata.extend(_stratum_id(item) for item in strata)
        x = [abs(item.key.gap) / item.key.amplitude_bound for item in strata]
        all_floors = [
            _method(item, name).median_attained_infidelity_upper_bound
            for item in strata
            for name in _METHODS
        ]
        _, epsilon = _positive_log_values(
            [float(item) for item in all_floors if item is not None]
        )
        for name in _METHODS:
            for angle_index in range(strata[0].key.search_dimension):
                angle_values = [
                    (_method(item, name).median_principal_angles or ())[angle_index]
                    for item in strata
                ]
                angle_style = dict(_STYLES[name])
                angle_style["linestyle"] = ("-", "--", ":", "-.")[
                    angle_index % 4
                ]
                axes[row, 0].plot(
                    x,
                    angle_values,
                    label=f"{_DISPLAY[name]} θ{angle_index + 1}",
                    **angle_style,
                )
            floors = np.maximum(
                [
                    float(
                        _method(item, name).median_attained_infidelity_upper_bound
                    )
                    for item in strata
                ],
                epsilon,
            )
            axes[row, 1].plot(
                x,
                floors,
                label=_DISPLAY[name],
                **_STYLES[name],
            )
        key = strata[0].key
        facet = (
            f"{key.system_name}, d={key.hilbert_dimension}, "
            f"k={key.search_dimension}, "
            f"shots={'exact' if key.shots is None else key.shots}"
        )
        for axis in axes[row]:
            axis.set_title(facet)
            axis.set_xlabel(
                "normalized gap |device gap| / amplitude bound [dimensionless]"
            )
            axis.legend()
        axes[row, 0].set_ylabel("target-k principal angles θᵢ [radians]")
        axes[row, 1].set_ylabel(
            "attained restricted infidelity upper bound "
            f"max(I, ε), ε={epsilon:.1e} [dimensionless]"
        )
        axes[row, 1].set_yscale("log")
        axes[row, 1].axhline(
            _TARGET_INFIDELITY,
            color="#CC79A7",
            linestyle="--",
            label="restricted target I ≤ 1−0.999",
        )
        axes[row, 1].legend()
    figure.suptitle("Target-k subspace rotation and restricted fidelity floor")
    _finish_figure(figure, caption)
    return figure, tuple(panel_strata)


def _rank_figure(
    summary: Summary,
    caption: str,
) -> tuple[matplotlib.figure.Figure, tuple[str, ...]]:
    strata = tuple(
        item for item in summary.strata if item.key.hilbert_dimension in {2, 4}
    )
    figure, axes = _axes_grid(len(strata), 2, width=4.4, height=2.6)
    panel_strata: list[str] = []
    threshold_positions = np.arange(len(_RANK_THRESHOLDS), dtype=np.float64)
    for row, stratum in enumerate(strata):
        panel_strata.append(_stratum_id(stratum))
        model = _method(stratum, "model_hessian")
        axes[row, 0].plot(
            threshold_positions,
            model.median_model_effective_ranks,
            color=_STYLES["model_hessian"]["color"],
            marker="o",
            label="Model effective rank",
        )
        axes[row, 0].plot(
            threshold_positions,
            model.median_truth_effective_ranks,
            color="#D55E00",
            marker="s",
            linestyle="--",
            label="Truth effective rank",
        )
        expected = 3 if stratum.key.hilbert_dimension == 2 else 15
        axes[row, 0].axhline(
            expected,
            color="#666666",
            linestyle=":",
            label=f"Expected invariant rank {expected}",
        )
        signed = model.median_signed_eigenvalue_gaps or ()
        components = np.arange(1, len(signed) + 1)
        axes[row, 1].plot(
            components,
            signed,
            color=_STYLES["model_hessian"]["color"],
            marker="o",
            label="Model-Hessian signed leading gaps",
        )
        axes[row, 1].axhline(0.0, color="#666666", linewidth=0.8, label="zero")
        facet = _stratum_id(stratum)
        axes[row, 0].set_title(facet)
        axes[row, 1].set_title(facet)
        axes[row, 0].set_xticks(
            threshold_positions,
            [f"{item:.0e}" for item in _RANK_THRESHOLDS],
        )
        axes[row, 0].set_xlabel(
            "relative threshold τ in |λ| > τ max|λ| [dimensionless]"
        )
        axes[row, 0].set_ylabel("effective Hessian rank [count]")
        axes[row, 1].set_xlabel("target-k eigenvalue index [count]")
        axes[row, 1].set_ylabel("signed leading eigenvalue gap [curvature units]")
        axes[row, 0].legend()
        axes[row, 1].legend()
    figure.suptitle("d=2 and d=4 Hessian rank invariants")
    _finish_figure(figure, caption)
    return figure, tuple(panel_strata)


def _failure_reason(stratum: StratumSummary) -> str | None:
    model = _method(stratum, "model_hessian")
    reasons: list[str] = []
    attained = model.median_attained_infidelity_upper_bound
    if attained is not None and attained > _TARGET_INFIDELITY:
        reasons.append(
            "restricted attained infidelity "
            f"{attained:.3g} exceeds target {_TARGET_INFIDELITY:.3g}"
        )
    for pair in stratum.paired_differences:
        if pair.censored_query_difference.estimate < 0.0:
            reasons.append(f"query disadvantage versus {_DISPLAY[pair.baseline]}")
        if pair.total_shot_difference.estimate < 0.0:
            reasons.append(f"shot disadvantage versus {_DISPLAY[pair.baseline]}")
        if pair.success_probability_difference.estimate < 0.0:
            reasons.append(f"success disadvantage versus {_DISPLAY[pair.baseline]}")
    return "; ".join(reasons) if reasons else None


def _select_failure(summary: Summary) -> tuple[StratumSummary, str]:
    candidates = [
        (item, reason)
        for item in summary.strata
        if (reason := _failure_reason(item)) is not None
    ]
    if not candidates:
        raise FigureError(
            "no qualifying production failure: Model Hessian has no paired "
            "query/shot/success disadvantage and all restricted attained "
            "infidelity upper bounds meet 1−0.999"
        )
    return min(candidates, key=lambda item: item[0].key.sort_key())


def _failure_figure(
    stratum: StratumSummary,
    reason: str,
    caption: str,
) -> tuple[matplotlib.figure.Figure, tuple[str, ...]]:
    figure, axes = _axes_grid(1, 4, width=3.5, height=3.1)
    names = list(_METHODS)
    positions = np.arange(len(names))
    colors = [_STYLES[name]["color"] for name in names]
    labels = [_DISPLAY[name] for name in names]
    queries = [
        float(np.median(_method(stratum, name).censored_first_certified_queries))
        for name in names
    ]
    shots = [
        float(np.median(_method(stratum, name).total_shots_by_trial))
        for name in names
    ]
    success = [_method(stratum, name).success_probability.value for name in names]
    floors_raw = [
        float(_method(stratum, name).median_attained_infidelity_upper_bound)
        for name in names
    ]
    floors, epsilon = _positive_log_values(floors_raw)
    values = (queries, shots, success, floors)
    ylabels = (
        "right-censored first certified query [optimizer queries]",
        "total optimizer + validation shots [shots]",
        "success probability within budget [fraction]",
        f"restricted infidelity max(I, ε), ε={epsilon:.1e} [dimensionless]",
    )
    for column, axis in enumerate(axes[0]):
        for index, name in enumerate(names):
            axis.bar(
                positions[index],
                values[column][index],
                color=colors[index],
                label=labels[index],
            )
        axis.set_xticks(positions, labels, rotation=25, ha="right")
        axis.set_xlabel("search method [fixed production method]")
        axis.set_ylabel(ylabels[column])
        axis.legend(fontsize=6)
    axes[0, 2].set_ylim(0.0, 1.05)
    axes[0, 3].set_yscale("log")
    axes[0, 3].axhline(
        _TARGET_INFIDELITY,
        color="#CC79A7",
        linestyle="--",
        label="target I ≤ 1−0.999",
    )
    axes[0, 3].legend(fontsize=6)
    figure.suptitle(f"Observed production failure: {_stratum_id(stratum)}\n{reason}")
    _finish_figure(figure, caption)
    return figure, (_stratum_id(stratum),)


def _strip_png_metadata(payload: bytes) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    if not payload.startswith(signature):
        raise FigureError("matplotlib did not produce a PNG")
    output = bytearray(signature)
    offset = len(signature)
    while offset < len(payload):
        if offset + 12 > len(payload):
            raise FigureError("truncated PNG output")
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        stop = offset + 12 + length
        if stop > len(payload):
            raise FigureError("truncated PNG chunk")
        data = payload[offset + 8 : offset + 8 + length]
        if chunk_type[0] & 0x20 == 0:
            output.extend(struct.pack(">I", length))
            output.extend(chunk_type)
            output.extend(data)
            output.extend(
                struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
            )
        offset = stop
        if chunk_type == b"IEND":
            break
    return bytes(output)


def _save_png(figure: matplotlib.figure.Figure, path: Path) -> str:
    buffer = io.BytesIO()
    figure.savefig(
        buffer,
        format="png",
        dpi=120,
        facecolor="white",
        metadata={},
    )
    payload = _strip_png_metadata(buffer.getvalue())
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def render_publication_figures(
    summary: Summary,
    output_directory: str | Path,
    *,
    source: str,
    config: str,
    run_id: str,
) -> FigureManifest:
    """Render all required deterministic figures from a strict canonical Summary."""
    for name, value in (("source", source), ("config", config), ("run_id", run_id)):
        if not isinstance(value, str) or not value.strip():
            raise FigureError(f"{name} caption must be a nonempty string")
    canonical = _strict_summary(summary)
    summary_digest = hashlib.sha256(
        canonical_json_bytes(summary.canonical_dict())
    ).hexdigest()
    failure, failure_reason = _select_failure(canonical)
    output = Path(output_directory)
    if output.exists() and not output.is_dir():
        raise FigureError("figure output path must be a directory")
    output.mkdir(parents=True, exist_ok=True)
    caption = _caption(canonical, source, config, run_id)
    builders: tuple[
        tuple[
            str,
            Callable[
                [],
                tuple[matplotlib.figure.Figure, tuple[str, ...]],
            ],
        ],
        ...,
    ] = (
        (_FILENAMES[0], lambda: _queries_figure(canonical, caption)),
        (_FILENAMES[1], lambda: _advantage_figure(canonical, caption)),
        (_FILENAMES[2], lambda: _subspace_figure(canonical, caption)),
        (_FILENAMES[3], lambda: _rank_figure(canonical, caption)),
        (
            _FILENAMES[4],
            lambda: _failure_figure(failure, failure_reason, caption),
        ),
    )
    entries: list[FigureManifestEntry] = []
    with matplotlib.rc_context(_RC):
        for filename, builder in builders:
            figure: matplotlib.figure.Figure | None = None
            try:
                figure, panel_strata = builder()
                if not figure.axes or any(not axis.has_data() for axis in figure.axes):
                    raise FigureError(f"{filename} contains an empty panel")
                digest = _save_png(figure, output / filename)
            finally:
                if figure is not None:
                    plt.close(figure)
            entries.append(
                FigureManifestEntry(
                    filename=filename,
                    panel_strata=panel_strata,
                    sha256=digest,
                    failure_reason=(
                        failure_reason if filename == "failure_case.png" else None
                    ),
                )
            )
    manifest = FigureManifest(
        summary_sha256=summary_digest,
        matplotlib_version=matplotlib.__version__,
        numpy_version=np.__version__,
        figures=tuple(entries),
    )
    (output / "figure_manifest.json").write_bytes(
        canonical_json_bytes(manifest.canonical_dict())
    )
    return manifest
