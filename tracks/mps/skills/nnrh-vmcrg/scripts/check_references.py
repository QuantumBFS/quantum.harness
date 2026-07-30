#!/usr/bin/env python3
import re
import sys
from pathlib import Path

def main() -> None:
    root = Path(sys.argv[1]).resolve()
    document = Path(sys.argv[2]).resolve()
    text = document.read_text(encoding="utf-8")
    candidates = set(re.findall(r"`(tracks/mps/[^`]+)`", text))
    candidates.update(re.findall(r"\[[^]]+\]\((?!https?://)([^)#]+)", text))
    missing = []
    for value in candidates:
        path = root.parents[1] / value if value.startswith("tracks/mps/") else document.parent / value
        if not path.exists():
            missing.append(value)
    if missing:
        print("missing references: " + ", ".join(sorted(missing)), file=sys.stderr)
        raise SystemExit(1)
    print(f"reference check PASS ({len(candidates)} paths)")

if __name__ == "__main__":
    main()
