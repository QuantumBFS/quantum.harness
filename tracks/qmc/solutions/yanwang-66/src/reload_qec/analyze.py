"""Checksum-verified paired analysis for completed immutable runs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from .stats import paired_comparison


class AnalysisError(ValueError):
    """Raised when run artifacts cannot support a paired comparison."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bootstrap-resamples", type=int, default=20_000)
    parser.add_argument("--bootstrap-seed", type=int, default=6_600_066)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksums(run_dir: Path) -> None:
    checksum_path = run_dir / "checksums.sha256"
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, separator, name = line.partition("  ")
        if separator != "  " or not name or "/" in name or "\\" in name:
            raise AnalysisError(f"invalid checksum entry {line!r}")
        artifact = run_dir / name
        if not artifact.is_file() or _sha256(artifact) != digest:
            raise AnalysisError(f"checksum mismatch for {artifact}")


def load_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    verify_checksums(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="ascii"))
    arrays: dict[str, list[np.ndarray]] = {
        "shot_id": [],
        "logical_observable": [],
        "decoder_prediction": [],
        "logical_failure": [],
        "catastrophic_loss": [],
    }
    for shard in manifest["shards"]:
        label_path = run_dir / shard["labels"]
        with np.load(label_path, allow_pickle=False) as payload:
            for key in arrays:
                arrays[key].append(np.asarray(payload[key]))
    concatenated = {
        key: np.concatenate(parts, axis=0) for key, parts in arrays.items()
    }
    shot_id = concatenated["shot_id"].reshape(-1)
    if len(shot_id) != manifest["request"]["shots"]:
        raise AnalysisError("label shard count does not match requested shots")
    if len(np.unique(shot_id)) != len(shot_id):
        raise AnalysisError("duplicate shot IDs in run")
    expected_failure = np.bitwise_xor(
        concatenated["logical_observable"].reshape(-1),
        concatenated["decoder_prediction"].reshape(-1),
    )
    if not np.array_equal(expected_failure, concatenated["logical_failure"].reshape(-1)):
        raise AnalysisError("logical failure labels do not equal observable XOR prediction")
    return manifest, concatenated


def _paired_request_view(request: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in request.items()
        if key not in {"run_id", "policy"}
    }


def analyze(
    baseline_dir: Path,
    candidate_dir: Path,
    *,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    baseline_manifest, baseline = load_run(baseline_dir)
    candidate_manifest, candidate = load_run(candidate_dir)
    if _paired_request_view(baseline_manifest["request"]) != _paired_request_view(
        candidate_manifest["request"]
    ):
        raise AnalysisError("runs differ in a field other than run_id/policy")
    if not np.array_equal(
        baseline["shot_id"].reshape(-1), candidate["shot_id"].reshape(-1)
    ):
        raise AnalysisError("paired runs have different shot IDs or ordering")
    comparison = paired_comparison(
        baseline["logical_failure"],
        candidate["logical_failure"],
        bootstrap_resamples=bootstrap_resamples,
        bootstrap_seed=bootstrap_seed,
    )
    return {
        "schema_version": "q66-paired-comparison-v1",
        "baseline_run_id": baseline_manifest["run_id"],
        "candidate_run_id": candidate_manifest["run_id"],
        "baseline_policy": baseline_manifest["request"]["policy"],
        "candidate_policy": candidate_manifest["request"]["policy"],
        "orientation": "candidate_minus_baseline",
        "bootstrap_resamples": bootstrap_resamples,
        "bootstrap_seed": bootstrap_seed,
        "comparison": comparison.as_dict(),
        "interpretation": "pilot-descriptive-only-no-fdr-claim",
    }


def main() -> None:
    args = parse_args()
    result = analyze(
        args.baseline,
        args.candidate,
        bootstrap_resamples=args.bootstrap_resamples,
        bootstrap_seed=args.bootstrap_seed,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="ascii"
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
