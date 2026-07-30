#!/usr/bin/env python3
import re
import sys
from pathlib import Path

REQUIRED = [
    "SKILL.md", "README.md", "references/issue28-scope.md",
    "references/evidence-policy.md", "references/easy-goal-gates.md",
    "references/hard-goal-gates.md", "references/mps-tt-route.md",
    "references/cleanup-policy.md", "references/finalization-workflow.md",
    "scripts/audit_evidence.py", "scripts/validate_final_status.py",
    "scripts/inventory_files.py", "scripts/check_references.py",
    "templates/final_status.schema.json", "templates/evidence.schema.json",
    "templates/cleanup_inventory.schema.json",
]

def main() -> None:
    root = Path(sys.argv[1]).resolve()
    missing = [item for item in REQUIRED if not (root / item).is_file()]
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    front = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    errors = []
    if missing:
        errors.append("missing: " + ", ".join(missing))
    if not front or "name: nnrh-vmcrg" not in front.group(1):
        errors.append("invalid frontmatter name")
    if not front or "Use when" not in front.group(1):
        errors.append("description must start with a usage trigger")
    if re.search(r"\b(TODO|TBD)\b", text):
        errors.append("placeholder found")
    if errors:
        print("; ".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print("track-local skill validation PASS")

if __name__ == "__main__":
    main()
