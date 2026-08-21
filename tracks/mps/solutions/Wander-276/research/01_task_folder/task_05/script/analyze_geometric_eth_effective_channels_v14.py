#!/usr/bin/env python3
"""Map archival evidence conservatively and evaluate the Paper-II title gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


VERSION = "v14"
SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO = SCRIPT_ROOT.parents[2]
OUTPUT_ROOT = SCRIPT_ROOT / "output"
THEORY_ROOT = OUTPUT_ROOT / "geometric_eth_theory_v14"
DEFAULT_THEORY = THEORY_ROOT / "channel_theory_v14.json"
DEFAULT_CHIRAL = THEORY_ROOT / "chiral_inference_v14.json"
DEFAULT_REGISTRY = OUTPUT_ROOT / "paper1_prb_v13/evidence_registry_v13.json"
DEFAULT_ARCHIVAL_OUTPUT = THEORY_ROOT / "effective_channel_inference_v14.json"
DEFAULT_GATE_OUTPUT = THEORY_ROOT / "theory_gate_v14.json"

POSITIVE_TITLE = "The Geometric ETH: Statistical Closure on Degenerate Quantum State Bundles"
FALLBACK_TITLE = "Geometric Response of Exactly Degenerate Quantum State Bundles"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON input is not an object: {path}")
    return payload


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def evaluate_archival_mapping(registry: Mapping[str, Any]) -> dict[str, Any]:
    """Use only stored independent-unit covariance arrays; never impute them."""

    models = registry.get("models")
    if not isinstance(models, dict) or not models:
        raise RuntimeError("Paper-I evidence registry has no model records")
    mapped_cases: list[dict[str, Any]] = []
    excluded: dict[str, Any] = {}
    for model_name, record in models.items():
        independent = record.get("independent_ensemble_complete") is True
        covariance_arrays = record.get("independent_unit_response_covariances")
        independent_units = record.get("documented_independent_units")
        if independent and isinstance(covariance_arrays, list) and covariance_arrays and independent_units:
            # No current v13 record enters this branch.  It is deliberately
            # explicit so a later artifact must supply both arrays and units.
            mapped_cases.append(
                {
                    "model": model_name,
                    "independent_units": independent_units,
                    "covariance_array_count": len(covariance_arrays),
                }
            )
        else:
            missing = []
            if not independent:
                missing.append("independent Hamiltonian/disorder ensemble is incomplete")
            if not isinstance(covariance_arrays, list) or not covariance_arrays:
                missing.append("independent-unit response covariance arrays are absent")
            if not independent_units:
                missing.append("exchangeable independent units are undocumented")
            excluded[model_name] = {
                "eligible": False,
                "reason": "; ".join(missing),
                "historical_role": record.get("role"),
            }
    return {
        "version": VERSION,
        "schema": "geometric_eth_archival_effective_channel_inference_v14",
        "mapping_rule": (
            "compute N_eff only from stored response covariances indexed by documented independent units"
        ),
        "mapped_cases": mapped_cases,
        "excluded_models": excluded,
        "imputed_values": [],
        "retrospective_support_used_for_title_gate": False,
        "claim_boundary": (
            "Paper I contributes qualitative mechanism comparisons only; it does not validate the v14 channel law"
        ),
    }


def evaluate_theory_gate(
    channel_theory: Mapping[str, Any],
    chiral: Mapping[str, Any],
    archival: Mapping[str, Any],
) -> dict[str, Any]:
    analytic = bool(channel_theory.get("all_checks_pass") is True)
    exact = bool(chiral.get("checks", {}).get("all_exact_index_gates_pass") is True)
    random_pass = bool(
        chiral.get("random_primary", {}).get("all_validation_points_inside_band") is True
    )
    control = bool(
        chiral.get("structured_control", {}).get("at_least_one_control_separates") is True
    )
    quantitative = bool(chiral.get("quantitative_prediction_available") is True)
    passed = analytic and exact and random_pass and control and quantitative
    branch = chiral.get("selected_branch", "feasibility_failure")
    return {
        "version": VERSION,
        "schema": "geometric_eth_theory_gate_v14",
        "components": {
            "analytic_channel_theorem": analytic,
            "exact_chiral_index_and_seal": exact,
            "random_chiral_validation": random_pass,
            "structured_control_separation": control,
            "quantitative_prediction_available": quantitative,
            "archival_agreement_required": False,
            "archival_used_for_title_gate": bool(
                archival.get("retrospective_support_used_for_title_gate")
            ),
        },
        "passed": passed,
        "selected_branch": branch,
        "selected_title": POSITIVE_TITLE if passed else FALLBACK_TITLE,
        "forbidden_positive_title": FALLBACK_TITLE if passed else POSITIVE_TITLE,
        "positive_claim_allowed": passed,
        "failure_reason": None if passed else (
            "the prospective random chiral validation did not satisfy the sealed channel-law band"
            if analytic and exact and not random_pass
            else "one or more mandatory theorem, exactness, control, or prediction gates failed"
        ),
        "claim_boundary": [
            "a finite-channel cumulant identity is exact under its assumptions",
            "the failed prospective validation forbids claiming that those assumptions close the chiral response ensemble",
            "archival comparisons are retrospective and cannot rescue the prospective title gate",
            "no asymptotic, universal, thermalization, or black-hole theorem is established",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--theory", type=Path, default=DEFAULT_THEORY)
    parser.add_argument("--chiral", type=Path, default=DEFAULT_CHIRAL)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--archival-output", type=Path, default=DEFAULT_ARCHIVAL_OUTPUT)
    parser.add_argument("--gate-output", type=Path, default=DEFAULT_GATE_OUTPUT)
    arguments = parser.parse_args()

    theory = _load(arguments.theory)
    chiral = _load(arguments.chiral)
    registry = _load(arguments.registry)
    archival = evaluate_archival_mapping(registry)
    archival["source_hashes"] = {
        str(arguments.registry.relative_to(arguments.repo_root)): _sha256(arguments.registry),
        str(Path(__file__).resolve().relative_to(arguments.repo_root.resolve())): _sha256(Path(__file__)),
    }
    gate = evaluate_theory_gate(theory, chiral, archival)
    gate["source_hashes"] = {
        str(arguments.theory.relative_to(arguments.repo_root)): _sha256(arguments.theory),
        str(arguments.chiral.relative_to(arguments.repo_root)): _sha256(arguments.chiral),
        str(arguments.archival_output.relative_to(arguments.repo_root)): "written_in_same_atomic_run",
        str(Path(__file__).resolve().relative_to(arguments.repo_root.resolve())): _sha256(Path(__file__)),
    }
    _atomic_json(arguments.archival_output, archival)
    gate["source_hashes"][str(arguments.archival_output.relative_to(arguments.repo_root))] = _sha256(arguments.archival_output)
    _atomic_json(arguments.gate_output, gate)
    print(
        json.dumps(
            {
                "archival_output": str(arguments.archival_output),
                "gate_output": str(arguments.gate_output),
                "passed": gate["passed"],
                "selected_title": gate["selected_title"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
