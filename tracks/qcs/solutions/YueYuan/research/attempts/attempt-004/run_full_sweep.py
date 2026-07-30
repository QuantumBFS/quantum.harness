#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import config
import experiments


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--task-index", type=int)
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--exclude-adaptive", action="store_true")
    parser.add_argument("--adaptive-focus", action="store_true")
    parser.add_argument("--combine-tasks", action="store_true")
    args = parser.parse_args()
    if args.combine_tasks and args.task_index is not None:
        parser.error("--combine-tasks cannot be used with --task-index")
    if args.combine_tasks and args.fast:
        parser.error("--combine-tasks cannot be used with --fast")
    if args.adaptive_focus and args.fast:
        parser.error("--adaptive-focus cannot be used with --fast")
    if args.adaptive_focus and args.exclude_adaptive:
        parser.error("--adaptive-focus cannot be used with --exclude-adaptive")
    sweep = (
        config.focused_adaptive_sweep()
        if args.adaptive_focus
        else config.default_full_sweep()
    )
    if args.combine_tasks:
        payload = experiments.combine_task_outputs(
            args.out,
            expected_task_files=experiments.work_item_count(sweep),
            expected_records=experiments.expected_record_count(
                sweep,
                include_adaptive=not args.exclude_adaptive,
            ),
        )
        print(json.dumps(payload, sort_keys=True))
        return 0
    records = experiments.run_sweep(
        sweep,
        args.out,
        selected_index=args.task_index,
        fast=args.fast,
        include_adaptive=not args.exclude_adaptive,
    )
    print(f"wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
