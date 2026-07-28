# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Stage 4 analysis for the triangular/honeycomb TFIM reproduction."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

NU = 0.629971
OMEGA = 0.83
REGISTERED_OMEGAS = (0.80, 0.83, 0.86)
MIN_INDEPENDENT_BLOCKS = 8
SAMPLING_Z_MAX = 5.0
FIT_GRID_POINTS = 201
GEOMETRY_VERSIONS = {
    "square": "square-v1",
    "triangular": "triangular-v1",
    "honeycomb": "honeycomb-v2",
}
PROTOCOL_WINDOWS = {
    "square": {"broad": (3.00, 3.10), "narrow": (3.03, 3.06), "l_min": (4, 6, 8)},
    "triangular": {"broad": (4.70, 4.84), "narrow": (4.74, 4.80), "l_min": (6, 8, 10, 12)},
    "honeycomb": {"broad": (2.08, 2.18), "narrow": (2.11, 2.15), "l_min": (10, 12, 14)},
}


def load_bins(path: Path):
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"missing or empty input: {path}")
    data = np.genfromtxt(path, delimiter=",", names=True, dtype=None, encoding="utf-8")
    data = np.atleast_1d(data)
    required = {
        "raw_schema", "lattice", "geometry_version", "L", "N", "Nb", "h", "beta",
        "c_tau", "seed", "initial_state", "bin",
        "n_thermal", "n_bins", "sweeps_per_bin", "config_checked",
        "consistency_failures", "update_algorithm", "sign_avg", "E", "spacetime_m2",
        "spacetime_m4", "S0", "Sq", "q_norm", "q_count",
    }
    names = set(data.dtype.names or ())
    missing = sorted(required - names)
    if missing:
        raise ValueError(f"input is missing columns: {', '.join(missing)}")
    if data.size == 0:
        raise ValueError("input has no data rows")

    chains = defaultdict(list)
    metadata = {}
    chain_expected_bins = {}
    seed_owner = {}
    starts_by_cell = defaultdict(set)
    lattice_versions = set()
    for row in data:
        L = int(row["L"])
        field_key = round(float(row["h"]), 8)
        seed = int(row["seed"])
        initial_state = str(row["initial_state"])
        key = (L, field_key, initial_state, seed)
        cell_key = (L, field_key)
        numeric = np.asarray(
            [row["beta"], row["E"], row["spacetime_m2"], row["spacetime_m4"],
             row["S0"], row["Sq"], row["q_norm"]],
            dtype=float,
        )
        if not np.all(np.isfinite(numeric)):
            raise ValueError(f"non-finite numeric value in cell {key}")
        if initial_state not in {"hot", "cold"}:
            raise ValueError(f"invalid initial state {initial_state!r} in cell {key}")
        owner_key = (*cell_key, initial_state)
        owner = seed_owner.setdefault(seed, owner_key)
        if owner != owner_key:
            raise ValueError(
                f"RNG seed {seed} is reused across chains {owner} and {owner_key}"
            )
        starts_by_cell[cell_key].add(initial_state)
        lattice_version = (str(row["lattice"]), str(row["geometry_version"]))
        lattice_versions.add(lattice_version)
        lattice, geometry_version = lattice_version
        if lattice not in GEOMETRY_VERSIONS:
            raise ValueError(f"unsupported lattice {lattice!r}")
        if geometry_version != GEOMETRY_VERSIONS[lattice]:
            raise ValueError(
                f"unexpected geometry version {geometry_version!r} for {lattice}"
            )
        field = float(row["h"])
        if not np.isfinite(field) or field <= 0.0:
            raise ValueError(f"invalid transverse field in cell {key}")
        expected_sites = L * L * (2 if lattice == "honeycomb" else 1)
        expected_bonds = {
            "square": 2 * expected_sites,
            "triangular": 3 * expected_sites,
            "honeycomb": 3 * expected_sites // 2,
        }[lattice]
        if L < 2 or int(row["N"]) != expected_sites or int(row["Nb"]) != expected_bonds:
            raise ValueError(f"inconsistent lattice counts in cell {key}")
        c_tau = float(row["c_tau"])
        if not np.isfinite(c_tau) or c_tau <= 0.0:
            raise ValueError(f"invalid c_tau in cell {key}")
        if not np.isclose(float(row["beta"]), c_tau * L / field, rtol=1e-12):
            raise ValueError(f"cell {key} does not use beta*h/L=c_tau")
        if (int(row["n_thermal"]) < 0 or int(row["n_bins"]) <= 0
                or int(row["sweeps_per_bin"]) <= 0):
            raise ValueError(f"invalid sampling budget in cell {key}")
        config_checked = int(row["config_checked"])
        consistency_failures = int(row["consistency_failures"])
        if config_checked not in (0, 1):
            raise ValueError(f"invalid configuration-check flag in cell {key}")
        if ((config_checked == 1 and consistency_failures < 0)
                or (config_checked == 0 and consistency_failures != -1)):
            raise ValueError(f"invalid configuration-check result in cell {key}")
        if str(row["raw_schema"]) != "challenge148-raw-v1":
            raise ValueError(f"unsupported raw schema in cell {key}")
        if str(row["update_algorithm"]) != "sandvik-tfim-cluster-v1":
            raise ValueError(f"unsupported update algorithm in cell {key}")
        if float(row["sign_avg"]) != 1.0:
            raise ValueError(f"cell {key} is not sign-free")
        expected_q_count = 4 if lattice == "square" else 6
        expected_q_norm = (
            2.0 * np.pi / L
            if lattice == "square"
            else 4.0 * np.pi / (np.sqrt(3.0) * L)
        )
        if (not np.isclose(float(row["q_norm"]), expected_q_norm, rtol=1e-12)
                or int(row["q_count"]) != expected_q_count):
            raise ValueError(f"invalid momentum metadata in cell {key}")
        chains[key].append(
            (
                int(row["bin"]),
                float(row["spacetime_m2"]),
                float(row["spacetime_m4"]),
                float(row["S0"]),
                float(row["Sq"]),
                float(row["E"]),
            )
        )
        row_metadata = {
            "lattice": lattice_version[0],
            "geometry_version": lattice_version[1],
            "beta": float(row["beta"]),
            "c_tau": c_tau,
            "q_norm": float(row["q_norm"]),
            "q_count": int(row["q_count"]),
            "sweeps_per_bin": int(row["sweeps_per_bin"]),
            "n_thermal": int(row["n_thermal"]),
            "n_bins": int(row["n_bins"]),
            "config_checked": bool(config_checked),
            "consistency_failures": consistency_failures,
        }
        if cell_key in metadata and metadata[cell_key] != row_metadata:
            raise ValueError(f"inconsistent metadata within cell {cell_key}")
        metadata[cell_key] = row_metadata
        expected = chain_expected_bins.setdefault(key, int(row["n_bins"]))
        if expected != int(row["n_bins"]):
            raise ValueError(f"inconsistent n_bins within chain {key}")
    if len(lattice_versions) != 1:
        raise ValueError(f"input mixes lattice/geometry versions: {sorted(lattice_versions)}")

    ordered = {}
    for key, rows in chains.items():
        rows.sort(key=lambda item: item[0])
        indices = [item[0] for item in rows]
        expected = chain_expected_bins[key]
        if indices != list(range(expected)):
            raise ValueError(
                f"chain {key} has duplicate or missing bins: expected 0..{expected - 1}"
            )
        ordered[key] = np.asarray([item[1:] for item in rows], dtype=float)
    fields_by_size = defaultdict(set)
    for L, h, _, _ in ordered:
        fields_by_size[L].add(h)
    field_sets = {tuple(sorted(fields)) for fields in fields_by_size.values()}
    if len(field_sets) != 1:
        raise ValueError("input is not a complete rectangular (L,h) grid")
    start_sets = {tuple(sorted(starts)) for starts in starts_by_cell.values()}
    if len(start_sets) != 1:
        raise ValueError("cells do not contain a consistent set of initial states")
    for cell_key, starts in starts_by_cell.items():
        metadata[cell_key]["initial_states"] = tuple(sorted(starts))
    c_tau_values = {row_metadata["c_tau"] for row_metadata in metadata.values()}
    if len(c_tau_values) != 1:
        raise ValueError(f"input mixes c_tau values: {sorted(c_tau_values)}")
    return ordered, metadata


