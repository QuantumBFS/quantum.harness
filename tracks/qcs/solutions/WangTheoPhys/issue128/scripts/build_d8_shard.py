#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback

from trottercert.cubic_field import fourth_order_suzuki_cubic_stages
from trottercert.cubic_local import exact_right_generator_stage_contribution
from trottercert.hpc_artifacts import (
    coordinate_encode_series,
    cubic_to_json,
    sha256_file,
    write_manifest_atomic,
    write_shard_gzip,
)


FORMULA_ID = "five_copy_suzuki_fourth_order_exact_cubic"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_state(root: Path) -> tuple[str, bool]:
    shipped_commit = os.environ.get("ISSUE128_SOURCE_COMMIT")
    if shipped_commit:
        dirty_text = os.environ.get("ISSUE128_SOURCE_DIRTY", "0").lower()
        return shipped_commit, dirty_text in {"1", "true", "yes"}
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return commit, dirty


def _max_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports KiB.
    return int(value if sys.platform == "darwin" else value * 1024)


def build_shard(
    *,
    stage_index: int,
    order: int,
    output: Path,
    manifest: Path,
    repository_root: Path,
) -> dict[str, object]:
    stages = fourth_order_suzuki_cubic_stages()
    if stage_index < 0 or stage_index >= len(stages):
        raise ValueError(f"stage index must be in [0, {len(stages) - 1}]")
    if order < 0:
        raise ValueError("order must be nonnegative")
    commit, dirty = _source_state(repository_root)
    started_at = _utc_now()
    started = time.perf_counter()
    running = {
        "schema_version": 1,
        "kind": "issue128_d8_stage_manifest",
        "status": "running",
        "stage_index": stage_index,
        "stage_count": len(stages),
        "order": order,
        "git_commit": commit,
        "git_dirty": dirty,
        "started_at": started_at,
    }
    write_manifest_atomic(manifest, running)
    print(
        f"stage={stage_index}/{len(stages)-1} order={order} status=running",
        flush=True,
    )
    try:
        registry, series = exact_right_generator_stage_contribution(
            stages, stage_index, order
        )
        stage = stages[stage_index]
        payload = {
            "schema_version": 1,
            "kind": "issue128_exact_right_generator_stage",
            "formula_id": FORMULA_ID,
            "stage_index": stage_index,
            "stage_count": len(stages),
            "fragment_index": stage.fragment_index,
            "stage_coefficient": cubic_to_json(stage.coefficient),
            "order": order,
            "series": coordinate_encode_series(registry, series),
        }
        write_shard_gzip(output, payload)
        elapsed = time.perf_counter() - started
        complete = {
            **running,
            "status": "complete",
            "completed_at": _utc_now(),
            "wall_seconds": elapsed,
            "peak_rss_bytes": _max_rss_bytes(),
            "degree_term_counts": [len(degree) for degree in series],
            "output": output.name,
            "output_sha256": sha256_file(output),
        }
        write_manifest_atomic(manifest, complete)
        print(
            f"stage={stage_index} status=complete wall={elapsed:.3f}s "
            f"terms={complete['degree_term_counts']} sha256={complete['output_sha256']}",
            flush=True,
        )
        return complete
    except BaseException as error:
        failed = {
            **running,
            "status": "failed",
            "completed_at": _utc_now(),
            "wall_seconds": time.perf_counter() - started,
            "peak_rss_bytes": _max_rss_bytes(),
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
        }
        write_manifest_atomic(manifest, failed)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-index", type=int, required=True)
    parser.add_argument("--order", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    arguments = parser.parse_args()
    issue_root = Path(__file__).resolve().parents[1]
    repository_root = issue_root.parents[4]
    build_shard(
        stage_index=arguments.stage_index,
        order=arguments.order,
        output=arguments.output,
        manifest=arguments.manifest,
        repository_root=repository_root,
    )


if __name__ == "__main__":
    main()
