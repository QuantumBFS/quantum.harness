"""CLI for the audited TensorCircuit-NG matched baseline."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from vqetape.spec import TFIMVQESpec
from vqetape.tensorcircuit_baseline import run_baseline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark TensorCircuit-NG on the exact VQETape "
            "TFIM RZZ-RX workload."
        )
    )
    parser.add_argument("--nqubits", type=int, default=10)
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--coupling", type=float, default=1.0)
    parser.add_argument("--field", type=float, default=1.0)
    parser.add_argument(
        "--initial-state",
        choices=("zero", "plus"),
        default="plus",
    )
    parser.add_argument(
        "--dtype",
        choices=("complex64", "complex128"),
        default="complex64",
    )
    parser.add_argument("--seed", type=int, default=33)
    parser.add_argument("--warm-repeats", type=int, default=5)
    parser.add_argument("--expected-steps", type=int, default=100)
    parser.add_argument(
        "--contractor",
        choices=("greedy", "omeco"),
        default="omeco",
    )
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2, allow_nan=False)
            handle.write("\n")
            temporary = Path(handle.name)
        os.replace(temporary, path)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.expected_steps < 1:
        raise ValueError("expected_steps must be positive")
    report = run_baseline(
        spec=TFIMVQESpec(
            nqubits=args.nqubits,
            depth=args.depth,
            coupling=args.coupling,
            field=args.field,
            initial_state=args.initial_state,
            dtype=args.dtype,
        ),
        seed=args.seed,
        warm_repeats=args.warm_repeats,
        contractor=args.contractor,
        reference_path=args.reference,
    )
    timings = report["timings"]
    objective_seconds = (
        timings["compile_seconds"]
        + timings["first_execute_seconds"]
        + args.expected_steps * timings["warm_seconds_median"]
    )
    report["objective"] = {
        "expected_vqe_steps": args.expected_steps,
        "definition": (
            "compile + first_execute + expected_steps * warm_median"
        ),
        "seconds": objective_seconds,
    }
    report["runtime"].update(
        {
            "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
            "slurm_node": os.environ.get("SLURMD_NODENAME"),
            "cuda_visible_devices": os.environ.get(
                "CUDA_VISIBLE_DEVICES"
            ),
        }
    )
    _write_json_atomic(args.output, report)

    correctness = report["correctness"]
    correctness_label = (
        "not-checked"
        if correctness is None
        else (
            "pass"
            if correctness["tolerance_passed"]
            else "fail"
        )
    )
    print(
        f"backend={report['runtime']['jax_backend']} "
        f"contractor={args.contractor} "
        f"compile={timings['compile_seconds']:.6f}s "
        f"first={timings['first_execute_seconds']:.6f}s "
        f"warm={timings['warm_seconds_median']:.6f}s "
        f"correctness={correctness_label}",
        flush=True,
    )
    if correctness is not None and not correctness["tolerance_passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
