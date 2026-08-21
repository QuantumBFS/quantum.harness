"""Strict h=3 assembly for the issue 147 validation evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from itertools import product
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .qmc_analysis import bootstrap_thermodynamics


H_FIELD = 3.0
M_VALUES = (32, 64, 128)
CHAINS = (0, 1, 2, 3)
MODES = ("ordinary", "thermodynamic")
CHIS = (16, 32)
PROTOCOL_PREFIX = "issue147-h3-"
THERMO_FIELDS = (
    "h",
    "beta",
    "method",
    "mode",
    "D",
    "chi",
    "f",
    "u",
    "C",
    "f_stat_error",
    "u_stat_error",
    "C_stat_error",
    "trotter_error",
    "contraction_error",
    "truncation_error",
    "differentiation_error",
    "status",
)
RESOURCE_FIELDS = (
    "method",
    "stage",
    "cell_id",
    "mode",
    "beta",
    "M",
    "chain",
    "wall_seconds",
    "peak_memory_bytes",
)


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing required file: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _atomic_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty table: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _read_csv(path: Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except FileNotFoundError as error:
        raise ValueError(f"missing required file: {path}") from error
    if not rows:
        raise ValueError(f"empty table: {path}")
    if not set(required).issubset(rows[0]):
        raise ValueError(f"table has an invalid schema: {path}")
    return rows


def _finite(value, *, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"non-numeric {name}") from error
    if not math.isfinite(result):
        raise ValueError(f"non-finite {name}")
    return result


def _load_cells(root: Path, label: str) -> tuple[dict, list[tuple[dict, dict]]]:
    root = Path(root)
    spec = _read_json(root / "run_spec.json")
    cells = spec.get("cells")
    if not isinstance(cells, list) or not cells:
        raise ValueError(f"{label} run spec has no cells")
    ids = [cell.get("cell_id") for cell in cells]
    if any(not isinstance(cell_id, str) for cell_id in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"{label} run spec has invalid cell ids")
    shared = spec.get("settings", {})
    provenance = spec.get("provenance", {})
    loaded = []
    for cell in cells:
        cell_id = cell["cell_id"]
        path = root / "cells" / cell_id / "manifest.json"
        try:
            manifest = _read_json(path)
        except ValueError as error:
            raise ValueError(f"missing successful {label} cell {cell_id}") from error
        if manifest.get("status") != "success":
            raise ValueError(f"missing successful {label} cell {cell_id}")
        if manifest.get("params") != cell.get("params", {}):
            raise ValueError(f"{label} parameter mismatch in {cell_id}")
        expected_settings = {**shared, **cell.get("settings", {})}
        if manifest.get("settings") != expected_settings:
            raise ValueError(f"{label} settings mismatch in {cell_id}")
        if manifest.get("provenance") != provenance:
            raise ValueError(f"{label} provenance mismatch in {cell_id}")
        loaded.append((cell, manifest))
    return spec, loaded


def _check_protocol(specs: tuple[dict, ...]) -> None:
    protocols = [spec.get("provenance", {}).get("protocol") for spec in specs]
    if len(set(protocols)) != 1 or not isinstance(protocols[0], str):
        raise ValueError("run specs do not share one protocol")
    if not protocols[0].startswith(PROTOCOL_PREFIX):
        raise ValueError("run specs are not issue147 h=3 evidence")


def _require_settings(spec: dict, expected: dict, label: str) -> None:
    settings = spec.get("settings", {})
    for name, value in expected.items():
        if settings.get(name) != value:
            raise ValueError(f"{label} requires {name}={value!r}")


def _check_production_grid(qmc_spec: dict, pepo_spec: dict) -> None:
    protocol = qmc_spec.get("provenance", {}).get("protocol")
    if protocol != "issue147-h3-v1":
        return
    expected = np.arange(0.025, 1.0001, 0.025)
    actual = np.asarray(
        sorted({float(cell["params"]["beta"]) for cell in qmc_spec["cells"]})
    )
    if actual.shape != expected.shape or not np.allclose(actual, expected, atol=1e-14):
        raise ValueError("production QMC grid must contain beta=0.025,...,1.0")
    _require_settings(
        pepo_spec,
        {"beta_stop": 1.0, "delta_beta": 0.025},
        "production PEPO",
    )


def _resource_row(
    method: str,
    stage: str,
    cell: dict,
    manifest: dict,
) -> dict:
    params = cell.get("params", {})
    resources = manifest.get("resources", {})
    return {
        "method": method,
        "stage": stage,
        "cell_id": cell["cell_id"],
        "mode": params.get("compression_mode", ""),
        "beta": params.get("beta", ""),
        "M": params.get("M", ""),
        "chain": params.get("chain", ""),
        "wall_seconds": resources.get("wall_seconds", ""),
        "peak_memory_bytes": resources.get("peak_memory_bytes", ""),
    }


def _checkpoint_root(
    manifest: dict,
    evolution_root: Path,
    cell_id: str,
    mode: str,
) -> Path | None:
    raw = manifest.get("artifacts", {}).get("checkpoint_root")
    candidates = []
    if isinstance(raw, str):
        candidates.extend((Path(raw), Path.cwd() / raw))
    candidates.append(evolution_root / "cells" / cell_id / mode / "checkpoints")
    return next((candidate for candidate in candidates if candidate.is_dir()), None)


def _checkpoint_resource_rows(
    manifest: dict,
    evolution_root: Path,
    cell_id: str,
    mode: str,
) -> list[dict]:
    expected = manifest.get("diagnostics", {}).get("checkpoint_count")
    root = _checkpoint_root(manifest, evolution_root, cell_id, mode)
    if expected is None and root is None:
        return []
    if root is None:
        raise ValueError(f"missing PEPO checkpoints for {cell_id}")
    markers = sorted(root.glob("beta-*/metadata.json"))
    if expected is not None and len(markers) != int(expected):
        raise ValueError(f"PEPO checkpoint count mismatch for {cell_id}")
    rows = []
    for marker in markers:
        metadata = _read_json(marker)
        diagnostics = metadata.get("diagnostics", {})
        beta = _finite(metadata.get("beta"), name="PEPO checkpoint beta")
        if metadata.get("mode") != mode:
            raise ValueError(f"PEPO checkpoint mode mismatch for {cell_id}")
        wall = _finite(diagnostics.get("wall_seconds"), name="PEPO wall time")
        memory = _finite(
            diagnostics.get("peak_memory_bytes"), name="PEPO peak memory"
        )
        rows.append(
            {
                "method": "PEPO",
                "stage": "checkpoint",
                "cell_id": cell_id,
                "mode": mode,
                "beta": beta,
                "M": "",
                "chain": "",
                "wall_seconds": wall,
                "peak_memory_bytes": memory,
            }
        )
    return rows


def _load_qmc(root: Path, *, bootstrap_samples: int):
    spec, loaded = _load_cells(root, "QMC")
    keys = []
    arrays = {}
    resources = []
    for cell, manifest in loaded:
        params = cell["params"]
        key = (
            _finite(params.get("h"), name="QMC h"),
            _finite(params.get("beta"), name="QMC beta"),
            int(params.get("M")),
            int(params.get("chain")),
        )
        if key in arrays:
            raise ValueError(f"duplicate QMC parameter tuple: {key}")
        bins_path = Path(root) / "cells" / cell["cell_id"] / "bins.npz"
        try:
            with np.load(bins_path) as payload:
                bins = np.asarray(payload["energy"], dtype=float)
        except (FileNotFoundError, KeyError) as error:
            raise ValueError(f"missing QMC bins for {cell['cell_id']}") from error
        if bins.ndim != 1 or len(bins) < 32 or not np.isfinite(bins).all():
            raise ValueError(f"invalid QMC bins for {cell['cell_id']}")
        arrays[key] = bins
        keys.append(key)
        resources.append(_resource_row("QMC", "chain", cell, manifest))

    fields = sorted({key[0] for key in keys})
    betas = np.asarray(sorted({key[1] for key in keys}), dtype=float)
    m_values = tuple(sorted({key[2] for key in keys}))
    chains = tuple(sorted({key[3] for key in keys}))
    if fields != [H_FIELD] or m_values != M_VALUES or chains != CHAINS:
        raise ValueError("QMC setup must be h=3 with M=32/64/128 and four chains")
    expected = set(product(fields, betas.tolist(), m_values, chains))
    if set(keys) != expected:
        raise ValueError("QMC run spec is not a complete Cartesian grid")
    bin_counts = {len(array) for array in arrays.values()}
    if len(bin_counts) != 1:
        raise ValueError("QMC chains have inconsistent bin counts")
    chain_bins = np.stack(
        [
            np.stack(
                [
                    np.stack([arrays[(H_FIELD, beta, m_value, chain)] for chain in chains])
                    for m_value in m_values
                ]
            )
            for beta in betas
        ]
    )
    result = bootstrap_thermodynamics(
        betas,
        np.asarray(m_values),
        chain_bins,
        bootstrap_samples=bootstrap_samples,
        seed=147,
    )
    rows = []
    convergence = []
    for index, beta in enumerate(betas):
        rows.append(
            {
                "h": H_FIELD,
                "beta": beta,
                "method": "QMC",
                "mode": "",
                "D": "",
                "chi": "",
                "f": result.f[index],
                "u": result.u[index],
                "C": result.c[index],
                "f_stat_error": result.f_error[index],
                "u_stat_error": result.u_error[index],
                "C_stat_error": result.c_error[index],
                "trotter_error": result.fit_spread[index],
                "contraction_error": "",
                "truncation_error": "",
                "differentiation_error": "",
                "status": result.status[index],
            }
        )
        for m_index, m_value in enumerate(m_values):
            block = chain_bins[index, m_index].reshape(-1)
            convergence.append(
                {
                    "kind": "qmc_M",
                    "mode": "",
                    "beta": beta,
                    "parameter": m_value,
                    "x": (beta / m_value) ** 2,
                    "u": float(np.mean(block)),
                    "u_error": float(np.std(block, ddof=1) / np.sqrt(len(block))),
                    "u_relative_change": "",
                    "z_absolute_change": "",
                    "status": result.status[index],
                }
            )
    return spec, rows, convergence, resources, result


def _resolve_artifact(
    raw: str,
    evolution_root: Path,
    source: str,
    mode: str,
    chi: int,
) -> Path:
    candidate = Path(raw)
    if candidate.is_dir():
        return candidate
    candidate = Path.cwd() / candidate
    if candidate.is_dir():
        return candidate
    derived = evolution_root / "cells" / source / "measurements" / mode / f"chi-{chi}"
    if derived.is_dir():
        return derived
    raise ValueError(f"missing PEPO measurement artifact for {mode}, chi={chi}")


def _load_pepo(evolution_root: Path, measurement_root: Path):
    evolution_spec, evolution = _load_cells(evolution_root, "PEPO evolution")
    measurement_spec, measurements = _load_cells(measurement_root, "PEPO measurement")
    source_modes = {}
    resources = []
    for cell, manifest in evolution:
        mode = cell["params"].get("compression_mode")
        if mode in source_modes:
            raise ValueError(f"duplicate PEPO evolution mode: {mode}")
        source_modes[cell["cell_id"]] = mode
        if manifest.get("resources"):
            resources.append(_resource_row("PEPO", "evolution", cell, manifest))
        resources.extend(
            _checkpoint_resource_rows(
                manifest,
                Path(evolution_root),
                cell["cell_id"],
                mode,
            )
        )
    if set(source_modes.values()) != set(MODES):
        raise ValueError("PEPO evolution must contain ordinary and thermodynamic modes")

    curves = {}
    for cell, manifest in measurements:
        params = cell["params"]
        source = params.get("source_cell")
        chi = int(params.get("chi"))
        if source not in source_modes:
            raise ValueError(f"unknown PEPO source cell: {source}")
        mode = source_modes[source]
        key = (mode, chi)
        if key in curves:
            raise ValueError(f"duplicate PEPO measurement: {key}")
        artifact_value = manifest.get("artifacts", {}).get("measurement_root")
        if not isinstance(artifact_value, str):
            raise ValueError(f"missing PEPO measurement artifact in {cell['cell_id']}")
        artifact = _resolve_artifact(
            artifact_value,
            Path(evolution_root),
            source,
            mode,
            chi,
        )
        internal = _read_json(artifact / "manifest.json")
        if (
            internal.get("status") != "success"
            or internal.get("mode") != mode
            or internal.get("chi") != chi
        ):
            raise ValueError(f"invalid PEPO measurement manifest for {mode}, chi={chi}")
        dense = artifact / "dense.csv"
        public = artifact / "thermodynamics.csv"
        if _sha256(dense) != internal.get("dense_sha256"):
            raise ValueError(f"PEPO dense table hash mismatch for {mode}, chi={chi}")
        if _sha256(public) != internal.get("thermodynamics_sha256"):
            raise ValueError(f"PEPO public table hash mismatch for {mode}, chi={chi}")
        raw_rows = _read_csv(
            dense,
            ("beta", "z", "f", "u", "c", "hermiticity_residual", "mode", "chi"),
        )
        curve = []
        for raw_row in raw_rows:
            row_mode = raw_row["mode"]
            row_chi = int(raw_row["chi"])
            values = {
                name: _finite(raw_row[name], name=f"PEPO {name}")
                for name in ("beta", "z", "f", "u", "c", "hermiticity_residual")
            }
            if row_mode != mode or row_chi != chi:
                raise ValueError(f"PEPO row convention mismatch for {mode}, chi={chi}")
            if values["hermiticity_residual"] > 1e-6:
                raise ValueError(f"PEPO Hermiticity gate failed for {mode}, chi={chi}")
            curve.append(values)
        beta = np.asarray([row["beta"] for row in curve])
        if np.any(np.diff(beta) <= 0) or len(curve) < 5:
            raise ValueError(f"PEPO beta grid is invalid for {mode}, chi={chi}")
        curves[key] = curve
        if manifest.get("resources"):
            resources.append(_resource_row("PEPO", "measurement", cell, manifest))

    if set(curves) != set(product(MODES, CHIS)):
        raise ValueError("PEPO measurements must contain both modes at chi=16/32")
    rows = []
    convergence = []
    lowest_stable = {}
    for mode in MODES:
        low = curves[(mode, CHIS[0])]
        high = curves[(mode, CHIS[1])]
        low_beta = np.asarray([row["beta"] for row in low])
        high_beta = np.asarray([row["beta"] for row in high])
        if not np.array_equal(low_beta, high_beta):
            raise ValueError(f"PEPO chi grids disagree for {mode}")
        stable_prefix = []
        prefix_open = True
        for low_row, high_row in zip(low, high, strict=True):
            u_delta = abs(high_row["u"] - low_row["u"])
            u_relative = u_delta / max(abs(high_row["u"]), 1e-15)
            z_delta = abs(high_row["z"] - low_row["z"])
            converged = u_relative < 1e-3 and z_delta < 1e-4
            status = (
                "chi_converged;D_not_assessed;trotter_not_assessed"
                if converged
                else "chi_unconverged;D_not_assessed;trotter_not_assessed"
            )
            if converged and prefix_open:
                stable_prefix.append(high_row["beta"])
            else:
                prefix_open = False
            rows.append(
                {
                    "h": H_FIELD,
                    "beta": high_row["beta"],
                    "method": "PEPO",
                    "mode": mode,
                    "D": 4,
                    "chi": CHIS[1],
                    "f": high_row["f"],
                    "u": high_row["u"],
                    "C": high_row["c"],
                    "f_stat_error": "",
                    "u_stat_error": "",
                    "C_stat_error": "",
                    "trotter_error": "",
                    "contraction_error": u_delta,
                    "truncation_error": "",
                    "differentiation_error": "",
                    "status": status,
                }
            )
            for chi, raw_row in ((CHIS[0], low_row), (CHIS[1], high_row)):
                convergence.append(
                    {
                        "kind": "pepo_chi",
                        "mode": mode,
                        "beta": raw_row["beta"],
                        "parameter": chi,
                        "x": chi,
                        "u": raw_row["u"],
                        "u_error": "",
                        "u_relative_change": u_relative,
                        "z_absolute_change": z_delta,
                        "status": status,
                    }
                )
        lowest_stable[mode] = max(stable_prefix) if stable_prefix else None
    return evolution_spec, measurement_spec, rows, convergence, resources, lowest_stable


def _load_ed(root: Path) -> list[dict]:
    manifest = _read_json(Path(root) / "manifest.json")
    if manifest.get("status") != "success" or float(manifest.get("field")) != H_FIELD:
        raise ValueError("ED artifact is not successful h=3 evidence")
    table = Path(root) / "thermodynamics.csv"
    if _sha256(table) != manifest.get("thermodynamics_sha256"):
        raise ValueError("ED thermodynamics hash mismatch")
    raw_rows = _read_csv(table, ("beta", "f", "u", "c"))
    rows = []
    for raw in raw_rows:
        rows.append(
            {
                "h": H_FIELD,
                "beta": _finite(raw["beta"], name="ED beta"),
                "method": "ED 4x4",
                "mode": "",
                "D": "",
                "chi": "",
                "f": _finite(raw["f"], name="ED f"),
                "u": _finite(raw["u"], name="ED u"),
                "C": _finite(raw["c"], name="ED C"),
                "f_stat_error": "",
                "u_stat_error": "",
                "C_stat_error": "",
                "trotter_error": "",
                "contraction_error": "",
                "truncation_error": "",
                "differentiation_error": "",
                "status": "finite_size_diagnostic",
            }
        )
    return rows


def _plot_comparison(rows: list[dict], output: Path) -> None:
    colors = {
        "QMC": "#0072B2",
        "ordinary": "#D55E00",
        "thermodynamic": "#009E73",
        "ED 4x4": "#000000",
    }
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), constrained_layout=True)
    for axis, quantity, error_key, ylabel in (
        (axes[0], "u", "u_stat_error", "Internal energy per site"),
        (axes[1], "C", "C_stat_error", "Specific heat per site"),
    ):
        for method in ("QMC", "PEPO", "ED 4x4"):
            if method == "PEPO":
                groups = [
                    (
                        mode,
                        [
                            row
                            for row in rows
                            if row["method"] == method and row["mode"] == mode
                        ],
                    )
                    for mode in MODES
                ]
            else:
                groups = [(method, [row for row in rows if row["method"] == method])]
            for label, group in groups:
                if not group:
                    continue
                group = sorted(group, key=lambda row: float(row["beta"]))
                beta = np.asarray([float(row["beta"]) for row in group])
                values = np.asarray([float(row[quantity]) for row in group])
                color = colors[label]
                if method == "QMC":
                    error = np.asarray([float(row[error_key]) for row in group])
                    axis.errorbar(
                        beta,
                        values,
                        yerr=error,
                        color=color,
                        marker="o",
                        ms=3,
                        lw=1,
                        capsize=2,
                        label="QMC",
                    )
                elif method == "ED 4x4":
                    axis.plot(beta, values, color=color, ls=":", lw=1.2, label="ED 4x4 diagnostic")
                else:
                    marker = "s" if label == "ordinary" else "^"
                    axis.plot(
                        beta,
                        values,
                        color=color,
                        marker=marker,
                        ms=3,
                        lw=1.2,
                        label=f"PEPO {label}",
                    )
        axis.set_xlabel("Inverse temperature beta J")
        axis.set_ylabel(ylabel)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, fontsize=7)
    fig.suptitle("10x10 open TFIM at h/J = 3 (ED shown only as 4x4 diagnostic)", fontsize=9)
    fig.savefig(output / "comparison.png", dpi=300)
    fig.savefig(output / "comparison.pdf")
    plt.close(fig)


def _plot_convergence(convergence: list[dict], output: Path) -> None:
    qmc = [row for row in convergence if row["kind"] == "qmc_M"]
    available_beta = sorted({float(row["beta"]) for row in qmc})
    target = min(available_beta, key=lambda value: abs(value - 0.5))
    qmc_target = sorted(
        [row for row in qmc if math.isclose(float(row["beta"]), target)],
        key=lambda row: float(row["x"]),
    )
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), constrained_layout=True)
    axes[0].errorbar(
        [float(row["x"]) for row in qmc_target],
        [float(row["u"]) for row in qmc_target],
        yerr=[float(row["u_error"]) for row in qmc_target],
        color="#0072B2",
        marker="o",
        capsize=2,
    )
    axes[0].set_xlabel("(beta / M)^2")
    axes[0].set_ylabel("QMC internal energy per site")
    axes[0].set_title(f"Trotter fit at beta J = {target:g}")
    colors = {"ordinary": "#D55E00", "thermodynamic": "#009E73"}
    for mode in MODES:
        rows = [
            row
            for row in convergence
            if row["kind"] == "pepo_chi"
            and row["mode"] == mode
            and int(row["parameter"]) == CHIS[1]
        ]
        rows.sort(key=lambda row: float(row["beta"]))
        axes[1].plot(
            [float(row["beta"]) for row in rows],
            [100.0 * float(row["u_relative_change"]) for row in rows],
            color=colors[mode],
            marker="s" if mode == "ordinary" else "^",
            ms=3,
            label=mode,
        )
    axes[1].axhline(0.1, color="#000000", ls=":", lw=1, label="0.1% gate")
    axes[1].set_xlabel("Inverse temperature beta J")
    axes[1].set_ylabel("chi=16 to 32 energy change (%)")
    axes[1].set_title("Boundary contraction convergence")
    axes[1].legend(frameon=False, fontsize=7)
    for axis in axes:
        axis.spines[["top", "right"]].set_visible(False)
    fig.savefig(output / "convergence.png", dpi=300)
    fig.savefig(output / "convergence.pdf")
    plt.close(fig)


def _target_summary(rows: list[dict], target: float = 0.8) -> dict:
    selected = [row for row in rows if math.isclose(float(row["beta"]), target)]
    qmc = next((row for row in selected if row["method"] == "QMC"), None)
    pepo = next(
        (row for row in selected if row["method"] == "PEPO" and row["mode"] == "thermodynamic"),
        None,
    )
    if qmc is None or pepo is None:
        return {"beta": target, "available": False}
    u_relative = abs(float(pepo["u"]) - float(qmc["u"])) / max(abs(float(qmc["u"])), 1e-15)
    c_relative = abs(float(pepo["C"]) - float(qmc["C"])) / max(abs(float(qmc["C"])), 1e-15)
    accepted = qmc["status"] == "success" and str(pepo["status"]).startswith(
        "chi_converged"
    )
    u_threshold = max(
        0.5 * abs(float(pepo["u"]) - float(qmc["u"])),
        abs(float(qmc["u"])) * 0.01 / 3.0,
    )
    c_threshold = max(
        0.5 * abs(float(pepo["C"]) - float(qmc["C"])),
        abs(float(qmc["C"])) * 0.03 / 3.0,
    )
    return {
        "beta": target,
        "available": True,
        "accepted_evidence": accepted,
        "u_relative_error": u_relative,
        "C_relative_error": c_relative,
        "u_reference_precise": float(qmc["u_stat_error"]) < u_threshold,
        "C_reference_precise": float(qmc["C_stat_error"]) < c_threshold,
        "u_target_pass": accepted and u_relative < 0.01,
        "C_target_pass": accepted and c_relative < 0.03,
    }


def assemble(
    qmc_root: Path,
    pepo_root: Path,
    pepo_measure_root: Path,
    output: Path,
    *,
    ed_root: Path | None = None,
    bootstrap_samples: int = 2000,
) -> int:
    if bootstrap_samples < 2:
        raise ValueError("at least two bootstrap samples are required")
    qmc_spec, qmc_rows, qmc_convergence, qmc_resources, _ = _load_qmc(
        Path(qmc_root), bootstrap_samples=bootstrap_samples
    )
    (
        pepo_spec,
        measurement_spec,
        pepo_rows,
        pepo_convergence,
        pepo_resources,
        lowest_stable,
    ) = _load_pepo(Path(pepo_root), Path(pepo_measure_root))
    _check_protocol((qmc_spec, pepo_spec, measurement_spec))
    _require_settings(
        qmc_spec,
        {"lx": 10, "ly": 10, "J": 1.0, "boundary": "open", "operator": "pauli"},
        "QMC",
    )
    pepo_setup = {
        "lx": 10,
        "ly": 10,
        "J": 1.0,
        "h": H_FIELD,
        "boundary": "open",
        "operator": "pauli",
        "D": 4,
        "delta_beta": 0.025,
    }
    _require_settings(pepo_spec, pepo_setup, "PEPO evolution")
    _require_settings(measurement_spec, pepo_setup, "PEPO measurement")
    _check_production_grid(qmc_spec, pepo_spec)
    rows = qmc_rows + pepo_rows
    if ed_root is not None:
        rows.extend(_load_ed(Path(ed_root)))
    rows.sort(key=lambda row: (float(row["beta"]), row["method"], row["mode"]))
    convergence = qmc_convergence + pepo_convergence
    convergence_fields = (
        "kind",
        "mode",
        "beta",
        "parameter",
        "x",
        "u",
        "u_error",
        "u_relative_change",
        "z_absolute_change",
        "status",
    )
    resources = qmc_resources + pepo_resources
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    _atomic_csv(output / "thermodynamics.csv", rows, THERMO_FIELDS)
    _atomic_csv(output / "convergence.csv", convergence, convergence_fields)
    _atomic_csv(output / "resources.csv", resources, RESOURCE_FIELDS)
    _plot_comparison(rows, output)
    _plot_convergence(convergence, output)
    summary = {
        "status": "assembled",
        "setup": {
            "hamiltonian": "H = -J sum_<ij> Z_i Z_j - h sum_i X_i",
            "operator": "Pauli",
            "lattice": "10x10 open",
            "J": 1.0,
            "h": H_FIELD,
            "D": 4,
            "chis": list(CHIS),
            "delta_beta": 0.025,
        },
        "completeness": {
            "qmc_cells": len(qmc_spec["cells"]),
            "pepo_evolution_cells": len(pepo_spec["cells"]),
            "pepo_measurement_cells": len(measurement_spec["cells"]),
        },
        "lowest_stable_beta": lowest_stable,
        "target_beta_0.8": _target_summary(rows),
        "limitations": [
            "Only D=4 is available, so PEPO truncation convergence is not assessed.",
            "Only delta_beta=0.025 is available, so PEPO Trotter convergence is not assessed.",
            "ED 4x4 is a finite-size diagnostic and is never treated as 10x10 reference data.",
        ],
    }
    _atomic_json(output / "summary.json", summary)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qmc", required=True, type=Path)
    parser.add_argument("--pepo", required=True, type=Path)
    parser.add_argument("--pepo-measure", required=True, type=Path)
    parser.add_argument("--ed", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    args = parser.parse_args(argv)
    return assemble(
        args.qmc,
        args.pepo,
        args.pepo_measure,
        args.output,
        ed_root=args.ed,
        bootstrap_samples=args.bootstrap_samples,
    )


if __name__ == "__main__":
    raise SystemExit(main())
