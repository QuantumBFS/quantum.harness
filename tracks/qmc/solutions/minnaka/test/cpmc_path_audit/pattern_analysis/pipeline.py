"""End-to-end CPMC important-path pattern analysis."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
import pathlib
import subprocess
from typing import Iterable

import numpy as np
import pandas as pd

from .counterfactual import build_m4_counterfactual
from .mechanisms import (
    attribute_events,
    join_critical_mask_predictions,
)
from .models import (
    fit_shallow_tree,
    fit_sparse_logistic,
    grouped_fold,
    precision_recall_auc,
    roc_auc,
)
from .path_records import PathHeader, open_path_records
from .patterns import (
    canonical_mask,
    canonical_path,
    decode_masks,
    mask_class,
    site_permutations_2x2,
    spatial_components,
    trial_preserving_permutations_2x2,
)
from .plotting import create_all_figures
from .report import write_pattern_report
from .selection import build_trial_selection
from .statistics import (
    bit_itemset_table,
    connected_itemset_table,
    fourth_order_parity_table,
    motif_tables,
)


@dataclass(frozen=True)
class AnalysisConfig:
    m6_results: pathlib.Path
    m4_results: pathlib.Path
    output: pathlib.Path
    executable: pathlib.Path
    trials: tuple[str, ...] = ("rhf_x", "rhf_y", "uhf")
    fraction: float = 0.01
    progress_updates: int = 20


def _progress(message: str) -> None:
    print(message, flush=True)


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: pathlib.Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _m6_path(config: AnalysisConfig, trial: str) -> pathlib.Path:
    return config.m6_results / f"paths_{trial}_site_row.bin"


def maximum_scaled_ratio_residual(site_steps: pd.DataFrame) -> float:
    """Return the largest determinant-lemma error on a mixed abs/rel scale."""

    ratio_columns = [
        "predicted_r_plus",
        "predicted_r_minus",
        "direct_r_plus",
        "direct_r_minus",
    ]
    scale = np.maximum(
        1.0,
        site_steps[ratio_columns].abs().max(axis=1).to_numpy(dtype=float),
    )
    residual = site_steps["ratio_residual"].to_numpy(dtype=float)
    if not len(residual):
        return math.nan
    return float(np.max(residual / scale))


def mark_counterfactual_selection(
    table: pd.DataFrame, fraction: float = 0.01
) -> pd.DataFrame:
    """Mark the exact row-proposal worst tail and its physical-weight bins."""

    if not 0.0 < fraction <= 1.0:
        raise ValueError("fraction must lie in (0,1]")
    result = table.copy()
    result["score_row"] = math.nan
    result["log_d_over_mean"] = math.nan
    result["d_over_mean"] = math.nan
    result["weight_bin"] = ""
    result["worst_1pct"] = False
    result["relevant_worst_1pct"] = False
    result["important_worst_1pct"] = False
    for _, group in result.groupby("trial", sort=False):
        indices = group.index.to_numpy()
        log_d = group["log_d_row"].to_numpy(dtype=float)
        log_q = group["log_q_row"].to_numpy(dtype=float)
        maximum = float(np.max(log_d))
        log_total = maximum + math.log(
            float(np.exp(log_d - maximum).sum())
        )
        log_ratio = log_d - (log_total - math.log(len(group)))
        scores = (log_d - log_total - log_q) / math.log(10.0)
        count = int(math.ceil(fraction * len(group)))
        order = np.lexsort(
            (
                group["config_id"].to_numpy(dtype=np.uint64),
                -scores,
            )
        )
        worst = np.zeros(len(group), dtype=bool)
        worst[order[:count]] = True
        bins = np.select(
            [
                log_ratio < math.log(0.5),
                log_ratio < 0.0,
                log_ratio < math.log(2.0),
            ],
            [
                "below_half",
                "near_average",
                "important",
            ],
            default="strongly_important",
        )
        result.loc[indices, "score_row"] = scores
        result.loc[indices, "log_d_over_mean"] = log_ratio
        result.loc[indices, "d_over_mean"] = np.exp(log_ratio)
        result.loc[indices, "weight_bin"] = bins
        result.loc[indices, "worst_1pct"] = worst
        result.loc[indices, "relevant_worst_1pct"] = (
            worst & (log_ratio >= math.log(0.5))
        )
        result.loc[indices, "important_worst_1pct"] = (
            worst & (log_ratio >= 0.0)
        )
    return result


def _all_input_paths(config: AnalysisConfig) -> list[pathlib.Path]:
    paths = [_m6_path(config, trial) for trial in config.trials]
    for trial in config.trials:
        paths.extend(
            [
                config.m4_results / f"paths_{trial}_site_row.bin",
                config.m4_results / f"paths_{trial}_site_reverse.bin",
                config.m4_results / f"paths_{trial}_site_sublattice.bin",
                config.m4_results / f"paths_{trial}_joint_na.bin",
            ]
        )
    return paths


def _path_identifier(row: pd.Series) -> str:
    role_names = {
        "case": "case",
        "control": "control",
        "low_weight_reference": "lowref",
        "worst_low": "worst",
    }
    role = role_names[str(row["role"])]
    if row["role"] in ("control", "low_weight_reference"):
        suffix = f"{int(row['case_id'])}_{int(row['config_id'])}"
    else:
        suffix = str(int(row["config_id"]))
    return f"{row['trial']}_{role}_{suffix}"


def _build_selection(
    config: AnalysisConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, PathHeader]]:
    selections = []
    headers = {}
    summaries = []
    for trial in config.trials:
        source = _m6_path(config, trial)
        header, _ = open_path_records(source)
        headers[trial] = header
        table = build_trial_selection(str(source), config.fraction)
        table["path_id"] = table.apply(_path_identifier, axis=1)
        selections.append(table)
        worst = table.loc[table["role"].isin(["case", "worst_low"])]
        bins = worst.groupby("weight_bin").size()
        summaries.append(
            {
                "trial": trial,
                "total_records": header.actual_records,
                "worst_count": len(worst),
                "below_half": int(bins.get("below_half", 0)),
                "near_average": int(bins.get("near_average", 0)),
                "important": int(bins.get("important", 0)),
                "strongly_important": int(
                    bins.get("strongly_important", 0)
                ),
                "important_cumulative": int(
                    bins.get("important", 0)
                    + bins.get("strongly_important", 0)
                ),
                "cutoff_score": float(worst["cutoff_score"].iloc[0]),
                "cutoff_tie_count": int(
                    worst["cutoff_tie_count"].iloc[0]
                ),
            }
        )
        _progress(
            f"selection {trial}: {len(worst)} worst paths, "
            f"{int((worst.d_over_mean >= 0.5).sum())} replay cases"
        )
    return (
        pd.concat(selections, ignore_index=True),
        pd.DataFrame.from_records(summaries),
        headers,
    )


def _write_manifests(
    config: AnalysisConfig, selection: pd.DataFrame
) -> dict[str, pathlib.Path]:
    paths = {}
    replay_roles = {"case", "control", "low_weight_reference"}
    for trial in config.trials:
        table = selection.loc[
            (selection["trial"] == trial)
            & selection["role"].isin(replay_roles)
        ].copy()
        manifest = pd.DataFrame(
            {
                "path_id": table["path_id"],
                "role": table["role"],
                "case_id": table["case_id"].astype(np.uint64),
                "config_id": table["config_id"].astype(np.uint64),
                "fields_file": "",
                "score": table["score"],
                "log_d_over_mean": table["log_d_over_mean"],
                "weight_bin": table["weight_bin"],
            }
        )
        path = config.output / f"manifest_{trial}.csv"
        manifest.to_csv(path, index=False)
        paths[trial] = path
    return paths


def _run_batch_replay(
    config: AnalysisConfig,
    headers: dict[str, PathHeader],
    manifests: dict[str, pathlib.Path],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    steps = []
    masks = []
    environment = _oneapi_environment()
    for trial in config.trials:
        header = headers[trial]
        steps_path = config.output / f"steps_{trial}.csv"
        masks_path = config.output / f"mask_predictions_{trial}.csv"
        command = [
            str(config.executable.resolve()),
            "batch-replay",
            "--lx",
            str(header.lx),
            "--ly",
            str(header.ly),
            "--n-up",
            str(header.n_up),
            "--n-down",
            str(header.n_down),
            "--t",
            str(header.hopping),
            "--u",
            str(header.interaction),
            "--dt",
            str(header.dt),
            "--slices",
            str(header.slices),
            "--trial",
            trial,
            "--proposal",
            "site",
            "--order",
            "row",
            "--manifest",
            str(manifests[trial].resolve()),
            "--steps-output",
            str(steps_path.resolve()),
            "--masks-output",
            str(masks_path.resolve()),
            "--progress-updates",
            str(config.progress_updates),
        ]
        _progress(f"batch replay {trial}: {manifests[trial].name}")
        subprocess.run(command, check=True, env=environment)
        step_table = pd.read_csv(steps_path)
        mask_table = pd.read_csv(masks_path)
        step_table.insert(0, "trial", trial)
        mask_table.insert(0, "trial", trial)
        steps.append(step_table)
        masks.append(mask_table)
    return pd.concat(steps, ignore_index=True), pd.concat(
        masks, ignore_index=True
    )


def _oneapi_environment() -> dict[str, str]:
    """Load the MKL runtime for C++ children without replacing Python."""

    if os.environ.get("MKLROOT") and os.environ.get("LD_LIBRARY_PATH"):
        return os.environ.copy()
    setup = pathlib.Path("/opt/intel/oneapi/setvars.sh")
    if not setup.exists():
        raise FileNotFoundError(setup)
    completed = subprocess.run(
        [
            "bash",
            "-c",
            "source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1 && env -0",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    environment = os.environ.copy()
    for item in completed.stdout.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        environment[key.decode()] = value.decode()
    return environment


def _comparison_groups(
    replay: pd.DataFrame,
) -> Iterable[tuple[str, pd.DataFrame, pd.DataFrame]]:
    cases = replay.loc[replay["role"] == "case"]
    controls = replay.loc[replay["role"] == "control"]
    yield "all_relevant", cases, controls
    for weight_bin in (
        "near_average",
        "important",
        "strongly_important",
    ):
        case_bin = cases.loc[cases["weight_bin"] == weight_bin]
        control_bin = controls.loc[controls["weight_bin"] == weight_bin]
        if len(case_bin):
            yield weight_bin, case_bin, control_bin
    references = replay.loc[replay["role"] == "low_weight_reference"]
    if len(cases) and len(references):
        yield "important_vs_low_reference", cases, references


def _decorate_slice_motifs(
    table: pd.DataFrame, trial: str
) -> pd.DataFrame:
    full = site_permutations_2x2()
    preserving = trial_preserving_permutations_2x2(trial)
    result = table.copy()
    result["mask_class"] = [
        mask_class(int(mask)) for mask in result["mask"]
    ]
    result["full_orbit"] = [
        canonical_mask(int(mask), full, allow_global_flip=True)
        for mask in result["mask"]
    ]
    result["trial_orbit"] = [
        canonical_mask(int(mask), preserving)
        for mask in result["mask"]
    ]
    return result


def _motif_analysis(
    selection: pd.DataFrame, headers: dict[str, PathHeader]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    slice_rows = []
    transition_rows = []
    interaction_rows = []
    replay = selection.loc[
        selection["role"].isin(
            ["case", "control", "low_weight_reference"]
        )
    ]
    for trial in selection["trial"].drop_duplicates():
        trial_replay = replay.loc[replay["trial"] == trial]
        slices = headers[str(trial)].slices
        bits = slices * 4
        for comparison, cases, controls in _comparison_groups(trial_replay):
            if len(cases) != len(controls):
                raise ValueError(
                    f"{trial} {comparison} is not one-to-one"
                )
            case_ids = cases["config_id"].to_numpy(dtype=np.uint64)
            control_ids = controls["config_id"].to_numpy(dtype=np.uint64)
            case_masks = decode_masks(case_ids, slices, 4)
            control_masks = decode_masks(control_ids, slices, 4)
            motifs = motif_tables(case_masks, control_masks)
            slice_table = _decorate_slice_motifs(
                motifs["slice"], str(trial)
            )
            slice_table.insert(0, "comparison", comparison)
            slice_table.insert(0, "trial", trial)
            slice_rows.append(slice_table)
            for order, name in ((2, "pair"), (3, "triple")):
                table = motifs[name].copy()
                table.insert(0, "motif_order", order)
                table.insert(0, "comparison", comparison)
                table.insert(0, "trial", trial)
                transition_rows.append(table)
            bit_table = bit_itemset_table(
                case_ids, control_ids, bits=bits, max_order=3
            )
            bit_table.insert(0, "interaction_type", "all_plus_itemset")
            bit_table.insert(0, "comparison", comparison)
            bit_table.insert(0, "trial", trial)
            interaction_rows.append(bit_table)
            if comparison == "all_relevant":
                parity = fourth_order_parity_table(
                    case_ids, control_ids, bits=bits
                )
                parity.insert(0, "interaction_type", "fourth_parity")
                parity.insert(0, "comparison", comparison)
                parity.insert(0, "trial", trial)
                interaction_rows.append(parity)
                connected = connected_itemset_table(
                    case_ids,
                    control_ids,
                    slices=slices,
                    sites=4,
                    lx=2,
                    ly=2,
                    max_size=min(6, bits),
                    min_support=0.001,
                )
                connected.insert(0, "interaction_type", "connected_itemset")
                connected.insert(0, "comparison", comparison)
                connected.insert(0, "trial", trial)
                interaction_rows.append(connected)
        _progress(f"motifs {trial}: complete")
    return (
        pd.concat(slice_rows, ignore_index=True),
        pd.concat(transition_rows, ignore_index=True),
        pd.concat(interaction_rows, ignore_index=True, sort=False),
    )


def _field_features(
    config_ids: np.ndarray, slices: int
) -> tuple[np.ndarray, list[str]]:
    ids = np.asarray(config_ids, dtype=np.uint64)
    bits = slices * 4
    bit_features = np.column_stack(
        [
            ((ids >> np.uint64(bits - 1 - position)) & 1).astype(float)
            for position in range(bits)
        ]
    )
    masks = decode_masks(ids, slices, 4)
    lookup = np.array(
        [
            list(spatial_components(mask).values())
            for mask in range(16)
        ],
        dtype=float,
    )
    components = lookup[masks].reshape(len(ids), -1)
    temporal_parts = []
    for slice_index in range(1, slices):
        previous = masks[:, slice_index - 1]
        current = masks[:, slice_index]
        hamming = np.array(
            [int(left ^ right).bit_count() for left, right in zip(previous, current)],
            dtype=float,
        )
        temporal_parts.extend(
            [
                hamming[:, None],
                (current == previous).astype(float)[:, None],
                (current == ((~previous) & 0xF)).astype(float)[:, None],
            ]
        )
    temporal = (
        np.hstack(temporal_parts)
        if temporal_parts
        else np.empty((len(ids), 0))
    )
    names = [f"bit_{position}" for position in range(bits)]
    component_names = ("uniform", "staggered", "x_stripe", "y_stripe")
    names.extend(
        f"slice_{slice_index}_{component}"
        for slice_index in range(slices)
        for component in component_names
    )
    names.extend(
        f"transition_{slice_index}_{feature}"
        for slice_index in range(1, slices)
        for feature in ("hamming", "repeat", "global_flip")
    )
    return np.hstack([bit_features, components, temporal]), names


def _dynamic_features(
    events: pd.DataFrame, path_ids: list[str]
) -> tuple[np.ndarray, list[str]]:
    site = events.loc[events["kind"] == "site"]
    grouped = events.groupby("path_id")
    site_grouped = site.groupby("path_id")
    sigma_min = events[["sigma_min_up", "sigma_min_down"]].min(axis=1)
    sigma_min.index = events["path_id"]
    table = pd.DataFrame(
        {
            "min_q": site_grouped["q_selected"].min(),
            "min_c": site_grouped["c_factor"].min(),
            "min_sigma": sigma_min.groupby(level=0).min(),
            "min_log_overlap": grouped["log_normalized_overlap"].min(),
            "min_log_w": grouped["cumulative_log_w"].min(),
            "final_log_w": grouped["cumulative_log_w"].last(),
            "max_angle_up": grouped["angle_max_up"].max(),
            "max_angle_down": grouped["angle_max_down"].max(),
            "max_ratio_residual": site_grouped["ratio_residual"].max(),
        }
    )
    table = table.reindex(path_ids)
    table = table.replace([np.inf, -np.inf], np.nan)
    table = table.fillna(table.median(numeric_only=True)).fillna(0.0)
    return table.to_numpy(dtype=float), table.columns.tolist()


def _model_analysis(
    selection: pd.DataFrame,
    events: pd.DataFrame,
    headers: dict[str, PathHeader],
) -> tuple[pd.DataFrame, str]:
    metric_rows = []
    rule_sections = []
    transforms = site_permutations_2x2()
    for trial in selection["trial"].drop_duplicates():
        data = selection.loc[
            (selection["trial"] == trial)
            & selection["role"].isin(["case", "control"])
        ].copy()
        if len(data) < 20:
            continue
        labels = (data["role"] == "case").to_numpy(dtype=float)
        config_ids = data["config_id"].to_numpy(dtype=np.uint64)
        slices = headers[str(trial)].slices
        field, field_names = _field_features(config_ids, slices)
        dynamic, dynamic_names = _dynamic_features(
            events.loc[events["trial"] == trial],
            data["path_id"].tolist(),
        )
        orbit_ids = np.array(
            [
                canonical_path(int(config_id), slices, transforms, True)
                for config_id in config_ids
            ],
            dtype=np.uint64,
        )
        grouped = grouped_fold(config_ids, orbit_ids, folds=5)
        ordered = np.argsort(config_ids, kind="stable")
        block = np.empty(len(config_ids), dtype=np.int16)
        block[ordered] = np.minimum(
            np.arange(len(config_ids)) * 5 // len(config_ids), 4
        )
        for feature_set, matrix, names in (
            ("field_only", field, field_names),
            (
                "field_dynamic",
                np.hstack([field, dynamic]),
                field_names + dynamic_names,
            ),
        ):
            for split_name, fold_values in (
                ("symmetry_grouped", grouped),
                ("config_block", block),
            ):
                for fold in range(5):
                    test = fold_values == fold
                    train = ~test
                    if (
                        test.sum() == 0
                        or len(np.unique(labels[test])) < 2
                        or len(np.unique(labels[train])) < 2
                    ):
                        continue
                    try:
                        logistic = fit_sparse_logistic(
                            matrix[train],
                            labels[train],
                            l1=0.01,
                            max_iter=3000,
                            tolerance=1.0e-6,
                        )
                        probability = logistic.predict_probability(
                            matrix[test]
                        )
                        metric_rows.append(
                            {
                                "trial": trial,
                                "feature_set": feature_set,
                                "model": "sparse_logistic",
                                "split": split_name,
                                "fold": fold,
                                "test_count": int(test.sum()),
                                "roc_auc": roc_auc(labels[test], probability),
                                "pr_auc": precision_recall_auc(
                                    labels[test], probability
                                ),
                            }
                        )
                    except RuntimeError:
                        pass
                    tree = fit_shallow_tree(
                        matrix[train],
                        labels[train],
                        names,
                        max_depth=3,
                        min_leaf=max(5, int(train.sum() * 0.01)),
                    )
                    probability = tree.predict_probability(matrix[test])
                    metric_rows.append(
                        {
                            "trial": trial,
                            "feature_set": feature_set,
                            "model": "shallow_tree",
                            "split": split_name,
                            "fold": fold,
                            "test_count": int(test.sum()),
                            "roc_auc": roc_auc(labels[test], probability),
                            "pr_auc": precision_recall_auc(
                                labels[test], probability
                            ),
                        }
                    )
            full_tree = fit_shallow_tree(
                matrix,
                labels,
                names,
                max_depth=3,
                min_leaf=max(5, int(len(labels) * 0.01)),
            )
            rule_sections.extend(
                [
                    f"[{trial} {feature_set} shallow_tree]",
                    full_tree.to_rules(),
                    "",
                ]
            )
    return pd.DataFrame.from_records(metric_rows), "\n".join(rule_sections)


def _decorate_counterfactual(
    table: pd.DataFrame, m4_results: pathlib.Path
) -> pd.DataFrame:
    result = mark_counterfactual_selection(table)
    decorated = []
    for trial, group in result.groupby("trial", sort=False):
        header, _ = open_path_records(
            m4_results / f"paths_{trial}_site_row.bin"
        )
        masks = decode_masks(
            group["config_id"].to_numpy(dtype=np.uint64),
            header.slices,
            4,
        )
        copy = group.copy()
        copy["contains_uniform"] = np.any(
            (masks == 0) | (masks == 15), axis=1
        )
        copy["contains_neel"] = np.any(
            (masks == 6) | (masks == 9), axis=1
        )
        copy["maximum_abs_uniform"] = [
            max(abs(spatial_components(int(mask))["uniform"]) for mask in path)
            for path in masks
        ]
        decorated.append(copy)
    return pd.concat(decorated, ignore_index=True)


def _export_representative_traces(
    summaries: pd.DataFrame,
    steps: pd.DataFrame,
    masks: pd.DataFrame,
    output: pathlib.Path,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    keys = ["trial", "weight_bin", "mechanism"]
    for _, group in summaries.groupby(keys, sort=True):
        selected = group.sort_values(
            ["score", "config_id"],
            ascending=[False, True],
        ).head(10)
        for row in selected.itertuples():
            stem = output / str(row.path_id)
            steps.loc[steps["path_id"] == row.path_id].to_csv(
                stem.with_name(stem.name + "_steps.csv"), index=False
            )
            masks.loc[masks["path_id"] == row.path_id].to_csv(
                stem.with_name(stem.name + "_masks.csv"), index=False
            )


def run_analysis(config: AnalysisConfig) -> None:
    """Run selection, detailed replay, patterns, models, plots, and report."""

    config.output.mkdir(parents=True, exist_ok=True)
    for path in _all_input_paths(config):
        if not path.exists():
            raise FileNotFoundError(path)
    if not config.executable.exists():
        raise FileNotFoundError(config.executable)
    checksums = {
        str(path.resolve()): _sha256(path)
        for path in _all_input_paths(config)
    }
    _atomic_json(config.output / "input_checksums.json", checksums)
    state = {"stage": "selection", "complete": False}
    _atomic_json(config.output / "run_state.json", state)

    selection, selection_summary, headers = _build_selection(config)
    worst = selection.loc[
        selection["role"].isin(["case", "worst_low"])
    ]
    replay = selection.loc[
        selection["role"].isin(
            ["case", "control", "low_weight_reference"]
        )
    ]
    selection_summary.to_csv(
        config.output / "selection_summary.csv", index=False
    )
    worst.to_csv(config.output / "worst1_all.csv", index=False)
    replay.to_csv(config.output / "cases_controls.csv", index=False)
    manifests = _write_manifests(config, selection)

    state["stage"] = "batch_replay"
    _atomic_json(config.output / "run_state.json", state)
    steps, masks = _run_batch_replay(config, headers, manifests)
    summaries, annotated_steps = attribute_events(replay, steps)
    case_metadata = replay.loc[
        replay["role"] == "case",
        [
            "path_id",
            "score",
            "config_id",
            "log_d",
            "log_d_over_mean",
            "d_over_mean",
        ],
    ]
    summaries = summaries.merge(
        case_metadata, on="path_id", how="left", validate="one_to_one"
    )
    predicted = join_critical_mask_predictions(summaries, masks)
    _export_representative_traces(
        summaries, annotated_steps, masks, config.output / "traces"
    )
    summaries.to_csv(config.output / "step_attribution.csv", index=False)
    orthogonality_columns = [
        column
        for column in summaries.columns
        if column
        in {
            "path_id",
            "trial",
            "case_id",
            "weight_bin",
            "score",
            "d_over_mean",
            "min_sigma_step",
            "min_sigma_spin",
            "minimum_sigma",
            "near_orthogonal",
            "scale_only",
            "recovery_step",
            "mechanism",
            "max_ratio_residual",
        }
    ]
    summaries[orthogonality_columns].to_csv(
        config.output / "orthogonality_diagnostics.csv", index=False
    )
    predicted.to_csv(
        config.output / "predicted_orthogonal_masks.csv", index=False
    )
    del steps
    del masks

    state["stage"] = "patterns"
    _atomic_json(config.output / "run_state.json", state)
    slice_motifs, transition_motifs, interactions = _motif_analysis(
        selection, headers
    )
    slice_motifs.to_csv(
        config.output / "slice_motif_enrichment.csv", index=False
    )
    transition_motifs.to_csv(
        config.output / "transition_motif_enrichment.csv", index=False
    )
    interactions.to_csv(
        config.output / "bit_interaction_enrichment.csv", index=False
    )

    state["stage"] = "counterfactual_models"
    _atomic_json(config.output / "run_state.json", state)
    counterfactual = _decorate_counterfactual(
        build_m4_counterfactual(config.m4_results, config.trials),
        config.m4_results,
    )
    counterfactual.to_csv(
        config.output / "counterfactual_m4.csv", index=False
    )
    model_metrics, model_rules = _model_analysis(
        selection, annotated_steps, headers
    )
    model_metrics.to_csv(config.output / "model_metrics.csv", index=False)
    (config.output / "model_rules.txt").write_text(
        model_rules, encoding="utf-8"
    )

    state["stage"] = "figures_report"
    _atomic_json(config.output / "run_state.json", state)
    create_all_figures(
        selection=selection,
        steps=annotated_steps,
        slice_motifs=slice_motifs,
        counterfactual=counterfactual,
        output_directory=config.output / "figures",
    )
    command = (
        "/usr/bin/python3 -u run_pattern_analysis.py "
        f"--m6-results {config.m6_results} "
        f"--m4-results {config.m4_results} "
        f"--output {config.output} --cpmc-audit {config.executable}"
    )
    write_pattern_report(
        selection_summary=selection_summary,
        path_summaries=summaries,
        predicted_masks=predicted,
        slice_motifs=slice_motifs,
        counterfactual=counterfactual,
        model_metrics=model_metrics,
        output=config.output / "PATTERN_REPORT.md",
        command=command,
    )
    state = {"stage": "complete", "complete": True}
    _atomic_json(config.output / "run_state.json", state)
    _progress(f"analysis complete: {config.output}")


def verify_analysis(config: AnalysisConfig) -> dict[str, object]:
    """Verify output schemas, path counts, diagnostics, and input checksums."""

    required = [
        "selection_summary.csv",
        "worst1_all.csv",
        "cases_controls.csv",
        "step_attribution.csv",
        "orthogonality_diagnostics.csv",
        "predicted_orthogonal_masks.csv",
        "slice_motif_enrichment.csv",
        "transition_motif_enrichment.csv",
        "bit_interaction_enrichment.csv",
        "counterfactual_m4.csv",
        "model_metrics.csv",
        "model_rules.txt",
        "PATTERN_REPORT.md",
    ]
    errors = [
        f"missing {name}"
        for name in required
        if not (config.output / name).exists()
    ]
    stored_checksums = json.loads(
        (config.output / "input_checksums.json").read_text(encoding="utf-8")
    )
    for raw_path, expected in stored_checksums.items():
        path = pathlib.Path(raw_path)
        if _sha256(path) != expected:
            errors.append(f"input checksum changed: {path}")
    summary = pd.read_csv(config.output / "selection_summary.csv")
    for row in summary.itertuples():
        expected = math.ceil(config.fraction * row.total_records)
        if row.worst_count != expected:
            errors.append(
                f"{row.trial} worst count {row.worst_count} != {expected}"
            )
    replay = pd.read_csv(config.output / "cases_controls.csv")
    for trial, group in replay.groupby("trial"):
        cases = group.loc[group["role"] == "case"]
        controls = group.loc[group["role"] == "control"]
        references = group.loc[group["role"] == "low_weight_reference"]
        if not (
            len(cases) == len(controls) == len(references)
            and controls["config_id"].is_unique
            and references["config_id"].is_unique
        ):
            errors.append(f"{trial} replay matching is not one-to-one")
        header, _ = open_path_records(_m6_path(config, str(trial)))
        steps = pd.read_csv(config.output / f"steps_{trial}.csv")
        counts = steps.groupby("path_id").size()
        expected_events = header.slices * (header.lx * header.ly + 2)
        if len(counts) != len(group) or not (counts == expected_events).all():
            errors.append(f"{trial} detailed event count mismatch")
        site_steps = steps.loc[steps["kind"] == "site"]
        site_residual = maximum_scaled_ratio_residual(site_steps)
        if not np.isfinite(site_residual) or site_residual > 1.0e-10:
            errors.append(
                f"{trial} scaled determinant-lemma residual "
                f"{site_residual}"
            )
        masks = pd.read_csv(
            config.output / f"mask_predictions_{trial}.csv"
        )
        if len(masks) != len(group) * header.slices:
            errors.append(f"{trial} mask prediction count mismatch")
    figure_paths = list((config.output / "figures").glob("*.pdf")) + list(
        (config.output / "figures").glob("*.png")
    )
    if len(figure_paths) != 12 or any(path.stat().st_size == 0 for path in figure_paths):
        errors.append("expected six nonempty PDF/PNG figure pairs")
    return {"valid": not errors, "errors": errors}
