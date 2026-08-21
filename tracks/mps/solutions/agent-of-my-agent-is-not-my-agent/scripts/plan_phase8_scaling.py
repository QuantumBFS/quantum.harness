#!/usr/bin/env python3
"""Plan and gate Phase 8 sigma=1.75 work without running TeNPy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lrtfim.phase8_protocol import (
    ALPHA,
    CROSSING_CHI,
    GAP_CHI,
    K,
    R_FIT,
    build_crossing_spec,
    build_gap_spec,
    build_st_gap_spec,
    decide_crossing,
)


DEFAULT_FIT = Path(
    "results/phase7-crossover/proposal/fits/sigma-1.75/fit-summary.json"
)
DEFAULT_PHASE7_ROOT = Path("results/phase7-crossover/broad/cells")


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
        stream.flush()
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_fit_summary(path: Path) -> dict:
    summary = json.loads(path.read_text())
    if float(summary.get("sigma")) != 1.75:
        raise ValueError("fit summary must have sigma=1.75")
    primary = summary.get("primary", {})
    expected = {
        "num_exponentials": K,
        "alpha": ALPHA,
        "r_fit": R_FIT,
    }
    for field, value in expected.items():
        if primary.get(field) != value:
            raise ValueError(
                f"fit summary {field} mismatch: "
                f"{primary.get(field)!r} != {value!r}"
            )
    return {
        "path": str(path),
        "sha256": _sha256(path),
    }


def _cell_command(cell: dict, fit_path: Path, run_dir: str) -> list[str]:
    return [
        "python",
        "-u",
        "scripts/benchmark_phase6_optimizations.py",
        "--fit-summary",
        str(fit_path),
        "--length",
        str(cell["L"]),
        "--gamma",
        str(cell["Gamma"]),
        "--num-exponentials",
        str(K),
        "--alpha",
        str(ALPHA),
        "--r-fit",
        str(R_FIT),
        "--chi-schedule",
        str(cell["chi"]),
        "--direct-only",
        "--sectors",
        cell["sector"],
        "--output-dir",
        str(Path(run_dir) / "cells" / cell["cell_id"]),
    ]


def _load_summaries(
    root: Path,
    *,
    sigma: float,
) -> dict[tuple[int, float], dict]:
    summaries = {}
    for path in sorted(root.rglob("summary.json")):
        summary = json.loads(path.read_text())
        settings = summary.get("settings", {})
        summary_sigma = settings.get("sigma")
        if summary_sigma is None or float(summary_sigma) != sigma:
            continue
        length = settings.get("length")
        gamma = settings.get("gamma")
        if length is None or gamma is None:
            continue
        key = (int(length), float(gamma))
        if key in summaries:
            raise ValueError(f"duplicate summary for L={key[0]}, Gamma={key[1]}")
        summaries[key] = summary
    return summaries


def command_crossing(args: argparse.Namespace) -> None:
    fit = _validate_fit_summary(args.fit_summary)
    spec = build_crossing_spec(args.output.parent)
    spec["provenance"] = {"fit_summary": fit}
    for cell in spec["cells"]:
        cell["command"] = _cell_command(
            cell,
            args.fit_summary,
            spec["run_dir"],
        )
    atomic_json(args.output, spec)
    print(f"planned {len(spec['cells'])} Phase 8 crossing cells", flush=True)


def command_decide(args: argparse.Namespace) -> None:
    crossing_spec = json.loads(args.crossing_spec.read_text())
    if len(crossing_spec.get("cells", [])) != 2:
        raise ValueError("crossing specification must contain exactly two cells")
    phase7_decision = json.loads(args.phase7_decision.read_text())
    summaries = _load_summaries(args.phase7_summary_root, sigma=1.75)
    summaries.update(_load_summaries(args.summary_root, sigma=1.75))
    decision = decide_crossing(phase7_decision, summaries)
    decision["inputs"] = {
        "crossing_spec": str(args.crossing_spec),
        "crossing_spec_sha256": _sha256(args.crossing_spec),
        "phase7_decision": str(args.phase7_decision),
        "phase7_decision_sha256": _sha256(args.phase7_decision),
    }
    atomic_json(args.output, decision)
    print(f"Phase 8 crossing status: {decision['status']}", flush=True)


def command_gaps(args: argparse.Namespace) -> None:
    decision = json.loads(args.decision.read_text())
    fit = _validate_fit_summary(args.fit_summary)
    spec = build_gap_spec(decision, args.output.parent)
    spec["provenance"] = {
        "fit_summary": fit,
        "crossing_decision": {
            "path": str(args.decision),
            "sha256": _sha256(args.decision),
        },
    }
    for cell in spec["cells"]:
        cell["command"] = _cell_command(
            cell,
            args.fit_summary,
            spec["run_dir"],
        )
    atomic_json(args.output, spec)
    print(f"planned {len(spec['cells'])} common-field states", flush=True)


def command_st_gaps(args: argparse.Namespace) -> None:
    fit = _validate_fit_summary(args.fit_summary)
    spec = build_st_gap_spec(args.output.parent)
    spec["provenance"] = {
        "fit_summary": fit,
        "field_source": {
            "role": "external_published_benchmark",
            "Gamma": 1.5609,
            "reference": "Shiratani-Todo arXiv:2305.14121v4",
        },
    }
    for cell in spec["cells"]:
        cell["command"] = _cell_command(
            cell,
            args.fit_summary,
            spec["run_dir"],
        )
    atomic_json(args.output, spec)
    print(
        f"planned {len(spec['cells'])} published-field sensitivity states",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    crossing = subparsers.add_parser("crossing")
    crossing.add_argument("--fit-summary", type=Path, default=DEFAULT_FIT)
    crossing.add_argument("--output", type=Path, required=True)
    crossing.set_defaults(handler=command_crossing)

    decide = subparsers.add_parser("decide")
    decide.add_argument("--crossing-spec", type=Path, required=True)
    decide.add_argument("--phase7-decision", type=Path, required=True)
    decide.add_argument(
        "--phase7-summary-root",
        type=Path,
        default=DEFAULT_PHASE7_ROOT,
    )
    decide.add_argument("--summary-root", type=Path, required=True)
    decide.add_argument("--output", type=Path, required=True)
    decide.set_defaults(handler=command_decide)

    gaps = subparsers.add_parser("gaps")
    gaps.add_argument("--decision", type=Path, required=True)
    gaps.add_argument("--fit-summary", type=Path, default=DEFAULT_FIT)
    gaps.add_argument("--output", type=Path, required=True)
    gaps.set_defaults(handler=command_gaps)

    st_gaps = subparsers.add_parser("st-gaps")
    st_gaps.add_argument("--fit-summary", type=Path, default=DEFAULT_FIT)
    st_gaps.add_argument("--output", type=Path, required=True)
    st_gaps.set_defaults(handler=command_st_gaps)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
