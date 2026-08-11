"""Run aggregation, Casimir extraction, and resolution-flow inference."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from .clean_ising import critical_ground_energy, fit_clean_ising
from .fits import (
    blockwise_casimir,
    covariance_weighted_casimir_samples,
    monotonicity_test,
)
from .schema import CellConfig, CellManifest


def _result_root(spec_path: Path, payload: dict[str, Any]) -> Path:
    declared = payload.get("result_root")
    if declared is None:
        return (spec_path.parent / "cells").resolve()
    root = Path(declared)
    return root if root.is_absolute() else (spec_path.parent / root).resolve()


def _verified_blocks(directory: Path) -> tuple[CellManifest, np.ndarray]:
    manifest = CellManifest.model_validate_json(
        (directory / "manifest.json").read_text(encoding="utf-8")
    )
    if manifest.status != "success":
        raise ValueError(f"cell {manifest.cell_id} did not succeed")
    block_path = directory / "blocks.npz"
    digest = hashlib.sha256(block_path.read_bytes()).hexdigest()
    if digest != manifest.blocks_sha256:
        raise ValueError(f"cell {manifest.cell_id} block hash mismatch")
    blocks = np.load(block_path)["blocks"]
    if not np.all(np.isfinite(blocks)):
        raise ValueError(f"cell {manifest.cell_id} has non-finite blocks")
    return manifest, blocks


def _resolution(config: CellConfig) -> float:
    if config.channel.kind == "identity":
        return 0.0
    if config.channel.kind == "confusion":
        return float(config.channel.parameter)
    return 1.0 - float(config.channel.parameter)


def _charge_blocks(
    config: CellConfig,
    blocks: np.ndarray,
    *,
    indices: np.ndarray | None = None,
    include_l3: bool = True,
) -> np.ndarray:
    if config.model == "clean_ising":
        return np.asarray([fit_clean_ising(config.lengths).central_charge])
    lengths = np.asarray(config.lengths)
    values = np.asarray(blocks)
    if indices is not None:
        lengths = lengths[indices]
        values = values[:, indices]
    background = None
    if config.model == "self_dual":
        background = 0.5 * critical_ground_energy(lengths)
    return blockwise_casimir(
        lengths,
        values,
        background=background,
        include_l3=include_l3,
    )


def _sample_summary(samples: np.ndarray) -> dict[str, float | int]:
    values = np.asarray(samples, dtype=float)
    return {
        "central_charge": float(np.mean(values)),
        "standard_error": (
            float(np.std(values, ddof=1) / np.sqrt(values.size))
            if values.size > 1
            else 0.0
        ),
        "samples": int(values.size),
    }


def _fit_charge_samples(
    config: CellConfig,
    blocks: np.ndarray,
    *,
    indices: np.ndarray | None = None,
    include_l3: bool = True,
) -> np.ndarray:
    """Return block samples aligned with a coupled-width GLS estimate."""

    if config.model == "clean_ising":
        return _charge_blocks(config, blocks)
    lengths = np.asarray(config.lengths, dtype=float)
    values = np.asarray(blocks, dtype=float)
    if indices is not None:
        lengths = lengths[indices]
        values = values[:, indices]
    if values.shape[0] < 2:
        raise ValueError("covariance-aware fitting requires at least two blocks")
    background = None
    if config.model == "self_dual":
        background = 0.5 * critical_ground_energy(lengths)
    return covariance_weighted_casimir_samples(
        lengths,
        values,
        background=background,
        alpha=1.0,
        include_l3=include_l3,
    )


def _fit_summary(
    config: CellConfig,
    blocks: np.ndarray,
    *,
    indices: np.ndarray | None = None,
    include_l3: bool = True,
) -> dict[str, float | int]:
    """Fit the mean width curve with its coupled-width covariance."""

    return _sample_summary(
        _fit_charge_samples(
            config,
            blocks,
            indices=indices,
            include_l3=include_l3,
        )
    )


def _is_analytic_endpoint(config: CellConfig) -> bool:
    return config.model == "self_dual" and (
        (
            config.channel.kind == "confusion"
            and float(config.channel.parameter) == 0.5
        )
        or (
            config.channel.kind == "erasure"
            and float(config.channel.parameter) == 0.0
        )
    )


def fit_window_audit(
    config: CellConfig,
    blocks: np.ndarray,
) -> dict[str, Any]:
    """Audit Casimir stability across correction, window, and omission fits."""

    if config.model == "clean_ising":
        return {"status": "not_applicable_exact_calibration"}
    analytic_endpoint = _is_analytic_endpoint(config)
    if analytic_endpoint:
        fitted = _sample_summary(_charge_blocks(config, blocks))
        exact = -0.5
        return {
            "status": "not_applicable_analytic_endpoint",
            "exact_central_charge": exact,
            "finite_width_fit": fitted,
            "finite_width_bias": float(fitted["central_charge"]) - exact,
            "rule": (
                "complete-loss rates are analytic, so Monte Carlo fit-window "
                "significance is not defined"
            ),
        }
    lengths = np.asarray(config.lengths, dtype=int)
    baseline = _fit_summary(config, blocks)
    candidates: list[tuple[str, np.ndarray, bool]] = [
        ("without_l3", np.arange(lengths.size), False)
    ]
    for start in (1, 2):
        keep = np.arange(start, lengths.size)
        if keep.size > 3:
            candidates.append((f"lmin_{lengths[start]}", keep, True))
    for omitted, length in enumerate(lengths):
        keep = np.arange(lengths.size) != omitted
        if np.count_nonzero(keep) > 3:
            candidates.append((f"omit_{length}", keep, True))

    variants: list[dict[str, Any]] = []
    baseline_mean = float(baseline["central_charge"])
    baseline_error = float(baseline["standard_error"])
    for label, indices, include_l3 in candidates:
        summary = _fit_summary(
            config,
            blocks,
            indices=np.asarray(indices),
            include_l3=include_l3,
        )
        shift = abs(float(summary["central_charge"]) - baseline_mean)
        combined_error = float(
            np.hypot(float(summary["standard_error"]), baseline_error)
        )
        summary.update(
            {
                "label": label,
                "include_l3": include_l3,
                "lengths": lengths[indices].tolist(),
                "absolute_shift": shift,
                "combined_standard_error": combined_error,
                "shift_in_combined_se": (
                    shift / combined_error
                    if combined_error > 0.0
                    else (0.0 if shift == 0.0 else float("inf"))
                ),
            }
        )
        variants.append(summary)
    maximum_shift = max(
        (float(variant["absolute_shift"]) for variant in variants),
        default=0.0,
    )
    maximum_z = max(
        (float(variant["shift_in_combined_se"]) for variant in variants),
        default=0.0,
    )
    return {
        "status": "evaluated",
        "baseline": baseline,
        "variants": variants,
        "maximum_absolute_shift": maximum_shift,
        "maximum_shift_in_combined_se": maximum_z,
        "stable_within_two_combined_se": bool(maximum_z <= 2.0),
        "rule": (
            "every alternative central charge must lie within two "
            "quadrature-combined standard errors of the all-width L^-3 fit"
        ),
    }


def reblocking_audit(
    config: CellConfig,
    arrays: list[np.ndarray],
    *,
    factors: tuple[int, ...] = (1, 2, 4, 5, 10),
) -> dict[str, Any]:
    """Audit the GLS estimate after within-seed longitudinal reblocking."""
    if not arrays or any(array.ndim != 2 for array in arrays):
        raise ValueError("reblocking requires one two-dimensional array per seed")
    widths = len(config.lengths)
    variants: list[dict[str, Any]] = []
    for factor in factors:
        if factor <= 0:
            raise ValueError("reblocking factors must be positive")
        if any(array.shape[0] % factor for array in arrays):
            continue
        reblocked = [
            array.reshape(array.shape[0] // factor, factor, array.shape[1]).mean(
                axis=1
            )
            for array in arrays
        ]
        blocks = np.concatenate(reblocked, axis=0)
        if blocks.shape[0] <= widths:
            continue
        try:
            summary = _fit_summary(config, blocks)
        except ValueError:
            continue
        variants.append(
            {
                "factor": factor,
                "effective_block_size": config.block_size * factor,
                **summary,
            }
        )
    if not variants or variants[0]["factor"] != 1:
        raise ValueError("the unreblocked baseline could not be evaluated")
    baseline = variants[0]
    alternatives: list[dict[str, Any]] = []
    for variant in variants[1:]:
        shift = abs(
            float(variant["central_charge"])
            - float(baseline["central_charge"])
        )
        combined = float(
            np.hypot(
                float(variant["standard_error"]),
                float(baseline["standard_error"]),
            )
        )
        alternatives.append(
            {
                **variant,
                "absolute_shift": shift,
                "combined_standard_error": combined,
                "shift_in_combined_se": (
                    shift / combined if combined > 0.0 else float("inf")
                ),
            }
        )
    maximum_z = max(
        (float(item["shift_in_combined_se"]) for item in alternatives),
        default=0.0,
    )
    return {
        "status": "evaluated",
        "baseline": baseline,
        "variants": alternatives,
        "maximum_shift_in_combined_se": maximum_z,
        "stable_within_two_combined_se": bool(maximum_z <= 2.0),
        "rule": (
            "every within-seed reblocking estimate must lie within two "
            "quadrature-combined standard errors of the unreblocked GLS fit"
        ),
    }


def analyze_run(
    run_spec_path: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    """Verify every result, fit charges, and write machine-readable outputs."""

    spec_path = Path(run_spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    root = _result_root(spec_path, spec)
    grouped: dict[tuple[str, str, float], list[np.ndarray]] = {}
    replicate_ids: dict[tuple[str, str, float], list[tuple[int, int]]] = {}
    provenance: list[dict[str, str]] = []
    settings_by_key: dict[tuple[str, str, float], CellConfig] = {}
    for cell in spec["cells"]:
        cell_id = str(cell["cell_id"])
        manifest, blocks = _verified_blocks(root / cell_id)
        config = manifest.settings
        key = (
            config.model,
            config.channel.kind,
            float(config.channel.parameter),
        )
        settings_by_key[key] = config
        grouped.setdefault(key, []).append(blocks)
        replicate_ids.setdefault(key, []).extend(
            (config.seed, block_index)
            for block_index in range(int(blocks.shape[0]))
        )
        provenance.append(
            {
                "cell_id": cell_id,
                "git_commit": manifest.provenance.get("git_commit", "unknown"),
            }
        )

    rows: list[dict[str, Any]] = []
    fit_audits: list[dict[str, Any]] = []
    reblocking_audits: list[dict[str, Any]] = []
    charge_samples_by_key: dict[tuple[str, str, float], np.ndarray] = {}
    for (model, channel, parameter), arrays in sorted(grouped.items()):
        blocks = np.concatenate(arrays, axis=0)
        key = (model, channel, parameter)
        config = settings_by_key[key]
        charge_samples = (
            _charge_blocks(config, blocks)
            if _is_analytic_endpoint(config)
            else _fit_charge_samples(config, blocks)
        )
        charge_samples_by_key[key] = charge_samples
        summary = _sample_summary(charge_samples)
        rows.append(
            {
                "model": model,
                "channel": channel,
                "parameter": parameter,
                "information_loss": _resolution(config),
                **summary,
            }
        )
        fit_audits.append(
            {
                "model": model,
                "channel": channel,
                "parameter": parameter,
                "information_loss": _resolution(config),
                **fit_window_audit(config, blocks),
            }
        )
        if model != "clean_ising" and not _is_analytic_endpoint(config):
            reblocking_audits.append(
                {
                    "model": model,
                    "channel": channel,
                    "parameter": parameter,
                    "information_loss": _resolution(config),
                    **reblocking_audit(config, arrays),
                }
            )

    tests: list[dict[str, Any]] = []
    for model in sorted({row["model"] for row in rows}):
        identity = next(
            (
                row
                for row in rows
                if row["model"] == model and row["channel"] == "identity"
            ),
            None,
        )
        for family in ("confusion", "erasure"):
            curve = [
                (row, (model, str(row["channel"]), float(row["parameter"])))
                for row in rows
                if row["model"] == model and row["channel"] == family
            ]
            if identity is not None:
                identity_key = (
                    model,
                    str(identity["channel"]),
                    float(identity["parameter"]),
                )
                curve = [(identity, identity_key), *curve]
            by_resolution = {
                float(row["information_loss"]): (row, key)
                for row, key in curve
            }
            curve = [by_resolution[key] for key in sorted(by_resolution)]
            if len(curve) < 2:
                continue
            rows_in_curve = [row for row, _ in curve]
            keys_in_curve = [key for _, key in curve]
            reference_ids = replicate_ids[keys_in_curve[0]]
            if any(replicate_ids[key] != reference_ids for key in keys_in_curve[1:]):
                raise ValueError(
                    f"{model}/{family} blocks do not share seed/block alignment"
                )
            sample_matrix = np.vstack(
                [charge_samples_by_key[key] for key in keys_in_curve]
            )
            covariance = np.cov(sample_matrix, rowvar=True, ddof=1) / float(
                sample_matrix.shape[1]
            )
            covariance = np.asarray(covariance, dtype=float)
            variance_floor = 1e-20
            for index in range(covariance.shape[0]):
                covariance[index, index] = max(
                    covariance[index, index], variance_floor
                )
            covariance = 0.5 * (covariance + covariance.T)
            result = monotonicity_test(
                [row["central_charge"] for row in rows_in_curve],
                covariance,
                bootstrap_draws=1_000,
                seed=12_200 + len(tests),
            )
            tests.append(
                {
                    "model": model,
                    "channel": family,
                    "information_loss": [
                        row["information_loss"] for row in rows_in_curve
                    ],
                    "covariance_method": (
                        "aligned_common_random_number_gls_block_samples"
                    ),
                    "aligned_blocks": int(sample_matrix.shape[1]),
                    "covariance_of_estimates": covariance.tolist(),
                    "constrained_curve": result.constrained_curve.tolist(),
                    "statistic": result.statistic,
                    "bootstrap_p_value": result.bootstrap_p_value,
                    "bootstrap_draws": result.bootstrap_draws,
                }
            )

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "ceff_resolution.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]) if rows else [],
            lineterminator="\n",
        )
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    summary: dict[str, Any] = {
        "schema_version": "1.0",
        "run_spec": str(spec_path.resolve()),
        "cells_verified": len(spec["cells"]),
        "resolution_points": rows,
        "fit_window_audits": fit_audits,
        "reblocking_audits": reblocking_audits,
        "monotonicity_tests": tests,
        "provenance": provenance,
        "interpretation": (
            "Central charges for self_dual are record Casimir coefficients "
            "minus the clean-Ising normalization background c=1/2."
        ),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    figure, axis = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)
    for (model, channel) in sorted(
        {(row["model"], row["channel"]) for row in rows}
    ):
        selected = [
            row
            for row in rows
            if row["model"] == model and row["channel"] == channel
        ]
        selected.sort(key=lambda row: row["information_loss"])
        axis.errorbar(
            [row["information_loss"] for row in selected],
            [row["central_charge"] for row in selected],
            yerr=[row["standard_error"] for row in selected],
            marker="o",
            capsize=2,
            label=f"{model}: {channel}",
        )
    axis.set(
        xlabel="information-loss parameter",
        ylabel=r"$c_{\mathrm{obs}}$",
        title="Observer-dependent Casimir central charge",
    )
    if rows:
        axis.legend(frameon=False, fontsize=8)
    figure.savefig(output / "ceff_resolution.png", dpi=180)
    plt.close(figure)
    return summary
