#!/usr/bin/env python3
"""Lightweight acceptance tests for the Challenge-113 final package."""

from __future__ import annotations

import json
import hashlib
import math
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

CORE = Path(__file__).resolve().parents[1]
REPO = CORE.parent
FINAL = CORE / "final"


def finite_tree(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(finite_tree(item) for item in value)
    if isinstance(value, dict):
        return all(finite_tree(item) for item in value.values())
    return False


def canonical_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FinalContractTests(unittest.TestCase):
    def test_cli_help(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(CORE / "run_challenge.py"), "--help"],
            cwd=REPO,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--mwe", completed.stdout)
        self.assertIn("--full", completed.stdout)
        self.assertIn("--output", completed.stdout)

    def test_independent_audit(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(CORE / "code" / "attempt50_result_audit.py"),
                "--verify-only",
            ],
            cwd=REPO,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("pass; checks=18/18", completed.stdout)

    def test_queries_to_target_delivery(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(CORE / "code" / "attempt51_queries_to_target.py"),
                "--verify-only",
            ],
            cwd=REPO,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("pass; checks=11/11", completed.stdout)
        payload = json.loads(
            (
                CORE
                / "results_summary"
                / "QL1F-attempt51-queries-to-target.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(payload["status"], "pass")
        self.assertTrue(all(payload["checks"].values()))
        self.assertEqual(
            [row["search_dimension"] for row in payload["development"]],
            [5, 10, 15, 20, 40],
        )
        self.assertTrue(
            (CORE / "plots" / "attempt51-queries-to-target.png").is_file()
        )

    def test_gap_invariant_delivery(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(
                    CORE
                    / "code"
                    / "attempt52_gap_invariant_audit.py"
                ),
                "--verify-only",
            ],
            cwd=REPO,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("pass; checks=22/22", completed.stdout)
        payload = json.loads(
            (
                CORE
                / "results_summary"
                / "QL1F-attempt52-gap-invariant-audit.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(payload["status"], "pass")
        self.assertTrue(all(payload["checks"].values()))
        self.assertEqual(
            sorted(
                {
                    row["dimension"]
                    for row in payload["cross_size_invariant"]["rows"]
                }
            ),
            [2, 3, 4],
        )

    def test_final_json_contract(self) -> None:
        run = json.loads((FINAL / "run.json").read_text(encoding="utf-8"))
        report = json.loads(
            (FINAL / "report.json").read_text(encoding="utf-8")
        )
        self.assertTrue(finite_tree(run))
        self.assertTrue(finite_tree(report))
        self.assertEqual(run["challenge"]["number"], 113)
        self.assertEqual(run["challenge"]["status"], "complete")
        self.assertEqual(len(run["figures"]), 3)
        figure_ids = {figure["id"] for figure in run["figures"]}
        self.assertEqual(
            figure_ids,
            {"queries-to-target", "headline", "gap-and-invariant"},
        )
        self.assertTrue(
            all(figure["results"]["figure"] for figure in run["figures"])
        )
        self.assertEqual(
            run["results"]["queries_to_target_delivery"]["status"],
            "pass",
        )
        self.assertEqual(
            run["results"]["gap_invariant_delivery"]["status"],
            "pass",
        )
        formal_result = (
            CORE
            / "results_summary"
            / "QL1F-attempt49-fresh-confirmation.json"
        )
        self.assertEqual(
            run["provenance"]["formal_result_canonical_sha256"],
            canonical_sha256(formal_result),
        )
        self.assertNotIn(
            "formal_result_binary_sha256",
            run["provenance"],
        )
        self.assertEqual(
            [section["title"] for section in report["sections"]],
            ["Challenge", "Approach", "Results", "Highlight"],
        )

        serialized = json.dumps(
            {"run": run, "report": report}, ensure_ascii=False
        )
        for forbidden in (
            "C:\\Users\\",
            "/home/coder_",
            "/mnt/c/Users/",
            "D:\\study\\",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_offline_html_contract(self) -> None:
        raw = (FINAL / "report.html").read_bytes()
        text = raw.decode("utf-8")
        self.assertEqual(text.count("data:image/png;base64,"), 3)
        self.assertNotIn("Missing image", text)
        self.assertIn("Queries to target versus dimension", text)
        self.assertIn("Failure boundary and cross-size invariant", text)
        for title in ("Challenge", "Approach", "Results", "Highlight"):
            self.assertIn(title, text)

    def test_protected_notebook_absent(self) -> None:
        self.assertFalse(
            any(
                path.name == "neural_schrodinger.ipynb"
                for path in CORE.rglob("*")
            )
        )


if __name__ == "__main__":
    unittest.main()
