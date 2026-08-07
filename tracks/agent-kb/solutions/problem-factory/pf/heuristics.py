"""Turn verdict records into heuristics-library entries (interface C).

Every verdict — success or failure — deposits one YAML into heuristics/.
The library and its growth curve are a reported output of issue #133.
Lessons are auto-drafted from the verdict reason; humans refine the good ones.
"""

from pathlib import Path

import yaml


def dump(records, outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for r in records:
        entry = {
            "problem_id": r["problem_id"],
            "verdict": r["verdict"],
            "root_cause": {"category": _category(r), "evidence": r["reason"]},
            "lesson": r["reason"],
        }
        with open(out / f"{r['problem_id']}.yaml", "w", encoding="utf-8") as fh:
            yaml.safe_dump(entry, fh, sort_keys=False, allow_unicode=True)
    return len(records)


def _category(r):
    if r["verdict"] != "dead":
        return None
    return r["reason"].split(":")[0]
