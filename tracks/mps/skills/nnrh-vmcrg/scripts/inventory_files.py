#!/usr/bin/env python3
import argparse
import hashlib
from pathlib import Path

CATEGORIES = {"SOURCE", "TEST", "CONFIG", "PRIMARY_EVIDENCE", "SUPPORTING_EVIDENCE", "FINAL_REPORT", "DOCUMENTATION", "CHECKPOINT_METADATA", "LARGE_RAW_DATA", "CACHE", "TEMPORARY", "DUPLICATE", "EMPTY", "UNKNOWN"}

def category(path: Path, size: int) -> str:
    value = path.as_posix()
    if size == 0:
        return "EMPTY"
    if "__pycache__" in value or path.suffix in {".pyc", ".pyo"} or ".pytest_cache" in value:
        return "CACHE"
    if any(part in {"tmp", "temp", "scratch"} for part in path.parts):
        return "TEMPORARY"
    if "checkpoint" in value and path.suffix in {".json", ".sha256"}:
        return "CHECKPOINT_METADATA"
    if path.suffix in {".py", ".jl", ".sh", ".slurm"}:
        return "TEST" if "test" in path.name or "tests" in path.parts else "SOURCE"
    if path.suffix in {".toml", ".yaml", ".yml"} or "config" in path.name:
        return "CONFIG"
    if path.name in {"manifest.json", "run.json", "final_status.json", "selection.json"}:
        return "PRIMARY_EVIDENCE"
    if path.name in {"report.html", "report.json"}:
        return "FINAL_REPORT"
    if path.suffix == ".md":
        return "DOCUMENTATION"
    if size > 5 * 1024 * 1024:
        return "LARGE_RAW_DATA"
    if "results" in path.parts or "output" in path.parts:
        return "SUPPORTING_EVIDENCE"
    return "UNKNOWN"

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = []
    for path in sorted(item for item in args.root.rglob("*") if item.is_file()):
        relative = path.relative_to(args.root)
        size = path.stat().st_size
        kind = category(relative, size)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        action = "DELETE" if kind in {"CACHE", "TEMPORARY", "EMPTY"} else ("REVIEW" if kind in {"UNKNOWN", "LARGE_RAW_DATA"} else "KEEP")
        reason = "generated or empty" if action == "DELETE" else "scientific, engineering, or audit value"
        rows.append((relative.as_posix(), size, digest, kind, reason, "inventory_scan", "true" if action == "DELETE" else "false", action, action))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    header = "path\tsize_bytes\tsha256\tcategory\treason\treferenced_by\treproducible\trecommended_action\tfinal_action\n"
    args.output.write_text(header + "".join("\t".join(map(str, row)) + "\n" for row in rows), encoding="utf-8")
    print(f"inventory PASS ({len(rows)} files)")

if __name__ == "__main__":
    main()
