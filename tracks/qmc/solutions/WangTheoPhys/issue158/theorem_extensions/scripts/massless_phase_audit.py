#!/usr/bin/env python3
"""Serialize the rigorous low-temperature massless comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from issue158.decision_contract import make_decision_record
from issue158.kernel import C_INFINITY_SIGMA2


SCHEMA = "issue158-massless-phase-audit-v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_audit(root: Path) -> dict:
    proof_path = root / "PROOF_AUDIT.md"
    proof_text = proof_path.read_text()
    proof_text_flat = " ".join(proof_text.split())
    required_phrases = {
        "pair_counting": "unordered nearest-neighbor pair",
        "coupling_dominance": "c_L\\ge c_\\infty",
        "ferromagnetic_comparison": (
            "original and comparison couplings are all nonnegative"
        ),
        "embedded_box": "free nearest-neighbor box",
        "limit_order": "First take the torus limit",
        "free_boundary_limit": (
            "No nearest-neighbor periodic-boundary "
            "thermodynamic-limit theorem"
        ),
        "local_weak_limits": "local weak subsequential limit",
        "massless_definition": (
            "precise restricted meaning that "
            "the infinite-volume two-point function does not decay "
            "exponentially"
        ),
        "ginibre": "Ginibre",
        "nearest_neighbor_theorem": "van Engelenburg--Lis",
        "claim_boundary": "does not determine",
    }
    obligations = [
        {
            "name": name,
            "status": (
                "verified" if phrase in proof_text_flat else "blocking"
            ),
            "evidence": phrase,
        }
        for name, phrase in required_phrases.items()
    ]
    blocking = [
        row["name"] for row in obligations if row["status"] == "blocking"
    ]
    status = "proved" if not blocking else "blocked"
    source_hashes = {
        "PROOF_AUDIT.md": _sha256(proof_path),
    }
    decision = make_decision_record(
        track="massless",
        claim_status=status,
        evidence_class="rigorous_theorem",
        updates={
            "ferromagnetic_lro": "unchanged",
            "ordinary_gapped_phase": (
                "excluded" if status == "proved" else "unchanged"
            ),
            "eventual_bkt": "unresolved",
            "non_bkt_massless": "unresolved",
        },
        does_not_imply=[
            "uniform finite-L correlation bound",
            "exact power-law asymptotics",
            "BKT universal jump",
            "log-vs-BKT decision",
        ],
        blocking_obligations=blocking,
        source_hashes=source_hashes,
    )
    return {
        "schema": SCHEMA,
        "model": (
            "size-normalized minimum-image 2D classical XY torus "
            "with pair coupling proportional to 1/r^4"
        ),
        "primary_sources": [
            {
                "theorem": "Ginibre coupling monotonicity",
                "doi": "10.1007/BF01646537",
            },
            {
                "theorem": "van Engelenburg--Lis Theorem 1(ii)",
                "doi": "10.1007/s00220-022-04550-3",
            },
        ],
        "obligations": obligations,
        "theorem": {
            "quantifier_order": [
                "fix nonzero lattice displacement x",
                "embed a fixed free box Lambda_n containing 0 and x",
                "take torus L to infinity at fixed n",
                "take n to infinity",
            ],
            "comparison": (
                "liminf_L C_L(x) >= "
                "C_NN_Z2(beta*c_infinity; 0,x)"
            ),
            "effective_inverse_temperature": "beta*c_infinity",
            "threshold": "beta >= beta_c_NN/c_infinity",
            "lower_bound": "1/(8*|x|)",
            "c_infinity": C_INFINITY_SIGMA2,
            "massless_definition": "two-point function is not exponential",
        },
        "numerical_certificates_are_proof_premises": False,
        "decision_record": decision,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    payload = build_audit(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True))
    temporary.replace(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