def tau_int(series: np.ndarray) -> float:
    values = np.asarray(series, dtype=float)
    if len(values) < 4:
        return 0.5
    centered = values - values.mean()
    variance = np.dot(centered, centered) / len(centered)
    if variance <= 1e-30:
        return 0.5
    tau = 0.5
    for lag in range(1, len(centered) // 2 + 1):
        rho = np.dot(centered[:-lag], centered[lag:]) / ((len(centered) - lag) * variance)
        if rho <= 0.0:
            break
        tau += rho
        if lag >= 6.0 * tau:
            break
    return max(tau, 0.5)


def chain_taus(values: np.ndarray) -> np.ndarray:
    if values.ndim != 2 or values.shape[1] != 5:
        raise ValueError("chain data must have columns m2, m4, S0, Sq, E")
    return np.asarray([tau_int(values[:, column]) for column in range(values.shape[1])])


def q_value(bins: np.ndarray) -> float:
    m2 = bins[:, 0].mean()
    m4 = bins[:, 1].mean()
    return m2 * m2 / m4 if m4 > 1e-30 else np.nan


def xi_value(bins: np.ndarray, L: int, q_norm: float) -> float:
    s0 = bins[:, 2].mean()
    sq = bins[:, 3].mean()
    denom = 4.0 * np.sin(q_norm / 2.0) ** 2
    xi2 = (s0 / sq - 1.0) / denom if sq > 1e-30 and denom > 1e-30 else np.nan
    return np.sqrt(xi2) / L if xi2 > 0.0 else np.nan


def circular_block_resample(values: np.ndarray, block: int, rng: np.random.Generator) -> np.ndarray:
    count = len(values)
    if count == 0:
        return values
    block = max(1, min(block, count))
    starts = rng.integers(0, count, int(np.ceil(count / block)))
    indices = np.concatenate([(start + np.arange(block)) % count for start in starts])[:count]
    return values[indices]


def grouped_cells(chains):
    cells = defaultdict(dict)
    for (L, h, initial_state, seed), values in chains.items():
        cells[(L, h)][(initial_state, seed)] = values
    return cells


def resample_cell(chain_map, block: int, rng: np.random.Generator) -> np.ndarray:
    chain_keys = sorted(chain_map)
    selected = rng.integers(0, len(chain_keys), len(chain_keys))
    return np.concatenate([
        circular_block_resample(chain_map[chain_keys[index]], block, rng)
        for index in selected
    ])


def point_estimates(cells, metadata, n_boot: int, rng: np.random.Generator):
    if n_boot < 2:
        raise ValueError("at least two bootstrap samples are required")
    chain_counts = {len(chain_map) for chain_map in cells.values()}
    if len(chain_counts) != 1 or min(chain_counts, default=0) < 2:
        raise ValueError("every cell must contain the same number of at least two chains")
    points = {}
    diagnostics = []
    for key in sorted(cells):
        L, h = key
        chain_map = cells[key]
        starts = [chain_key[0] for chain_key in chain_map]
        if set(starts) == {"hot", "cold"}:
            per_start = {start: starts.count(start) for start in {"hot", "cold"}}
            if min(per_start.values()) < 2:
                raise ValueError(f"cell {key} needs at least two chains per hot/cold start")
        tau_by_chain = []
        for (initial_state, seed), values in sorted(chain_map.items()):
            taus = chain_taus(values)
            tau = float(np.max(taus))
            tau_by_chain.append(tau)
            diagnostics.append(
                (
                    L, h, initial_state, seed, *taus, tau,
                    tau * metadata[key]["sweeps_per_bin"],
                    len(values) / (2.0 * tau),
                    int(len(values) // max(1, np.ceil(2.0 * tau))),
                )
            )
        block = max(1, int(np.ceil(2.0 * max(tau_by_chain))))
        combined = np.concatenate([chain_map[chain_key] for chain_key in sorted(chain_map)])
        q = q_value(combined)
        xi = xi_value(combined, L, metadata[key]["q_norm"])
        q_boot = np.empty(n_boot)
        xi_boot = np.empty(n_boot)
        for sample in range(n_boot):
            resampled = resample_cell(chain_map, block, rng)
            q_boot[sample] = q_value(resampled)
            xi_boot[sample] = xi_value(resampled, L, metadata[key]["q_norm"])
        if np.isfinite(q_boot).sum() < 2 or np.isfinite(xi_boot).sum() < 2:
            raise ValueError(f"insufficient finite bootstrap estimates in cell {key}")
        points[key] = {
            "Q": q,
            "Q_err": np.nanstd(q_boot, ddof=1),
            "xi": xi,
            "xi_err": np.nanstd(xi_boot, ddof=1),
            "block": block,
            "block_sweeps": block * metadata[key]["sweeps_per_bin"],
            "chains": len(chain_map),
        }
    return points, diagnostics


def _difference_z(first: np.ndarray, second: np.ndarray) -> float:
    if len(first) < 2 or len(second) < 2:
        return np.nan
    variance = np.var(first, axis=0, ddof=1) / len(first)
    variance += np.var(second, axis=0, ddof=1) / len(second)
    scale = np.sqrt(np.maximum(variance, 0.0))
    difference = np.abs(np.mean(first, axis=0) - np.mean(second, axis=0))
    z = np.divide(difference, scale, out=np.zeros_like(difference), where=scale > 0.0)
    z[(scale == 0.0) & (difference > 0.0)] = np.inf
    return float(np.max(z))


def sampling_diagnostics(cells):
    rows = []
    failures = []
    for (L, h), chain_map in sorted(cells.items()):
        starts = defaultdict(list)
        stationarity = []
        minimum_blocks = np.inf
        for (initial_state, _), values in sorted(chain_map.items()):
            tau = float(np.max(chain_taus(values)))
            block = max(1, int(np.ceil(2.0 * tau)))
            minimum_blocks = min(minimum_blocks, len(values) // block)
            block_means = np.asarray([
                values[index:index + block].mean(axis=0)
                for index in range(0, len(values) - block + 1, block)
            ])
            starts[initial_state].append(block_means)
            midpoint = len(block_means) // 2
            if midpoint >= 2 and len(block_means) - midpoint >= 2:
                stationarity.append(
                    _difference_z(block_means[:midpoint], block_means[midpoint:])
                )
        start_z = np.nan
        if set(starts) == {"hot", "cold"}:
            start_z = _difference_z(
                np.concatenate(starts["hot"]), np.concatenate(starts["cold"])
            )
        stationarity_z = max(stationarity, default=np.nan)
        starts_ok = set(starts) == {"hot", "cold"} and min(map(len, starts.values())) >= 2
        blocks_ok = minimum_blocks >= MIN_INDEPENDENT_BLOCKS
        start_ok = np.isfinite(start_z) and start_z <= SAMPLING_Z_MAX
        stationarity_ok = (
            np.isfinite(stationarity_z) and stationarity_z <= SAMPLING_Z_MAX
        )
        passed = starts_ok and blocks_ok and start_ok and stationarity_ok
        rows.append((
            L, h, len(starts.get("hot", [])), len(starts.get("cold", [])),
            int(minimum_blocks), start_z, stationarity_z, int(passed),
        ))
        if not passed:
            failures.append(
                f"L={L} h={h}: hot/cold={dict((k, len(v)) for k, v in starts.items())} "
                f"min_blocks={int(minimum_blocks)} start_z={start_z:.3g} "
                f"stationarity_z={stationarity_z:.3g}"
            )
    return rows, failures


def design_matrix(L, h, hc, omega=OMEGA, include_mixed=True):
    thermal = 1.0 / NU
    delta = h - hc
    columns = [
        np.ones_like(L),
        delta * L**thermal,
        delta**2 * L ** (2.0 * thermal),
        L ** (-omega),
    ]
    if include_mixed:
        columns.append(delta * L ** (thermal - omega))
    return np.column_stack(columns)


def fit_at_hc(L, h, y, error, hc, omega=OMEGA, include_mixed=True):
    matrix = design_matrix(L, h, hc, omega, include_mixed)
    if len(y) <= matrix.shape[1]:
        raise ValueError("fit is underdetermined")
    weight = 1.0 / np.maximum(error, 1e-12)
    weighted_matrix = matrix * weight[:, None]
    column_scale = np.linalg.norm(weighted_matrix, axis=0)
    if np.any(column_scale <= 1e-14):
        raise ValueError("fit design contains a zero column")
    scaled_matrix = weighted_matrix / column_scale
    scaled_coeff, _, rank, singular = np.linalg.lstsq(
        scaled_matrix, y * weight, rcond=None
    )
    if rank != matrix.shape[1] or singular[-1] <= 0.0:
        raise ValueError(f"rank-deficient fit design ({rank}/{matrix.shape[1]})")
    condition = float(singular[0] / singular[-1])
    if not np.isfinite(condition) or condition > 1e12:
        raise ValueError(f"ill-conditioned fit design ({condition:.3e})")
    coeff = scaled_coeff / column_scale
    residual = (y - matrix @ coeff) * weight
    return float(residual @ residual), coeff, int(rank), condition


def fit_hc(L, h, y, error, omega=OMEGA, include_mixed=True):
    arrays = (L, h, y, error)
    if any(len(array) != len(L) for array in arrays):
        raise ValueError("fit arrays have inconsistent lengths")
    if not all(np.all(np.isfinite(array)) for array in arrays) or np.any(error <= 0.0):
        raise ValueError("fit arrays must be finite with positive errors")
    lo = float(np.min(h) + 0.002)
    hi = float(np.max(h) - 0.002)
    if not lo < hi:
        raise ValueError("field window is too narrow for the registered fit")

    grid = np.linspace(lo, hi, FIT_GRID_POINTS)
    scores = np.asarray(
        [fit_at_hc(L, h, y, error, value, omega, include_mixed)[0] for value in grid]
    )
    best_index = int(np.argmin(scores))
    if best_index == 0 or best_index == len(grid) - 1:
        raise ValueError("fit minimum lies on the search boundary")
    local_minima = [
        index for index in range(1, len(grid) - 1)
        if scores[index] <= scores[index - 1] and scores[index] <= scores[index + 1]
    ]
    competitive = [
        index for index in local_minima
        if abs(index - best_index) > 2 and scores[index] <= scores[best_index] + 1.0
    ]
    if competitive:
        raise ValueError("fit objective has multiple competitive minima")

    lo = float(grid[best_index - 1])
    hi = float(grid[best_index + 1])
    golden = (np.sqrt(5.0) - 1.0) / 2.0
    left = hi - golden * (hi - lo)
    right = lo + golden * (hi - lo)
    f_left = fit_at_hc(L, h, y, error, left, omega, include_mixed)[0]
    f_right = fit_at_hc(L, h, y, error, right, omega, include_mixed)[0]
    for _ in range(80):
        if f_left < f_right:
            hi, right, f_right = right, left, f_left
            left = hi - golden * (hi - lo)
            f_left = fit_at_hc(L, h, y, error, left, omega, include_mixed)[0]
        else:
            lo, left, f_left = left, right, f_right
            right = lo + golden * (hi - lo)
            f_right = fit_at_hc(L, h, y, error, right, omega, include_mixed)[0]
    hc = 0.5 * (lo + hi)
    chi2, coeff, rank, condition = fit_at_hc(
        L, h, y, error, hc, omega, include_mixed
    )
    dof = len(y) - len(coeff) - 1
    if dof <= 0:
        raise ValueError(f"fit has non-positive degrees of freedom ({dof})")
    return hc, chi2, dof, coeff, rank, condition


def fit_observable(
    observable, keys, points, cells, metadata, n_boot, seed, omega, include_mixed
):
    L = np.asarray([key[0] for key in keys], dtype=float)
    h = np.asarray([key[1] for key in keys], dtype=float)
    error_name = {"Q": "Q_err", "xi": "xi_err"}.get(observable)
    if error_name is None:
        raise ValueError(f"unsupported observable {observable!r}")
    rng = np.random.default_rng(seed + (0 if observable == "Q" else 1))
    y = np.asarray([points[key][observable] for key in keys])
    error = np.asarray([points[key][error_name] for key in keys])
    finite = np.isfinite(y) & np.isfinite(error) & (error > 0.0)
    minimum_points = (4 if not include_mixed else 5) + 2
    if finite.sum() < minimum_points:
        raise ValueError(
            f"{observable} fit has only {finite.sum()} valid points; needs {minimum_points}"
        )
    hc, chi2, dof, coeff, rank, condition = fit_hc(
        L[finite], h[finite], y[finite], error[finite],
        omega=omega, include_mixed=include_mixed,
    )
    samples = []
    failed = 0
    for _ in range(n_boot):
        sampled_y = []
        for key in keys:
            sampled = resample_cell(cells[key], points[key]["block"], rng)
            sampled_y.append(
                q_value(sampled)
                if observable == "Q"
                else xi_value(sampled, key[0], metadata[key]["q_norm"])
            )
        sampled_y = np.asarray(sampled_y)
        valid = np.isfinite(sampled_y) & finite
        if valid.sum() >= minimum_points:
            try:
                samples.append(fit_hc(
                    L[valid], h[valid], sampled_y[valid], error[valid],
                    omega=omega, include_mixed=include_mixed,
                )[0])
            except ValueError:
                failed += 1
        else:
            failed += 1
    if len(samples) < 2:
        raise ValueError(f"{observable} bootstrap produced fewer than two valid fits")
    samples = np.asarray(samples)
    ci_low, ci_high = np.quantile(samples, [0.025, 0.975])
    return {
        "hc": hc,
        "error": np.std(samples, ddof=1),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "chi2": chi2,
        "dof": dof,
        "coeff": coeff,
        "rank": rank,
        "condition": condition,
        "omega": omega,
        "include_mixed": include_mixed,
        "bootstrap_success": len(samples),
        "bootstrap_failed": failed,
        "bootstrap_failure_rate": failed / n_boot,
    }


def fit_observables(keys, points, cells, metadata, n_boot, seed, omega, include_mixed):
    return {
        observable: fit_observable(
            observable, keys, points, cells, metadata, n_boot, seed, omega,
            include_mixed,
        )
        for observable in ("Q", "xi")
    }


def select_keys(points, h_min, h_max, l_min):
    keys = sorted(
        key for key in points
        if key[0] >= l_min and h_min <= key[1] <= h_max
    )
    if len(keys) < 8:
        raise ValueError("fit selection has fewer than eight points")
    return keys


def validate_protocol_selection(metadata, points, window, l_min, omega):
    lattice = next(iter(metadata.values()))["lattice"]
    protocol = PROTOCOL_WINDOWS[lattice]
    if window not in ("broad", "narrow"):
        raise ValueError("protocol enforcement requires a broad or narrow window")
    if l_min not in protocol["l_min"]:
        raise ValueError(
            f"L_min={l_min} is not registered for {lattice}: {protocol['l_min']}"
        )
    if not any(np.isclose(omega, value, rtol=0.0, atol=1e-12)
               for value in REGISTERED_OMEGAS):
        raise ValueError(f"omega={omega} is not registered: {REGISTERED_OMEGAS}")
    sizes = {key[0] for key in points}
    if l_min not in sizes:
        raise ValueError(f"registered L_min={l_min} is absent from the input")
    for key, row_metadata in metadata.items():
        if row_metadata["initial_states"] != ("cold", "hot"):
            raise ValueError(f"cell {key} does not contain both hot and cold starts")
        if row_metadata["c_tau"] not in (1.0, 2.0):
            raise ValueError(f"cell {key} uses unregistered c_tau={row_metadata['c_tau']}")


def robustness_matrix(points, cells, metadata, n_boot, seed):
    lattice = next(iter(metadata.values()))["lattice"]
    protocol = PROTOCOL_WINDOWS[lattice]
    rows = []
    failures = []
    for window in ("broad", "narrow"):
        h_min, h_max = protocol[window]
        for l_min in protocol["l_min"]:
            for include_mixed in (True, False):
                for omega in REGISTERED_OMEGAS:
                    variant = (
                        f"window={window} L_min={l_min} omega={omega:.2f} "
                        f"mixed={int(include_mixed)}"
                    )
                    try:
                        validate_protocol_selection(
                            metadata, points, window, l_min, omega
                        )
                        keys = select_keys(points, h_min, h_max, l_min)
                    except ValueError as error:
                        for observable in ("Q", "xi"):
                            failures.append(
                                f"{variant} observable={observable}: {error}"
                            )
                            rows.append((
                                window, h_min, h_max, l_min, omega,
                                int(include_mixed), observable, "failed", str(error),
                                0, *(np.nan,) * 11,
                            ))
                        continue
                    for observable in ("Q", "xi"):
                        try:
                            result = fit_observable(
                                observable, keys, points, cells, metadata, n_boot,
                                seed, omega, include_mixed,
                            )
                            rows.append((
                                window, h_min, h_max, l_min, omega,
                                int(include_mixed), observable, "ok", "", len(keys),
                                result["hc"], result["error"], result["ci_low"],
                                result["ci_high"], result["chi2"], result["dof"],
                                result["chi2"] / result["dof"], result["condition"],
                                result["bootstrap_success"],
                                result["bootstrap_failed"],
                                result["bootstrap_failure_rate"],
                            ))
                        except ValueError as error:
                            failures.append(f"{variant} observable={observable}: {error}")
                            rows.append((
                                window, h_min, h_max, l_min, omega,
                                int(include_mixed), observable, "failed", str(error),
                                len(keys), *(np.nan,) * 11,
                            ))
    return rows, failures


def crossing(fields, first, second):
    difference = first - second
    roots = []
    for index in range(len(fields) - 1):
        if difference[index] == 0.0:
            roots.append(fields[index])
        elif difference[index] * difference[index + 1] < 0.0:
            fraction = difference[index] / (difference[index] - difference[index + 1])
            roots.append(fields[index] + fraction * (fields[index + 1] - fields[index]))
    return roots[0] if len(roots) == 1 else np.nan


def crossings(points, observable):
    sizes = sorted({L for L, _ in points})
    fields = sorted({h for _, h in points})
    rows = []
    for first, second in zip(sizes, sizes[1:]):
        common = np.asarray([h for h in fields if (first, h) in points and (second, h) in points])
        y_first = np.asarray([points[(first, h)][observable] for h in common])
        y_second = np.asarray([points[(second, h)][observable] for h in common])
        rows.append((first, second, crossing(common, y_first, y_second)))
    return rows


def write_outputs(
    input_path, points, diagnostics, sampling_rows, fits, crossing_rows, suffix=""
):
    stem = input_path.with_name(input_path.stem.removesuffix("_bins") + suffix)
    with stem.with_name(stem.name + "_autocorrelation.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "L", "h", "initial_state", "seed", "tau_m2", "tau_m4", "tau_S0",
            "tau_Sq", "tau_E", "tau_max_bins", "tau_max_sweeps",
            "effective_samples", "independent_blocks",
        ])
        writer.writerows(diagnostics)
    with stem.with_name(stem.name + "_sampling_gates.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "L", "h", "hot_chains", "cold_chains", "minimum_independent_blocks",
            "hot_cold_z_max", "stationarity_z_max", "passed",
        ])
        writer.writerows(sampling_rows)
    with stem.with_name(stem.name + "_points.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["L", "h", "Q", "Q_err", "xi_over_L", "xi_err", "block_bins", "block_sweeps", "chains"])
        for (L, h), point in sorted(points.items()):
            writer.writerow([L, h, point["Q"], point["Q_err"], point["xi"], point["xi_err"], point["block"], point["block_sweeps"], point["chains"]])
    with stem.with_name(stem.name + "_fits.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "observable", "hc", "hc_boot_err", "hc_boot_ci_low", "hc_boot_ci_high",
            "chi2", "dof", "chi2_per_dof", "rank", "condition", "omega",
            "include_mixed",
            "bootstrap_success", "bootstrap_failed", "bootstrap_failure_rate",
        ])
        for name, result in fits.items():
            writer.writerow([
                name, result["hc"], result["error"], result["ci_low"], result["ci_high"],
                result["chi2"], result["dof"], result["chi2"] / result["dof"],
                result["rank"], result["condition"], result["omega"],
                int(result["include_mixed"]), result["bootstrap_success"],
                result["bootstrap_failed"], result["bootstrap_failure_rate"],
            ])
    with stem.with_name(stem.name + "_crossings.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["observable", "L1", "L2", "h_cross"])
        writer.writerows(crossing_rows)

    sizes = sorted({L for L, _ in points})
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    for L in sizes:
        rows = sorted((h, point) for (size, h), point in points.items() if size == L)
        fields = np.asarray([row[0] for row in rows])
        axes[0].errorbar(fields, [row[1]["Q"] for row in rows], yerr=[row[1]["Q_err"] for row in rows], marker="o", ms=3, label=f"L={L}")
        axes[1].errorbar(fields, [row[1]["xi"] for row in rows], yerr=[row[1]["xi_err"] for row in rows], marker="o", ms=3, label=f"L={L}")
    axes[0].set(xlabel="transverse field h/J", ylabel="space-time Binder ratio Q")
    axes[1].set(xlabel="transverse field h/J", ylabel="equal-time correlation length xi/L")
    axes[0].legend(ncol=2, fontsize=8)
    axes[1].legend(ncol=2, fontsize=8)
    figure.savefig(stem.with_name(stem.name + "_crossings.png"), dpi=180)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    for axis, (observable, error_name, title) in zip(
        axes,
        (("Q", "Q_err", "Binder ratio"), ("xi", "xi_err", "Correlation length")),
    ):
        result = fits[observable]
        for L in sizes:
            rows = sorted(
                (h, point) for (size, h), point in points.items() if size == L
            )
            fields = np.asarray([row[0] for row in rows])
            values = np.asarray([row[1][observable] for row in rows])
            errors = np.asarray([row[1][error_name] for row in rows])
            lengths = np.full_like(fields, float(L))
            model = design_matrix(
                lengths, fields, result["hc"], result["omega"],
                result["include_mixed"],
            ) @ result["coeff"]
            finite = np.isfinite(values) & np.isfinite(errors) & (errors > 0.0)
            scaling_variable = (
                (fields - result["hc"]) * lengths ** (1.0 / NU)
            )
            axis.plot(
                scaling_variable[finite],
                ((values - model) / errors)[finite],
                "o", ms=3, label=f"L={L}",
            )
        axis.axhline(0.0, color="black", linewidth=0.8)
        axis.axhline(2.0, color="0.6", linewidth=0.7, linestyle="--")
        axis.axhline(-2.0, color="0.6", linewidth=0.7, linestyle="--")
        axis.set(
            xlabel=r"$(h-h_c)L^{1/\nu}$",
            ylabel="standardized residual",
            title=title,
        )
        axis.legend(ncol=2, fontsize=8)
    figure.savefig(stem.with_name(stem.name + "_residuals.png"), dpi=180)
    plt.close(figure)


def write_robustness_output(input_path, rows, suffix=""):
    stem = input_path.with_name(input_path.stem.removesuffix("_bins") + suffix)
    path = stem.with_name(stem.name + "_robustness.csv")
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "window", "h_min", "h_max", "L_min", "omega", "include_mixed",
            "observable", "status", "failure", "n_points", "hc", "hc_boot_err",
            "hc_boot_ci_low", "hc_boot_ci_high", "chi2", "dof", "chi2_per_dof",
            "condition", "bootstrap_success", "bootstrap_failed",
            "bootstrap_failure_rate",
        ])
        writer.writerows(rows)
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bins", type=Path)
    parser.add_argument("--bootstrap", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--h-min", type=float)
    parser.add_argument("--h-max", type=float)
    parser.add_argument("--l-min", type=int)
    parser.add_argument("--omega", type=float, default=OMEGA)
    parser.add_argument("--omit-mixed", action="store_true")
    parser.add_argument("--protocol-window", choices=("broad", "narrow"))
    parser.add_argument("--enforce-protocol", action="store_true")
    parser.add_argument("--robustness-matrix", action="store_true")
    parser.add_argument("--label", default="")
    parser.add_argument("--enforce-sampling-gates", action="store_true")
    args = parser.parse_args()
    if args.bootstrap < 2:
        parser.error("--bootstrap must be at least 2")

    chains, metadata = load_bins(args.bins)
    cells = grouped_cells(chains)
    points, diagnostics = point_estimates(
        cells, metadata, args.bootstrap, np.random.default_rng(args.seed)
    )
    sampling_rows, sampling_failures = sampling_diagnostics(cells)
    lattice = next(iter(metadata.values()))["lattice"]
    protocol = PROTOCOL_WINDOWS[lattice]
    if args.protocol_window is not None:
        if args.h_min is not None or args.h_max is not None:
            parser.error("--protocol-window cannot be combined with --h-min/--h-max")
        h_min, h_max = protocol[args.protocol_window]
        l_min = args.l_min if args.l_min is not None else protocol["l_min"][0]
    else:
        h_min = args.h_min if args.h_min is not None else -np.inf
        h_max = args.h_max if args.h_max is not None else np.inf
        l_min = args.l_min if args.l_min is not None else 0
    if args.enforce_protocol:
        validate_protocol_selection(
            metadata, points, args.protocol_window, l_min, args.omega
        )

    keys = select_keys(points, h_min, h_max, l_min)
    L = np.asarray([key[0] for key in keys], dtype=float)
    h = np.asarray([key[1] for key in keys], dtype=float)
    fits = fit_observables(
        keys, points, cells, metadata, args.bootstrap, args.seed, args.omega,
        not args.omit_mixed,
    )

    selected_points = {key: points[key] for key in keys}
    crossing_rows = []
    for observable in ("Q", "xi"):
        crossing_rows.extend((observable, first, second, value) for first, second, value in crossings(selected_points, observable))
    suffix = f"_{args.label}" if args.label else ""
    write_outputs(
        args.bins, selected_points, diagnostics, sampling_rows, fits, crossing_rows, suffix
    )

    matrix_failures = []
    if args.robustness_matrix:
        matrix_rows, matrix_failures = robustness_matrix(
            points, cells, metadata, args.bootstrap, args.seed
        )
        matrix_path = write_robustness_output(args.bins, matrix_rows, suffix)
        print(
            f"robustness_matrix={matrix_path} rows={len(matrix_rows)} "
            f"failed={len(matrix_failures)}"
        )

    geometry = next(iter(metadata.values()))["geometry_version"]
    starts = next(iter(metadata.values()))["initial_states"]
    c_tau = next(iter(metadata.values()))["c_tau"]
    print(
        f"lattice={lattice} geometry={geometry} cells={len(points)} chains={len(chains)} "
        f"c_tau={c_tau:g} starts={','.join(starts)}"
    )
    print(
        f"fit_selection={len(keys)} h=[{h.min():.8g},{h.max():.8g}] "
        f"L=[{int(L.min())},{int(L.max())}] omega={args.omega} mixed={not args.omit_mixed}"
    )
    print(f"max_tau_int_bins={max(row[9] for row in diagnostics):.3f}")
    print(
        f"sampling_gates={'pass' if not sampling_failures else 'fail'} "
        f"failed_cells={len(sampling_failures)}/{len(sampling_rows)}"
    )
    for observable, result in fits.items():
        print(
            f"{observable}: hc={result['hc']:.8f} +/- {result['error']:.8f} "
            f"chi2/dof={result['chi2'] / result['dof']:.3f} "
            f"condition={result['condition']:.3e} "
        f"bootstrap_failed={result['bootstrap_failed']}/{args.bootstrap}"
        )
    if (args.enforce_sampling_gates or args.enforce_protocol) and sampling_failures:
        raise ValueError("sampling gates failed:\n" + "\n".join(sampling_failures))
    if args.enforce_protocol and matrix_failures:
        raise ValueError(
            "registered robustness variants failed:\n" + "\n".join(matrix_failures)
        )


if __name__ == "__main__":
    main()
