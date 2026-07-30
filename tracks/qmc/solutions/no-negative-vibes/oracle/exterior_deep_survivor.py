"""Depth-9..12 pressure scan of Stage-2 exterior-cone survivors."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from .exterior_candidates import candidate_card, candidate_id
from .exterior_thin_scan import mixed_words, screen_card


SCHEMA_VERSION = "exterior-deep-survivor-v1"
RUN_ID = "exterior-survivor-depth12-v1"
PARENT_SURVIVOR_STATUS = "survivor-pressure-zero-failure"
SURVIVOR_STATUS = "survivor-depth12-zero-failure"
DEEP_DEPTHS = (9, 10, 11, 12)
DEEP_WORDS = mixed_words(2, depths=DEEP_DEPTHS)
PARENT_TERMINAL_STATUSES = {
    "rejected-negative",
    "rejected-complex",
    "uncertain-high-precision",
    PARENT_SURVIVOR_STATUS,
}
TERMINAL_STATUSES = {
    "rejected-negative",
    "rejected-complex",
    "uncertain-high-precision",
    SURVIVOR_STATUS,
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _protocol_hash(plan: Mapping[str, object], run_id: str) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "parent_run_id": plan["run_id"],
        "parent_protocol_hash": plan["protocol_hash"],
        "depths": list(DEEP_DEPTHS),
        "word_order": "right-append-lexicographic-mixed",
        "oracle": "oracle.weights.classify_product",
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _entry_card(entry: Mapping[str, object]) -> Mapping[str, object]:
    card = candidate_card(template=str(entry["template"]), seed=entry["seed"])
    identity = candidate_id(card)
    if (
        identity != entry.get("candidate_id")
        or identity != entry.get("card_sha256")
        or card["dimension"] != entry.get("dimension")
    ):
        raise RuntimeError("Stage-2 candidate entry does not reconstruct exactly")
    return card


def _load_stage2_survivors(
    stage2_run_dir: str | Path,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    root = Path(stage2_run_dir)
    plan = json.loads((root / "plan-summary.json").read_text(encoding="utf-8"))
    entries = plan.get("candidates")
    if (
        not isinstance(plan.get("run_id"), str)
        or not isinstance(plan.get("protocol_hash"), str)
        or not isinstance(plan.get("source_commit"), str)
        or not isinstance(entries, list)
        or not all(isinstance(entry, dict) for entry in entries)
    ):
        raise RuntimeError("invalid Stage-2 plan summary")
    if "planned" in plan and plan["planned"] != len(entries):
        raise RuntimeError("incomplete Stage-2 plan summary")

    selected: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in entries:
        identity = entry.get("candidate_id")
        if not isinstance(identity, str) or identity in seen:
            raise RuntimeError("invalid or duplicate Stage-2 candidate")
        seen.add(identity)
        path = root / "candidates" / identity / "manifest.json"
        if not path.is_file():
            raise RuntimeError(f"Stage-2 manifest missing: {identity}")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if (
            manifest.get("run_id") != plan["run_id"]
            or manifest.get("protocol_hash") != plan["protocol_hash"]
            or manifest.get("candidate_id") != identity
            or manifest.get("card_sha256") != identity
            or manifest.get("status") not in PARENT_TERMINAL_STATUSES
        ):
            raise RuntimeError(f"invalid Stage-2 terminal manifest: {identity}")
        if manifest["status"] == PARENT_SURVIVOR_STATUS:
            selected.append(entry)
    return plan, sorted(selected, key=lambda entry: str(entry["candidate_id"]))


def partition_entries(
    entries: Sequence[Mapping[str, object]],
    *,
    worker_index: int,
    workers: int,
) -> list[Mapping[str, object]]:
    """Return a deterministic balanced partition of candidate entries."""

    if (
        not isinstance(workers, int)
        or isinstance(workers, bool)
        or workers <= 0
        or not isinstance(worker_index, int)
        or isinstance(worker_index, bool)
        or worker_index < 0
        or worker_index >= workers
    ):
        raise ValueError("require 0 <= worker_index < workers")
    ordered = sorted(entries, key=lambda entry: str(entry["candidate_id"]))
    return [
        entry
        for position, entry in enumerate(ordered)
        if position % workers == worker_index
    ]


def _expected_depths() -> list[int]:
    return sorted({len(word) for word in DEEP_WORDS})


def _terminal_manifest_is_valid(
    manifest: Mapping[str, object],
    *,
    entry: Mapping[str, object],
    plan: Mapping[str, object],
    run_id: str,
    protocol_hash: str,
) -> bool:
    status = manifest.get("status")
    planned = len(DEEP_WORDS)
    tested = manifest.get("tested_words")
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("run_id") != run_id
        or manifest.get("protocol_hash") != protocol_hash
        or manifest.get("parent_run_id") != plan["run_id"]
        or manifest.get("parent_protocol_hash") != plan["protocol_hash"]
        or manifest.get("candidate_id") != entry["candidate_id"]
        or manifest.get("card_sha256") != entry["candidate_id"]
        or manifest.get("depths") != _expected_depths()
        or manifest.get("planned_words") != planned
        or status not in TERMINAL_STATUSES
        or not isinstance(tested, int)
        or isinstance(tested, bool)
        or tested < 1
        or tested > planned
    ):
        return False
    failure = manifest.get("first_failure")
    if status == SURVIVOR_STATUS:
        return tested == planned and failure is None
    if not isinstance(failure, Mapping):
        return False
    expected_classification = {
        "rejected-negative": "negative",
        "rejected-complex": "complex",
        "uncertain-high-precision": "uncertain",
    }[str(status)]
    return failure.get("classification") == expected_classification


def run_worker(
    *,
    stage2_run_dir: str | Path,
    output_dir: str | Path,
    worker_index: int,
    workers: int,
    run_id: str = RUN_ID,
    progress: bool = False,
) -> dict[str, int]:
    """Scan this worker's deterministic share and atomically resume terminals."""

    plan, selected = _load_stage2_survivors(stage2_run_dir)
    assigned = partition_entries(
        selected, worker_index=worker_index, workers=workers
    )
    root = Path(output_dir)
    protocol_hash = _protocol_hash(plan, run_id)
    completed = 0
    reused = 0
    for entry in assigned:
        identity = str(entry["candidate_id"])
        manifest_path = root / "candidates" / identity / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not _terminal_manifest_is_valid(
                manifest,
                entry=entry,
                plan=plan,
                run_id=run_id,
                protocol_hash=protocol_hash,
            ):
                raise RuntimeError(f"stale Stage-3 manifest: {identity}")
            reused += 1
            if progress:
                print(f"worker {worker_index}/{workers}: reuse {identity}", flush=True)
            continue

        card = _entry_card(entry)
        manifest = screen_card(
            card,
            source_commit=str(plan["source_commit"]),
            run_id=run_id,
            words=DEEP_WORDS,
            protocol_hash=protocol_hash,
            machine_role="deep-survivor-worker",
            shard=worker_index,
            survivor_status=PARENT_SURVIVOR_STATUS,
        )
        if manifest["status"] == PARENT_SURVIVOR_STATUS:
            manifest["status"] = SURVIVOR_STATUS
        manifest.update(
            {
                "schema_version": SCHEMA_VERSION,
                "parent_run_id": plan["run_id"],
                "parent_protocol_hash": plan["protocol_hash"],
                "parent_status": PARENT_SURVIVOR_STATUS,
                "worker_index": worker_index,
                "workers": workers,
            }
        )
        _write_json_atomic(manifest_path, manifest)
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
    output_dir: str | Path,
    run_id: str = RUN_ID,
    markdown: str | Path | None = None,
) -> dict[str, object]:
    """Collect valid Stage-3 terminals into compact JSON and Markdown summaries."""

    plan, selected = _load_stage2_survivors(stage2_run_dir)
    root = Path(output_dir)
    protocol_hash = _protocol_hash(plan, run_id)
    counts: Counter[str] = Counter()
    tested_words = 0
    missing = 0
    stale = 0
    first_failures: list[dict[str, object]] = []
    survivors: list[str] = []
    for entry in selected:
        identity = str(entry["candidate_id"])
        path = root / "candidates" / identity / "manifest.json"
        if not path.is_file():
            missing += 1
            continue
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if not _terminal_manifest_is_valid(
            manifest,
            entry=entry,
            plan=plan,
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
            first_failures.append(
                {
                    "candidate_id": identity,
                    "template": entry["template"],
                    "status": status,
                    "depth": failure["depth"],
                    "word_indices": failure["word_indices"],
                    "sigma_min_I_plus_D": failure["sigma_min_I_plus_D"],
                }
            )
    terminal = sum(counts.values())
    summary: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "protocol_hash": protocol_hash,
        "parent_run_id": plan["run_id"],
        "parent_protocol_hash": plan["protocol_hash"],
        "depths": list(DEEP_DEPTHS),
        "selected": len(selected),
        "terminal": terminal,
        "missing": missing,
        "stale": stale,
        "scientific_counts": dict(sorted(counts.items())),
        "tested_words": tested_words,
        "survivors": survivors,
        "first_failures": first_failures,
    }
    _write_json_atomic(root / "summary.json", summary)
    markdown_path = Path(markdown) if markdown is not None else root / "summary.md"
    _write_text_atomic(markdown_path, _summary_markdown(summary))
    return summary


