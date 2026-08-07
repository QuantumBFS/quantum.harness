"""Fixed-physical-weight comparisons among CPMC proposal factorizations."""

from __future__ import annotations

import math
import pathlib

import numpy as np
import pandas as pd

from .path_records import open_path_records


LN10 = math.log(10.0)


def _prepare_variant(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    required = {"config_id", "log_d", "log_q"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{name} frame misses columns: {sorted(missing)}")
    if frame["config_id"].duplicated().any():
        raise ValueError(f"{name} frame has duplicate config_id")
    return frame[["config_id", "log_d", "log_q"]].rename(
        columns={
            "log_d": f"log_d_{name}",
            "log_q": f"log_q_{name}",
        }
    )


def compare_proposals(
    *,
    row: pd.DataFrame,
    reverse: pd.DataFrame,
    sublattice: pd.DataFrame,
    joint: pd.DataFrame,
    tolerance: float = 1.0e-9,
) -> pd.DataFrame:
    """Join proposal variants and compare Q while holding path D fixed."""

    result = _prepare_variant(row, "row")
    for name, frame in (
        ("reverse", reverse),
        ("sublattice", sublattice),
        ("joint", joint),
    ):
        result = result.merge(
            _prepare_variant(frame, name),
            on="config_id",
            how="outer",
            validate="one_to_one",
            indicator=True,
        )
        if not (result["_merge"] == "both").all():
            raise ValueError(f"{name} config_id set differs from row")
        result = result.drop(columns="_merge")

    for name in ("reverse", "sublattice", "joint"):
        residual = np.abs(
            result[f"log_d_{name}"].to_numpy(dtype=float)
            - result["log_d_row"].to_numpy(dtype=float)
        )
        if len(residual) and float(np.max(residual)) > tolerance:
            raise ValueError(
                f"{name} physical log D differs from row by "
                f"{float(np.max(residual))}"
            )
        result[f"delta_log_q_{name}"] = (
            result[f"log_q_{name}"] - result["log_q_row"]
        )
        result[f"score_improvement_{name}"] = (
            result[f"delta_log_q_{name}"] / LN10
        )
    return result.sort_values("config_id").reset_index(drop=True)


def _frame_from_path(path: pathlib.Path) -> tuple[str, pd.DataFrame]:
    header, records = open_path_records(path)
    frame = pd.DataFrame(
        {
            "config_id": np.asarray(records["config_id"]),
            "log_d": np.asarray(records["log_d"]),
            "log_q": np.asarray(records["log_q"]),
        }
    )
    return header.trial, frame


def build_m4_counterfactual(
    results_directory: pathlib.Path | str,
    trials: tuple[str, ...] = ("rhf_x", "rhf_y", "uhf"),
) -> pd.DataFrame:
    """Load all four proposal variants for every requested trial."""

    root = pathlib.Path(results_directory)
    rows = []
    for trial in trials:
        paths = {
            "row": root / f"paths_{trial}_site_row.bin",
            "reverse": root / f"paths_{trial}_site_reverse.bin",
            "sublattice": root / f"paths_{trial}_site_sublattice.bin",
            "joint": root / f"paths_{trial}_joint_na.bin",
        }
        missing = [str(path) for path in paths.values() if not path.exists()]
        if missing:
            raise FileNotFoundError(
                "missing counterfactual path files: " + ", ".join(missing)
            )
        frames = {}
        for name, path in paths.items():
            path_trial, frame = _frame_from_path(path)
            if path_trial != trial:
                raise ValueError(f"trial mismatch in {path}")
            frames[name] = frame
        compared = compare_proposals(**frames)
        compared.insert(0, "trial", trial)
        rows.append(compared)
    return pd.concat(rows, ignore_index=True)
