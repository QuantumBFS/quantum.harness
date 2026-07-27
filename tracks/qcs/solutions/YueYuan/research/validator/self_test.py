#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VALIDATE = ROOT / "validate.py"
MANIFEST = ROOT / "MANIFEST.json"

EXPECTED = {
    "passing-synthetic": ("accepted", None, 0),
    "cheater": ("rejected", "forbidden_source", 1),
    "wrong-answer": ("rejected", "final_infidelity_above_threshold", 1),
    "timeout": ("rejected", "candidate_timeout", 1),
    "env-escape": ("rejected", "forbidden_source", 1),
    "lucky-noisy-fidelity": ("rejected", "no_exact_final_check", 1),
    "weak-baseline": ("rejected", "missing_required_method", 1),
    "cherry-picked-k": ("rejected", "missing_k_sweep", 1),
    "one-seed": ("rejected", "insufficient_seeds", 1),
    "too-easy-gap": ("rejected", "insufficient_gap_sweep", 1),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run YueYuan validator controls.")
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="yueyuan-validator-") as tmp:
        tmp_path = Path(tmp)
        control_results = {}
        for name, (expected_status, expected_error, expected_exit) in EXPECTED.items():
            report_path = tmp_path / f"{name}.json"
            candidate = ROOT / "controls" / name
            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE),
                    str(candidate),
                    "--instances",
                    "dev",
                    "--out",
                    str(report_path),
                    "--timeout-seconds",
                    str(args.timeout_seconds),
                ],
                text=True,
                capture_output=True,
            )
            if report_path.exists():
                report = json.loads(report_path.read_text())
                error_codes = [err.get("code") for err in report.get("errors", [])]
            else:
                report = {"status": "missing_report", "errors": []}
                error_codes = []
            ok = (
                result.returncode == expected_exit
                and report.get("status") == expected_status
                and (expected_error is None or expected_error in error_codes)
            )
            control_results[name] = {
                "ok": ok,
                "exit_code": result.returncode,
                "status": report.get("status"),
                "expected_status": expected_status,
                "expected_error": expected_error,
                "error_codes": error_codes,
            }

    summary = {
        "status": "passed" if all(item["ok"] for item in control_results.values()) else "failed",
        "ran_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "controls": control_results,
    }

    if args.write_manifest:
        manifest = json.loads(MANIFEST.read_text())
        manifest["self_test"] = summary
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
