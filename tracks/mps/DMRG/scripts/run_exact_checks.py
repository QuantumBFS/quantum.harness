#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vmcrg_ref.mps_patch import PatchMPS
from vmcrg_ref.patch_table import PatchLookupTable, enumerate_patches
from vmcrg_ref.symmetries import transform_patches


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic exact checks for the MPS residual")
    parser.add_argument("--output", type=Path, default=ROOT / "results/mps_challenge/exact_checks.json")
    args = parser.parse_args()
    patches = enumerate_patches()
    rows = []
    for chi in (2, 4, 8):
        model = PatchMPS.random(chi=chi, seed=20260800 + chi)
        values = model.symmetric_values(patches)
        z2_error = float(np.max(np.abs(values - model.symmetric_values(-patches))))
        d4_error = max(
            float(np.max(np.abs(values - model.symmetric_values(transform_patches(patches, index)))))
            for index in range(8)
        )
        lookup = PatchLookupTable.from_model(model)
        lookup_error = float(np.max(np.abs(lookup.values - (values - values.mean()))))
        rows.append(
            {
                "chi": chi,
                "parameter_count": model.parameter_count,
                "parameter_norm": model.parameter_norm,
                "z2_error": z2_error,
                "d4_error": d4_error,
                "lookup_error": lookup_error,
                "centered_mean": float(lookup.values.mean()),
            }
        )
    payload = {
        "exact_ising_critical_coupling": 0.5 * float(np.log(1.0 + np.sqrt(2.0))),
        "paper_operational_coupling": 0.436,
        "patch_states": 512,
        "results": rows,
        "status": "PASS"
        if all(max(row["z2_error"], row["d4_error"], row["lookup_error"]) < 1e-10 for row in rows)
        else "FAIL",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"exact checks status={payload['status']} output={args.output}", flush=True)
    if payload["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
