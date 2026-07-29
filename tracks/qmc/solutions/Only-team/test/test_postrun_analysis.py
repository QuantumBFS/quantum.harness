from __future__ import annotations

import csv
import hashlib
import importlib
import json
import math
import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parents[3]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_synthetic_cell(
    run_dir: Path,
    cell_id: str,
    *,
    lattice: str = "triangular",
    size: int = 12,
    field: float = 4.76811,
    requested_dt: float = 0.013,
    seeds: list[str] | None = None,
    bin_count: int = 32,
    nonfinite_bin: int | None = None,
) -> Path:
    cell_dir = run_dir / "cells" / cell_id
    qmc_dir = cell_dir / "qmc"
    qmc_dir.mkdir(parents=True)
    beta = size / field
    ltrot = math.ceil(beta / requested_dt)
    if ltrot % 2:
        ltrot += 1
    actual_dt = beta / ltrot
    seeds = seeds or [str(10_000 + index) for index in range(32)]

    bins_path = qmc_dir / "bins.csv"
    with bins_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["bin", "m2_bin", "m4_bin", "Q_bin"],
        )
        writer.writeheader()
        for index in range(1, bin_count + 1):
            m2 = 0.1 + index * 1e-4
            m4 = 0.02 + index * 2e-5
            q_value = m2 * m2 / m4
            if nonfinite_bin == index:
                q_value = float("nan")
            writer.writerow(
                {
                    "bin": index,
                    "m2_bin": repr(m2),
                    "m4_bin": repr(m4),
                    "Q_bin": repr(q_value),
                }
            )

    metadata_path = qmc_dir / "metadata.toml"
    metadata_path.write_text(
        f"""[actual_parameters]
BetaT = {beta!r}
Dltau = {actual_dt!r}
FixedDltau = {requested_dt!r}
IfSetDltau = true
J1 = -1.0
J2 = 0.0
LTrot = {ltrot}
NumL1 = {size}
NumL2 = {size}
NumNS = {size * size}
hTrfd = {field!r}
initial_state = "random"
input_LTrot = {ltrot}
lattice = "{lattice}"
nLocal = 1
nWolff = 5
seed = "20260729"

[runtime]
julia_version = "1.12.6"
mpi_size = 32
rank_seeds = {json.dumps(seeds)}
wall_time_seconds = 10.0

[sampling]
NSwep = 2000
NmBin = 32
NmMeaConfg = 10
nWarm = 10000
total_measurements = 2048000

[statistics]
discard_initial_bins = 1
number_of_bins_after_filtering = 29
number_of_bins_before_filtering = 32
statistics_mode = "bin_sem"
trim_extrema = true
""",
        encoding="utf-8",
    )
    results_path = qmc_dir / "results.csv"
    results_path.write_text(
        "lattice,nprocs,total_measurements,m2,m2_error,binder_Q,"
        "binder_Q_error\n"
        f"{lattice},32,2048000,0.1,0.001,0.5,0.002\n",
        encoding="utf-8",
    )
    config_path = cell_dir / "config.toml"
    config_path.write_text("J1 = -1.0\nJ2 = 0.0\n", encoding="utf-8")
    context_path = cell_dir / "cell_context.json"
    context_path.write_text("{}\n", encoding="utf-8")

    actual = {
        "BetaT": beta,
        "Dltau": actual_dt,
        "FixedDltau": requested_dt,
        "IfSetDltau": True,
        "J1": -1.0,
        "J2": 0.0,
        "LTrot": ltrot,
        "NumL1": size,
        "NumL2": size,
        "NumNS": size * size,
        "hTrfd": field,
        "initial_state": "random",
        "input_LTrot": ltrot,
        "lattice": lattice,
        "nLocal": 1,
        "nWolff": 5,
        "seed": "20260729",
    }
    manifest = {
        "schema_version": 1,
        "state": "success",
        "run_id": run_dir.name,
        "cell_id": cell_id,
        "role": "scan",
        "params": {
            "lattice": lattice,
            "L": size,
            "hTrfd": field,
            "FixedDltau": requested_dt,
            "scan_kind": "main",
        },
        "settings": {
            "J1": -1.0,
            "J2": 0.0,
            "nLocal": 1,
            "nWolff": 5,
            "nWarm": 10000,
            "NmBin": 32,
            "NSwep": 2000,
            "NmMeaConfg": 10,
            "nprocs": 32,
            "discard_initial_bins": 1,
            "trim_extrema": True,
            "statistics_mode": "bin_sem",
        },
        "actual_parameters": actual,
        "observables": {
            "m2": 0.1,
            "m2_error": 0.001,
            "binder_Q": 0.5,
            "binder_Q_error": 0.002,
        },
        "runtime": {
            "mpi_size": 32,
            "rank_seed_count": 32,
            "wall_time_seconds": 10.0,
        },
        "hashes": {
            "bins.csv": digest(bins_path),
            "metadata.toml": digest(metadata_path),
            "results.csv": digest(results_path),
            "config.toml": digest(config_path),
            "cell_context.json": digest(context_path),
        },
    }
    (cell_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return cell_dir


def write_run_spec(run_dir: Path, cells: list[tuple[str, dict]]) -> None:
    (run_dir / "run_spec.json").write_text(
        json.dumps(
            {
                "run_id": run_dir.name,
                "run_dir": str(run_dir),
                "settings": {},
                "provenance": {},
                "cells": [
                    {"cell_id": cell_id, "params": params}
                    for cell_id, params in cells
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


class AuditChallengeResultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = importlib.import_module("audit_challenge_results")

    def test_complete_cell_passes_integrity_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run-a"
            cell_dir = write_synthetic_cell(run_dir, "cell-0001")
            record = self.audit.load_cell(cell_dir)
            self.assertEqual(record.bin_count, 32)
            self.assertEqual(record.rank_seed_count, 32)
            self.assertEqual(record.distinct_rank_seed_count, 32)
            self.assertTrue(record.hashes_valid)
            self.assertEqual(record.issues, [])
            self.assertTrue(math.isfinite(record.z_m2))
            self.assertTrue(math.isfinite(record.z_Q))

    def test_corrupt_hash_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run-a"
            cell_dir = write_synthetic_cell(run_dir, "cell-0001")
            with (cell_dir / "qmc" / "bins.csv").open(
                "a",
                encoding="utf-8",
            ) as stream:
                stream.write("\n")
            record = self.audit.load_cell(cell_dir)
            self.assertIn("hash_mismatch:bins.csv", record.issues)
            self.assertFalse(record.hashes_valid)

    def test_missing_bin_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run-a"
            cell_dir = write_synthetic_cell(
                run_dir,
                "cell-0001",
                bin_count=31,
            )
            record = self.audit.load_cell(cell_dir)
            self.assertIn("bin_count:31", record.issues)

    def test_nonfinite_bin_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run-a"
            cell_dir = write_synthetic_cell(
                run_dir,
                "cell-0001",
                nonfinite_bin=9,
            )
            record = self.audit.load_cell(cell_dir)
            self.assertIn("nonfinite_bin:9", record.issues)

    def test_duplicate_rank_seed_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run-a"
            seeds = [str(10_000 + index) for index in range(31)] + ["10000"]
            cell_dir = write_synthetic_cell(
                run_dir,
                "cell-0001",
                seeds=seeds,
            )
            record = self.audit.load_cell(cell_dir)
            self.assertIn("distinct_rank_seed_count:31", record.issues)

    def test_run_audit_reports_missing_and_duplicate_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_a = root / "run-a"
            run_b = root / "run-b"
            params = {
                "lattice": "triangular",
                "L": 12,
                "hTrfd": 4.76811,
                "FixedDltau": 0.013,
            }
            write_synthetic_cell(run_a, "cell-0001")
            write_synthetic_cell(run_b, "cell-0001")
            write_run_spec(
                run_a,
                [
                    ("cell-0001", params),
                    ("cell-0002", {**params, "hTrfd": 4.76911}),
                ],
            )
            write_run_spec(run_b, [("cell-0001", params)])
            report = self.audit.audit_runs([run_a, run_b])
            self.assertEqual(report.total_cells, 2)
            self.assertEqual(report.unique_parameter_cells, 1)
            self.assertEqual(report.missing_cells, ["run-a/cell-0002"])
            self.assertEqual(
                report.duplicate_parameter_cells,
                [["run-a/cell-0001", "run-b/cell-0001"]],
            )

    def test_real_completed_runs_have_177_unique_cells(self) -> None:
        results_root = REPO_ROOT / "tracks" / "qmc" / "results" / "Only-team"
        run_dirs = [
            results_root / "challenge-extremes-min-20260729",
            results_root / "challenge-extremes-max-20260729",
            results_root / "challenge-production-triangular-20260729",
            results_root / "challenge-production-honeycomb-20260729",
        ]
        if not all(path.is_dir() for path in run_dirs):
            self.skipTest("completed challenge runs are not available")
        report = self.audit.audit_runs(run_dirs)
        self.assertEqual(report.total_cells, 177)
        self.assertEqual(report.unique_parameter_cells, 177)
        self.assertEqual(report.failed_cells, [])
        self.assertEqual(report.missing_cells, [])
        self.assertEqual(report.duplicate_parameter_cells, [])


class AssembleChallengeDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = importlib.import_module("audit_challenge_results")
        cls.assemble = importlib.import_module("assemble_challenge_dataset")

    def test_synthetic_rows_have_exact_columns_and_actual_dtau(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run-a"
            cell_dir = write_synthetic_cell(run_dir, "cell-0001")
            report = self.audit.audit_runs([run_dir])
            cell_rows = self.assemble.assemble_cells(report)
            bin_rows = self.assemble.assemble_bins(report)
            self.assertEqual(list(cell_rows[0]), self.assemble.CELL_COLUMNS)
            self.assertEqual(list(bin_rows[0]), self.assemble.BIN_COLUMNS)
            self.assertEqual(cell_rows[0]["Dltau"], self.audit.load_cell(cell_dir).Dltau)
            self.assertEqual(len(bin_rows), 32)

    def test_sorting_and_output_bytes_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "run-a"
            write_synthetic_cell(
                run_dir,
                "cell-0002",
                lattice="triangular",
                size=16,
                field=4.76911,
            )
            write_synthetic_cell(
                run_dir,
                "cell-0001",
                lattice="honeycomb",
                size=12,
                field=2.13101,
            )
            report = self.audit.audit_runs([run_dir])
            rows = self.assemble.assemble_cells(report)
            self.assertEqual(
                [(row["lattice"], row["L"]) for row in rows],
                [("honeycomb", 12), ("triangular", 16)],
            )
            first = root / "first"
            second = root / "second"
            self.assemble.write_dataset(report, first)
            self.assemble.write_dataset(report, second)
            self.assertEqual(digest(first / "cells.csv"), digest(second / "cells.csv"))
            self.assertEqual(digest(first / "bins.csv"), digest(second / "bins.csv"))

    def test_real_dataset_has_expected_shape_and_unique_keys(self) -> None:
        results_root = REPO_ROOT / "tracks" / "qmc" / "results" / "Only-team"
        run_dirs = [
            results_root / "challenge-extremes-min-20260729",
            results_root / "challenge-extremes-max-20260729",
            results_root / "challenge-production-triangular-20260729",
            results_root / "challenge-production-honeycomb-20260729",
        ]
        if not all(path.is_dir() for path in run_dirs):
            self.skipTest("completed challenge runs are not available")
        report = self.audit.audit_runs(run_dirs)
        cell_rows = self.assemble.assemble_cells(report)
        bin_rows = self.assemble.assemble_bins(report)
        self.assertEqual(len(cell_rows), 177)
        self.assertEqual(len(bin_rows), 177 * 32)
        keys = {
            (
                row["lattice"],
                row["L"],
                row["hTrfd"],
                row["FixedDltau"],
                row["Dltau"],
            )
            for row in cell_rows
        }
        self.assertEqual(len(keys), 177)


class QualityGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = importlib.import_module("audit_challenge_results")

    def decision(
        self,
        *,
        lattice: str = "triangular",
        size: int = 40,
        z_m2: float = 3.0,
        z_q: float = 3.0,
        binder_error: float = 1.0e-4,
        issues: list[str] | None = None,
    ):
        cell = types.SimpleNamespace(
            lattice=lattice,
            L=size,
            z_m2=z_m2,
            z_Q=z_q,
            binder_Q_error=binder_error,
            issues=issues or [],
        )
        return self.audit.evaluate_quality(cell)

    def test_exact_boundaries_pass(self) -> None:
        decision = self.decision()
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.reasons, [])

    def test_values_above_boundaries_are_named(self) -> None:
        self.assertIn(
            "z_m2>3",
            self.decision(z_m2=math.nextafter(3.0, math.inf)).reasons,
        )
        self.assertIn(
            "z_Q>3",
            self.decision(z_q=math.nextafter(3.0, math.inf)).reasons,
        )
        self.assertIn(
            "triangular_L>=40_binder_Q_error>1e-4",
            self.decision(
                binder_error=math.nextafter(1.0e-4, math.inf),
            ).reasons,
        )

    def test_honeycomb_large_sizes_are_diagnostic_only(self) -> None:
        decision = self.decision(
            lattice="honeycomb",
            size=32,
            binder_error=9.0e-4,
        )
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.reasons, [])
        self.assertEqual(decision.diagnostics, ["honeycomb_L28_or_L32_binder_Q_error"])

    def test_integrity_failure_is_rejected(self) -> None:
        decision = self.decision(issues=["hash_mismatch:bins.csv"])
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reasons, ["integrity_audit"])

    def test_ratified_selection_keeps_every_unique_cell_and_is_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "run-a"
            write_synthetic_cell(run_dir, "cell-0001")
            report = self.audit.audit_runs([run_dir])
            selection_path = root / "accepted_cells.json"
            payload = self.audit.write_selection(report, selection_path)
            self.assertEqual(payload["selected_cell_count"], 1)
            self.assertEqual(len(payload["selection_payload_sha256"]), 64)
            self.assertEqual(
                json.loads(selection_path.read_text())["cells"][0]["cell_id"],
                "cell-0001",
            )


class BinderScalingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scaling = importlib.import_module("fit_binder_scaling")

    def synthetic_rows(self, terms: frozenset[str]):
        theta = {
            "h_c": 2.13237,
            "Q_star": 0.55,
            "a1": -0.08,
            "b1": 0.12,
            "a2": 0.01,
            "b2": -0.03,
            "c1": 0.02,
        }
        rows = []
        bins = []
        for size in (12, 16, 20, 24, 32):
            for offset_index, offset in enumerate((-0.003, -0.0015, 0.0, 0.0015, 0.003)):
                field = theta["h_c"] + offset
                q_value = float(
                    self.scaling.binder_model(
                        theta,
                        np.array([size], dtype=float),
                        np.array([field]),
                        terms,
                    )[0]
                )
                cell_id = f"L{size}-h{offset_index}"
                rows.append(
                    {
                        "run_id": "synthetic",
                        "cell_id": cell_id,
                        "lattice": "honeycomb",
                        "L": size,
                        "hTrfd": field,
                        "FixedDltau": 0.013,
                        "Dltau": 0.01299,
                        "binder_Q": q_value,
                        "binder_Q_error": 1.0e-5,
                    }
                )
                perturbations = [0.0, 0.0]
                for index in range(1, 16):
                    perturbations.extend((-index * 2.0e-6, index * 2.0e-6))
                for bin_number, perturbation in enumerate(perturbations, start=1):
                    q_bin = q_value + perturbation
                    bins.append(
                        {
                            "run_id": "synthetic",
                            "cell_id": cell_id,
                            "lattice": "honeycomb",
                            "L": size,
                            "hTrfd": field,
                            "FixedDltau": 0.013,
                            "Dltau": 0.01299,
                            "bin": bin_number,
                            "m2_bin": 0.1,
                            "m4_bin": 0.01 / q_bin,
                            "Q_bin": q_bin,
                        }
                    )
        return theta, rows, bins

    def test_noiseless_fit_recovers_known_critical_field(self) -> None:
        terms = frozenset({"a2", "b2", "c1"})
        theta, rows, _ = self.synthetic_rows(terms)
        fit = self.scaling.fit_variant(rows, "honeycomb", 12, terms)
        self.assertTrue(fit.converged)
        self.assertAlmostEqual(fit.parameters["h_c"], theta["h_c"], delta=1.0e-10)
        self.assertGreater(fit.dof, 0)

    def test_scan_external_critical_field_is_recovered_and_flagged(self) -> None:
        terms = frozenset({"a2"})
        theta = {
            "h_c": 2.140,
            "Q_star": 0.55,
            "a1": -0.08,
            "b1": 0.12,
            "a2": 0.01,
        }
        rows = []
        for size in (12, 16, 20, 24, 32):
            for field in (2.132, 2.133, 2.134):
                q_value = self.scaling.binder_model(
                    theta,
                    np.array([size]),
                    np.array([field]),
                    terms,
                )[0]
                rows.append(
                    {
                        "run_id": "synthetic",
                        "cell_id": f"L{size}-h{field}",
                        "lattice": "honeycomb",
                        "L": size,
                        "hTrfd": field,
                        "FixedDltau": 0.013,
                        "Dltau": 0.01299,
                        "binder_Q": q_value,
                        "binder_Q_error": 1.0e-5,
                    }
                )
        fit = self.scaling.fit_variant(rows, "honeycomb", 12, terms)
        self.assertAlmostEqual(fit.parameters["h_c"], theta["h_c"], delta=1.0e-9)
        self.assertFalse(fit.h_c_inside_scan)
        self.assertFalse(fit.boundary_contact)

    def test_bootstrap_interval_contains_injected_value(self) -> None:
        terms = frozenset()
        theta, rows, bins = self.synthetic_rows(terms)
        fit_spec = self.scaling.FitSpec(
            rows=rows,
            lattice="honeycomb",
            Lmin=12,
            terms=terms,
        )
        result = self.scaling.bootstrap_variant(
            bins,
            fit_spec,
            samples=100,
            rng=np.random.default_rng(20260729),
        )
        self.assertGreaterEqual(result.success_fraction, 0.95)
        self.assertLessEqual(result.h_c_ci95[0], theta["h_c"])
        self.assertGreaterEqual(result.h_c_ci95[1], theta["h_c"])


class DtauExtrapolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.extrapolate = importlib.import_module("extrapolate_dtau")

    def test_weighted_linear_dtau2_fit_recovers_intercept(self) -> None:
        h_zero = 4.76821
        slope = 27.5
        points = [
            {"dtau2": dt**2, "h_c": h_zero + slope * dt**2, "error": 2.0e-5}
            for dt in (0.013, 0.016, 0.020)
        ]
        result = self.extrapolate.linear_dtau2_fit(points)
        self.assertAlmostEqual(result.h_c_zero, h_zero, delta=1.0e-12)
        self.assertAlmostEqual(result.slope, slope, delta=1.0e-10)
        self.assertEqual(result.dof, 1)

    def test_ratio_bootstrap_reports_sqrt5_offset(self) -> None:
        honey = np.array([2.0, 2.0, 2.0, 2.0])
        triangular = honey * math.sqrt(5.0) + np.array([-1e-4, 0.0, 1e-4, 0.0])
        result = self.extrapolate.ratio_bootstrap(triangular, honey)
        self.assertAlmostEqual(result.median, math.sqrt(5.0), delta=1.0e-15)
        self.assertAlmostEqual(result.delta_sqrt5, 0.0, delta=1.0e-15)
        self.assertGreater(result.standard_error, 0.0)


class PlotSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plotting = importlib.import_module("plot_challenge_results")

    def assert_pair(self, path: Path) -> None:
        self.assertGreater(path.stat().st_size, 1000)
        self.assertGreater(path.with_suffix(".pdf").stat().st_size, 1000)

    def test_all_plot_functions_create_png_and_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cells = [
                {
                    "lattice": "triangular",
                    "L": size,
                    "hTrfd": field,
                    "FixedDltau": 0.013,
                    "binder_Q": 0.55 - (field - 4.768) * size,
                    "binder_Q_error": 2e-4,
                    "quality_status": "pass",
                }
                for size in (12, 16)
                for field in (4.767, 4.768, 4.769)
            ]
            binder_path = root / "binder.png"
            self.plotting.plot_binder_curves(cells, "triangular", binder_path)
            self.assert_pair(binder_path)

            fits = [
                {
                    "lattice": lattice,
                    "Lmin": lmin,
                    "terms": terms,
                    "h_c": value,
                    "h_c_bootstrap_std": 2e-5,
                    "bootstrap_success_fraction": 1.0,
                }
                for lattice, value in (("triangular", 4.7681), ("honeycomb", 2.1325))
                for lmin in (12, 16, 20)
                for terms in ("a2", "a2+c1")
            ]
            stability_path = root / "stability.png"
            self.plotting.plot_fit_stability(fits, "both", stability_path)
            self.assert_pair(stability_path)

            collapse_fits = [
                {
                    "variant_id": f"{lattice}-Lmin16-a2",
                    "lattice": lattice,
                    "Lmin": 16,
                    "terms": "a2",
                    "h_c": critical,
                    "Q_star": 0.55,
                    "a1": -0.08,
                    "b1": 0.12,
                    "a2": 0.01,
                }
                for lattice, critical in (
                    ("triangular", 4.768),
                    ("honeycomb", 2.1325),
                )
            ]
            collapse_cells = [
                {
                    "lattice": lattice,
                    "L": size,
                    "hTrfd": critical + offset,
                    "FixedDltau": 0.013,
                    "binder_Q": (
                        0.55
                        - 0.08 * offset * size**self.plotting.YT
                        + 0.12 * size**self.plotting.YI
                        + 0.01 * offset**2 * size ** (2.0 * self.plotting.YT)
                    ),
                    "binder_Q_error": 2e-4,
                    "quality_status": "pass",
                }
                for lattice, critical in (
                    ("triangular", 4.768),
                    ("honeycomb", 2.1325),
                )
                for size in (16, 20)
                for offset in (-0.001, 0.0, 0.001)
            ]
            collapse_path = root / "collapse.png"
            self.plotting.plot_data_collapse(
                collapse_cells,
                collapse_fits,
                collapse_path,
            )
            self.assert_pair(collapse_path)

            dtau = [
                {
                    "record_type": "step",
                    "lattice": lattice,
                    "actual_dtau2_mean": dt**2,
                    "h_c": base + slope * dt**2,
                    "h_c_error": 3e-5,
                    "inside_field_scan": dt == 0.013,
                }
                for lattice, base, slope in (
                    ("triangular", 4.7681, 20.0),
                    ("honeycomb", 2.1325, 2.0),
                )
                for dt in (0.013, 0.016, 0.020)
            ]
            dtau_path = root / "dtau.png"
            self.plotting.plot_dtau_extrapolation(dtau, "both", dtau_path)
            self.assert_pair(dtau_path)

            ratio_path = root / "ratio.png"
            self.plotting.plot_ratio(
                {
                    "median": math.sqrt(5.0),
                    "ci95": [2.235, 2.237],
                    "standard_error": 5e-4,
                    "sqrt5": math.sqrt(5.0),
                },
                ratio_path,
            )
            self.assert_pair(ratio_path)


class ChallengeRunRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = importlib.import_module("build_challenge_run")

    def test_real_run_record_contains_required_provenance(self) -> None:
        analysis_dir = (
            REPO_ROOT
            / "tracks"
            / "qmc"
            / "results"
            / "Only-team"
            / "challenge-analysis-20260729"
        )
        required = [
            "raw_inventory.json",
            "audit.json",
            "cells.csv",
            "finite_size_fits.csv",
            "dtau_fits.csv",
            "final_results.json",
        ]
        if not all((analysis_dir / name).is_file() for name in required):
            self.skipTest("completed challenge analysis is not available")
        record = self.builder.build_run(analysis_dir)
        self.assertEqual(record["model"]["J1"], -1.0)
        self.assertEqual(record["model"]["J2"], 0.0)
        self.assertEqual(record["audit"]["unique_parameter_cells"], 177)
        self.assertEqual(record["audit"]["failed_cells"], [])
        self.assertEqual(len(record["finite_size"]["variants"]), 64)
        self.assertEqual(len(record["time_step"]["step_variants"]), 6)
        self.assertIn("ratio", record["results"])
        self.assertIn("raw_inventory_sha256", record["provenance"])
        self.assertGreaterEqual(len(record["figures"]), 5)
        self.assertTrue(all("src" in figure for figure in record["figures"]))
        json.dumps(record, allow_nan=False)
        report = self.builder.build_report(record)
        self.assertEqual(len(report["sections"]), 4)
        self.assertEqual(
            [section["title"] for section in report["sections"]],
            ["Challenge", "Approach", "Results", "Highlight"],
        )
        result_blocks = report["sections"][2]["blocks"]
        figure_sources = [
            item["src"]
            for block in result_blocks
            if block.get("kind") == "figures"
            for item in block["items"]
        ]
        self.assertIn("figures/data_collapse.png", figure_sources)
        self.assertLess(
            figure_sources.index("figures/data_collapse.png"),
            figure_sources.index("figures/dtau2_extrapolation.png"),
        )
        figure_ids = [figure["id"] for figure in record["figures"]]
        self.assertIn("data-collapse", figure_ids)
        self.assertIn("DRAFT", report["eyebrow"])
        json.dumps(report, allow_nan=False)


class PrecisionRecoverySpecificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generator = importlib.import_module(
            "generate_precision_recovery_specs"
        )

    def test_exact_approved_cells_are_unique_and_longest_first(self) -> None:
        expected_counts = {"triangular": 45, "honeycomb": 21}
        expected_sizes = {
            "triangular": {32, 40, 48},
            "honeycomb": {24, 28, 32},
        }
        expected_steps = {
            "triangular": {0.010, 0.013, 0.016},
            "honeycomb": {0.010, 0.016},
        }
        for lattice in ("triangular", "honeycomb"):
            spec = self.generator.build_spec(lattice)
            cells = spec["cells"]
            self.assertEqual(len(cells), expected_counts[lattice])
            keys = {
                (
                    cell["params"]["L"],
                    cell["params"]["hTrfd"],
                    cell["params"]["FixedDltau"],
                )
                for cell in cells
            }
            self.assertEqual(len(keys), expected_counts[lattice])
            self.assertEqual(
                {key[0] for key in keys},
                expected_sizes[lattice],
            )
            self.assertEqual(
                {key[2] for key in keys},
                expected_steps[lattice],
            )
            seeds = [cell["params"]["seed"] for cell in cells]
            self.assertEqual(len(seeds), len(set(seeds)))
            costs = [
                self.generator.cost_proxy(cell["params"])
                for cell in cells
            ]
            self.assertEqual(costs, sorted(costs, reverse=True))

            bundles = spec["execution"]["bundles"]
            expected_bundle_count = 12 if lattice == "triangular" else 8
            self.assertEqual(len(bundles), expected_bundle_count)
            covered = [
                index
                for bundle in bundles
                for index in bundle["cell_indices"]
            ]
            self.assertEqual(
                sorted(covered),
                list(range(1, expected_counts[lattice] + 1)),
            )
            self.assertEqual(len(covered), len(set(covered)))
            loads = [bundle["cost_proxy_sum"] for bundle in bundles]
            self.assertLessEqual(max(loads) / min(loads), 1.25)

    def test_array_scripts_request_32_ranks_and_six_hours(self) -> None:
        for lattice, count in (("triangular", 45), ("honeycomb", 21)):
            script = (
                PROJECT_ROOT
                / "scripts"
                / f"scnet-precision-recovery-{lattice}.sbatch"
            )
            source = script.read_text(encoding="utf-8")
            self.assertIn("#SBATCH --partition=xhacnormalb", source)
            self.assertIn("#SBATCH --nodes=1", source)
            self.assertIn("#SBATCH --ntasks=32", source)
            self.assertIn("#SBATCH --mem=64G", source)
            self.assertIn("#SBATCH --time=06:00:00", source)
            self.assertIn(f"#SBATCH --array=1-{count}%8", source)
            self.assertIn(
                f"challenge-precision-recovery-{lattice}-20260729/"
                "run_spec.json",
                source,
            )

    def test_bundle_scripts_fit_the_group_submission_limit(self) -> None:
        runner = (
            PROJECT_ROOT / "scripts" / "run_precision_recovery_bundle.sh"
        )
        runner_source = runner.read_text(encoding="utf-8")
        self.assertIn("execution", runner_source)
        self.assertIn("cell_indices", runner_source)
        self.assertIn("run_challenge_scan_cell.sh", runner_source)
        for lattice, count in (("triangular", 12), ("honeycomb", 8)):
            script = (
                PROJECT_ROOT
                / "scripts"
                / f"scnet-precision-recovery-{lattice}-bundle.sbatch"
            )
            source = script.read_text(encoding="utf-8")
            self.assertIn("#SBATCH --partition=xhacnormalb", source)
            self.assertIn("#SBATCH --ntasks=32", source)
            self.assertIn("#SBATCH --mem=64G", source)
            self.assertIn("#SBATCH --time=10:00:00", source)
            self.assertIn(f"#SBATCH --array=1-{count}%{count}", source)
            self.assertIn(
                "run_precision_recovery_bundle.sh",
                source,
            )


if __name__ == "__main__":
    unittest.main()
