"""Tests for the resumable two-hour RBIM production scheduler."""

import importlib.util
import json
import math
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np


_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE.parent / "random_bond_ising_production.py"


def _load_module():
    if not _SCRIPT.exists():
        raise AssertionError(f"missing production module: {_SCRIPT}")
    spec = importlib.util.spec_from_file_location(
        "random_bond_ising_production", _SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["random_bond_ising_production"] = module
    spec.loader.exec_module(module)
    return module


def _record(L=4, sample_index=0, seed=17):
    return {
        "L": L,
        "p": 0.1092212,
        "coupling": 1.0493604763025683,
        "sample_index": sample_index,
        "seed": seed,
        "burn_in": 10,
        "retained_rows": 100,
        "block_length": 10,
        "block_log_norm_means": [6.9, 7.0],
        "lyapunov": 6.95,
        "lyapunov_se": 0.05,
        "free_energy": -6.95 / L,
        "free_energy_se": 0.05 / L,
        "runtime_seconds": 0.1,
        "rows_per_second": 1100.0,
        "antiferromagnetic_bonds": round(0.1092212 * 2 * L * 100),
        "total_retained_bonds": 2 * L * 100,
        "disorder_ensemble": "fixed_count",
    }


def _slow_fake_runner(**kwargs):
    time.sleep(0.03)
    L = int(kwargs["L"])
    retained_rows = int(kwargs["retained_rows"])
    block_length = int(kwargs["block_length"])
    p = float(kwargs["p"])
    return {
        "L": L,
        "p": p,
        "coupling": 0.5 * math.log((1.0 - p) / p),
        "seed": int(kwargs["seed"]),
        "burn_in": int(kwargs["burn_in"]),
        "retained_rows": retained_rows,
        "block_length": block_length,
        "block_log_norm_means": np.array([6.9, 7.0]),
        "lyapunov": 6.95,
        "lyapunov_se": 0.05,
        "free_energy": -6.95 / L,
        "free_energy_se": 0.05 / L,
        "runtime_seconds": 0.03,
        "rows_per_second": retained_rows / 0.03,
        "antiferromagnetic_bonds": round(p * 2 * L * retained_rows),
        "total_retained_bonds": 2 * L * retained_rows,
        "disorder_ensemble": "fixed_count",
    }


class ProductionSchedulerTests(unittest.TestCase):
    def test_default_tasks_have_unique_indices_and_seeds(self):
        """Catches dropped, duplicated, or correlated production samples."""
        module = _load_module()
        self.assertEqual(sum(module.DEFAULT_SAMPLE_COUNTS.values()), 816)
        completed = {(4, 0), (12, 0)}

        tasks = module.build_tasks(module.DEFAULT_SAMPLE_COUNTS, completed)
        keys = [(item["L"], item["sample_index"]) for item in tasks]
        seeds = [
            module.sample_seed(1221092212, item["L"], item["sample_index"])
            for item in tasks
        ]

        self.assertEqual(len(tasks), 814)
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(seeds), len(set(seeds)))
        self.assertNotIn((4, 0), keys)
        self.assertNotIn((12, 0), keys)

    def test_atomic_records_resume_and_malformed_records_are_reported(self):
        """Catches interrupted output being silently counted as a sample."""
        module = _load_module()
        expected = {
            "p": 0.1092212,
            "burn_in": 10,
            "retained_rows": 100,
            "block_length": 10,
            "sample_counts": {4: 2},
        }
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            final_path = module.write_sample_record_atomic(
                _record(), output_dir
            )
            malformed = output_dir / "samples" / "L4" / "sample_0001.json"
            malformed.write_text("{not-json", encoding="utf-8")

            records, invalid = module.load_valid_records(output_dir, expected)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["sample_index"], 0)
            self.assertEqual(invalid, [malformed])
            self.assertEqual(json.loads(final_path.read_text())["L"], 4)
            self.assertFalse(final_path.with_suffix(".json.tmp").exists())

    def test_deadline_stops_new_submissions_and_drains_running_samples(self):
        """Catches a soft deadline that abandons valid work or runs unbounded."""
        module = _load_module()
        with tempfile.TemporaryDirectory() as temporary:
            result = module.run_production(
                sample_counts={4: 5},
                p=0.1092212,
                base_seed=122,
                burn_in=10,
                retained_rows=100,
                block_length=10,
                workers=2,
                soft_deadline_seconds=0.01,
                bootstrap_samples=20,
                output_dir=Path(temporary),
                strip_runner=_slow_fake_runner,
                executor_factory=ThreadPoolExecutor,
            )

            self.assertEqual(result["actual_counts"], {4: 2})
            self.assertTrue(result["deadline_reached"])
            records, invalid = module.load_valid_records(
                Path(temporary),
                {
                    "p": 0.1092212,
                    "burn_in": 10,
                    "retained_rows": 100,
                    "block_length": 10,
                    "sample_counts": {4: 5},
                },
            )
            self.assertEqual(len(records), 2)
            self.assertEqual(invalid, [])


if __name__ == "__main__":
    unittest.main()