def _summary_markdown(summary: Mapping[str, object]) -> str:
    counts = summary["scientific_counts"]
    assert isinstance(counts, Mapping)
    lines = [
        f"# Deep exterior survivor scan — {summary['run_id']}",
        "",
        (
            f"Depths 9–12; selected {summary['selected']}; terminal "
            f"{summary['terminal']}; missing {summary['missing']}; "
            f"stale {summary['stale']}."
        ),
        "",
        "| status | candidates |",
        "|---|---:|",
    ]
    lines.extend(f"| {status} | {counts[status]} |" for status in sorted(counts))
    lines.extend(
        [
            "",
            f"Tested words: {summary['tested_words']}.",
            f"Depth-12 survivors: {len(summary['survivors'])}.",
            "",
        ]
    )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--stage2-run-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--worker-index", type=int, required=True)
    run.add_argument("--workers", type=int, required=True)
    run.add_argument("--run-id", default=RUN_ID)
    collect = commands.add_parser("collect")
    collect.add_argument("--stage2-run-dir", required=True)
    collect.add_argument("--output-dir", required=True)
    collect.add_argument("--run-id", default=RUN_ID)
    collect.add_argument("--markdown")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "run":
        result = run_worker(
            stage2_run_dir=args.stage2_run_dir,
            output_dir=args.output_dir,
            worker_index=args.worker_index,
            workers=args.workers,
            run_id=args.run_id,
            progress=True,
        )
    else:
        result = collect_run(
            stage2_run_dir=args.stage2_run_dir,
            output_dir=args.output_dir,
            run_id=args.run_id,
            markdown=args.markdown,
        )
    print(_canonical_json(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEEP_DEPTHS",
    "DEEP_WORDS",
    "RUN_ID",
    "SURVIVOR_STATUS",
    "TERMINAL_STATUSES",
    "collect_run",
    "main",
    "partition_entries",
    "run_worker",
]
