import json
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_bp_array_cell.py"
MODULE_SPEC = importlib.util.spec_from_file_location("run_bp_array_cell", SCRIPT)
ARRAY_ENTRYPOINT = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(ARRAY_ENTRYPOINT)


class ArrayEntrypointTests(unittest.TestCase):
    def test_inspect_selects_the_one_based_cell_from_the_real_run_spec_shape(self):
        spec = {
            "run_id": "test-run",
            "run_dir": "results/test-run",
            "settings": {"delta": "0.15"},
            "provenance": {"qasm_sha256": "abc"},
            "cells": [
                {"cell_id": "cell-0001", "params": {"seed": 2, "chi": 192}},
                {"cell_id": "cell-0002", "params": {"seed": 2, "chi": 512}},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "run_spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--inspect-only",
                    "--run-spec",
                    str(spec_path),
                    "--selector",
                    "2",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "cell_id": "cell-0002",
                "params": {"seed": 2, "chi": 512},
                "settings": {"delta": "0.15"},
                "provenance": {"qasm_sha256": "abc"},
                "run_dir": "results/test-run",
            },
        )

    def test_confirmation_token_is_extracted_from_runner_output(self):
        output = "\n".join(
            [
                "problem=operator_loschmidt_echo_49x648",
                "confirmation_token=0123456789abcdef",
                "dry_run=true; no tensor-network computation was started",
            ]
        )
        parser = getattr(ARRAY_ENTRYPOINT, "parse_confirmation_token", lambda _: None)
        self.assertEqual(parser(output), "0123456789abcdef")

    def test_result_path_preserves_seed_padding_and_delta_directory(self):
        builder = getattr(ARRAY_ENTRYPOINT, "result_path", lambda *_: None)
        self.assertEqual(
            builder(
                Path("/work/ole"),
                {"seed": 7, "chi": 512, "delta": "0.15"},
            ),
            Path(
                "/work/ole/runs/baseline-49x648/"
                "delta-0p15/chi-512/seed-0007.toml"
            ),
        )

    def test_manifest_echoes_declared_cell_and_summarizes_completed_result(self):
        builder = getattr(
            ARRAY_ENTRYPOINT,
            "success_manifest",
            lambda *_: {"status": None},
        )
        payload = {
            "cell_id": "cell-0002",
            "params": {"seed": 2, "chi": 512, "delta": "0.15"},
            "settings": {"dtype": "ComplexF64"},
            "provenance": {"qasm_sha256": "abc"},
            "run_dir": "results/test-run",
        }
        document = {
            "run": {"status": "complete"},
            "result": {
                "seed_id": 2,
                "maxdim": 512,
                "sample_value": 0.82,
                "wall_seconds": 123.0,
                "peak_rss_bytes": 4096,
                "max_truncation_error": 1.0e-9,
                "sum_truncation_error": 2.0e-9,
                "layers": [
                    {"bp_residual": 1.0e-10, "bp_converged": True},
                    {"bp_residual": 2.0e-10, "bp_converged": False},
                ],
            },
        }

        manifest = builder(payload, document, Path("/work/result.toml"))

        self.assertEqual(manifest["status"], "success")
        self.assertEqual(manifest["cell_id"], "cell-0002")
        self.assertEqual(manifest["params"], payload["params"])
        self.assertEqual(manifest["settings"], payload["settings"])
        self.assertEqual(manifest["provenance"], payload["provenance"])
        self.assertEqual(manifest["source_result"], "/work/result.toml")
        self.assertEqual(
            manifest["result"],
            {
                "sample_value": 0.82,
                "wall_seconds": 123.0,
                "peak_rss_bytes": 4096,
                "max_truncation_error": 1.0e-9,
                "sum_truncation_error": 2.0e-9,
                "max_bp_residual": 2.0e-10,
                "bp_nonconverged_layers": 1,
            },
        )

    def test_run_cell_uses_dry_run_token_and_writes_success_manifest(self):
        payload = {
            "cell_id": "cell-0001",
            "params": {"seed": 2, "chi": 512, "delta": "0.15"},
            "settings": {"dtype": "ComplexF64"},
            "provenance": {"qasm_sha256": "abc"},
            "run_dir": "results/test-run",
        }
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            ole_root = workspace / "ole"
            (ole_root / "scripts").mkdir(parents=True)
            (ole_root / "scripts" / "run_bp.jl").write_text("", encoding="utf-8")
            fake_julia = workspace / "fake_julia.py"
            fake_julia.write_text(
                """#!/usr/bin/env python3
import pathlib
import sys

args = sys.argv[1:]
root = pathlib.Path(next(x.split("=", 1)[1] for x in args if x.startswith("--project=")))
if "--execute" not in args:
    print("confirmation_token=0123456789abcdef")
    print("dry_run=true; no tensor-network computation was started")
    raise SystemExit(0)
seed = int(args[args.index("--seed") + 1])
chi = int(args[args.index("--chi") + 1])
token = args[args.index("--confirm") + 1]
if token != "0123456789abcdef":
    raise SystemExit(3)
result = root / "runs" / "baseline-49x648" / "delta-0p15" / f"chi-{chi}" / f"seed-{seed:04d}.toml"
result.parent.mkdir(parents=True, exist_ok=True)
result.write_text('''[run]
status = "complete"
[result]
seed_id = 2
maxdim = 512
sample_value = 0.82
wall_seconds = 123.0
peak_rss_bytes = 4096
max_truncation_error = 1.0e-9
sum_truncation_error = 2.0e-9
[[result.layers]]
bp_residual = 2.0e-10
bp_converged = true
''')
""",
                encoding="utf-8",
            )
            os.chmod(fake_julia, 0o755)
            runner = getattr(ARRAY_ENTRYPOINT, "run_cell", lambda *_: None)

            with redirect_stdout(io.StringIO()):
                manifest_path = runner(payload, ole_root, workspace, fake_julia)

            expected_path = (
                workspace
                / "results"
                / "test-run"
                / "cells"
                / "cell-0001"
                / "manifest.json"
            )
            self.assertEqual(manifest_path, expected_path)
            manifest = json.loads(expected_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "success")
            self.assertEqual(manifest["result"]["sample_value"], 0.82)


if __name__ == "__main__":
    unittest.main()
