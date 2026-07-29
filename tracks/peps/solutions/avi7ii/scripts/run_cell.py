"""Dispatch one opaque issue-147 run-spec cell."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import traceback

from qh147 import qmc


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
QMC_CONFIG = SOLUTION_ROOT / "configs" / "qmc-reference.json"
PEPO_CONFIG = SOLUTION_ROOT / "configs" / "pepo-h3-d4.json"


def _load_pepo_stack():
    from qh147 import run

    return run


def _cell(spec: dict) -> dict:
    requested = os.environ.get("HARNESS_CELL_ID")
    if requested:
        try:
            return next(cell for cell in spec["cells"] if cell["cell_id"] == requested)
        except StopIteration as error:
            raise ValueError(f"unknown cell id: {requested}") from error
    raw = os.environ.get(
        "HARNESS_CELL_INDEX", os.environ.get("SLURM_ARRAY_TASK_ID")
    )
    if raw is None:
        raise ValueError("HARNESS_CELL_ID or one-based cell index is required")
    index = int(raw)
    if index < 1 or index > len(spec["cells"]):
        raise ValueError("cell index is outside the run spec")
    return spec["cells"][index - 1]


def _atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _echo_contract(
    manifest: dict, *, params: dict, settings: dict, provenance: dict
) -> dict:
    runtime_provenance = manifest.get("provenance", {})
    result = dict(manifest)
    if runtime_provenance:
        result["runtime_provenance"] = runtime_provenance
    result.update(
        {"params": params, "settings": settings, "provenance": provenance}
    )
    return result


def _dry_run(kind: str, params: dict) -> dict:
    if kind == "qmc":
        raw = json.loads(QMC_CONFIG.read_text(encoding="utf-8"))
        h_index = raw["model"]["fields"].index(params["h"])
        beta_index = raw["betas"].index(params["beta"])
        m_index = raw["trotter_slices"].index(params["M"])
        chain = int(params["chain"])
        if chain < 0 or chain >= raw["chains"]:
            raise ValueError("chain index is outside the configured range")
        seed = (
            raw["seed_base"]
            + 10000 * h_index
            + 100 * beta_index
            + 10 * m_index
            + chain
        )
        qmc.QMCConfig(
            raw["model"]["lx"],
            raw["model"]["ly"],
            params["beta"],
            params["h"],
            raw["model"]["j"],
            params["M"],
            raw["thermal_sweeps"],
            raw["measure_sweeps"],
            raw["bins"],
            seed,
        )
    else:
        run = _load_pepo_stack()
        production = run.load_production_config(PEPO_CONFIG)
        if kind == "pepo":
            if params["compression_mode"] not in {"ordinary", "thermodynamic"}:
                raise ValueError("unsupported PEPO compression mode")
        else:
            if params["chi"] not in production.measurement_chis:
                raise ValueError("measurement chi is not declared")
            if not str(params["source_cell"]).startswith("cell-"):
                raise ValueError("invalid source cell")
    return {"status": "rehearsed"}


def _run_qmc(params: dict, output: Path) -> dict:
    code = qmc.main(
        [
            "--config",
            str(QMC_CONFIG),
            "--run-dir",
            str(output),
            "--field",
            str(params["h"]),
            "--beta",
            str(params["beta"]),
            "--M",
            str(params["M"]),
            "--chain",
            str(params["chain"]),
        ]
    )
    if code:
        raise RuntimeError(f"QMC cell returned {code}")
    return json.loads((output / "manifest.json").read_text(encoding="utf-8"))


def _run_pepo(params: dict, output: Path) -> dict:
    run = _load_pepo_stack()
    production = run.load_production_config(PEPO_CONFIG)
    mode = params["compression_mode"]
    code = run.main(
        [
            "evolve",
            "--config",
            str(PEPO_CONFIG),
            "--run-root",
            str(output),
            "--compression-mode",
            mode,
        ]
    )
    if code:
        raise RuntimeError(f"PEPO evolution returned {code}")
    checkpoint_root = output / mode / "checkpoints"
    checkpoints = tuple(checkpoint_root.glob("beta-*/metadata.json"))
    if len(checkpoints) != production.chain.steps:
        raise RuntimeError(
            f"PEPO evolution produced {len(checkpoints)} of {production.chain.steps} checkpoints"
        )
    return {
        "status": "success",
        "diagnostics": {"checkpoint_count": len(checkpoints)},
        "artifacts": {"checkpoint_root": str(checkpoint_root)},
    }


def _run_pepo_measure(params: dict, settings: dict) -> dict:
    run = _load_pepo_stack()
    evolution_run_dir = Path(settings["evolution_run_dir"])
    source = evolution_run_dir / "cells" / params["source_cell"]
    source_manifest_path = source / "manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("status") != "success":
        raise RuntimeError("source PEPO evolution is not successful")
    mode = source_manifest["params"]["compression_mode"]
    code = run.main(
        [
            "measure",
            "--config",
            str(PEPO_CONFIG),
            "--run-root",
            str(source),
            "--compression-mode",
            mode,
            "--chi",
            str(params["chi"]),
        ]
    )
    if code:
        raise RuntimeError(f"PEPO measurement returned {code}")
    artifact = source / "measurements" / mode / f"chi-{params['chi']}"
    runtime = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
    return {
        "status": "success",
        "runtime_provenance": runtime,
        "artifacts": {"measurement_root": str(artifact)},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--kind", choices=("qmc", "pepo", "pepo-measure"), required=True
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    spec_path = Path(os.environ["HARNESS_RUN_SPEC"])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    cell = _cell(spec)
    params = cell["params"]
    settings = {**spec.get("settings", {}), **cell.get("settings", {})}
    provenance = spec.get("provenance", {})
    output = Path(spec["run_dir"]) / "cells" / cell["cell_id"]
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("status") == "success":
            return 0
    try:
        if args.dry_run:
            manifest = _dry_run(args.kind, params)
        elif args.kind == "qmc":
            manifest = _run_qmc(params, output)
        elif args.kind == "pepo":
            manifest = _run_pepo(params, output)
        else:
            manifest = _run_pepo_measure(params, settings)
        _atomic(
            manifest_path,
            _echo_contract(
                manifest,
                params=params,
                settings=settings,
                provenance=provenance,
            ),
        )
        return 0
    except Exception as error:
        _atomic(
            manifest_path,
            {
                "status": "failed",
                "params": params,
                "settings": settings,
                "provenance": provenance,
                "error": type(error).__name__,
                "traceback": traceback.format_exc(),
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
