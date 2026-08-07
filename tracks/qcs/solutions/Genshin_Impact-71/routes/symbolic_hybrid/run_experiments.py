#!/usr/bin/env python3
"""Run pinned Espresso and ABC flows, convert K=2 LUTs, and audit exhaustively."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence

import routes


def run_logged(
    argv: Sequence[str],
    log_path: Path,
    *,
    stdout_path: Path | None = None,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if stdout_path is None:
        completed = subprocess.run(
            list(argv),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        log_path.write_text(completed.stdout, encoding="utf-8", newline="\n")
    else:
        with stdout_path.open("w", encoding="utf-8", newline="\n") as output:
            completed = subprocess.run(
                list(argv),
                text=True,
                stdout=output,
                stderr=subprocess.PIPE,
                check=False,
            )
        log_path.write_text(completed.stderr, encoding="utf-8", newline="\n")
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {list(argv)!r}; log={log_path}"
        )


def abc_map(abc: Path, source: Path, destination: Path, log_path: Path) -> None:
    command = (
        f"read {source}; "
        "strash; balance; rewrite; refactor; rewrite -z; balance; "
        "if -K 2; print_stats; "
        f"write_blif {destination}"
    )
    run_logged((str(abc), "-c", command), log_path)
    if not destination.is_file():
        raise RuntimeError(f"ABC did not create {destination}")


def abc_map_incomplete(
    abc: Path, source: Path, destination: Path, log_path: Path
) -> None:
    # collapse selects an ISOP using the global pExdc care network.
    command = (
        f"read_blif {source}; strash; collapse; strash; "
        "balance; rewrite; refactor; rewrite -z; balance; "
        "if -K 2; print_stats; "
        f"write_blif {destination}"
    )
    run_logged((str(abc), "-c", command), log_path)
    if not destination.is_file():
        raise RuntimeError(f"ABC did not create {destination}")


def convert_and_audit(
    discovery_path: Path,
    mapped_blif: Path,
    challenge_path: Path,
    audit_path: Path,
    *,
    require_exact: bool,
) -> dict[str, object]:
    routes.command_convert_k2(
        type("Args", (), {"blif": str(mapped_blif), "out": str(challenge_path)})
    )
    routes.command_verify(
        type(
            "Args",
            (),
            {
                "discovery": str(discovery_path),
                "circuit": str(challenge_path),
                "out": str(audit_path),
                "require_exact": require_exact,
            },
        )
    )
    return json.loads(audit_path.read_text(encoding="utf-8"))


def run_one(name: str, work: Path, abc: Path, espresso: Path) -> dict[str, object]:
    directory = work / name
    discovery_path = directory / "discovery.json"

    # Confirm ABC's BLIF reader recognizes the explicit external don't-care
    # network. This roundtrip is a format check, not the minimization route.
    exdc_roundtrip = directory / "train-incomplete-exdc.roundtrip.blif"
    run_logged(
        (
            str(abc),
            "-c",
            f"read_blif {directory / 'train-incomplete-exdc.blif'}; "
            f"print_stats; write_blif {exdc_roundtrip}",
        ),
        directory / "abc-exdc-roundtrip.log",
    )

    abc_incomplete_blif = directory / "abc-incomplete-k2.blif"
    abc_map_incomplete(
        abc,
        directory / "train-incomplete-exdc.blif",
        abc_incomplete_blif,
        directory / "abc-incomplete.log",
    )
    abc_incomplete_audit = convert_and_audit(
        discovery_path,
        abc_incomplete_blif,
        directory / "abc-incomplete.txt",
        directory / "abc-incomplete-audit.json",
        require_exact=False,
    )

    # Standalone Berkeley Espresso consumes F/D/R from `.type fr`. ABC's
    # `read_pla` intentionally ignores `.type`, so it is used only after
    # Espresso has selected a fully specified ON cover.
    minimized = directory / "espresso-minimized.pla"
    run_logged(
        (str(espresso), "-o", "f", str(directory / "train-incomplete.pla")),
        directory / "espresso.log",
        stdout_path=minimized,
    )
    incomplete_blif = directory / "espresso-incomplete-k2.blif"
    abc_map(
        abc,
        minimized,
        incomplete_blif,
        directory / "abc-espresso-incomplete.log",
    )
    incomplete_audit = convert_and_audit(
        discovery_path,
        incomplete_blif,
        directory / "espresso-incomplete.txt",
        directory / "espresso-incomplete-audit.json",
        require_exact=False,
    )

    exact_candidates: list[dict[str, object]] = []
    bdd_metrics = json.loads(
        (directory / "bdd-metrics.json").read_text(encoding="utf-8")
    )
    for order_name, order_data in sorted(bdd_metrics["orders"].items()):
        source = Path(order_data["blif_path"])
        mapped = directory / f"hybrid-bdd-{order_name}-k2.blif"
        challenge = directory / f"hybrid-bdd-{order_name}.txt"
        audit_path = directory / f"hybrid-bdd-{order_name}-audit.json"
        abc_map(abc, source, mapped, directory / f"abc-bdd-{order_name}.log")
        audit = convert_and_audit(
            discovery_path,
            mapped,
            challenge,
            audit_path,
            require_exact=True,
        )
        exact_candidates.append(
            {
                "route": f"bdd-{order_name}",
                "source_nodes": order_data["nonterminal_nodes"],
                "challenge": str(challenge),
                "audit": str(audit_path),
                "gates": audit["gates"],
            }
        )

    # Also hand the frozen semantic truth table directly to ABC. This controls
    # for any restriction introduced by the selected BDD decomposition.
    semantic_mapped = directory / "hybrid-semantic-full-k2.blif"
    semantic_challenge = directory / "hybrid-semantic-full.txt"
    semantic_audit_path = directory / "hybrid-semantic-full-audit.json"
    abc_map(
        abc,
        directory / "semantic-full.pla",
        semantic_mapped,
        directory / "abc-semantic-full.log",
    )
    semantic_audit = convert_and_audit(
        discovery_path,
        semantic_mapped,
        semantic_challenge,
        semantic_audit_path,
        require_exact=True,
    )
    exact_candidates.append(
        {
            "route": "semantic-full",
            "source_nodes": None,
            "challenge": str(semantic_challenge),
            "audit": str(semantic_audit_path),
            "gates": semantic_audit["gates"],
        }
    )

    best = min(exact_candidates, key=lambda item: (item["gates"], item["route"]))
    best_path = directory / "hybrid-best.txt"
    shutil.copyfile(best["challenge"], best_path)
    best_audit = convert_and_audit(
        discovery_path,
        Path(best["challenge"]).with_name(
            Path(best["challenge"]).stem + "-k2.blif"
        )
        if False
        else (
            semantic_mapped
            if best["route"] == "semantic-full"
            else directory / f"hybrid-{best['route']}-k2.blif"
        ),
        directory / "hybrid-best-reconverted.txt",
        directory / "hybrid-best-reconverted-audit.json",
        require_exact=True,
    )
    # Preserve the selected original byte-for-byte; the reconversion above is
    # a deterministic audit of the selected mapped BLIF.
    if routes.sha256_file(best_path) != routes.sha256_file(
        directory / "hybrid-best-reconverted.txt"
    ):
        raise RuntimeError("selected hybrid conversion is not deterministic")

    result = {
        "instance": name,
        "espresso_incomplete": incomplete_audit,
        "abc_incomplete": abc_incomplete_audit,
        "exact_candidates": exact_candidates,
        "best": {
            **best,
            "copied_challenge": str(best_path),
            "reconversion_audit": best_audit,
        },
    }
    routes.atomic_json(directory / "flow-summary.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", required=True)
    parser.add_argument("--abc", required=True)
    parser.add_argument("--espresso", required=True)
    args = parser.parse_args()
    work = Path(args.work).resolve()
    abc = Path(args.abc).resolve()
    espresso = Path(args.espresso).resolve()
    if not os.access(abc, os.X_OK) or not os.access(espresso, os.X_OK):
        raise ValueError("ABC/Espresso executable missing")

    summary: dict[str, object] = {
        "schema": "occam71-official-espresso-abc-hybrid-v1",
        "root_seed": routes.ROOT_SEED,
        "abc": str(abc),
        "espresso": str(espresso),
        "instances": {},
    }
    for name in routes.INSTANCE_NAMES:
        summary["instances"][name] = run_one(name, work, abc, espresso)
    routes.atomic_json(work / "flow-summary.json", summary)
    (work / "FLOW_COMPLETE").write_text("success\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
