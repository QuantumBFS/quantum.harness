"""VMCRG 复现项目的统一命令入口。

实现声明
--------
本文件只负责参数检查、执行顺序和输出目录，不重复实现物理算法。
神经网络基础挑战的完整调用链是：

    reproduce.py neural-easy
        -> scripts/neural_challenge.py
        -> src/vmcrg_ref/hybrid_neural.py
        -> src/vmcrg_ref/neural_energy.py

这样可以保证命令入口只有一个，同时采样器、优化器和神经能量各自只有
一份真实实现，避免“整合”后出现两套算法结果不一致。
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    previous = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(SRC) if not previous else str(SRC) + os.pathsep + previous
    )
    return environment


def _display(command: Sequence[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def _run(command: Sequence[str], dry_run: bool) -> None:
    normalized = [str(part) for part in command]
    print(f"> {_display(normalized)}", flush=True)
    if dry_run:
        return
    subprocess.run(
        normalized,
        check=True,
        cwd=ROOT,
        env=_environment(),
    )


def _tag(value: float) -> str:
    return f"{value:.7f}".replace("-", "m").replace(".", "p")


def _resolve_output(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _assert_new_run(output: Path, expected_files: Sequence[str]) -> None:
    existing = [name for name in expected_files if (output / name).exists()]
    if existing:
        names = ", ".join(existing)
        raise FileExistsError(f"refusing to overwrite {output}: {names}")


def _positive(name: str, value: int | float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _neural_easy(args: argparse.Namespace) -> None:
    output = _resolve_output(
        args.output
        or Path(f"output/neural_hybrid_easy_{args.preset}")
    )
    _assert_new_run(output, ["config.json", "bias_model.npz", "trajectory.npz"])
    _run(
        [sys.executable, "-m", "unittest", "discover", "-s", ROOT / "tests"],
        args.dry_run,
    )
    command = [
        sys.executable,
        SCRIPTS / "neural_challenge.py",
        "--preset",
        args.preset,
        "--output",
        output,
        "--fixed-point-map",
        _resolve_output(args.fixed_point_map),
    ]
    _run(command, args.dry_run)


def _neural_confirm(args: argparse.Namespace) -> None:
    output_root = _resolve_output(
        args.output_root
        or Path(f"output/neural_confirmation_{args.preset}_v1")
    )
    _assert_new_run(
        output_root,
        ["run_manifest.json", "pre_autocorrelation_assessment.json", "confirmation_report.json"],
    )
    _run(
        [sys.executable, "-m", "unittest", "discover", "-s", ROOT / "tests"],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "neural_confirmation.py",
            "--preset",
            args.preset,
            "--output-root",
            output_root,
            "--fixed-point-map",
            _resolve_output(args.fixed_point_map),
            "--protocol",
            _resolve_output(args.protocol),
        ],
        args.dry_run,
    )


def _neural_replacement_confirm(args: argparse.Namespace) -> None:
    output_root = _resolve_output(
        args.output_root or Path("output/neural_replacement_confirmation_formal_v1")
    )
    _assert_new_run(
        output_root,
        [
            "run_manifest.json",
            "pre_autocorrelation_assessment.json",
            "confirmation_report.json",
        ],
    )
    _run(
        [sys.executable, "-m", "unittest", "discover", "-s", ROOT / "tests"],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "neural_confirmation.py",
            "--preset",
            "formal",
            "--output-root",
            output_root,
            "--fixed-point-map",
            _resolve_output(args.fixed_point_map),
            "--protocol",
            _resolve_output(args.protocol),
        ],
        args.dry_run,
    )


def _neural_three_arm(args: argparse.Namespace) -> None:
    output_root = _resolve_output(
        args.output_root or Path("output/neural_three_arm_formal_v1")
    )
    _assert_new_run(output_root, ["run_manifest.json", "three_arm_report.json"])
    _run(
        [sys.executable, "-m", "unittest", "discover", "-s", ROOT / "tests"],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "neural_three_arm.py",
            "--output-root",
            output_root,
            "--protocol",
            _resolve_output(args.protocol),
        ],
        args.dry_run,
    )


def _neural_root_cause(args: argparse.Namespace) -> None:
    output = _resolve_output(
        args.output or Path("output/neural_root_cause_formal_v1")
    )
    _assert_new_run(output, ["run_manifest.json", "root_cause_report.json"])
    _run(
        [sys.executable, "-m", "unittest", "discover", "-s", ROOT / "tests"],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "diagnose_neural_root_cause.py",
            "--output",
            output,
            "--protocol",
            _resolve_output(args.protocol),
        ],
        args.dry_run,
    )


def _neural_identity_gradient(args: argparse.Namespace) -> None:
    output = _resolve_output(
        args.output or Path(f"output/neural_identity_gradient_{args.preset}_v1")
    )
    _assert_new_run(
        output,
        ["identity_gradient_diagnostic.json", "identity_gradient_batches.npz"],
    )
    _run(
        [sys.executable, "-m", "unittest", "discover", "-s", ROOT / "tests"],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "neural_identity_gradient_diagnostic.py",
            "--preset",
            args.preset,
            "--output",
            output,
            "--model",
            _resolve_output(args.model),
            "--fixed-point-map",
            _resolve_output(args.fixed_point_map),
            "--seed",
            args.seed,
        ],
        args.dry_run,
    )


def _neural_optimizer_stability(args: argparse.Namespace) -> None:
    output = _resolve_output(
        args.output or Path(f"output/neural_optimizer_stability_{args.preset}_v1")
    )
    _assert_new_run(
        output,
        ["optimizer_stability_report.json", "config.json", "bias_model.npz"],
    )
    _run(
        [sys.executable, "-m", "unittest", "discover", "-s", ROOT / "tests"],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "neural_identity_optimizer_certification.py",
            "--preset",
            args.preset,
            "--output",
            output,
            "--fixed-point-map",
            _resolve_output(args.fixed_point_map),
            "--initial-model",
            _resolve_output(args.initial_model),
        ],
        args.dry_run,
    )


def _neural_replacement(args: argparse.Namespace) -> None:
    output = _resolve_output(
        args.output or Path(f"output/neural_replacement_{args.preset}_v1")
    )
    _assert_new_run(output, ["config.json", "bias_model.npz", "trajectory.npz"])
    _run(
        [sys.executable, "-m", "unittest", "discover", "-s", ROOT / "tests"],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "neural_challenge.py",
            "--preset",
            args.preset,
            "--output",
            output,
            "--fixed-point-map",
            _resolve_output(args.fixed_point_map),
            "--representation",
            "pure",
            "--model-seed",
            202677101,
            "--optimizer-seed",
            202677102,
            "--validation-seed",
            202677103,
            "--projection-seed",
            202677104,
            "--ablation-seed",
            202677105,
            "--autocorrelation-seed",
            202677106,
        ],
        args.dry_run,
    )


def _assess_neural_replacement(args: argparse.Namespace) -> None:
    root = _resolve_output(args.input)
    output = _resolve_output(args.output) if args.output else root / "pilot_assessment.json"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    _run(
        [
            sys.executable,
            SCRIPTS / "assess_neural_replacement_pilot.py",
            "--input",
            root,
            "--output",
            output,
        ],
        args.dry_run,
    )


def _paper(args: argparse.Namespace) -> None:
    if args.length % 3:
        raise ValueError("length must be divisible by 3")
    _positive("rounds", args.rounds)
    _positive("steps", args.steps)
    _positive("sweeps", args.sweeps)
    _positive("walkers", args.walkers)
    _positive("mu", args.mu)
    _positive("validation thermalization", args.validation_thermalization)
    _positive("validation measurements", args.validation_measurements)
    _positive("validation runs", args.validation_runs)

    output_root = _resolve_output(
        args.output_root
        or Path(f"output/reproduction/paper_L{args.length}_K{_tag(args.coupling)}")
    )
    outputs = [output_root / f"rg{index}" for index in range(1, args.rounds + 1)]
    for output in outputs:
        expected = ["summary.json", "trajectory.npz", "convergence.json"]
        if args.validate:
            expected.append("frozen_validation.json")
        _assert_new_run(output, expected)

    previous: Path | None = None
    for index, output in enumerate(outputs, start=1):
        command = [
            sys.executable,
            SCRIPTS / "run_paper_even_rg.py",
            "--length",
            args.length,
            "--steps",
            args.steps,
            "--sweeps",
            args.sweeps,
            "--walkers",
            args.walkers,
            "--mu",
            args.mu,
            "--seed",
            args.seed + index - 1,
            "--output",
            output,
        ]
        if previous is None:
            command.extend(["--coupling", args.coupling])
        else:
            command.extend(["--previous", previous])
        _run(command, args.dry_run)
        _run(
            [sys.executable, SCRIPTS / "analyze_even_trajectory.py", output],
            args.dry_run,
        )
        if args.validate:
            _run(
                [
                    sys.executable,
                    SCRIPTS / "validate_frozen_even_basis.py",
                    "--input",
                    output,
                    "--thermalization",
                    args.validation_thermalization,
                    "--measurements",
                    args.validation_measurements,
                    "--runs",
                    args.validation_runs,
                    "--seed",
                    args.validation_seed + index - 1,
                ],
                args.dry_run,
            )
        previous = output

    print(f"paper workflow output: {output_root}")


def _candidate26(args: argparse.Namespace) -> None:
    if args.length < 45 or args.length % 3:
        raise ValueError("candidate-26 screening requires length >= 45 and divisible by 3")
    _positive("steps", args.steps)
    _positive("sweeps", args.sweeps)
    _positive("walkers", args.walkers)
    _positive("mu", args.mu)
    _positive("threshold", args.threshold)
    _positive("validation thermalization", args.validation_thermalization)
    _positive("validation measurements", args.validation_measurements)
    _positive("validation runs", args.validation_runs)
    _positive("bootstrap", args.bootstrap)

    ties = (
        ("axis5", "generic43")
        if args.pair_tie == "both"
        else (args.pair_tie,)
    )
    output_root = _resolve_output(
        args.output_root
        or Path(
            f"output/reproduction/candidate26_L{args.length}_K{_tag(args.coupling)}"
        )
    )
    outputs = {tie: output_root / tie for tie in ties}
    for output in outputs.values():
        _assert_new_run(
            output,
            ("run_config.json", "summary.json", "trajectory.npz", "frozen_validation.json"),
        )
    for offset, tie in enumerate(ties):
        output = outputs[tie]
        _run(
            [
                sys.executable,
                SCRIPTS / "run_candidate_26_screening.py",
                "--pair-tie",
                tie,
                "--coupling",
                args.coupling,
                "--length",
                args.length,
                "--steps",
                args.steps,
                "--sweeps",
                args.sweeps,
                "--walkers",
                args.walkers,
                "--mu",
                args.mu,
                "--threshold",
                args.threshold,
                "--seed",
                args.seed + offset,
                "--output",
                output,
            ],
            args.dry_run,
        )
        if args.validate:
            _run(
                [
                    sys.executable,
                    SCRIPTS / "validate_candidate_26_screening.py",
                    "--input",
                    output,
                    "--thermalization",
                    args.validation_thermalization,
                    "--measurements",
                    args.validation_measurements,
                    "--runs",
                    args.validation_runs,
                    "--bootstrap",
                    args.bootstrap,
                    "--family-alpha",
                    args.family_alpha,
                    "--seed",
                    args.validation_seed + offset,
                ],
                args.dry_run,
            )
    print(f"candidate-26 workflow output: {output_root}")


def _tests(args: argparse.Namespace) -> None:
    _run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        args.dry_run,
    )


def _derive26(args: argparse.Namespace) -> None:
    _run(
        [sys.executable, SCRIPTS / "derive_original_26_candidates.py"],
        args.dry_run,
    )


def _jacobian(args: argparse.Namespace) -> None:
    input_dir = _resolve_output(args.input)
    output = _resolve_output(args.output) if args.output else input_dir / "paper_jacobian.json"
    _assert_new_run(output.parent, (output.name, output.with_suffix(".npz").name))
    _run(
        [
            sys.executable,
            SCRIPTS / "measure_paper_jacobian.py",
            "--input",
            input_dir,
            "--output",
            output,
            "--thermalization",
            args.thermalization,
            "--measurements",
            args.measurements,
            "--spacing",
            args.spacing,
            "--runs",
            args.runs,
            "--bootstrap",
            args.bootstrap,
            "--seed",
            args.seed,
        ],
        args.dry_run,
    )


def _fixed_point(args: argparse.Namespace) -> None:
    if args.length % 3:
        raise ValueError("length must be divisible by 3")
    for name in (
        "steps",
        "sweeps",
        "walkers",
        "mu",
        "validation thermalization",
        "validation measurements",
        "validation runs",
        "absolute tolerance",
        "relative tolerance",
        "maximum condition number",
        "maximum correction",
    ):
        attribute = name.replace(" ", "_")
        _positive(name, getattr(args, attribute))

    map_input = _resolve_output(args.map_input)
    jacobian = _resolve_output(args.jacobian)
    output_root = _resolve_output(
        args.output_root or Path("output/reproduction/fixed_point_newton")
    )
    candidate = output_root / "fixed_point_candidate.json"
    verification = output_root / "verification_rg"
    residual = output_root / "fixed_point_residual.json"
    _assert_new_run(output_root, (candidate.name, residual.name))
    _assert_new_run(
        verification,
        ("summary.json", "trajectory.npz", "convergence.json", "frozen_validation.json"),
    )

    _run(
        [
            sys.executable,
            SCRIPTS / "solve_fixed_point_newton.py",
            "--map-input",
            map_input,
            "--jacobian",
            jacobian,
            "--output",
            candidate,
            "--maximum-condition-number",
            args.maximum_condition_number,
            "--maximum-correction",
            args.maximum_correction,
        ],
        args.dry_run,
    )
    verification_command = [
        sys.executable,
        SCRIPTS / "run_paper_even_rg.py",
        "--length",
        args.length,
        "--couplings-file",
        candidate,
        "--steps",
        args.steps,
        "--sweeps",
        args.sweeps,
        "--walkers",
        args.walkers,
        "--mu",
        args.mu,
        "--seed",
        args.seed,
        "--output",
        verification,
    ]
    if args.initial_bias_from is not None:
        verification_command.extend(
            ["--initial-bias-from", _resolve_output(args.initial_bias_from)]
        )
    _run(verification_command, args.dry_run)
    _run(
        [sys.executable, SCRIPTS / "analyze_even_trajectory.py", verification],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "validate_frozen_even_basis.py",
            "--input",
            verification,
            "--thermalization",
            args.validation_thermalization,
            "--measurements",
            args.validation_measurements,
            "--runs",
            args.validation_runs,
            "--seed",
            args.validation_seed,
        ],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "analyze_fixed_point_residual.py",
            "--candidate",
            candidate,
            "--rg-output",
            verification,
            "--output",
            residual,
            "--absolute-tolerance",
            args.absolute_tolerance,
            "--relative-l2-tolerance",
            args.relative_tolerance,
        ],
        args.dry_run,
    )
    if not args.dry_run:
        report = json.loads(residual.read_text(encoding="utf-8"))
        print(
            "fixed-point gate: "
            f"{report['status']} "
            f"(Linf={report['linf_norm']:.6g}, "
            f"relative-L2={report['relative_l2_norm']:.6g})"
        )


V2_REPEAT_SEEDS = {
    1: {
        "base_rg": 202607901,
        "base_validation": 202608001,
        "jacobian": 202608101,
        "fixed_rg": 202608201,
        "fixed_validation": 202608301,
        "equivalence_bootstrap": 202608401,
    },
    2: {
        "base_rg": 202607911,
        "base_validation": 202608011,
        "jacobian": 202608111,
        "fixed_rg": 202608211,
        "fixed_validation": 202608311,
        "equivalence_bootstrap": 202608411,
    },
    3: {
        "base_rg": 202607921,
        "base_validation": 202608021,
        "jacobian": 202608121,
        "fixed_rg": 202608221,
        "fixed_validation": 202608321,
        "equivalence_bootstrap": 202608421,
    },
}


def _require_report_status(path: Path, expected: str) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("status") != expected:
        raise RuntimeError(
            f"predeclared gate failed in {path}: "
            f"{report.get('status')} != {expected}"
        )
    return report


def _v2_frozen_equivalence(
    input_dir: Path,
    validation_seed: int,
    bootstrap_seed: int,
    dry_run: bool,
) -> None:
    _run(
        [
            sys.executable,
            SCRIPTS / "validate_frozen_even_basis.py",
            "--input",
            input_dir,
            "--thermalization",
            5000,
            "--measurements",
            120000,
            "--runs",
            16,
            "--seed",
            validation_seed,
        ],
        dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "assess_frozen_bias_equivalence.py",
            "--input",
            input_dir,
            "--late-window",
            600,
            "--maximum-condition-number",
            1.0e6,
            "--maximum-correction",
            1.0e-3,
            "--bootstrap",
            2000,
            "--bootstrap-seed",
            bootstrap_seed,
            "--confidence",
            0.95,
        ],
        dry_run,
    )
    if not dry_run:
        _require_report_status(input_dir / "frozen_bias_equivalence.json", "PASS")


def _fixed_point_repeat_v2(args: argparse.Namespace) -> None:
    seeds = V2_REPEAT_SEEDS[args.repeat]
    root = _resolve_output(
        Path(f"output/reproduction/fixed_point_repeats_v2/repeat{args.repeat}")
    )
    rg1 = root / "base" / "rg1"
    rg2 = root / "base" / "rg2"
    jacobian_json = root / "jacobian.json"
    jacobian_npz = root / "jacobian.npz"
    fixed_root = root / "fixed_point"
    candidate = fixed_root / "fixed_point_candidate.json"
    verification = fixed_root / "verification_rg"
    residual = fixed_root / "fixed_point_residual.json"
    repeat_report = root / "repeat_report.json"

    _assert_new_run(root, (jacobian_json.name, jacobian_npz.name, repeat_report.name))
    for directory in (rg1, rg2, verification):
        _assert_new_run(
            directory,
            (
                "summary.json",
                "trajectory.npz",
                "convergence.json",
                "frozen_validation.json",
                "frozen_bias_equivalence.json",
            ),
        )
    _assert_new_run(fixed_root, (candidate.name, residual.name))

    previous: Path | None = None
    for index, output in enumerate((rg1, rg2)):
        command: list[object] = [
            sys.executable,
            SCRIPTS / "run_paper_even_rg.py",
            "--length",
            45,
            "--steps",
            3000,
            "--sweeps",
            20,
            "--walkers",
            16,
            "--mu",
            5.0e-5,
            "--seed",
            seeds["base_rg"] + index,
            "--output",
            output,
        ]
        if previous is None:
            command.extend(["--coupling", 0.436])
        else:
            command.extend(["--previous", previous])
        _run(command, args.dry_run)
        _run(
            [sys.executable, SCRIPTS / "analyze_even_trajectory.py", output],
            args.dry_run,
        )
        _v2_frozen_equivalence(
            output,
            seeds["base_validation"] + index,
            seeds["equivalence_bootstrap"] + index,
            args.dry_run,
        )
        previous = output

    _run(
        [
            sys.executable,
            SCRIPTS / "measure_paper_jacobian.py",
            "--input",
            rg2,
            "--output",
            jacobian_json,
            "--thermalization",
            5000,
            "--measurements",
            1_000_000,
            "--spacing",
            1,
            "--runs",
            16,
            "--bootstrap",
            2000,
            "--seed",
            seeds["jacobian"],
        ],
        args.dry_run,
    )
    if not args.dry_run:
        jacobian_report = _require_report_status(
            jacobian_json, "NUMERICALLY_STABLE"
        )
        for parity in ("even", "odd"):
            block = jacobian_report[parity]
            if not math.isfinite(float(block["b_condition_number"])):
                raise RuntimeError(f"non-finite {parity} B condition number")
            if float(block["equation_relative_residual"]) >= 1.0e-10:
                raise RuntimeError(f"{parity} Jacobian equation residual failed")

    _run(
        [
            sys.executable,
            SCRIPTS / "solve_fixed_point_newton.py",
            "--map-input",
            rg2,
            "--jacobian",
            jacobian_npz,
            "--output",
            candidate,
            "--maximum-condition-number",
            1.0e6,
            "--maximum-correction",
            0.05,
        ],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "run_paper_even_rg.py",
            "--length",
            45,
            "--couplings-file",
            candidate,
            "--initial-bias-from",
            rg2,
            "--steps",
            3000,
            "--sweeps",
            20,
            "--walkers",
            16,
            "--mu",
            5.0e-5,
            "--seed",
            seeds["fixed_rg"],
            "--output",
            verification,
        ],
        args.dry_run,
    )
    _run(
        [sys.executable, SCRIPTS / "analyze_even_trajectory.py", verification],
        args.dry_run,
    )
    _v2_frozen_equivalence(
        verification,
        seeds["fixed_validation"],
        seeds["equivalence_bootstrap"] + 2,
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "analyze_fixed_point_residual.py",
            "--candidate",
            candidate,
            "--rg-output",
            verification,
            "--output",
            residual,
            "--absolute-tolerance",
            1.0e-3,
            "--relative-l2-tolerance",
            5.0e-3,
        ],
        args.dry_run,
    )
    if args.dry_run:
        return
    residual_report = _require_report_status(residual, "PASS")
    candidate_report = json.loads(candidate.read_text(encoding="utf-8"))
    result = {
        "status": "PASS",
        "protocol": str((ROOT / "docs/fixed_point_replication_protocol_v2.md").resolve()),
        "repeat": args.repeat,
        "seeds": seeds,
        "lambda_even": jacobian_report["even"]["leading_eigenvalue"],
        "lambda_odd": jacobian_report["odd"]["leading_eigenvalue"],
        "lambda_even_bootstrap": jacobian_report["even"]["bootstrap"],
        "lambda_odd_bootstrap": jacobian_report["odd"]["bootstrap"],
        "fixed_point_candidate": candidate_report["candidate_couplings"],
        "fixed_point_residual_linf": residual_report["linf_norm"],
        "fixed_point_residual_relative_l2": residual_report["relative_l2_norm"],
    }
    repeat_report.parent.mkdir(parents=True, exist_ok=True)
    repeat_report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


V3_REPEAT_SEEDS = {
    1: {
        "base_rg": 202609101,
        "base_calibration": 202609201,
        "base_confirmation": 202609301,
        "base_bootstrap": 202609401,
        "jacobian": 202609501,
        "fixed_rg": 202609601,
        "fixed_calibration": 202609701,
        "fixed_confirmation": 202609801,
        "fixed_bootstrap": 202609901,
    },
    2: {
        "base_rg": 202609111,
        "base_calibration": 202609211,
        "base_confirmation": 202609311,
        "base_bootstrap": 202609411,
        "jacobian": 202609511,
        "fixed_rg": 202609611,
        "fixed_calibration": 202609711,
        "fixed_confirmation": 202609811,
        "fixed_bootstrap": 202609911,
    },
    3: {
        "base_rg": 202609121,
        "base_calibration": 202609221,
        "base_confirmation": 202609321,
        "base_bootstrap": 202609421,
        "jacobian": 202609521,
        "fixed_rg": 202609621,
        "fixed_calibration": 202609721,
        "fixed_confirmation": 202609821,
        "fixed_bootstrap": 202609921,
    },
}


V4_PILOT_SEEDS = {
    "anchor_rg": 202610101,
    "anchor_calibration": 202610201,
    "anchor_confirmation": 202610301,
    "anchor_bootstrap": 202610401,
    "jacobian_left": 202610501,
    "jacobian_right": 202610511,
    "jacobian_third": 202610521,
    "permutation": 202610522,
}


def _v3_calibrated_rg(
    *,
    raw_output: Path,
    calibrated_output: Path,
    rg_seed: int,
    calibration_seed: int,
    confirmation_seed: int,
    bootstrap_seed: int,
    dry_run: bool,
    coupling: float | None = None,
    previous: Path | None = None,
    couplings_file: Path | None = None,
    initial_bias_from: Path | None = None,
) -> Path:
    sources = sum(value is not None for value in (coupling, previous, couplings_file))
    if sources != 1:
        raise ValueError("exactly one RG input source is required")
    _assert_new_run(
        raw_output,
        (
            "summary.json",
            "trajectory.npz",
            "convergence.json",
            "calibration_validation.json",
        ),
    )
    _assert_new_run(
        calibrated_output,
        (
            "summary.json",
            "correction.json",
            "frozen_validation.json",
            "frozen_bias_equivalence.json",
        ),
    )
    command: list[object] = [
        sys.executable,
        SCRIPTS / "run_paper_even_rg.py",
        "--length",
        45,
        "--steps",
        3000,
        "--sweeps",
        20,
        "--walkers",
        16,
        "--mu",
        5.0e-5,
        "--seed",
        rg_seed,
        "--output",
        raw_output,
    ]
    if coupling is not None:
        command.extend(["--coupling", coupling])
    elif previous is not None:
        command.extend(["--previous", previous])
    else:
        command.extend(["--couplings-file", couplings_file])
    if initial_bias_from is not None:
        command.extend(["--initial-bias-from", initial_bias_from])
    _run(command, dry_run)
    _run(
        [sys.executable, SCRIPTS / "analyze_even_trajectory.py", raw_output],
        dry_run,
    )

    calibration_validation = raw_output / "calibration_validation.json"
    _run(
        [
            sys.executable,
            SCRIPTS / "validate_frozen_even_basis.py",
            "--input",
            raw_output,
            "--thermalization",
            5000,
            "--measurements",
            120000,
            "--runs",
            16,
            "--seed",
            calibration_seed,
            "--output",
            calibration_validation,
        ],
        dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "apply_bias_newton_correction.py",
            "--input",
            raw_output,
            "--validation",
            calibration_validation,
            "--covariance-source",
            raw_output,
            "--output",
            calibrated_output,
            "--late-window",
            600,
            "--maximum-condition-number",
            1.0e6,
            "--maximum-correction",
            0.002,
        ],
        dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "validate_frozen_even_basis.py",
            "--input",
            calibrated_output,
            "--thermalization",
            5000,
            "--measurements",
            120000,
            "--runs",
            16,
            "--seed",
            confirmation_seed,
        ],
        dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "assess_frozen_bias_equivalence.py",
            "--input",
            calibrated_output,
            "--covariance-source",
            raw_output,
            "--late-window",
            600,
            "--maximum-condition-number",
            1.0e6,
            "--maximum-correction",
            1.0e-3,
            "--bootstrap",
            2000,
            "--bootstrap-seed",
            bootstrap_seed,
            "--confidence",
            0.95,
        ],
        dry_run,
    )
    if not dry_run:
        _require_report_status(
            calibrated_output / "frozen_bias_equivalence.json", "PASS"
        )
    return calibrated_output


def _fixed_point_repeat_v3(args: argparse.Namespace) -> None:
    seeds = V3_REPEAT_SEEDS[args.repeat]
    root = _resolve_output(
        Path(f"output/reproduction/fixed_point_repeats_v3/repeat{args.repeat}")
    )
    rg1_raw = root / "base" / "rg1_optimization"
    rg1 = root / "base" / "rg1"
    rg2_raw = root / "base" / "rg2_optimization"
    rg2 = root / "base" / "rg2"
    jacobian_json = root / "jacobian.json"
    jacobian_npz = root / "jacobian.npz"
    fixed_root = root / "fixed_point"
    candidate = fixed_root / "fixed_point_candidate.json"
    verification_raw = fixed_root / "verification_optimization"
    verification = fixed_root / "verification_rg"
    residual = fixed_root / "fixed_point_residual.json"
    repeat_report = root / "repeat_report.json"

    _assert_new_run(root, (jacobian_json.name, jacobian_npz.name, repeat_report.name))
    _assert_new_run(fixed_root, (candidate.name, residual.name))
    _v3_calibrated_rg(
        raw_output=rg1_raw,
        calibrated_output=rg1,
        rg_seed=seeds["base_rg"],
        calibration_seed=seeds["base_calibration"],
        confirmation_seed=seeds["base_confirmation"],
        bootstrap_seed=seeds["base_bootstrap"],
        coupling=0.436,
        dry_run=args.dry_run,
    )
    _v3_calibrated_rg(
        raw_output=rg2_raw,
        calibrated_output=rg2,
        rg_seed=seeds["base_rg"] + 1,
        calibration_seed=seeds["base_calibration"] + 1,
        confirmation_seed=seeds["base_confirmation"] + 1,
        bootstrap_seed=seeds["base_bootstrap"] + 1,
        previous=rg1,
        dry_run=args.dry_run,
    )

    _run(
        [
            sys.executable,
            SCRIPTS / "measure_paper_jacobian.py",
            "--input",
            rg2,
            "--output",
            jacobian_json,
            "--thermalization",
            5000,
            "--measurements",
            1_000_000,
            "--spacing",
            1,
            "--runs",
            16,
            "--bootstrap",
            2000,
            "--seed",
            seeds["jacobian"],
        ],
        args.dry_run,
    )
    if not args.dry_run:
        jacobian_report = _require_report_status(
            jacobian_json, "NUMERICALLY_STABLE"
        )
        for parity in ("even", "odd"):
            block = jacobian_report[parity]
            if not math.isfinite(float(block["b_condition_number"])):
                raise RuntimeError(f"non-finite {parity} B condition number")
            if float(block["equation_relative_residual"]) >= 1.0e-10:
                raise RuntimeError(f"{parity} Jacobian equation residual failed")

    _run(
        [
            sys.executable,
            SCRIPTS / "solve_fixed_point_newton.py",
            "--map-input",
            rg2,
            "--jacobian",
            jacobian_npz,
            "--output",
            candidate,
            "--maximum-condition-number",
            1.0e6,
            "--maximum-correction",
            0.05,
        ],
        args.dry_run,
    )
    _v3_calibrated_rg(
        raw_output=verification_raw,
        calibrated_output=verification,
        rg_seed=seeds["fixed_rg"],
        calibration_seed=seeds["fixed_calibration"],
        confirmation_seed=seeds["fixed_confirmation"],
        bootstrap_seed=seeds["fixed_bootstrap"],
        couplings_file=candidate,
        initial_bias_from=rg2,
        dry_run=args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "analyze_fixed_point_residual.py",
            "--candidate",
            candidate,
            "--rg-output",
            verification,
            "--output",
            residual,
            "--absolute-tolerance",
            1.0e-3,
            "--relative-l2-tolerance",
            5.0e-3,
        ],
        args.dry_run,
    )
    if args.dry_run:
        return
    residual_report = _require_report_status(residual, "PASS")
    candidate_report = json.loads(candidate.read_text(encoding="utf-8"))
    result = {
        "status": "PASS",
        "protocol": str((ROOT / "docs/fixed_point_replication_protocol_v3.md").resolve()),
        "repeat": args.repeat,
        "seeds": seeds,
        "lambda_even": jacobian_report["even"]["leading_eigenvalue"],
        "lambda_odd": jacobian_report["odd"]["leading_eigenvalue"],
        "lambda_even_bootstrap": jacobian_report["even"]["bootstrap"],
        "lambda_odd_bootstrap": jacobian_report["odd"]["bootstrap"],
        "fixed_point_candidate": candidate_report["candidate_couplings"],
        "fixed_point_residual_linf": residual_report["linf_norm"],
        "fixed_point_residual_relative_l2": residual_report["relative_l2_norm"],
    }
    repeat_report.parent.mkdir(parents=True, exist_ok=True)
    repeat_report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def _audit_fixed_point_v3(args: argparse.Namespace) -> None:
    root = _resolve_output(args.root)
    output = _resolve_output(args.output)
    anchor_output = _resolve_output(args.anchor_output)
    if output.exists() or anchor_output.exists():
        raise FileExistsError("refusing to overwrite an existing v3 audit or anchor")
    _run(
        [
            sys.executable,
            SCRIPTS / "audit_v3_repeat_consistency.py",
            "--root",
            root,
            "--repeats",
            *args.repeats,
            "--output",
            output,
            "--anchor-output",
            anchor_output,
            "--candidate-linf",
            0.002,
            "--candidate-relative-l2",
            0.01,
        ],
        args.dry_run,
    )


def _fixed_point_v4_pilot(args: argparse.Namespace) -> None:
    root = _resolve_output(args.output_root)
    anchor = _resolve_output(args.anchor)
    anchor_raw = root / "anchor_optimization"
    anchor_rg = root / "anchor_rg"
    residual = root / "anchor_residual.json"
    jacobian_left = root / "jacobian_left.json"
    jacobian_right = root / "jacobian_right.json"
    report = root / "pilot_report.json"
    _assert_new_run(
        root,
        (
            residual.name,
            jacobian_left.name,
            jacobian_left.with_suffix(".npz").name,
            jacobian_right.name,
            jacobian_right.with_suffix(".npz").name,
            report.name,
        ),
    )
    _v3_calibrated_rg(
        raw_output=anchor_raw,
        calibrated_output=anchor_rg,
        rg_seed=V4_PILOT_SEEDS["anchor_rg"],
        calibration_seed=V4_PILOT_SEEDS["anchor_calibration"],
        confirmation_seed=V4_PILOT_SEEDS["anchor_confirmation"],
        bootstrap_seed=V4_PILOT_SEEDS["anchor_bootstrap"],
        couplings_file=anchor,
        dry_run=args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "analyze_fixed_point_residual.py",
            "--candidate",
            anchor,
            "--rg-output",
            anchor_rg,
            "--output",
            residual,
            "--absolute-tolerance",
            1.0e-3,
            "--relative-l2-tolerance",
            5.0e-3,
        ],
        args.dry_run,
    )
    if not args.dry_run:
        _require_report_status(residual, "PASS")

    for output, seed in (
        (jacobian_left, V4_PILOT_SEEDS["jacobian_left"]),
        (jacobian_right, V4_PILOT_SEEDS["jacobian_right"]),
    ):
        _run(
            [
                sys.executable,
                SCRIPTS / "measure_paper_jacobian.py",
                "--input",
                anchor_rg,
                "--output",
                output,
                "--thermalization",
                5000,
                "--measurements",
                250000,
                "--spacing",
                1,
                "--runs",
                8,
                "--bootstrap",
                2000,
                "--seed",
                seed,
            ],
            args.dry_run,
        )
    _run(
        [
            sys.executable,
            SCRIPTS / "assess_common_anchor_jacobian_pilot.py",
            "--left",
            jacobian_left,
            "--right",
            jacobian_right,
            "--output",
            report,
            "--maximum-standardized-difference",
            1.96,
        ],
        args.dry_run,
    )
    if not args.dry_run:
        _require_report_status(report, "PASS")


def _fixed_point_v4_batch_diagnostic(args: argparse.Namespace) -> None:
    root = _resolve_output(args.output_root)
    anchor_rg = root / "anchor_rg"
    left = root / "jacobian_left.json"
    right = root / "jacobian_right.json"
    third = root / "jacobian_third.json"
    report = root / "three_batch_diagnostic.json"
    for required in (anchor_rg / "summary.json", left, right):
        if not required.exists():
            raise FileNotFoundError(f"required completed pilot output is missing: {required}")
    _assert_new_run(
        root,
        (third.name, third.with_suffix(".npz").name, report.name),
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "measure_paper_jacobian.py",
            "--input",
            anchor_rg,
            "--output",
            third,
            "--thermalization",
            5000,
            "--measurements",
            250000,
            "--spacing",
            1,
            "--runs",
            8,
            "--bootstrap",
            2000,
            "--seed",
            V4_PILOT_SEEDS["jacobian_third"],
        ],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "assess_three_jacobian_batches.py",
            "--inputs",
            left,
            right,
            third,
            "--output",
            report,
            "--permutations",
            10000,
            "--permutation-seed",
            V4_PILOT_SEEDS["permutation"],
            "--alpha",
            0.05,
        ],
        args.dry_run,
    )


def _table1_v5_repeat(args: argparse.Namespace) -> None:
    anchor_rg = _resolve_output(args.input)
    root = _resolve_output(args.output_root) / f"repeat{args.repeat}"
    jacobian = root / "jacobian.json"
    repeat_report = root / "repeat_report.json"
    manifest = ROOT / "config" / f"v5_table1_repeat{args.repeat}_seeds.json"
    for required in (anchor_rg / "summary.json", manifest):
        if not required.exists():
            raise FileNotFoundError(f"required v5 input is missing: {required}")
    _assert_new_run(
        root,
        (jacobian.name, jacobian.with_suffix(".npz").name, repeat_report.name),
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "measure_paper_jacobian.py",
            "--input",
            anchor_rg,
            "--output",
            jacobian,
            "--thermalization",
            5000,
            "--measurements",
            1_000_000,
            "--spacing",
            1,
            "--runs",
            16,
            "--bootstrap",
            2000,
            "--seed-manifest",
            manifest,
        ],
        args.dry_run,
    )
    if args.dry_run:
        return
    report = _require_report_status(jacobian, "NUMERICALLY_STABLE")
    for parity in ("even", "odd"):
        block = report[parity]
        if not math.isfinite(float(block["b_condition_number"])):
            raise RuntimeError(f"non-finite {parity} B condition number")
        if float(block["equation_relative_residual"]) >= 1.0e-10:
            raise RuntimeError(f"{parity} Jacobian equation residual failed")
    result = {
        "status": "PASS",
        "scope": "single_preregistered_v5_Table_I_repeat",
        "protocol": str((ROOT / "docs/table1_replication_protocol_v5.md").resolve()),
        "repeat": args.repeat,
        "input": str(anchor_rg),
        "seed_manifest": str(manifest.resolve()),
        "lambda_even": report["even"]["leading_eigenvalue"],
        "lambda_odd": report["odd"]["leading_eigenvalue"],
        "lambda_even_bootstrap": report["even"]["bootstrap"],
        "lambda_odd_bootstrap": report["odd"]["bootstrap"],
    }
    repeat_report.parent.mkdir(parents=True, exist_ok=True)
    repeat_report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def _paper_table1_manifest(repeat: int) -> tuple[Path, dict[str, object]]:
    path = ROOT / "config" / f"paper_table1_repeat{repeat}.json"
    if not path.exists():
        raise FileNotFoundError(f"preregistered Table-I manifest is missing: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("protocol_version") != "paper_table1_map_repeats_v1":
        raise ValueError("unexpected paper Table-I protocol version")
    if int(manifest.get("repeat", 0)) != repeat:
        raise ValueError("paper Table-I manifest repeat does not match --repeat")
    rg = manifest.get("rg")
    validation = manifest.get("frozen_validation")
    gate = manifest.get("gate")
    jacobian = manifest.get("jacobian")
    records = manifest.get("run_seed_sequences")
    if not all(isinstance(item, dict) for item in (rg, validation, gate, jacobian)):
        raise ValueError("paper Table-I manifest is missing a parameter section")
    if int(rg.get("rounds", 0)) != 2 or len(rg.get("seeds", [])) != 2:
        raise ValueError("paper Table-I protocol requires exactly two RG rounds")
    if int(validation.get("round", 0)) != 2:
        raise ValueError("only the RG2 frozen bias may enter the Table-I gate")
    if not isinstance(records, list) or len(records) != int(
        jacobian.get("independent_runs", 0)
    ):
        raise ValueError("Jacobian seed sequences do not match independent runs")
    return path, manifest


def _paper_table1_repeat(args: argparse.Namespace) -> None:
    manifest_path, manifest = _paper_table1_manifest(args.repeat)
    rg = manifest["rg"]
    validation = manifest["frozen_validation"]
    gate = manifest["gate"]
    jacobian_settings = manifest["jacobian"]
    length = int(rg["length"])
    if length % 3:
        raise ValueError("length must be divisible by three")

    root = _resolve_output(args.output_root) / f"repeat{args.repeat}"
    rg1 = root / "rg1"
    rg2 = root / "rg2"
    jacobian = root / "jacobian.json"
    repeat_report = root / "repeat_report.json"
    _assert_new_run(rg1, ("summary.json", "trajectory.npz", "convergence.json"))
    _assert_new_run(
        rg2,
        (
            "summary.json",
            "trajectory.npz",
            "convergence.json",
            "frozen_validation.json",
            "gate_report.json",
        ),
    )
    _assert_new_run(
        root,
        (jacobian.name, jacobian.with_suffix(".npz").name, repeat_report.name),
    )

    previous: Path | None = None
    for index, output in enumerate((rg1, rg2)):
        command = [
            sys.executable,
            SCRIPTS / "run_paper_even_rg.py",
            "--length",
            length,
            "--steps",
            int(rg["steps"]),
            "--sweeps",
            int(rg["sweeps_per_step"]),
            "--walkers",
            int(rg["walkers"]),
            "--mu",
            float(rg["learning_rate"]),
            "--seed",
            int(rg["seeds"][index]),
            "--output",
            output,
        ]
        if previous is None:
            command.extend(["--coupling", float(rg["coupling"])])
        else:
            command.extend(["--previous", previous])
        _run(command, args.dry_run)
        _run(
            [sys.executable, SCRIPTS / "analyze_even_trajectory.py", output],
            args.dry_run,
        )
        previous = output

    _run(
        [
            sys.executable,
            SCRIPTS / "validate_frozen_even_basis.py",
            "--input",
            rg2,
            "--thermalization",
            int(validation["thermalization_sweeps"]),
            "--measurements",
            int(validation["measurement_sweeps_per_run"]),
            "--runs",
            int(validation["independent_runs"]),
            "--family-alpha",
            float(validation["family_alpha"]),
            "--seed",
            int(validation["seed"]),
        ],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "assess_paper_rg_gate.py",
            "--input",
            rg2,
            "--max-coupling-drift",
            float(gate["maximum_absolute_component_drift_90_to_100_percent"]),
            "--expected-operators",
            13,
            "--minimum-validation-runs",
            int(validation["independent_runs"]),
            "--minimum-validation-measurements",
            int(validation["measurement_sweeps_per_run"]),
            "--expected-family-alpha",
            float(validation["family_alpha"]),
        ],
        args.dry_run,
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "measure_paper_jacobian.py",
            "--input",
            rg2,
            "--output",
            jacobian,
            "--thermalization",
            int(jacobian_settings["thermalization_sweeps"]),
            "--measurements",
            int(jacobian_settings["measurements_per_run"]),
            "--spacing",
            int(jacobian_settings["spacing_sweeps"]),
            "--runs",
            int(jacobian_settings["independent_runs"]),
            "--bootstrap",
            int(jacobian_settings["bootstrap_replicates"]),
            "--seed-manifest",
            manifest_path,
        ],
        args.dry_run,
    )
    if args.dry_run:
        return

    gate_report = _require_report_status(rg2 / "gate_report.json", "PASS")
    jacobian_report = _require_report_status(jacobian, "NUMERICALLY_STABLE")
    for parity in ("even", "odd"):
        block = jacobian_report[parity]
        if not math.isfinite(float(block["b_condition_number"])):
            raise RuntimeError(f"non-finite {parity} B condition number")
        if float(block["equation_relative_residual"]) >= 1.0e-10:
            raise RuntimeError(f"{parity} Jacobian equation residual failed")
    rg2_summary = json.loads((rg2 / "summary.json").read_text(encoding="utf-8"))
    result = {
        "material_passport": {
            "schema": 9,
            "artifact_type": "code_experiment_result",
            "verification_status": "VERIFIED",
        },
        "status": "PASS",
        "scope": "single_preregistered_direct_paper_RG2_map_and_Table_I_measurement",
        "protocol": str(
            (ROOT / "docs/paper_table1_map_replication_protocol_v1.md").resolve()
        ),
        "repeat": args.repeat,
        "manifest": str(manifest_path.resolve()),
        "rg2_input_couplings": rg2_summary["input_couplings"],
        "rg2_renormalized_couplings": rg2_summary["final_renormalized_couplings"],
        "pre_jacobian_gate": gate_report,
        "lambda_even": jacobian_report["even"]["leading_eigenvalue"],
        "lambda_odd": jacobian_report["odd"]["leading_eigenvalue"],
        "lambda_even_bootstrap": jacobian_report["even"]["bootstrap"],
        "lambda_odd_bootstrap": jacobian_report["odd"]["bootstrap"],
    }
    repeat_report.parent.mkdir(parents=True, exist_ok=True)
    repeat_report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def _assess_paper_table1(args: argparse.Namespace) -> None:
    root = _resolve_output(args.root)
    output = _resolve_output(args.output) if args.output else root / "pooled_assessment.json"
    _assert_new_run(output.parent, (output.name,))
    _run(
        [
            sys.executable,
            SCRIPTS / "assess_paper_table1_repeats.py",
            "--root",
            root,
            "--output",
            output,
            "--bootstrap",
            args.bootstrap,
            "--seed",
            args.seed,
        ],
        args.dry_run,
    )


def _autocorrelation(args: argparse.Namespace) -> None:
    input_dir = _resolve_output(args.input)
    output = (
        _resolve_output(args.output)
        if args.output
        else input_dir / "paper_autocorrelation.json"
    )
    _assert_new_run(output.parent, (output.name, output.with_suffix(".npz").name))
    _run(
        [
            sys.executable,
            SCRIPTS / "compare_paper_autocorrelation.py",
            "--input",
            input_dir,
            "--output",
            output,
            "--thermalization",
            args.thermalization,
            "--measurements",
            args.measurements,
            "--spacing",
            args.spacing,
            "--max-lag",
            args.max_lag,
            "--chains",
            args.chains,
            "--ratio-threshold",
            args.ratio_threshold,
            "--seed",
            args.seed,
        ],
        args.dry_run,
    )


FULL_PRESETS: dict[str, dict[str, int | float]] = {
    "smoke": {
        "rounds": 2,
        "steps": 2,
        "sweeps": 1,
        "walkers": 2,
        "validation_thermalization": 1,
        "validation_measurements": 2,
        "validation_runs": 3,
        "jacobian_thermalization": 5,
        "jacobian_measurements": 200,
        "jacobian_runs": 4,
        "jacobian_bootstrap": 50,
        "autocorrelation_thermalization": 10,
        "autocorrelation_measurements": 500,
        "autocorrelation_max_lag": 50,
        "autocorrelation_chains": 3,
    },
    "formal": {
        "rounds": 5,
        "steps": 3000,
        "sweeps": 20,
        "walkers": 16,
        "validation_thermalization": 500,
        "validation_measurements": 1000,
        "validation_runs": 16,
        "jacobian_thermalization": 5000,
        "jacobian_measurements": 1_000_000,
        "jacobian_runs": 16,
        "jacobian_bootstrap": 2000,
        "autocorrelation_thermalization": 5000,
        "autocorrelation_measurements": 100_000,
        "autocorrelation_max_lag": 2000,
        "autocorrelation_chains": 8,
    },
}


def _full(args: argparse.Namespace) -> None:
    if args.length != 45:
        raise ValueError("the integrated full workflow is frozen to the paper's L=45 case")
    settings = FULL_PRESETS[args.preset]
    output_root = _resolve_output(
        args.output_root
        or Path(
            f"output/reproduction/full_L{args.length}_K{_tag(args.coupling)}_{args.preset}"
        )
    )
    final_files = (
        "paper_jacobian.json",
        "paper_jacobian.npz",
        "paper_autocorrelation.json",
        "paper_autocorrelation.npz",
        "paper_report.json",
        "paper_results.png",
    )
    _assert_new_run(output_root, final_files)

    paper_args = argparse.Namespace(
        length=args.length,
        coupling=args.coupling,
        rounds=int(settings["rounds"]),
        steps=int(settings["steps"]),
        sweeps=int(settings["sweeps"]),
        walkers=int(settings["walkers"]),
        mu=5e-5,
        seed=args.seed,
        output_root=output_root,
        validate=True,
        validation_thermalization=int(settings["validation_thermalization"]),
        validation_measurements=int(settings["validation_measurements"]),
        validation_runs=int(settings["validation_runs"]),
        validation_seed=args.seed + 100,
        dry_run=args.dry_run,
    )
    _paper(paper_args)
    fixed_point_input = output_root / "rg2"
    jacobian_output = output_root / "paper_jacobian.json"
    autocorrelation_output = output_root / "paper_autocorrelation.json"
    _jacobian(
        argparse.Namespace(
            input=fixed_point_input,
            output=jacobian_output,
            thermalization=int(settings["jacobian_thermalization"]),
            measurements=int(settings["jacobian_measurements"]),
            spacing=1,
            runs=int(settings["jacobian_runs"]),
            bootstrap=int(settings["jacobian_bootstrap"]),
            seed=args.seed + 200,
            dry_run=args.dry_run,
        )
    )
    _autocorrelation(
        argparse.Namespace(
            input=fixed_point_input,
            output=autocorrelation_output,
            thermalization=int(settings["autocorrelation_thermalization"]),
            measurements=int(settings["autocorrelation_measurements"]),
            spacing=1,
            max_lag=int(settings["autocorrelation_max_lag"]),
            chains=int(settings["autocorrelation_chains"]),
            ratio_threshold=0.5,
            seed=args.seed + 300,
            dry_run=args.dry_run,
        )
    )
    _run(
        [
            sys.executable,
            SCRIPTS / "assemble_paper_report.py",
            "--root",
            output_root,
            "--jacobian",
            jacobian_output,
            "--autocorrelation",
            autocorrelation_output,
            "--mode",
            args.preset,
            "--output",
            output_root / "paper_report.json",
        ],
        args.dry_run,
    )
    print(f"full paper workflow output: {output_root}")


def _add_dry_run(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print commands without running Monte Carlo calculations",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python reproduce.py",
        description="Unified entry point for the Wu-Carrasquilla VMCRG reproduction"
    )
    subparsers = parser.add_subparsers(dest="workflow", required=True)

    tests = subparsers.add_parser("test", help="run all deterministic unit tests")
    _add_dry_run(tests)
    tests.set_defaults(handler=_tests)

    derive = subparsers.add_parser(
        "derive26", help="print the auditable reconstructed 26-operator candidates"
    )
    _add_dry_run(derive)
    derive.set_defaults(handler=_derive26)

    paper = subparsers.add_parser(
        "paper",
        help="run the source-confirmed 13-operator paper workflow",
    )
    paper.add_argument("--length", type=int, default=45)
    paper.add_argument("--coupling", type=float, default=0.436)
    paper.add_argument("--rounds", type=int, default=1)
    paper.add_argument("--steps", type=int, default=3000)
    paper.add_argument("--sweeps", type=int, default=20)
    paper.add_argument("--walkers", type=int, default=16)
    paper.add_argument("--mu", type=float, default=5e-5)
    paper.add_argument("--seed", type=int, default=20260715)
    paper.add_argument("--output-root", type=Path)
    paper.add_argument(
        "--no-validation",
        action="store_false",
        dest="validate",
        help="skip the independent frozen-bias validation",
    )
    paper.add_argument("--validation-thermalization", type=int, default=500)
    paper.add_argument("--validation-measurements", type=int, default=1000)
    paper.add_argument("--validation-runs", type=int, default=16)
    paper.add_argument("--validation-seed", type=int, default=20260716)
    _add_dry_run(paper)
    paper.set_defaults(handler=_paper, validate=True)

    candidate = subparsers.add_parser(
        "candidate26",
        help="run the non-source-verified 26-to-13 sensitivity workflow",
    )
    candidate.add_argument(
        "--pair-tie",
        choices=("both", "axis5", "generic43"),
        default="both",
    )
    candidate.add_argument(
        "--coupling",
        type=float,
        required=True,
        help="user-supplied because the paper does not publish the preliminary value",
    )
    candidate.add_argument("--length", type=int, default=45)
    candidate.add_argument("--steps", type=int, default=3000)
    candidate.add_argument("--sweeps", type=int, default=20)
    candidate.add_argument("--walkers", type=int, default=16)
    candidate.add_argument("--mu", type=float, default=5e-5)
    candidate.add_argument("--threshold", type=float, default=0.001)
    candidate.add_argument("--seed", type=int, default=20260720)
    candidate.add_argument("--output-root", type=Path)
    candidate.add_argument(
        "--no-validation",
        action="store_false",
        dest="validate",
    )
    candidate.add_argument("--validation-thermalization", type=int, default=500)
    candidate.add_argument("--validation-measurements", type=int, default=1000)
    candidate.add_argument("--validation-runs", type=int, default=32)
    candidate.add_argument("--bootstrap", type=int, default=20000)
    candidate.add_argument("--family-alpha", type=float, default=0.05)
    candidate.add_argument("--validation-seed", type=int, default=20260721)
    _add_dry_run(candidate)
    candidate.set_defaults(handler=_candidate26, validate=True)

    jacobian = subparsers.add_parser(
        "jacobian",
        help="measure even/odd RG Jacobians and critical exponents from a frozen RG2 bias",
    )
    jacobian.add_argument("--input", type=Path, required=True)
    jacobian.add_argument("--output", type=Path)
    jacobian.add_argument("--thermalization", type=int, default=5000)
    jacobian.add_argument("--measurements", type=int, default=1_000_000)
    jacobian.add_argument("--spacing", type=int, default=1)
    jacobian.add_argument("--runs", type=int, default=16)
    jacobian.add_argument("--bootstrap", type=int, default=2000)
    jacobian.add_argument("--seed", type=int, default=20260740)
    _add_dry_run(jacobian)
    jacobian.set_defaults(handler=_jacobian)

    fixed_point = subparsers.add_parser(
        "fixed-point",
        help="solve and independently verify the complete 13D RG fixed point",
    )
    fixed_point.add_argument("--map-input", type=Path, required=True)
    fixed_point.add_argument(
        "--jacobian", type=Path, required=True, help="NPZ containing t_even"
    )
    fixed_point.add_argument("--length", type=int, default=45)
    fixed_point.add_argument("--steps", type=int, default=3000)
    fixed_point.add_argument("--sweeps", type=int, default=20)
    fixed_point.add_argument("--walkers", type=int, default=16)
    fixed_point.add_argument("--mu", type=float, default=5e-5)
    fixed_point.add_argument("--seed", type=int, default=20260760)
    fixed_point.add_argument("--output-root", type=Path)
    fixed_point.add_argument("--initial-bias-from", type=Path)
    fixed_point.add_argument("--absolute-tolerance", type=float, default=1e-3)
    fixed_point.add_argument("--relative-tolerance", type=float, default=5e-3)
    fixed_point.add_argument("--maximum-condition-number", type=float, default=1e6)
    fixed_point.add_argument("--maximum-correction", type=float, default=0.05)
    fixed_point.add_argument("--validation-thermalization", type=int, default=500)
    fixed_point.add_argument("--validation-measurements", type=int, default=1000)
    fixed_point.add_argument("--validation-runs", type=int, default=16)
    fixed_point.add_argument("--validation-seed", type=int, default=20260761)
    _add_dry_run(fixed_point)
    fixed_point.set_defaults(handler=_fixed_point)

    repeat_v2 = subparsers.add_parser(
        "fixed-point-repeat-v2",
        help="run one preregistered end-to-end fixed-point/Table-I repeat",
    )
    repeat_v2.add_argument("--repeat", type=int, choices=(1, 2, 3), required=True)
    _add_dry_run(repeat_v2)
    repeat_v2.set_defaults(handler=_fixed_point_repeat_v2)

    repeat_v3 = subparsers.add_parser(
        "fixed-point-repeat-v3",
        help="run one calibrated preregistered fixed-point/Table-I repeat",
    )
    repeat_v3.add_argument("--repeat", type=int, choices=(1, 2, 3), required=True)
    _add_dry_run(repeat_v3)
    repeat_v3.set_defaults(handler=_fixed_point_repeat_v3)

    audit_v3 = subparsers.add_parser(
        "audit-fixed-point-v3",
        help="audit completed v3 repeats and build a calibration-only common anchor",
    )
    audit_v3.add_argument(
        "--root",
        type=Path,
        default=Path("output/reproduction/fixed_point_repeats_v3"),
    )
    audit_v3.add_argument("--repeats", type=int, nargs="+", required=True)
    audit_v3.add_argument(
        "--output",
        type=Path,
        default=Path(
            "output/reproduction/fixed_point_repeats_v3/early_stop_audit.json"
        ),
    )
    audit_v3.add_argument(
        "--anchor-output",
        type=Path,
        default=Path(
            "output/reproduction/fixed_point_repeats_v3/v4_calibration_anchor.json"
        ),
    )
    _add_dry_run(audit_v3)
    audit_v3.set_defaults(handler=_audit_fixed_point_v3)

    pilot_v4 = subparsers.add_parser(
        "fixed-point-v4-pilot",
        help="test two independent Jacobian batches at one frozen pooled anchor",
    )
    pilot_v4.add_argument(
        "--anchor",
        type=Path,
        default=Path(
            "output/reproduction/fixed_point_repeats_v3/v4_calibration_anchor.json"
        ),
    )
    pilot_v4.add_argument(
        "--output-root",
        type=Path,
        default=Path("output/reproduction/fixed_point_v4_pilot"),
    )
    _add_dry_run(pilot_v4)
    pilot_v4.set_defaults(handler=_fixed_point_v4_pilot)

    batch_v4 = subparsers.add_parser(
        "fixed-point-v4-batch-diagnostic",
        help="add a frozen third common-anchor batch and test master-seed effects",
    )
    batch_v4.add_argument(
        "--output-root",
        type=Path,
        default=Path("output/reproduction/fixed_point_v4_pilot"),
    )
    _add_dry_run(batch_v4)
    batch_v4.set_defaults(handler=_fixed_point_v4_batch_diagnostic)

    table1_v5 = subparsers.add_parser(
        "table1-v5-repeat",
        help="run one formal stratified common-anchor Table-I repeat",
    )
    table1_v5.add_argument("--repeat", type=int, choices=(1, 2, 3), required=True)
    table1_v5.add_argument(
        "--input",
        type=Path,
        default=Path("output/reproduction/fixed_point_v4_pilot/anchor_rg"),
    )
    table1_v5.add_argument(
        "--output-root",
        type=Path,
        default=Path("output/reproduction/table1_v5"),
    )
    _add_dry_run(table1_v5)
    table1_v5.set_defaults(handler=_table1_v5_repeat)

    paper_table1 = subparsers.add_parser(
        "paper-table1-repeat",
        help="run one preregistered direct-paper RG1/RG2/gate/Table-I repeat",
    )
    paper_table1.add_argument("--repeat", type=int, choices=(1, 2, 3), required=True)
    paper_table1.add_argument(
        "--output-root",
        type=Path,
        default=Path("output/reproduction/paper_table1_map_repeats"),
    )
    _add_dry_run(paper_table1)
    paper_table1.set_defaults(handler=_paper_table1_repeat)

    assess_paper_table1 = subparsers.add_parser(
        "paper-table1-assess",
        help="pool passed direct-paper repeats with a hierarchical bootstrap",
    )
    assess_paper_table1.add_argument(
        "--root",
        type=Path,
        default=Path("output/reproduction/paper_table1_map_repeats"),
    )
    assess_paper_table1.add_argument("--output", type=Path)
    assess_paper_table1.add_argument("--bootstrap", type=int, default=10_000)
    assess_paper_table1.add_argument("--seed", type=int, default=202617901)
    _add_dry_run(assess_paper_table1)
    assess_paper_table1.set_defaults(handler=_assess_paper_table1)

    autocorrelation = subparsers.add_parser(
        "autocorrelation",
        help="compare biased and unbiased time correlations of the paper estimator",
    )
    autocorrelation.add_argument("--input", type=Path, required=True)
    autocorrelation.add_argument("--output", type=Path)
    autocorrelation.add_argument("--thermalization", type=int, default=5000)
    autocorrelation.add_argument("--measurements", type=int, default=100_000)
    autocorrelation.add_argument("--spacing", type=int, default=1)
    autocorrelation.add_argument("--max-lag", type=int, default=2000)
    autocorrelation.add_argument("--chains", type=int, default=8)
    autocorrelation.add_argument("--ratio-threshold", type=float, default=0.5)
    autocorrelation.add_argument("--seed", type=int, default=20260750)
    _add_dry_run(autocorrelation)
    autocorrelation.set_defaults(handler=_autocorrelation)

    neural_easy = subparsers.add_parser(
        "neural-easy",
        help="run the complete L45 hybrid-neural VMCRG easy challenge",
    )
    neural_easy.add_argument(
        "--preset", choices=("smoke", "pilot", "formal"), required=True
    )
    neural_easy.add_argument("--output", type=Path)
    neural_easy.add_argument(
        "--fixed-point-map",
        type=Path,
        default=Path(
            "output/reproduction/fixed_point_newton_v2/corrected_rg_v3/summary.json"
        ),
    )
    _add_dry_run(neural_easy)
    neural_easy.set_defaults(handler=_neural_easy)

    neural_confirm = subparsers.add_parser(
        "neural-confirm",
        help="run the locked five-seed L45 hybrid-neural confirmation protocol",
    )
    neural_confirm.add_argument(
        "--preset", choices=("smoke", "pilot", "formal"), required=True
    )
    neural_confirm.add_argument("--output-root", type=Path)
    neural_confirm.add_argument(
        "--fixed-point-map",
        type=Path,
        default=Path(
            "output/reproduction/fixed_point_newton_v2/corrected_rg_v3/summary.json"
        ),
    )
    neural_confirm.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/neural_confirmation_v1.json"),
    )
    _add_dry_run(neural_confirm)
    neural_confirm.set_defaults(handler=_neural_confirm)

    neural_replacement_confirm = subparsers.add_parser(
        "neural-replacement-confirm",
        help="run the locked five-seed L45 pure-neural replacement protocol",
    )
    neural_replacement_confirm.add_argument("--output-root", type=Path)
    neural_replacement_confirm.add_argument(
        "--fixed-point-map",
        type=Path,
        default=Path(
            "output/reproduction/fixed_point_newton_v2/corrected_rg_v3/summary.json"
        ),
    )
    neural_replacement_confirm.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/neural_replacement_formal_v1.json"),
    )
    _add_dry_run(neural_replacement_confirm)
    neural_replacement_confirm.set_defaults(handler=_neural_replacement_confirm)

    neural_three_arm = subparsers.add_parser(
        "neural-three-arm",
        help="attribute sampling acceleration among unbiased, linear, and hybrid arms",
    )
    neural_three_arm.add_argument("--output-root", type=Path)
    neural_three_arm.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/neural_three_arm_v1.json"),
    )
    _add_dry_run(neural_three_arm)
    neural_three_arm.set_defaults(handler=_neural_three_arm)

    neural_root_cause = subparsers.add_parser(
        "neural-root-cause",
        help="diagnose why the frozen neural residual did not improve sampling",
    )
    neural_root_cause.add_argument("--output", type=Path)
    neural_root_cause.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/neural_root_cause_v1.json"),
    )
    _add_dry_run(neural_root_cause)
    neural_root_cause.set_defaults(handler=_neural_root_cause)

    neural_identity_gradient = subparsers.add_parser(
        "neural-identity-gradient",
        help="compare the frozen identity-RG neural gradient with an importance oracle",
    )
    neural_identity_gradient.add_argument(
        "--preset", choices=("smoke", "pilot", "formal"), required=True
    )
    neural_identity_gradient.add_argument("--output", type=Path)
    neural_identity_gradient.add_argument(
        "--model",
        type=Path,
        default=Path(
            "output/neural_supervised_identity_formal_v1/supervised_model.npz"
        ),
    )
    neural_identity_gradient.add_argument(
        "--fixed-point-map",
        type=Path,
        default=Path(
            "output/reproduction/fixed_point_newton_v2/corrected_rg_v3/summary.json"
        ),
    )
    neural_identity_gradient.add_argument("--seed", type=int, default=202607281)
    _add_dry_run(neural_identity_gradient)
    neural_identity_gradient.set_defaults(handler=_neural_identity_gradient)

    neural_optimizer_stability = subparsers.add_parser(
        "neural-optimizer-stability",
        help="test Robbins-Monro identity-RG stability from a certified checkpoint",
    )
    neural_optimizer_stability.add_argument(
        "--preset", choices=("smoke", "pilot"), required=True
    )
    neural_optimizer_stability.add_argument("--output", type=Path)
    neural_optimizer_stability.add_argument(
        "--initial-model",
        type=Path,
        default=Path(
            "output/neural_supervised_identity_formal_v1/supervised_model.npz"
        ),
    )
    neural_optimizer_stability.add_argument(
        "--fixed-point-map",
        type=Path,
        default=Path(
            "output/reproduction/fixed_point_newton_v2/corrected_rg_v3/summary.json"
        ),
    )
    _add_dry_run(neural_optimizer_stability)
    neural_optimizer_stability.set_defaults(handler=_neural_optimizer_stability)

    neural_replacement = subparsers.add_parser(
        "neural-replacement",
        help="train a radius-3 D4/Z2 neural energy with no 13-operator bias branch",
    )
    neural_replacement.add_argument(
        "--preset", choices=("smoke", "pilot", "formal"), required=True
    )
    neural_replacement.add_argument("--output", type=Path)
    neural_replacement.add_argument(
        "--fixed-point-map",
        type=Path,
        default=Path(
            "output/reproduction/fixed_point_newton_v2/corrected_rg_v3/summary.json"
        ),
    )
    _add_dry_run(neural_replacement)
    neural_replacement.set_defaults(handler=_neural_replacement)

    assess_neural_replacement = subparsers.add_parser(
        "neural-replacement-assess",
        help="compare the pure-neural L45 pilot with a paired zero-bias baseline",
    )
    assess_neural_replacement.add_argument("--input", type=Path, required=True)
    assess_neural_replacement.add_argument("--output", type=Path)
    _add_dry_run(assess_neural_replacement)
    assess_neural_replacement.set_defaults(handler=_assess_neural_replacement)

    full = subparsers.add_parser(
        "full",
        help="run RG flow, Jacobians, critical exponents, autocorrelation, and report",
    )
    full.add_argument("--preset", choices=tuple(FULL_PRESETS), required=True)
    full.add_argument("--length", type=int, default=45)
    full.add_argument("--coupling", type=float, default=0.436)
    full.add_argument("--seed", type=int, default=20260780)
    full.add_argument("--output-root", type=Path)
    _add_dry_run(full)
    full.set_defaults(handler=_full)

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.handler(args)


if __name__ == "__main__":
    main()
