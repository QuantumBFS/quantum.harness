#!/usr/bin/env python3
"""Build the compact final run and report documents for Challenge 113."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORE = HERE.parent
REPO_ROOT = CORE.parent
FINAL = CORE / "final"
RESULT_PATH = (
    CORE / "results_summary" / "QL1F-attempt49-fresh-confirmation.json"
)
AUDIT_PATH = CORE / "results_summary" / "QL1F-attempt50-final-audit.json"
FIGURE_PATH = CORE / "plots" / "attempt49-fresh-confirmation.png"
QUERY_RESULT_PATH = (
    CORE / "results_summary" / "QL1F-attempt51-queries-to-target.json"
)
QUERY_FIGURE_PATH = CORE / "plots" / "attempt51-queries-to-target.png"
INVARIANT_RESULT_PATH = (
    CORE / "results_summary" / "QL1F-attempt52-gap-invariant-audit.json"
)
INVARIANT_FIGURE_PATH = (
    CORE / "plots" / "attempt45-gap-size-evidence-development.png"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def binary_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def key_numbers(result: dict[str, Any]) -> dict[str, Any]:
    summary = result["summary"]
    methods = summary["methods"]
    paired = summary["paired_success_differences"]
    safety = summary["k15_destructive_accepted_step_rate"]
    return {
        "model_informed_k15": methods["model-informed-k15"]["success"],
        "completed_model_informed_k40": methods["model-informed-k40"][
            "success"
        ],
        "raw_coordinate_k40": methods["raw-coordinate-global-40"]["success"],
        "paired_k15_minus_k40": paired["model-informed-k40"],
        "paired_k15_minus_raw40": paired["raw-coordinate-global-40"],
        "query_cap_ratio": summary["cost_ratios"][
            "model-informed-k40"
        ]["query_ratio"],
        "shot_cap_ratio": summary["cost_ratios"][
            "model-informed-k40"
        ]["shot_ratio"],
        "destructive_step_safety": safety,
    }


def build_run(
    result: dict[str, Any],
    audit: dict[str, Any],
    query_delivery: dict[str, Any],
    invariant_delivery: dict[str, Any],
    source_commit: str,
) -> dict[str, Any]:
    numbers = key_numbers(result)
    query_methods = {
        row["method"]: row for row in query_delivery["confirmation"]
    }
    return {
        "schema": "quantum-harness-challenge-run-v1",
        "paper": {
            "id": "QuantumBFS/quantum.harness#113",
            "title": "Sim-to-Real for Quantum Gates",
            "url": (
                "https://github.com/QuantumBFS/quantum.harness/issues/113"
            ),
        },
        "challenge": {
            "number": 113,
            "track": "other",
            "status": "complete",
        },
        "title": (
            "Low-dimensional model-informed calibration of a synthetic CNOT"
        ),
        "model": {
            "name": "Synthetic d=4 CNOT control benchmark",
            "hilbert_dimension": 4,
            "pulse_parameters": 40,
            "nominal_hessian_rank": 15,
            "boundary": "query-only finite-shot synthetic device",
        },
        "method": {
            "family": "differentiable quantum control",
            "name": "model-informed principal-global k=15",
            "exact": False,
            "tool": "JAX + SciPy + finite-shot scalar oracle",
            "settings": {
                "search_dimension": 15,
                "cycles": 2,
                "shots_per_decision_query": 32768,
                "trust_radius": 0.25,
                "target_infidelity": 0.001,
            },
            "note": (
                "A differentiable nominal simulator supplies a warm pulse and "
                "the top 15 Hessian directions. The mismatched device exposes "
                "only sampled scalar fidelities; exact truth values are "
                "attached after calibration for scoring."
            ),
        },
        "params": [
            {
                "name": "fresh benchmark",
                "value": "24 truth cells x 4 nested replicates x 3 methods",
            }
        ],
        "scope": {
            "label": "one-shot preregistered synthetic confirmation",
            "independent_truth_cells": 24,
        },
        "estimate": [
            {
                "point": "mwe",
                "wall": "about 15 seconds on audited WSL2 CPU",
                "memory": "CPU-only; not profiled",
            },
            {
                "point": "full public replay",
                "wall": "about 90 seconds on audited WSL2 CPU",
                "memory": "CPU-only; compact ledgers",
            },
        ],
        "actual": [
            {
                "point": "formal Attempt 49",
                "wall": (
                    f"{result['elapsed_seconds_this_process']:.2f} seconds"
                ),
                "memory": "CPU-only; not profiled",
            }
        ],
        "where": "Ubuntu 26.04 WSL2, CPU/x64",
        "risks": [
            (
                "The formal result stores aggregate query-ledger closure and "
                "a canonical row hash, not every query row."
            ),
            (
                "The online early-stop rule failed its development cost gate; "
                "the headline resource quantity is a deterministic full cap."
            ),
            (
                "The unconditional rank(H)=d^2-1 statement was rejected; "
                "only a conditional local endpoint/Hessian-rank invariant is "
                "supported."
            ),
        ],
        "figures": [
            {
                "id": "queries-to-target",
                "plots": (
                    "Restricted-mean post-hoc queries to target versus "
                    "search dimension"
                ),
                "x": "model-informed search dimension / frozen comparator",
                "y": "black-box queries to post-hoc exact target",
                "expected": (
                    "selected k=15 reaches the target with materially fewer "
                    "queries than either k=40 comparator"
                ),
                "results": {
                    "figure": "queries-to-target.png",
                    "numbers": {
                        method: {
                            "queries_to_target": row["queries_to_target"],
                            "oracle_scored_success": row[
                                "oracle_scored_success"
                            ],
                        }
                        for method, row in query_methods.items()
                    },
                    "match": "pass",
                    "why": (
                        "The development panel spans k=5,10,15,20,40 and "
                        "the preregistered confirmation panel gives 48.76 "
                        "queries for k=15 versus 160.63 and 166 for the "
                        "frozen k=40 comparators. Failures are retained at "
                        "their full method cap."
                    ),
                    "wall": "derived from sealed Attempt-44/49 artifacts",
                    "changes": [],
                    "rerun": (
                        "python core-sim-to-real/code/"
                        "attempt51_queries_to_target.py"
                    ),
                },
            },
            {
                "id": "headline",
                "plots": (
                    "Fresh truth-cell success and deterministic full-cap "
                    "resources"
                ),
                "x": "frozen search geometry",
                "y": "oracle-scored success / full query and shot cap",
                "expected": (
                    "k=15 passes all preregistered confirmation gates"
                ),
                "results": {
                    "figure": "headline.png",
                    "numbers": {
                        "k15_success": numbers["model_informed_k15"],
                        "k15_minus_k40": numbers[
                            "paired_k15_minus_k40"
                        ],
                        "k15_minus_raw40": numbers[
                            "paired_k15_minus_raw40"
                        ],
                        "query_cap_ratio": numbers["query_cap_ratio"],
                        "shot_cap_ratio": numbers["shot_cap_ratio"],
                    },
                    "match": "pass",
                    "why": (
                        "All six frozen statistical/resource/safety gates and "
                        "18 independent final-audit checks pass."
                    ),
                    "wall": (
                        f"{result['elapsed_seconds_this_process']:.2f} seconds"
                    ),
                    "changes": [],
                    "rerun": (
                        "python core-sim-to-real/run_challenge.py --full"
                    ),
                },
            },
            {
                "id": "gap-and-invariant",
                "plots": (
                    "Development failure boundary versus model-truth gap and "
                    "cross-size endpoint/Hessian-rank invariant"
                ),
                "x": "model-truth gap epsilon / audited system",
                "y": "oracle-scored success / converged numerical rank",
                "expected": (
                    "success degrades at large mismatch while converged "
                    "endpoint and Hessian ranks agree across d=2,3,4"
                ),
                "results": {
                    "figure": "gap-and-invariant.png",
                    "numbers": {
                        "combined_success_epsilon_0_05": 0.875,
                        "combined_success_epsilon_0_10": 0.15625,
                        "rank_pairs": [
                            [
                                row["endpoint_rank"],
                                row["hessian_rank"],
                            ]
                            for row in invariant_delivery[
                                "cross_size_invariant"
                            ]["rows"]
                        ],
                    },
                    "match": "pass",
                    "why": (
                        "Attempt 52 closes all 22 simulator-free checks, "
                        "including source hashes, the large-gap failure "
                        "boundary, conditional endpoint/Hessian-rank equality, "
                        "the old d=4 numerical-artifact correction, and the "
                        "retained unidentifiable resource-scaling result."
                    ),
                    "wall": (
                        "derived from sealed Attempts 25–28, 34, and 45"
                    ),
                    "changes": [],
                    "rerun": (
                        "python core-sim-to-real/code/"
                        "attempt52_gap_invariant_audit.py --verify-only"
                    ),
                },
            },
        ],
        "results": {
            "confirmation_decision": result["confirmation_decision"],
            "confirmation_gates": result["summary"]["gate_checks"],
            "final_audit": {
                "status": audit["status"],
                "checks_passed": sum(audit["checks"].values()),
                "checks_total": len(audit["checks"]),
            },
            "queries_to_target_delivery": {
                "status": query_delivery["status"],
                "checks_passed": sum(
                    query_delivery["checks"].values()
                ),
                "checks_total": len(query_delivery["checks"]),
                "metric": query_delivery["metric"],
                "confirmation": query_delivery["confirmation"],
            },
            "gap_invariant_delivery": {
                "status": invariant_delivery["status"],
                "checks_passed": sum(
                    invariant_delivery["checks"].values()
                ),
                "checks_total": len(invariant_delivery["checks"]),
                "failure_mode_evidence": invariant_delivery[
                    "failure_mode_evidence"
                ],
                "cross_size_invariant": invariant_delivery[
                    "cross_size_invariant"
                ],
                "honest_negative_result": invariant_delivery[
                    "honest_negative_result"
                ],
            },
            "numbers": numbers,
        },
        "provenance": {
            "source_commit": source_commit,
            "preregistration_commit": result["preregistration"][
                "before_truth"
            ]["git"]["head"],
            "formal_result": (
                "../results_summary/"
                "QL1F-attempt49-fresh-confirmation.json"
            ),
            "formal_result_canonical_sha256": canonical_sha256(RESULT_PATH),
            "final_audit": (
                "../results_summary/QL1F-attempt50-final-audit.json"
            ),
            "final_audit_canonical_sha256": canonical_sha256(AUDIT_PATH),
            "headline_figure_binary_sha256": binary_sha256(FIGURE_PATH),
            "queries_to_target_result": (
                "../results_summary/"
                "QL1F-attempt51-queries-to-target.json"
            ),
            "queries_to_target_result_canonical_sha256": (
                canonical_sha256(QUERY_RESULT_PATH)
            ),
            "queries_to_target_figure_binary_sha256": binary_sha256(
                QUERY_FIGURE_PATH
            ),
            "gap_invariant_result": (
                "../results_summary/"
                "QL1F-attempt52-gap-invariant-audit.json"
            ),
            "gap_invariant_result_canonical_sha256": canonical_sha256(
                INVARIANT_RESULT_PATH
            ),
            "gap_invariant_figure_binary_sha256": binary_sha256(
                INVARIANT_FIGURE_PATH
            ),
        },
        "claim_boundary": [
            "Synthetic two-qubit CNOT benchmark only.",
            "No real-hardware or cesium-specific evidence.",
            "Success is post-hoc oracle-scored, not an online certificate.",
            "Full-cap cost is a deterministic frozen protocol cap.",
            (
                "Queries-to-target is a post-hoc restricted-mean benchmark; "
                "failures are charged their complete method cap."
            ),
            "Four shot-noise replicates are nested within 24 truth cells.",
            (
                "Gap and cross-size evidence is development/mechanism "
                "evidence, not fresh principal-global confirmation."
            ),
        ],
    }


def build_report(
    result: dict[str, Any],
    audit: dict[str, Any],
    query_delivery: dict[str, Any],
    invariant_delivery: dict[str, Any],
) -> dict[str, Any]:
    numbers = key_numbers(result)
    k15 = numbers["model_informed_k15"]
    k40 = numbers["completed_model_informed_k40"]
    raw = numbers["raw_coordinate_k40"]
    delta40 = numbers["paired_k15_minus_k40"]
    delta_raw = numbers["paired_k15_minus_raw40"]
    safety = numbers["destructive_step_safety"]
    query_methods = {
        row["method"]: row for row in query_delivery["confirmation"]
    }
    query_k15 = query_methods["model-informed-k15"]["queries_to_target"]
    query_k40 = query_methods["model-informed-k40"]["queries_to_target"]
    query_raw = query_methods["raw-coordinate-global-40"][
        "queries_to_target"
    ]
    return {
        "title": "Challenge 113: Sim-to-Real for Quantum Gates",
        "eyebrow": "QCS Track · preregistered synthetic confirmation",
        "url": "https://github.com/QuantumBFS/quantum.harness/issues/113",
        "lede": (
            "A frozen 15-dimensional model-Hessian subspace calibrated a "
            "40-parameter synthetic CNOT black box with 90.6% fresh-truth "
            "success at a deterministic 66-query online cap, versus 25% and "
            "0% success at 166 queries for the k=40 comparators. The "
            "post-hoc oracle-scored first-hit indices are 48.76, 160.63, "
            "and 166."
        ),
        "sections": [
            {
                "title": "Challenge",
                "note": "Why the expensive device loop needs fewer directions",
                "blocks": [
                    {
                        "kind": "text",
                        "text": (
                            "A differentiable simulator can optimize a quantum "
                            "gate cheaply, but a mismatched device must be "
                            "calibrated through noisy, derivative-free physical "
                            "queries. Challenge 113 asks whether the nominal "
                            "control landscape identifies a small subspace in "
                            "which that expensive closed loop remains effective."
                        ),
                    },
                    {
                        "kind": "card",
                        "title": "Significance",
                        "blocks": [
                            {
                                "kind": "text",
                                "text": (
                                    "For a two-qubit gate the local phase-blind "
                                    "landscape suggests 15 curved directions, "
                                    "even though the pulse has 40 parameters. "
                                    "If those directions transfer across model "
                                    "mismatch, finite-shot calibration can spend "
                                    "substantially fewer device queries."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "kv",
                        "pairs": [
                            ["Challenge", "#113 Sim-to-Real for Quantum Gates"],
                            ["System", "Synthetic d=4 CNOT, 40 pulse parameters"],
                            ["Independent units", "24 fresh truth cells"],
                            ["Nested noise", "4 finite-shot replicates per cell"],
                        ],
                    },
                ],
            },
            {
                "title": "Approach",
                "note": "Differentiable model outside, scalar oracle inside",
                "blocks": [
                    {
                        "kind": "badge",
                        "text": "Approximate finite-shot black-box calibration",
                        "style": "neutral",
                    },
                    {
                        "kind": "kv",
                        "pairs": [
                            ["Method", "principal-global model-informed k=15"],
                            ["Tool", "JAX autodiff + SciPy statistics"],
                            ["Cycles", "2 global updates"],
                            ["Shots/query", "32,768 (+ two 1,024 sentinels)"],
                            ["Target", "exact post-hoc infidelity <= 1e-3"],
                        ],
                    },
                    {
                        "kind": "text",
                        "text": (
                            "The nominal simulator supplies a warm-start pulse "
                            "and Hessian principal directions. The true device "
                            "is represented by a separately constructed "
                            "mismatched model behind `query(parameters, shots) "
                            "-> sampled scalar fidelity`. Calibration cannot "
                            "differentiate through or inspect the true device. "
                            "Exact fidelity is attached only after the client "
                            "closes and cannot change an accepted step."
                        ),
                    },
                    {
                        "kind": "table",
                        "columns": [
                            "Method",
                            "Dimension",
                            "Full queries/run",
                            "Full shots/run",
                        ],
                        "rows": [
                            ["model-informed k=15", "15", "66", "2,099,200"],
                            ["completed model k=40", "40", "166", "5,376,000"],
                            ["raw-coordinate k=40", "40", "166", "5,376,000"],
                        ],
                        "numeric": [False, True, True, True],
                    },
                    {
                        "kind": "note",
                        "label": "Cost semantics",
                        "style": "info",
                        "text": (
                            "Frozen full-cap cost remains the primary online "
                            "resource quantity. The queries-to-target figure "
                            "uses post-hoc exact scoring and charges failures "
                            "their full method cap. It answers the benchmark "
                            "question but is not a deployable stopping rule; "
                            "the attempted online certificate failed."
                        ),
                    },
                ],
            },
            {
                "title": "Results",
                "note": "One-shot public result plus independent reconstruction",
                "blocks": [
                    {
                        "kind": "heading",
                        "text": "Queries to target versus dimension",
                        "level": 2,
                    },
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "queries-to-target.png",
                                "caption": (
                                    "Left: the development dimension sweep "
                                    "over k=5,10,15,20,40. Right: the "
                                    "preregistered fresh comparison. Values "
                                    "are restricted-mean post-hoc queries to "
                                    "exact infidelity <= 1e-3; failures are "
                                    "charged their complete method cap. "
                                    "Success percentages must be read jointly "
                                    "with query cost."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "table",
                        "columns": [
                            "Fresh method",
                            "Search dimension",
                            "Queries to target",
                            "95% interval",
                        ],
                        "rows": [
                            [
                                "model-informed k=15",
                                "15",
                                f"{query_k15['estimate']:.2f}",
                                (
                                    f"[{query_k15['lower_95']:.2f}, "
                                    f"{query_k15['upper_95']:.2f}]"
                                ),
                            ],
                            [
                                "completed model k=40",
                                "40",
                                f"{query_k40['estimate']:.2f}",
                                (
                                    f"[{query_k40['lower_95']:.2f}, "
                                    f"{query_k40['upper_95']:.2f}]"
                                ),
                            ],
                            [
                                "raw-coordinate k=40",
                                "40",
                                f"{query_raw['estimate']:.2f}",
                                (
                                    f"[{query_raw['lower_95']:.2f}, "
                                    f"{query_raw['upper_95']:.2f}]"
                                ),
                            ],
                        ],
                        "numeric": [False, True, True, True],
                    },
                    {
                        "kind": "note",
                        "label": "Interpret together with success",
                        "style": "info",
                        "text": (
                            "A small method cap is not evidence of reaching "
                            "the target: development k=5 used only 26 queries "
                            "but succeeded in 0% of truth cells. The selected "
                            "k=15 is the smallest tested geometry that combines "
                            "high success with a low query horizon."
                        ),
                    },
                    {
                        "kind": "heading",
                        "text": "Fresh confirmation",
                        "level": 2,
                    },
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": (
                                    "headline.png"
                                ),
                                "caption": (
                                    "PASS on the fixed 24-cell synthetic CNOT "
                                    "benchmark. Bars show truth-cell success "
                                    "with empirical stratified-bootstrap "
                                    "intervals and deterministic full-cap "
                                    "resource ratios. This is not hardware "
                                    "evidence."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "verdict",
                        "status": "good",
                        "label": "PASS · 6/6 frozen gates",
                        "why": (
                            "The k=15 success lower bound exceeds 75%, both "
                            "paired-difference gates pass, both cost ratios are "
                            "below 0.60, and the destructive-step upper bound "
                            "is below 5%."
                        ),
                    },
                    {
                        "kind": "table",
                        "columns": [
                            "Quantity",
                            "Estimate",
                            "Empirical bootstrap interval",
                        ],
                        "rows": [
                            [
                                "k=15 success",
                                f"{100*k15['estimate']:.2f}%",
                                (
                                    f"[{100*k15['lower_95']:.2f}, "
                                    f"{100*k15['upper_95']:.2f}]%"
                                ),
                            ],
                            [
                                "completed k=40 success",
                                f"{100*k40['estimate']:.2f}%",
                                (
                                    f"[{100*k40['lower_95']:.2f}, "
                                    f"{100*k40['upper_95']:.2f}]%"
                                ),
                            ],
                            [
                                "raw k=40 success",
                                f"{100*raw['estimate']:.2f}%",
                                "[0.00, 0.00]%",
                            ],
                            [
                                "k15 - completed k40",
                                f"{100*delta40['estimate']:.2f} pp",
                                (
                                    f"[{100*delta40['lower_95']:.2f}, "
                                    f"{100*delta40['upper_95']:.2f}] pp"
                                ),
                            ],
                            [
                                "k15 - raw k40",
                                f"{100*delta_raw['estimate']:.2f} pp",
                                (
                                    f"[{100*delta_raw['lower_95']:.2f}, "
                                    f"{100*delta_raw['upper_95']:.2f}] pp"
                                ),
                            ],
                        ],
                        "numeric": [False, True, True],
                    },
                    {
                        "kind": "note",
                        "label": "Bootstrap boundary",
                        "style": "info",
                        "text": (
                            "These are empirical family-stratified "
                            "truth-cell bootstrap summaries. The raw-k=40 "
                            "[0,0] interval is degenerate because every "
                            "observed truth cell and every resample has zero "
                            "success; it is not a strict confidence interval "
                            "asserting zero population success probability."
                        ),
                    },
                    {
                        "kind": "kv",
                        "pairs": [
                            [
                                "Query-cap ratio",
                                f"{numbers['query_cap_ratio']:.4f}",
                            ],
                            [
                                "Shot-cap ratio",
                                f"{numbers['shot_cap_ratio']:.4f}",
                            ],
                            [
                                "Destructive accepted steps",
                                (
                                    f"{safety['destructive_accepted_steps']}/"
                                    f"{safety['accepted_nonzero_steps']}"
                                ),
                            ],
                            [
                                "Safety one-sided UCB95",
                                f"{100*safety['upper_95']:.2f}%",
                            ],
                            [
                                "Independent final audit",
                                (
                                    f"{sum(audit['checks'].values())}/"
                                    f"{len(audit['checks'])} checks"
                                ),
                            ],
                        ],
                    },
                    {
                        "kind": "heading",
                        "text": "Failure boundary and cross-size invariant",
                        "level": 2,
                    },
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "gap-and-invariant.png",
                                "caption": (
                                    "Development/mechanism evidence only. "
                                    "The three upper/left panels show "
                                    "oracle-scored target success degrading "
                                    "with model-truth gap for historical "
                                    "Joint-15 v1, principal-line-15, and "
                                    "raw-40 methods. The lower-right panel "
                                    "shows equality of converged endpoint and "
                                    "Hessian ranks across d=2,3,4 systems."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "note",
                        "label": "Conditional invariant, not a universal law",
                        "style": "info",
                        "text": (
                            "Near the audited converged optima, Hessian rank "
                            "matches the accessible weighted phase-blind "
                            "endpoint-error rank: 3, 8, and 15 for d=2,3,4. "
                            "The unconditional rank(H)=d^2-1 claim is rejected; "
                            "an earlier d=4 discrepancy was traced to optimizer "
                            "residual and spectral-gap numerics."
                        ),
                    },
                    {
                        "kind": "card",
                        "title": "Honest negative results",
                        "blocks": [
                            {
                                "kind": "list",
                                "items": [
                                    (
                                        "The online early-stop rule missed "
                                        "successes and failed its cost gate."
                                    ),
                                    (
                                        "The attempted cross-dimension "
                                        "resource-scaling comparison was not "
                                        "identifiable because the frozen "
                                        "epsilon left zero-cost raw warm-start "
                                        "successes in d=2,3,4."
                                    ),
                                    (
                                        "A frozen residual platform sketch "
                                        "reached the target in 0/4 positive "
                                        "stress seeds and was not escalated."
                                    ),
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "title": "Highlight",
                "note": "What is new, and where the claim stops",
                "blocks": [
                    {
                        "kind": "card",
                        "title": "What's innovative",
                        "blocks": [
                            {
                                "kind": "text",
                                "text": (
                                    "The comparison isolates geometry from "
                                    "optimizer class: the k=15 and completed "
                                    "k=40 methods share the same principal "
                                    "prefix, update rule, confidence thresholds, "
                                    "and paired finite-shot noise. Adding 25 "
                                    "nominally flat complement directions makes "
                                    "the calibration worse while spending over "
                                    "2.5 times the fixed query cap. On the "
                                    "fresh benchmark, k=15 also reduces the "
                                    "restricted-mean post-hoc query-to-target "
                                    "score from 160.63 to 48.76."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "card",
                        "title": "Significance of output",
                        "blocks": [
                            {
                                "kind": "text",
                                "text": (
                                    "A separately preregistered holdout confirms "
                                    "that the development-selected k=15 geometry "
                                    "transfers across three mismatch families. "
                                    "The result supports a practical local "
                                    "sim-to-real rule: concentrate finite-shot "
                                    "feedback in simulator-informed curved "
                                    "directions and treat complement widening as "
                                    "a risky, testable intervention."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "card",
                        "title": "Broader impact and boundary",
                        "blocks": [
                            {
                                "kind": "text",
                                "text": (
                                    "The software cleanly separates a free "
                                    "differentiable model from a costly scalar "
                                    "device oracle and can be adapted to another "
                                    "simulator or hardware client. The present "
                                    "evidence is nevertheless synthetic CNOT "
                                    "evidence only: it is not cesium-specific, "
                                    "not hardware calibration, and not a "
                                    "universal cross-dimension law."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "note",
                        "label": "Audit boundary",
                        "style": "info",
                        "text": (
                            "The immutable formal result retains aggregate "
                            "ledger closure and a canonical row hash, not every "
                            "query row. The fast MWE closes this presentation "
                            "gap by retaining all 66/166/166 query rows. A "
                            "drift-only metadata field is also documented as a "
                            "sampled-but-unapplied control map; it does not enter "
                            "the simulator or any gate."
                        ),
                    },
                ],
            },
        ],
    }


def main() -> None:
    result = load_json(RESULT_PATH)
    audit = load_json(AUDIT_PATH)
    query_delivery = load_json(QUERY_RESULT_PATH)
    invariant_delivery = load_json(INVARIANT_RESULT_PATH)
    if (
        result["status"] != "complete"
        or result["confirmation_decision"] != "pass"
        or audit["status"] != "pass"
        or query_delivery["status"] != "pass"
        or invariant_delivery["status"] != "pass"
    ):
        raise RuntimeError(
            "formal result or one of the delivery audits is not pass"
        )
    source_commit = git_head()
    FINAL.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIGURE_PATH, FINAL / "headline.png")
    shutil.copyfile(
        QUERY_FIGURE_PATH,
        FINAL / "queries-to-target.png",
    )
    shutil.copyfile(
        INVARIANT_FIGURE_PATH,
        FINAL / "gap-and-invariant.png",
    )
    atomic_write_json(
        FINAL / "run.json",
        build_run(
            result,
            audit,
            query_delivery,
            invariant_delivery,
            source_commit,
        ),
    )
    atomic_write_json(
        FINAL / "report.json",
        build_report(
            result,
            audit,
            query_delivery,
            invariant_delivery,
        ),
    )
    print(
        f"built {FINAL / 'run.json'} and {FINAL / 'report.json'} "
        f"from source commit {source_commit}"
    )


if __name__ == "__main__":
    main()
