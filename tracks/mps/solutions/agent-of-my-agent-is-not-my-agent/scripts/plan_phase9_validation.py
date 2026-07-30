#!/usr/bin/env python3
"""Create resumable Phase 9 validation specifications without running DMRG."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from lrtfim.phase9_protocol import (
    ALPHA,
    CHI,
    K,
    MEAN_FIELD_BENCHMARKS,
    R_FIT,
    SIGMA_18,
    build_mean_field_spec,
    build_nn_spec,
    build_sigma18_z_spec,
)


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
    sigma = float(summary.get("sigma"))
    expected_sigmas = [item["sigma"] for item in MEAN_FIELD_BENCHMARKS]
    if not any(np.isclose(sigma, expected) for expected in expected_sigmas):
        raise ValueError(f"unexpected mean-field fit sigma={sigma:g}")
    primary = summary.get("primary", {})
    expected = {
        "num_exponentials": K,
        "alpha": ALPHA,
        "r_fit": R_FIT,
    }
    for field, expected_value in expected.items():
        actual = primary.get(field)
        if actual != expected_value:
            raise ValueError(
                f"fit summary {field} mismatch: "
                f"{actual!r} != {expected_value!r}"
            )
    return {"path": str(path), "sha256": _sha256(path), "sigma": sigma}


def _validate_sigma18_fit(path: Path) -> dict:
    summary = json.loads(path.read_text())
    sigma = float(summary.get("sigma"))
    if not np.isclose(sigma, SIGMA_18):
        raise ValueError("sigma=1.8 validation requires a sigma=1.8 fit")
    primary = summary.get("primary", {})
    for field, expected in (
        ("num_exponentials", K),
        ("alpha", ALPHA),
        ("r_fit", R_FIT),
    ):
        if primary.get(field) != expected:
            raise ValueError(
                f"fit summary {field} mismatch: "
                f"{primary.get(field)!r} != {expected!r}"
            )
    return {"path": str(path), "sha256": _sha256(path), "sigma": sigma}


def _nn_command(cell: dict, run_dir: str) -> list[str]:
    return [
        "python",
        "-u",
        "scripts/run_phase9_nn_cell.py",
        "--length",
        str(cell["L"]),
        "--gamma",
        str(cell["Gamma"]),
        "--sector",
        cell["sector"],
        "--chi",
        str(CHI),
        "--max-sweeps",
        "30",
        "--output-dir",
        str(Path(run_dir) / "cells" / cell["cell_id"]),
    ]


def _mean_field_command(
    cell: dict,
    fit_summary: Path,
    run_dir: str,
) -> list[str]:
    return [
        "python",
        "-u",
        "scripts/benchmark_phase6_optimizations.py",
        "--fit-summary",
        str(fit_summary),
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
        str(CHI),
        "--direct-only",
        "--sectors",
        cell["sector"],
        "--max-sweeps",
        "30",
        "--output-dir",
        str(Path(run_dir) / "cells" / cell["cell_id"]),
    ]


def _sigma18_command(cell: dict, fit_summary: Path, run_dir: str) -> list[str]:
    return [
        "python",
        "-u",
        "scripts/benchmark_phase6_optimizations.py",
        "--fit-summary",
        str(fit_summary),
        "--length",
        str(cell["L"]),
        "--gamma",
        str(cell["Gamma"]),
        "--num-exponentials",
        str(cell["K"]),
        "--alpha",
        str(ALPHA),
        "--r-fit",
        str(R_FIT),
        "--chi-schedule",
        str(cell["chi"]),
        "--direct-only",
        "--sectors",
        cell["sector"],
        "--max-sweeps",
        "30",
        "--output-dir",
        str(Path(run_dir) / "cells" / cell["cell_id"]),
    ]


def command_nn(args: argparse.Namespace) -> None:
    spec = build_nn_spec(args.output.parent)
    for cell in spec["cells"]:
        cell["command"] = _nn_command(cell, spec["run_dir"])
    atomic_json(args.output, spec)
    print(f"planned {len(spec['cells'])} NN validation cells", flush=True)


def command_mean_field(args: argparse.Namespace) -> None:
    validated = [_validate_fit_summary(path) for path in args.fit_summary]
    fit_paths = {record["sigma"]: Path(record["path"]) for record in validated}
    expected_sigmas = {2.0 / 3.0}
    if set(fit_paths) != expected_sigmas:
        raise ValueError(
            "mean-field planning requires only the qualified sigma=2/3 fit"
        )
    spec = build_mean_field_spec(args.output.parent, fit_paths)
    spec["provenance"] = {
        "fit_summaries": {
            str(record["sigma"]): record for record in validated
        }
    }
    for cell in spec["cells"]:
        cell["command"] = _mean_field_command(
            cell,
            fit_paths[cell["sigma"]],
            spec["run_dir"],
        )
    atomic_json(args.output, spec)
    print(
        f"planned {len(spec['cells'])} mean-field validation cells",
        flush=True,
    )


def command_sigma18_z(args: argparse.Namespace) -> None:
    fit = _validate_sigma18_fit(args.fit_summary)
    spec = build_sigma18_z_spec(args.output.parent)
    spec["provenance"] = {
        "fit_summary": fit,
        "field_source": {
            "role": "external_published_benchmark",
            "Gamma": 1.5288,
            "reference": "Shiratani-Todo arXiv:2305.14121",
        },
    }
    for cell in spec["cells"]:
        cell["command"] = _sigma18_command(
            cell,
            args.fit_summary,
            spec["run_dir"],
        )
    atomic_json(args.output, spec)
    print(f"planned {len(spec['cells'])} sigma=1.8 z states", flush=True)


def command_all(args: argparse.Namespace) -> None:
    command_nn(
        argparse.Namespace(
            output=args.output_root / "nn-limit" / "run_spec.json"
        )
    )
    command_mean_field(
        argparse.Namespace(
            fit_summary=args.fit_summary,
            output=(
                args.output_root
                / "mean-field-sigma-2over3"
                / "run_spec.json"
            ),
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    nn = subparsers.add_parser("nn")
    nn.add_argument("--output", type=Path, required=True)
    nn.set_defaults(handler=command_nn)

    mean_field = subparsers.add_parser("mean-field")
    mean_field.add_argument(
        "--fit-summary",
        type=Path,
        nargs=1,
        required=True,
    )
    mean_field.add_argument("--output", type=Path, required=True)
    mean_field.set_defaults(handler=command_mean_field)

    sigma18 = subparsers.add_parser("sigma18-z")
    sigma18.add_argument("--fit-summary", type=Path, required=True)
    sigma18.add_argument("--output", type=Path, required=True)
    sigma18.set_defaults(handler=command_sigma18_z)

    all_specs = subparsers.add_parser("all")
    all_specs.add_argument(
        "--fit-summary",
        type=Path,
        nargs=1,
        required=True,
    )
    all_specs.add_argument("--output-root", type=Path, required=True)
    all_specs.set_defaults(handler=command_all)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
