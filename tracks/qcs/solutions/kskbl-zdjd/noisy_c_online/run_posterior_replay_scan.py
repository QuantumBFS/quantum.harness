"""Execute a parameter-scan run spec for posterior-replay learners."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).with_name("train_posterior_replay.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--cell", action="append", default=[])
    return parser.parse_args()


def option(name: str) -> str:
    return "--" + name.replace("_", "-")


def build_command(
    settings: dict[str, Any],
    params: dict[str, Any],
    output_dir: Path,
) -> list[str]:
    payload = {
        "learning_rate_schedule": "cosine",
        "anneal_loss_threshold": 0.05,
        "anneal_steps": 1000,
        **settings,
        **params,
    }
    ordered_keys = (
        "steps",
        "batch_size",
        "replay_batch_size",
        "replay_strategy",
        "candidate_multiplier",
        "active_exploration",
        "noise_rate",
        "ensemble_size",
        "architecture",
        "hidden",
        "depth",
        "learning_rate",
        "minimum_learning_rate",
        "learning_rate_schedule",
        "anneal_loss_threshold",
        "anneal_steps",
        "weight_decay",
        "confidence_power",
        "eval_every",
        "base_seed",
        "device",
        "threads",
    )
    command = [sys.executable, str(SCRIPT)]
    for key in ordered_keys:
        command.extend((option(key), str(payload[key])))
    command.extend(("--output-dir", str(output_dir)))
    return command


def main() -> None:
    args = parse_args()
    run_spec = json.loads(args.run_spec.read_text(encoding="utf-8"))
    run_dir = Path(run_spec["run_dir"])
    selected = set(args.cell)

    for cell in run_spec["cells"]:
        cell_id = cell["cell_id"]
        if selected and cell_id not in selected:
            continue
        cell_dir = run_dir / "cells" / cell_id
        artifact_dir = cell_dir / "artifacts"
        manifest_path = cell_dir / "manifest.json"
        if manifest_path.exists():
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
            if previous.get("status") == "success":
                print(f"{cell_id}: already successful; skipping", flush=True)
                continue

        cell_dir.mkdir(parents=True, exist_ok=True)
        command = build_command(
            run_spec["settings"],
            cell["params"],
            artifact_dir,
        )
        started = time.perf_counter()
        completed = subprocess.run(command, check=False)
        elapsed = time.perf_counter() - started

        manifest: dict[str, Any] = {
            "status": "success" if completed.returncode == 0 else "failed",
            "params": cell["params"],
            "settings": run_spec["settings"],
            "provenance": run_spec["provenance"],
            "command": command,
            "returncode": completed.returncode,
            "elapsed_seconds": elapsed,
        }
        run_path = artifact_dir / "run.json"
        if run_path.exists():
            run = json.loads(run_path.read_text(encoding="utf-8"))
            manifest["result"] = run.get("final", {})
            manifest["verification"] = run.get("verification", {})
        manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        print(
            f"{cell_id}: {manifest['status']} in {elapsed:.1f}s",
            flush=True,
        )


if __name__ == "__main__":
    main()
