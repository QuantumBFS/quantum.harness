# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Deterministic validation for the Stage 4 statistics pipeline."""

from __future__ import annotations

import importlib.util
import csv
import sys
import tempfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_stage4", ROOT / "tools" / "analyze_stage4.py"
)
ANALYSIS = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ANALYSIS)
sys.modules["analyze_stage4"] = ANALYSIS

CTAU_SPEC = importlib.util.spec_from_file_location(
    "compare_ctau", ROOT / "tools" / "compare_ctau.py"
)
CTAU = importlib.util.module_from_spec(CTAU_SPEC)
assert CTAU_SPEC.loader is not None
CTAU_SPEC.loader.exec_module(CTAU)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_value_error(function, message: str) -> None:
    try:
        function()
    except ValueError:
        return
    raise AssertionError(message)


HEADER = (
    "raw_schema,lattice,geometry_version,L,N,Nb,h,beta,c_tau,seed,initial_state,"
    "bin,n_thermal,n_bins,sweeps_per_bin,update_algorithm,sign_avg,config_checked,"
    "consistency_failures,E,spacetime_m2,"
    "spacetime_m4,S0,Sq,q_norm,q_count\n"
)
HEADER_COLUMNS = HEADER.strip().split(",")


def valid_rows() -> list[str]:
    rows = []
    fields = (3.02, 3.06)
    for size in (4, 6):
        for field_index, field in enumerate(fields):
            for replica in (1, 2):
                seed = size * 10000 + field_index * 100 + replica
                for bin_index in (0, 1):
                    rows.append(
                        f"challenge148-raw-v1,square,square-v1,{size},{size * size},"
                        f"{2 * size * size},{field:.17g},{size / field:.17g},1,{seed},"
                        f"{'hot' if replica == 1 else 'cold'},{bin_index},10,2,5,"
                        f"sandvik-tfim-cluster-v1,1,0,-1,-1.0,0.2,0.08,0.2,0.1,"
                        f"{2 * np.pi / size:.17g},4\n"
                    )
    return rows


def write_csv(path: Path, rows: list[str], header: str = HEADER) -> None:
    path.write_text(header + "".join(rows), encoding="utf-8")


def test_input_validation(directory: Path) -> None:
    valid = directory / "valid.csv"
    rows = valid_rows()
    write_csv(valid, rows)
    chains, metadata = ANALYSIS.load_bins(valid)
    require(len(chains) == 8, "valid rectangular input should contain eight chains")
    require(len(metadata) == 4, "valid rectangular input should contain four cells")

    missing_bin = directory / "missing_bin.csv"
    write_csv(missing_bin, rows[:-1])
    expect_value_error(
        lambda: ANALYSIS.load_bins(missing_bin),
        "a chain with a missing bin must be rejected",
    )

    reused_seed = directory / "reused_seed.csv"
    first_seed = rows[0].split(",")[HEADER_COLUMNS.index("seed")]
    altered = rows.copy()
    columns = altered[8].split(",")
    columns[HEADER_COLUMNS.index("seed")] = first_seed
    altered[8] = ",".join(columns)
    write_csv(reused_seed, altered)
    expect_value_error(
        lambda: ANALYSIS.load_bins(reused_seed),
        "a seed reused across parameter cells must be rejected",
    )

    incomplete_grid = directory / "incomplete_grid.csv"
    def keep_complete_row(row: str) -> bool:
        columns = row.split(",")
        return not (
            columns[HEADER_COLUMNS.index("L")] == "6"
            and np.isclose(float(columns[HEADER_COLUMNS.index("h")]), 3.06)
        )
    write_csv(
        incomplete_grid,
        [row for row in rows if keep_complete_row(row)],
    )
    expect_value_error(
        lambda: ANALYSIS.load_bins(incomplete_grid),
        "an incomplete (L,h) rectangle must be rejected",
    )

    missing_column = directory / "missing_column.csv"
    write_csv(missing_column, rows, HEADER.replace(",q_count", ""))
    expect_value_error(
        lambda: ANALYSIS.load_bins(missing_column),
        "a missing metadata column must be rejected",
    )

    wrong_momentum = directory / "wrong_momentum.csv"
    altered = rows.copy()
    columns = altered[0].split(",")
    columns[HEADER_COLUMNS.index("q_norm")] = f"{1.01 * 2 * np.pi / 4:.17g}"
    altered[0] = ",".join(columns)
    write_csv(wrong_momentum, altered)
    expect_value_error(
        lambda: ANALYSIS.load_bins(wrong_momentum),
        "a lattice-incompatible momentum norm must be rejected",
    )

    ambiguous_check = directory / "ambiguous_check.csv"
    altered = rows.copy()
    columns = altered[0].split(",")
    columns[HEADER_COLUMNS.index("consistency_failures")] = "0"
    altered[0] = ",".join(columns)
    write_csv(ambiguous_check, altered)
    expect_value_error(
        lambda: ANALYSIS.load_bins(ambiguous_check),
        "an unchecked configuration must use the -1 sentinel",
    )

    mixed_c_tau = directory / "mixed_c_tau.csv"
    altered = rows.copy()
    columns = altered[0].split(",")
    columns[HEADER_COLUMNS.index("c_tau")] = "2"
    columns[HEADER_COLUMNS.index("beta")] = f"{2 * 4 / 3.02:.17g}"
    altered[0] = ",".join(columns)
    write_csv(mixed_c_tau, altered)
    expect_value_error(
        lambda: ANALYSIS.load_bins(mixed_c_tau),
        "a file containing mixed imaginary-time aspect ratios must be rejected",
    )


