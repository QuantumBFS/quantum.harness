#!/usr/bin/env python3
"""Execute one opaque Issue #28 Slurm cell."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
from typing import Any, Sequence


TRACK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(
    os.environ.get("HARNESS_REPO_ROOT", str(TRACK_ROOT.parents[2]))
).resolve()
SRC = TRACK_ROOT / "src"
if str(TRACK_ROOT) not in sys.path:
    sys.path.insert(0, str(TRACK_ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value.resolve() if value.is_absolute() else (REPO_ROOT / value).resolve()


def _isolate_numba_cache() -> Path:
    """Prevent compiled-cache reuse across Slurm jobs and array processes."""
    base = Path(
        os.environ.get(
            "NUMBA_CACHE_DIR",
            str(Path(tempfile.gettempdir()) / "issue28-numba-cache"),
        )
    ).resolve()

    def component(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", value)

    job = component(os.environ.get("SLURM_JOB_ID", "local"))
    task = component(
        os.environ.get(
            "SLURM_ARRAY_TASK_ID",
            os.environ.get("HARNESS_CELL_INDEX", "single"),
        )
    )
    isolated = base / f"job-{job}-task-{task}-pid-{os.getpid()}"
    isolated.mkdir(parents=True, exist_ok=False)
    os.environ["NUMBA_CACHE_DIR"] = str(isolated)
    return isolated


def _read_cell(path: Path, selector: str) -> tuple[str, dict[str, Any]]:
    value = json.loads(path.read_text(encoding="ascii"))
    if value.get("schema_version") != 1 or not isinstance(value.get("cells"), list):
        raise ValueError("unsupported run spec")
    cells = value["cells"]
    matches = [cell for cell in cells if str(cell.get("cell_id")) == selector]
    if not matches and selector.isdigit():
        index = int(selector) - 1
        if 0 <= index < len(cells):
            matches = [cells[index]]
    if len(matches) != 1:
        raise ValueError(f"cell selector is not unique: {selector}")
    cell = matches[0]
    params = cell.get("params")
    if not isinstance(params, dict):
        raise ValueError("cell params must be an object")
    return str(cell["cell_id"]), dict(params)


def _smoke(output: Path, cell_id: str) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite smoke output: {output}")
    import numba
    import numpy as np
    import scipy

    from vmcrg_ref.artifacts import atomic_write_json
    from vmcrg_ref.fast import FastMultiOperatorBiasedMetropolis
    from vmcrg_ref.ising import IsingLattice
    from vmcrg_ref.issue28_workflow import current_code_sha256
    from vmcrg_ref.multi import MultiOperatorBiasedMetropolis
    from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis

    rng = np.random.default_rng(2026289001)
    initial = IsingLattice.random(21, rng).spins.copy()
    couplings = np.asarray([0.436, *([0.0] * 12)], dtype=np.float64)
    bias = np.linspace(-0.01, 0.001, len(EVEN_SHAPES))
    micro_basis = OperatorBasis(21, EVEN_SHAPES)
    block_basis = OperatorBasis(7, EVEN_SHAPES)
    reference = MultiOperatorBiasedMetropolis(
        IsingLattice(initial.copy()),
        couplings,
        bias,
        np.random.default_rng(2026289002),
        EVEN_SHAPES,
        block_size=3,
        micro_basis=micro_basis,
        block_basis=block_basis,
    )
    compiled = FastMultiOperatorBiasedMetropolis(
        IsingLattice(initial.copy()),
        couplings,
        bias,
        np.random.default_rng(2026289002),
        EVEN_SHAPES,
        block_size=3,
        micro_basis=micro_basis,
        block_basis=block_basis,
    )
    reference.sweep()
    compiled.sweep()
    identical = bool(
        np.array_equal(reference.lattice.spins, compiled.lattice.spins)
        and np.array_equal(reference.micro_values, compiled.micro_values)
        and np.array_equal(reference.block_values, compiled.block_values)
    )
    compiled.assert_cache_consistent()
    if not identical:
        raise AssertionError("compiled and Python trajectories differ")
    output.mkdir(parents=True)
    result = {
        "schema_version": 1,
        "cell_id": cell_id,
        "stage": "SMOKE",
        "status": "ok",
        "host": platform.node(),
        "compiled_trajectory_identity": identical,
        "numba_cache_dir": os.environ["NUMBA_CACHE_DIR"],
        "code_sha256": current_code_sha256(),
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "numba": numba.__version__,
        },
    }
    atomic_write_json(output / "manifest.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行一个 Issue #28 Slurm cell")
    parser.add_argument("--stage", choices=("SMOKE", "N3", "N4"), required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def run_cell(
    stage: str,
    run_spec: Path,
    selector: str,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    cell_id, params = _read_cell(run_spec, selector)
    if params.get("stage") != stage:
        raise ValueError(
            f"stage mismatch: requested {stage}, cell declares {params.get('stage')}"
        )
    if "output" not in params:
        raise ValueError("cell output is required")
    output = _resolve(str(params["output"]))
    plan: dict[str, Any] = {
        "cell_id": cell_id,
        "stage": stage,
        "output": str(output),
    }
    if stage in {"N3", "N4"}:
        if "protocol" not in params:
            raise ValueError("cell protocol is required")
        plan["protocol"] = str(_resolve(str(params["protocol"])))
    if stage == "N4":
        bundle_id = str(params.get("bundle_id", ""))
        if bundle_id not in {f"formal-{index}" for index in range(1, 6)}:
            raise ValueError("N4 bundle_id must be formal-1 through formal-5")
        plan["bundle_id"] = bundle_id
    if dry_run:
        return plan
    _isolate_numba_cache()
    os.chdir(TRACK_ROOT)
    if stage == "SMOKE":
        return _smoke(output, cell_id)
    if stage == "N3":
        from scripts.issue28_five_round import main as n3_main

        arguments = [
            "--protocol",
            plan["protocol"],
            "--preset",
            "pilot",
            "--rounds",
            "5",
            "--backend",
            "slurm",
            "--output",
            str(output),
        ]
        if bool(params.get("resume", False)):
            arguments.append("--resume")
        if n3_main(arguments) != 0:
            raise RuntimeError("N3 runner returned a nonzero status")
    else:
        from scripts.issue28_formal import main as n4_main

        arguments = [
            "--protocol",
            plan["protocol"],
            "--bundle",
            plan["bundle_id"],
            "--output",
            str(output),
            "--backend",
            "slurm",
        ]
        if bool(params.get("resume", False)):
            arguments.append("--resume")
        if n4_main(arguments) != 0:
            raise RuntimeError("N4 runner returned a nonzero status")
    return json.loads((output / "manifest.json").read_text(encoding="ascii"))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_cell(
            args.stage,
            _resolve(args.run_spec),
            args.selector,
            dry_run=args.dry_run,
        )
    except (FileExistsError, FileNotFoundError, KeyError, TypeError, ValueError) as error:
        print(f"Issue #28 集群运行失败: {error}", file=sys.stderr, flush=True)
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
