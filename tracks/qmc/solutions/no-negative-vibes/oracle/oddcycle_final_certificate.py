"""One-command exact replay summary for the final oddcycle candidate."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path

import numpy
import sympy

from .oddcycle_metric_dual import exact_no_common_metric_certificate
from .oddcycle_pair_physical import exact_pair_physical_certificate
from .oddcycle_path_metric import exact_last_letter_path_metric_certificate


SCHEMA = "oddcycle-final-certificate-v1"


def _source_commit() -> str:
    root = Path(__file__).resolve().parents[1]
    try:
        commit_process = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        status_process = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    commit = commit_process.stdout.strip()
    if commit_process.returncode != 0 or len(commit) != 40:
        return "unavailable"
    if status_process.returncode != 0:
        return "unavailable"
    if status_process.stdout.strip():
        return f"dirty-worktree@{commit}"
    return commit


def final_certificate_summary() -> dict[str, object]:
    """Replay every exact publication gate and return compact JSON data."""

    started = time.perf_counter()
    theorem = exact_last_letter_path_metric_certificate()
    novelty = exact_no_common_metric_certificate()
    physical = exact_pair_physical_certificate()
    exact_payload = {
        "theorem": theorem,
        "novelty": novelty,
        "physical": physical,
    }
    digest = hashlib.sha256(
        json.dumps(
            exact_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    gates = {
        "arbitrary_word_determinant_positive": bool(
            theorem["exact_arbitrary_word_determinant_positive"]
        ),
        "no_common_strict_metric": (
            novelty["status"] == "exact-no-common-metric-certificate"
        ),
        "hermitian_interacting_positive_field_model": (
            physical["status"] == "exact-hermitian-interacting-transfer"
            and physical["normalized_auxiliary_fields"][
                "all_coefficients_positive"
            ]
            and physical["sign_free_gate"].startswith("closed by")
        ),
    }
    return {
        "schema": SCHEMA,
        "status": (
            "all-exact-gates-passed"
            if all(gates.values())
            else "exact-gate-failed"
        ),
        "source_commit": _source_commit(),
        "candidate": {
            "dimension": 5,
            "points": theorem["points"],
            "alphabet": (
                "B(1/1000)",
                "B(1/1000)^T",
                "B(4/5)",
                "B(4/5)^T",
            ),
        },
        "gates": gates,
        "exact_certificate_sha256": digest,
        "discovery_evidence": {
            "exhaustive_words_through_depth_12": 22_369_620,
            "exact_minimum_determinant": "176/5",
            "hodge_words_at_depth_14": 268_435_456,
            "hodge_depth_14_minimum": 0.998672912017811,
            "note": "search evidence only; the exact theorem is independent",
        },
        "physical": {
            "fock_dimension": physical["fock_dimension"],
            "shift": physical["c"],
            "field_coefficients": physical[
                "normalized_auxiliary_fields"
            ]["coefficients"],
            "non_gaussian_entry_count": physical["non_gaussian_gate"][
                "nonzero_entry_count"
            ],
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": numpy.__version__,
            "sympy": sympy.__version__,
        },
        "exact_replay_wall_seconds": time.perf_counter() - started,
    }


if __name__ == "__main__":  # pragma: no cover - CLI
    print(
        json.dumps(final_certificate_summary(), indent=2, sort_keys=True),
        flush=True,
    )