def test_scaling_fit() -> None:
    sizes = np.repeat(np.asarray([6.0, 8.0, 10.0, 12.0]), 7)
    fields = np.tile(np.linspace(4.73, 4.81, 7), 4)
    true_hc = 4.76811
    coefficients = np.asarray([0.62, 0.012, -0.00015, 0.04, 0.003])
    values = ANALYSIS.design_matrix(sizes, fields, true_hc) @ coefficients
    errors = np.full_like(values, 0.002)
    fitted_hc, chi2, dof, _, rank, condition = ANALYSIS.fit_hc(
        sizes, fields, values, errors
    )
    require(abs(fitted_hc - true_hc) < 2e-6, "synthetic critical field was not recovered")
    require(chi2 < 1e-12, "exact synthetic fit should have zero residual")
    require(dof == len(values) - len(coefficients) - 1, "fit degrees of freedom are wrong")
    require(rank == len(coefficients), "synthetic design should have full rank")
    require(np.isfinite(condition), "synthetic design condition number must be finite")

    degenerate_sizes = np.full(12, 8.0)
    degenerate_fields = np.linspace(4.74, 4.80, 12)
    expect_value_error(
        lambda: ANALYSIS.fit_hc(
            degenerate_sizes,
            degenerate_fields,
            np.linspace(0.5, 0.6, 12),
            np.full(12, 0.01),
        ),
        "rank-deficient scaling design must be rejected",
    )


def test_sampling_gates() -> None:
    rng = np.random.default_rng(20260729)
    chain_map = {}
    baseline = np.asarray([0.2, 0.08, 0.2, 0.1, -3.0])
    for initial_state in ("hot", "cold"):
        for replica in (0, 1):
            values = baseline + rng.normal(scale=0.002, size=(64, 5))
            chain_map[(initial_state, 100 * (initial_state == "cold") + replica)] = values
    cells = {(8, 3.04): chain_map}
    metadata = {
        (8, 3.04): {"sweeps_per_bin": 5, "q_norm": 2 * np.pi / 8}
    }
    points, diagnostics = ANALYSIS.point_estimates(
        cells, metadata, 20, np.random.default_rng(1234)
    )
    require((8, 3.04) in points and len(diagnostics) == 4, "valid chains were not analyzed")
    rows, failures = ANALYSIS.sampling_diagnostics(cells)
    require(not failures, f"stationary hot/cold chains failed gates: {failures}")
    require(len(rows[0]) == 11, "sampling diagnostics omitted registered columns")
    require(rows[0][-1] == 1, "valid sampling diagnostics did not pass")

    shifted = {key: values.copy() for key, values in chain_map.items()}
    for key in shifted:
        if key[0] == "cold":
            shifted[key][:, 0] += 0.2
    _, failures = ANALYSIS.sampling_diagnostics({(8, 3.04): shifted})
    require(failures, "a large hot/cold split was not rejected")

    shortened = ANALYSIS.discard_chain_prefix(cells, 0.20)
    require(
        all(len(values) == 52 for values in shortened[(8, 3.04)].values()),
        "discarded-prefix analysis retained the wrong number of bins",
    )
    expect_value_error(
        lambda: ANALYSIS.discard_chain_prefix(cells, 0.0),
        "a zero discarded-prefix fraction must be rejected",
    )


def test_ctau_comparison() -> None:
    points = {
        (8, 3.04): {
            "Q": 0.5, "Q_err": 0.01, "xi": 0.4, "xi_err": 0.01,
        }
    }
    rows, failures = CTAU.compare_points(points, points)
    require(len(rows) == 2 and not failures, "equal c_tau points must agree")
    fits = {
        "Q": {"hc": 3.04438, "error": 1e-7},
        "xi": {"hc": 3.04438, "error": 1e-7},
    }
    rows, failures = CTAU.compare_fits(fits, fits, 1e-6)
    require(len(rows) == 2 and not failures, "resolved equal c_tau fits must pass")
    rows, failures = CTAU.compare_fits(fits, fits, 1e-8)
    require(
        len(failures) == 2 and all(row[-1] == 0 for row in rows),
        "an unresolved c_tau shift budget must fail",
    )


