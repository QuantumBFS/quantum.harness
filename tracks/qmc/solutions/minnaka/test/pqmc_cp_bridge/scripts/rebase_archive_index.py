#!/usr/bin/env python3
"""Rewrite a fetched archive index to portable paths beside the index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

from path_archive import ArchiveReader
from prepare_alf_chain import atomic_json


def rebase_entries(document: Mapping[str, object]) -> dict[str, object]:
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("archive index has no entries")
    result = dict(document)
    rebased = []
    for entry_raw in entries:
        if not isinstance(entry_raw, Mapping):
            raise ValueError("archive index entry is not an object")
        entry = dict(entry_raw)
        ensemble = str(entry["ensemble"])
        chain = int(entry["chain"])
        if ensemble not in {"II", "TI"} or not 0 <= chain < 256:
            raise ValueError("invalid archive ensemble/chain")
        entry["path"] = f"{ensemble}/chain_{chain}.qhpath"
        rebased.append(entry)
    result["entries"] = rebased
    result["path_scope"] = "relative_to_index"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = rebase_entries(json.loads(args.source.read_text()))
    for entry in document["entries"]:
        path = args.archive_root / entry["path"]
        reader = ArchiveReader(path)
        scan = reader.scan()
        if (
            scan.truncated_tail
            or scan.complete_records != int(entry["records"])
        ):
            raise ValueError(f"local archive validation failed: {path}")
    if args.output.parent.resolve() != args.archive_root.resolve():
        raise ValueError("portable index must be written in archive root")
    atomic_json(args.output, document)
    print(
        f"rebased {len(document['entries'])} archive entries",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
