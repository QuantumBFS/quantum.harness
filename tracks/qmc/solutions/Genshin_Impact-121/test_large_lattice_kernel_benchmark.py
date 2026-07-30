from __future__ import annotations

import os

_THREAD_ENV = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)
for _name in _THREAD_ENV:
    os.environ[_name] = "1"

import json
import math
from pathlib import Path
import tempfile
import unittest

import large_lattice_kernel_benchmark as benchmark


class KernelBenchmarkTests(unittest.TestCase):
    def test_default_grid_is_declared_but_not_executed_on_import(self) -> None:
        self.assertEqual(benchmark.DEFAULT_SIZES, (4, 8, 12, 16))
        self.assertEqual(benchmark.DEFAULT_BETA, 4.0)
        self.assertGreaterEqual(benchmark.DEFAULT_REPEATS, 1)
        self.assertGreaterEqual(benchmark.DEFAULT_WARMUP, 0)
        self.assertTrue(all(os.environ[name] == "1" for name in _THREAD_ENV))

    def test_quick_insert_delete_correctness_and_strict_json(self) -> None:
        report = benchmark.run_benchmark(
            sizes=(2, 3),
            beta=0.5,
            seed=121_730_001,
            repeats=2,
            warmup=1,
        )
        self.assertIs(report["overall_correctness_pass"], True)
        self.assertEqual(report["parameters"]["sizes"], [2, 3])
        self.assertIs(
            report["single_thread_blas"]["set_before_numpy_import"],
            True,
        )
        self.assertEqual(
            set(
                report["single_thread_blas"]["environment"].values()
            ),
            {"1"},
        )
        self.assertEqual(
            len(report["provenance"]["benchmark_source_sha256"]),
            64,
        )
        self.assertEqual(
            len(report["provenance"]["ctqmc_source_sha256"]),
            64,
        )
        source_commit = report["provenance"]["source_commit"]
        self.assertTrue(source_commit is None or len(source_commit) == 40)

        for L, case in zip((2, 3), report["cases"]):
            with self.subTest(L=L):
                self.assertEqual(case["L"], L)
                self.assertEqual(case["N"], L * L)
                self.assertEqual(
                    case["order"], math.ceil(0.5 * L * L)
                )
                self.assertEqual(
                    case["fallback_count"],
                    {"insert": 0, "delete": 0},
                )
                self.assertIs(case["correctness"]["pass"], True)
                for move in ("insert", "delete"):
                    timing = case["latency"][move]
                    self.assertGreater(
                        timing["rank3"]["median_ns"], 0
                    )
                    self.assertGreater(
                        timing["full_word_rebuild"]["median_ns"], 0
                    )
                    self.assertEqual(
                        len(timing["rank3"]["samples_ns"]), 2
                    )
                    self.assertEqual(
                        len(
                            timing["full_word_rebuild"][
                                "samples_ns"
                            ]
                        ),
                        2,
                    )
                    self.assertGreater(
                        timing["speedup_dense_over_rank3"], 0.0
                    )
                    errors = case["correctness"][
                        f"{move}_max_error"
                    ]
                    self.assertLessEqual(
                        errors["T_relative_inf"], 1.0e-9
                    )
                    self.assertLessEqual(
                        errors["Q_relative_inf"], 1.0e-9
                    )
                    self.assertLessEqual(
                        errors["logdet_absolute"], 1.0e-9
                    )
                    self.assertLessEqual(
                        errors["log_ratio_absolute"], 1.0e-9
                    )
                    self.assertLessEqual(
                        errors["det_ratio_relative"], 1.0e-9
                    )

        encoded = json.dumps(
            report, allow_nan=False, sort_keys=True
        )
        decoded = json.loads(encoded)
        self.assertIs(decoded["overall_correctness_pass"], True)

    def test_cli_writes_atomic_resource_tsv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "benchmark.json"
            resource = root / "resource.tsv"
            code = benchmark.main([
                "--sizes", "2",
                "--beta", "0.5",
                "--repeats", "1",
                "--warmup", "0",
                "--output", str(output),
                "--resource-output", str(resource),
            ])
            self.assertEqual(code, 0)
            self.assertTrue(output.is_file())
            lines = resource.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0].split("\t")[0], "elapsed_seconds")
            self.assertGreaterEqual(float(lines[0].split("\t")[1]), 0.0)
            self.assertEqual(lines[1].split("\t")[0], "max_rss_kb")
            self.assertGreater(int(lines[1].split("\t")[1]), 0)

    def test_fixed_seed_reproduces_word_and_candidate_fixtures(self) -> None:
        arguments = {
            "L": 2,
            "beta": 0.5,
            "seed": 121_730_001,
            "repeats": 1,
            "warmup": 1,
        }
        first = benchmark.benchmark_size(**arguments)
        second = benchmark.benchmark_size(**arguments)
        self.assertEqual(
            first["word_sha256"], second["word_sha256"]
        )
        self.assertEqual(
            first["candidate_sha256"],
            second["candidate_sha256"],
        )
        self.assertEqual(first["order"], 2)
        self.assertEqual(second["order"], 2)
        self.assertEqual(
            first["word_sha256"],
            "c82de2ee2effcf61f353e85d315b9a540b560ebec4b8783d0fd433553d0e2b13",
        )
        self.assertEqual(
            first["candidate_sha256"],
            "1a2a7cf21550d83c7f18c6e8c5fb0cb58be3772078cfed18de71b3eb2fae277c",
        )


if __name__ == "__main__":
    unittest.main()
