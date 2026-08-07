#!/usr/bin/env python3
"""Prepare reproducible ALF inputs for binary-Hirsch smoke and production runs."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALF_ROOT = PROJECT_ROOT / "ALF"
START_PARAMETERS = (
    ALF_ROOT / "Scripts_and_Parameters_files" / "Start" / "parameters"
)
START_SEEDS = ALF_ROOT / "Scripts_and_Parameters_files" / "Start" / "seeds"
RAW_OUTPUT_NAMES = ("info", "Ener_scal", "confout_0", "run.log")


def replace_assignment(text: str, name: str, value: str, count: int = 1) -> str:
    pattern = re.compile(
        rf"(?m)^(\s*{re.escape(name)}\s*=\s*)[^!\n]*(.*)$",
        re.IGNORECASE,
    )
    updated, replacements = pattern.subn(
        lambda match: f"{match.group(1)}{value}{match.group(2)}",
        text,
        count=count,
    )
    if replacements != count:
        raise RuntimeError(
            f"expected {count} assignment(s) for {name}, found {replacements}"
        )
    return updated


def make_parameters(nsweep: int, nbin: int) -> str:
    text = START_PARAMETERS.read_text(encoding="utf-8")
    text = replace_assignment(text, "ham_name", '"Hubbard_Plain_Vanilla"')
    text = replace_assignment(text, "L1", "4")
    text = replace_assignment(text, "L2", "4")
    text = replace_assignment(text, "NSweep", str(nsweep))
    text = replace_assignment(text, "NBin", str(nbin))
    text = replace_assignment(text, "Ltau", "0")
    text = replace_assignment(text, "n_skip", "1")
    text = replace_assignment(text, "N_rebin", "1")

    group_start = text.index("&VAR_Hubbard_Plain_Vanilla")
    group_end_match = re.search(r"(?m)^/\s*$", text[group_start:])
    if group_end_match is None:
        raise RuntimeError("unterminated VAR_Hubbard_Plain_Vanilla group")
    group_end = group_start + group_end_match.start()
    group = text[group_start:group_end]
    for name, value in (
        ("ham_T", "1.d0"),
        ("ham_chem", "0.d0"),
        ("ham_U", "4.d0"),
        ("Dtau", "0.05d0"),
        ("Beta", "1.d0"),
        ("Projector", ".T."),
        ("Theta", "10.d0"),
        ("Symm", ".T."),
    ):
        group = replace_assignment(group, name, value)
    group += "Hirsch_binary = .T.       ! Exact two-valued spin HS field\n"
    return text[:group_start] + group + text[group_end:]


def check_clean_target(run_dir: Path) -> None:
    present = [name for name in RAW_OUTPUT_NAMES if (run_dir / name).exists()]
    if present:
        names = ", ".join(present)
        raise RuntimeError(
            f"{run_dir} already contains run output ({names}); "
            "move it aside before preparing a new run"
        )


def prepare_run(run_dir: Path, parameters: str, seed: int) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    check_clean_target(run_dir)
    (run_dir / "parameters").write_text(parameters, encoding="utf-8")
    (run_dir / "seeds").write_text(f"{seed:12d}\n", encoding="utf-8")


def prepare_smoke(seeds: list[int]) -> None:
    run_dir = PROJECT_ROOT / "run" / "binary" / "smoke"
    prepare_run(run_dir, make_parameters(nsweep=20, nbin=1), seeds[0])
    # A grouped six-rank smoke needs six seeds in one file.
    (run_dir / "seeds").write_text(
        "".join(f"{seed:12d}\n" for seed in seeds[:6]), encoding="utf-8"
    )


def prepare_production(seeds: list[int]) -> None:
    parameters = make_parameters(nsweep=2000, nbin=7)
    root = PROJECT_ROOT / "run" / "binary" / "production"
    for chain, seed in enumerate(seeds[:6]):
        prepare_run(root / f"chain_{chain}", parameters, seed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("smoke", "production", "all"),
        default="all",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not START_PARAMETERS.is_file() or not START_SEEDS.is_file():
        raise SystemExit("pinned ALF checkout is missing; run the build step first")
    seeds = [
        int(line)
        for line in START_SEEDS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(seeds) < 6 or len(set(seeds[:6])) != 6:
        raise SystemExit("ALF seed file does not provide six distinct seeds")
    if args.mode in ("smoke", "all"):
        prepare_smoke(seeds)
    if args.mode in ("production", "all"):
        prepare_production(seeds)


if __name__ == "__main__":
    main()