def synthetic_protocol_data():
    rng = np.random.default_rng(148)
    sizes = (4, 6, 8, 10, 12)
    fields = (3.00, 3.02, 3.03, 3.04, 3.05, 3.06, 3.08, 3.10)
    points = {}
    cells = {}
    metadata = {}
    q_coeff = np.asarray([0.61, 0.012, -0.00010, 0.035, 0.002])
    xi_coeff = np.asarray([0.42, -0.008, 0.00008, 0.025, -0.001])
    for size in sizes:
        for field in fields:
            lengths = np.asarray([float(size)])
            field_array = np.asarray([field])
            q = (ANALYSIS.design_matrix(lengths, field_array, 3.044) @ q_coeff).item()
            xi = (ANALYSIS.design_matrix(lengths, field_array, 3.044) @ xi_coeff).item()
            key = (size, field)
            points[key] = {
                "Q": q,
                "Q_err": 0.002,
                "xi": xi,
                "xi_err": 0.002,
                "block": 1,
            }
            q_norm = 2 * np.pi / size
            denom = 4 * np.sin(q_norm / 2) ** 2
            chain_map = {}
            for start_index, initial_state in enumerate(("hot", "cold")):
                for replica in (0, 1):
                    values = np.empty((32, 5))
                    values[:, 0] = 0.2 + rng.normal(scale=2e-4, size=32)
                    values[:, 1] = 0.04 / q + rng.normal(scale=1e-4, size=32)
                    values[:, 2] = (
                        1.0 + (xi * size) ** 2 * denom
                        + rng.normal(scale=2e-3, size=32)
                    )
                    values[:, 3] = 1.0 + rng.normal(scale=2e-3, size=32)
                    values[:, 4] = -1.0 + rng.normal(scale=2e-3, size=32)
                    chain_map[(initial_state, 1000 * size + 10 * start_index + replica)] = values
            cells[key] = chain_map
            metadata[key] = {
                "lattice": "square",
                "geometry_version": "square-v1",
                "q_norm": q_norm,
                "c_tau": 1.0,
                "initial_states": ("cold", "hot"),
                "config_checked": True,
                "consistency_failures": 0,
                "sweeps_per_bin": 5,
            }
    return points, cells, metadata


def test_protocol_and_robustness(directory: Path) -> None:
    points, cells, metadata = synthetic_protocol_data()
    ANALYSIS.validate_protocol_selection(metadata, points, "broad", 4, 0.83)
    expect_value_error(
        lambda: ANALYSIS.validate_protocol_selection(
            metadata, points, "broad", 5, 0.83
        ),
        "an unregistered minimum size must be rejected",
    )
    expect_value_error(
        lambda: ANALYSIS.validate_protocol_selection(
            metadata, points, "broad", 4, 0.9
        ),
        "an unregistered correction exponent must be rejected",
    )

    rows, failures = ANALYSIS.robustness_matrix(
        points, cells, metadata, n_boot=2, seed=20260729
    )
    expected_rows = 2 * 3 * 2 * 3 * 2
    require(len(rows) == expected_rows, "robustness matrix omitted registered variants")
    require(
        all(row[7] in {"ok", "failed"} for row in rows),
        "every robustness row must have an explicit status",
    )
    require(
        len(failures) == sum(row[7] == "failed" for row in rows),
        "matrix failures and failed rows must agree",
    )
    output = ANALYSIS.write_robustness_output(
        directory / "square_bins.csv", rows, "_test"
    )
    with output.open(newline="") as handle:
        written = list(csv.DictReader(handle))
    require(len(written) == expected_rows, "robustness CSV has the wrong row count")
    require(
        {row["observable"] for row in written} == {"Q", "xi"},
        "robustness CSV omitted an observable",
    )

    keys = ANALYSIS.select_keys(points, 3.03, 3.06, 4)
    fits = ANALYSIS.fit_observables(
        keys, points, cells, metadata, 10, 20260729, 0.83, True
    )
    prefix_rows, prefix_failures = ANALYSIS.prefix_fit_diagnostics(
        keys, fits, cells, metadata, 10, 20260729, 0.83, True
    )
    require(
        len(prefix_rows) == 2 * len(ANALYSIS.PREFIX_FRACTIONS),
        "discarded-prefix diagnostics omitted a registered variant",
    )
    require(
        len(prefix_failures) == sum(row[-1] == 0 for row in prefix_rows),
        "discarded-prefix failures and rows disagree",
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        test_input_validation(path)
        test_protocol_and_robustness(path)
    test_scaling_fit()
    test_sampling_gates()
    test_ctau_comparison()
    print("All Stage 4 analysis tests passed.")


if __name__ == "__main__":
    main()
