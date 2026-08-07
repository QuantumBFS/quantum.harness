"""Depth-13..16 pressure scan of completed Stage-3 survivors."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from . import exterior_deep_survivor as stage3
from .exterior_thin_scan import mixed_words, screen_card


SCHEMA_VERSION = "exterior-depth16-survivor-v1"
RUN_ID = "exterior-survivor-depth16-v1"
PARENT_STATUS = stage3.SURVIVOR_STATUS
SURVIVOR_STATUS = "survivor-depth16-zero-failure"
DEPTHS = (13, 14, 15, 16)
WORDS = mixed_words(2, depths=DEPTHS)
TERMINAL_STATUSES = {
    "rejected-negative",
    "rejected-complex",
    "uncertain-high-precision",
    SURVIVOR_STATUS,
}


def _protocol_hash(
    plan: Mapping[str, object],
    stage3_protocol_hash: str,
    run_id: str,
) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "stage2_protocol_hash": plan["protocol_hash"],
        "parent_run_id": stage3.RUN_ID,
        "parent_protocol_hash": stage3_protocol_hash,
        "depths": list(DEPTHS),
        "word_order": "right-append-lexicographic-mixed",
        "oracle": "oracle.weights.classify_product",
    }
    return hashlib.sha256(stage3._canonical_json(payload).encode("utf-8")).hexdigest()


def load_stage3_survivors(
    stage2_run_dir: str | Path,
    stage3_run_dir: str | Path,
) -> tuple[dict[str, object], list[dict[str, object]], str]:
    """Require a completed Stage-3 run and select only its depth-12 survivors."""

    plan, entries = stage3._load_stage2_survivors(stage2_run_dir)
    stage3_protocol = stage3._protocol_hash(plan, stage3.RUN_ID)
    root = Path(stage3_run_dir)
    selected: list[dict[str, object]] = []
    for entry in entries:
        identity = str(entry["candidate_id"])
        path = root / "candidates" / identity / "manifest.json"
        if not path.is_file():
            raise RuntimeError(f"Stage-3 manifest missing: {identity}")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if not stage3._terminal_manifest_is_valid(
            manifest,
            entry=entry,
            plan=plan,
            run_id=stage3.RUN_ID,
            protocol_hash=stage3_protocol,
        ):
            raise RuntimeError(f"invalid Stage-3 terminal manifest: {identity}")
        if manifest["status"] == PARENT_STATUS:
            selected.append(entry)
    return plan, selected, stage3_protocol


def _manifest_is_valid(
    manifest: Mapping[str, object],
    *,
    entry: Mapping[str, object],
    plan: Mapping[str, object],
    stage3_protocol: str,
    run_id: str,
    protocol_hash: str,
) -> bool:
    tested = manifest.get("tested_words")
    status = manifest.get("status")
    planned = len(WORDS)
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("run_id") != run_id
        or manifest.get("protocol_hash") != protocol_hash
        or manifest.get("parent_run_id") != stage3.RUN_ID
        or manifest.get("parent_protocol_hash") != stage3_protocol
        or manifest.get("stage2_protocol_hash") != plan["protocol_hash"]
        or manifest.get("candidate_id") != entry["candidate_id"]
        or manifest.get("card_sha256") != entry["candidate_id"]
        or manifest.get("depths") != sorted({len(word) for word in WORDS})
        or manifest.get("planned_words") != planned
        or status not in TERMINAL_STATUSES
        or not isinstance(tested, int)
        or isinstance(tested, bool)
        or not 1 <= tested <= planned
    ):
        return False
    failure = manifest.get("first_failure")
    if status == SURVIVOR_STATUS:
        return tested == planned and failure is None
    if not isinstance(failure, Mapping):
        return False
    expected = {
        "rejected-negative": "negative",
        "rejected-complex": "complex",
        "uncertain-high-precision": "uncertain",
    }[str(status)]
    return failure.get("classification") == expected


def run_worker(
    *,
    stage2_run_dir: str | Path,
    stage3_run_dir: str | Path,
    output_dir: str | Path,
    worker_index: int,
    workers: int = 76,
    run_id: str = RUN_ID,
    progress: bool = False,
) -> dict[str, int]:
    plan, selected, stage3_protocol = load_stage3_survivors(
        stage2_run_dir, stage3_run_dir
    )
    assigned = stage3.partition_entries(
        selected, worker_index=worker_index, workers=workers
    )
    protocol_hash = _protocol_hash(plan, stage3_protocol, run_id)
    root = Path(output_dir)
    completed = 0
    reused = 0
    for entry in assigned:
        identity = str(entry["candidate_id"])
        path = root / "candidates" / identity / "manifest.json"
        if path.is_file():
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if not _manifest_is_valid(
                manifest,
                entry=entry,
                plan=plan,
                stage3_protocol=stage3_protocol,
                run_id=run_id,
                protocol_hash=protocol_hash,
            ):
                raise RuntimeError(f"stale Stage-4 manifest: {identity}")
            reused += 1
            if progress:
                print(f"worker {worker_index}/{workers}: reuse {identity}", flush=True)
            continue

        card = stage3._entry_card(entry)
        manifest = screen_card(
            card,
            source_commit=str(plan["source_commit"]),
            run_id=run_id,
            words=WORDS,
            protocol_hash=protocol_hash,
            machine_role="depth16-survivor-worker",
            shard=worker_index,
            survivor_status=stage3.PARENT_SURVIVOR_STATUS,
        )
        if manifest["status"] == stage3.PARENT_SURVIVOR_STATUS:
            manifest["status"] = SURVIVOR_STATUS
        manifest.update(
            {
                "schema_version": SCHEMA_VERSION,
                "parent_run_id": stage3.RUN_ID,
                "parent_protocol_hash": stage3_protocol,
                "stage2_protocol_hash": plan["protocol_hash"],
                "parent_status": PARENT_STATUS,
                "worker_index": worker_index,
                "workers": workers,
            }
        )
        stage3._write_json_atomic(path, manifest)
        completed += 1
        if progress:
            print(
                f"worker {worker_index}/{workers}: {identity} {manifest['status']}",
                flush=True,
            )
    return {
        "selected": len(selected),
        "assigned": len(assigned),
        "completed": completed,
        "reused": reused,
    }


def collect_run(
    *,
    stage2_run_dir: str | Path,
    stage3_run_dir: str | Path,
    output_dir: str | Path,
    run_id: str = RUN_ID,
    markdown: str | Path | None = None,
) -> dict[str, object]:
    plan, selected, stage3_protocol = load_stage3_survivors(
        stage2_run_dir, stage3_run_dir
    )
    protocol_hash = _protocol_hash(plan, stage3_protocol, run_id)
    root = Path(output_dir)
    counts: Counter[str] = Counter()
    missing = 0
    stale = 0
    tested_words = 0
    failures: list[dict[str, object]] = []
    survivors: list[str] = []
    for entry in selected:
        identity = str(entry["candidate_id"])
        path = root / "candidates" / identity / "manifest.json"
        if not path.is_file():
            missing += 1
            continue
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if not _manifest_is_valid(
            manifest,
            entry=entry,
            plan=plan,
            stage3_protocol=stage3_protocol,
            run_id=run_id,
            protocol_hash=protocol_hash,
        ):
            stale += 1
            continue
        status = str(manifest["status"])
        counts[status] += 1
        tested_words += int(manifest["tested_words"])
        if status == SURVIVOR_STATUS:
            survivors.append(identity)
        else:
            failure = manifest["first_failure"]
            failures.append(
                {
                    "candidate_id": identity,
                    "template": entry["template"],
                    "status": status,
                    "depth": failure["depth"],
                    "word_indices": failure["word_indices"],
                }
            )
    summary: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "protocol_hash": protocol_hash,
        "parent_run_id": stage3.RUN_ID,
        "parent_protocol_hash": stage3_protocol,
        "depths": list(DEPTHS),
        "selected": len(selected),
        "terminal": sum(counts.values()),
        "missing": missing,
        "stale": stale,
        "scientific_counts": dict(sorted(counts.items())),
        "tested_words": tested_words,
        "survivors": survivors,
        "first_failures": failures,
    }
    stage3._write_json_atomic(root / "summary.json", summary)
    report = Path(markdown) if markdown is not None else root / "summary.md"
    stage3._write_text_atomic(report, _markdown(summary))
    return summary


def _markdown(summary: Mapping[str, object]) -> str:
    counts = summary["scientific_counts"]
    assert isinstance(counts, Mapping)
    lines = [
        f"# Depth-16 exterior survivor scan — {summary['run_id']}",
        "",
        (
            f"Selected {summary['selected']}; terminal {summary['terminal']}; "
            f"missing {summary['missing']}; stale {summary['stale']}."
        ),
        "",
        "| status | candidates |",
        "|---|---:|",
        *(f"| {status} | {counts[status]} |" for status in sorted(counts)),
        "",
        f"Tested words: {summary['tested_words']}.",
        f"Depth-16 survivors: {len(summary['survivors'])}.",
        "",
    ]
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--stage2-run-dir", required=True)
    run.add_argument("--stage3-run-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--worker-index", type=int, required=True)
    run.add_argument("--workers", type=int, default=76)
    run.add_argument("--run-id", default=RUN_ID)
    collect = commands.add_parser("collect")
    collect.add_argument("--stage2-run-dir", required=True)
    collect.add_argument("--stage3-run-dir", required=True)
    collect.add_argument("--output-dir", required=True)
    collect.add_argument("--run-id", default=RUN_ID)
    collect.add_argument("--markdown")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "run":
        result = run_worker(
            stage2_run_dir=args.stage2_run_dir,
            stage3_run_dir=args.stage3_run_dir,
            output_dir=args.output_dir,
            worker_index=args.worker_index,
            workers=args.workers,
            run_id=args.run_id,
            progress=True,
        )
    else:
        result = collect_run(
            stage2_run_dir=args.stage2_run_dir,
            stage3_run_dir=args.stage3_run_dir,
            output_dir=args.output_dir,
            run_id=args.run_id,
            markdown=args.markdown,
        )
    print(stage3._canonical_json(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
