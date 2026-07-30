#!/usr/bin/env python3
"""Rehash downloaded direct-smoke artifacts and report seed coverage only."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import sys
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(
        raw.decode("utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant: {value}")
        ),
        object_pairs_hook=pairs,
    )


def real_file(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"{label} must be a regular non-symlink file")
    return path


def envelope(path: Path, schema: str) -> tuple[dict[str, Any], bytes]:
    real_file(path, schema)
    raw = path.read_bytes()
    document = strict_json(raw)
    if raw != canonical(document) + b"\n":
        raise ValueError(f"{schema} is not canonical JSON")
    if (
        not isinstance(document, dict)
        or set(document) != {"payload", "payload_sha256", "schema"}
        or document.get("schema") != schema
        or not isinstance(document.get("payload"), dict)
    ):
        raise ValueError(f"invalid {schema}")
    if sha_bytes(canonical(document["payload"])) != document["payload_sha256"]:
        raise ValueError(f"{schema} payload SHA256 mismatch")
    return document, raw


def verify(manifest_path: Path, outputs: Path) -> dict[str, Any]:
    manifest_document, manifest_raw = envelope(
        manifest_path, "challenge15.direct-run-manifest.v1"
    )
    manifest = manifest_document["payload"]
    if (
        manifest.get("particles") != 6
        or manifest.get("rank") != 1
        or manifest.get("seeds") != [0, 1, 2, 3, 4]
    ):
        raise ValueError("manifest is not the direct N=6 rank-1 smoke")
    manifest_sha = sha_bytes(manifest_raw)
    expected_seeds = manifest["seeds"]
    covered: list[int] = []

    for entry in manifest["tasks"]:
        relative = Path(entry["relative_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("task path traversal rejected")
        task_document, task_raw = envelope(
            manifest_path.parent / relative,
            "challenge15.direct-seed-task.v1",
        )
        if (
            sha_bytes(task_raw) != entry["sha256"]
            or task_document["payload_sha256"] != entry["payload_sha256"]
        ):
            raise ValueError("task document SHA256 mismatch")
        task = task_document["payload"]
        seed = task["seed"]
        done_path = outputs / f"seed-{seed}" / "DONE.json"
        if not done_path.exists() and not done_path.is_symlink():
            continue
        done_document, done_raw = envelope(
            done_path, "challenge15.direct-done.v1"
        )
        # Computing this digest is intentional even though there is no
        # pre-download copy to compare against: every DONE document is rehashed.
        done_sha = sha_bytes(done_raw)
        if len(done_sha) != 64:
            raise ValueError("DONE document SHA256 is invalid")
        done = done_document["payload"]
        expected = {
            "config_canonical_sha256": task["config_canonical_sha256"],
            "interpreter_sha256": task["interpreter_sha256"],
            "manifest_sha256": manifest_sha,
            "runtime_identity_sha256": task["runtime_identity_sha256"],
            "seed": seed,
            "source_commit": task["source_commit"],
            "task_sha256": sha_bytes(task_raw),
        }
        if {key: done.get(key) for key in expected} != expected:
            raise ValueError(f"DONE provenance SHA256 mismatch for seed {seed}")
        inventory = done.get("outputs")
        if not isinstance(inventory, list) or not inventory:
            raise ValueError(f"DONE output inventory is invalid for seed {seed}")
        names = set()
        for item in inventory:
            if not isinstance(item, dict) or set(item) != {
                "relative_path",
                "sha256",
                "size_bytes",
            }:
                raise ValueError(f"DONE output inventory is invalid for seed {seed}")
            name = item["relative_path"]
            if name not in {"checkpoint.json", "result.json"}:
                raise ValueError(f"DONE output path is invalid for seed {seed}")
            names.add(name)
            path = real_file(done_path.parent / name, "downloaded output")
            if (
                path.stat().st_size != item["size_bytes"]
                or sha_file(path) != item["sha256"]
            ):
                raise ValueError(f"output SHA256 mismatch for seed {seed}: {name}")
        actual = {path.name for path in done_path.parent.iterdir()}
        if actual != names | {"DONE.json"}:
            raise ValueError(f"ambiguous downloaded output for seed {seed}")
        covered.append(seed)

    return {
        "covered_seeds": covered,
        "expected_seeds": expected_seeds,
        "missing_seeds": sorted(set(expected_seeds) - set(covered)),
        "scientific_acceptance_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--outputs", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        report = verify(arguments.manifest, arguments.outputs)
    except (KeyError, OSError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
