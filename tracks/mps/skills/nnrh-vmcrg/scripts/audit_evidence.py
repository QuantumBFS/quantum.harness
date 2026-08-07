#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

def load(root: Path, relative: str):
    path = root / relative
    return json.loads(path.read_text(encoding="utf-8")), path

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.track_root.resolve()
    ltrg, ltrg_path = load(root, "results/20260727-131302-li2011-xy-ltrg/run.json")
    table, table_path = load(root, "DMRG/output/reproduction/paper_table1_map_repeats/pooled_assessment.json")
    hard, hard_path = load(root, "DMRG/results/hard_goal/submission-20260730/manifest.json")
    old_rounds = sorted((root / "DMRG/results/issue28-n3-local-20260728-02").glob("round-*/manifest.json"))
    corrected = sorted((root / "DMRG/results/issue28-n3-local-gatefix-3round-20260730-02").glob("round-*/manifest.json"))
    payload = {
        "schema_version": 1,
        "reproduction_status": "REPRODUCTION_COMPLETE",
        "easy_goal_status": "PROTOCOL_INCOMPLETE",
        "mps_tt_support_status": "SUPPORTING_EVIDENCE",
        "hard_goal_status": "STAGE_6_NO_GO",
        "observations": {
            "ltrg_result_blocks": len(ltrg.get("figures", [])),
            "lambda_even": table["point_estimate_from_all_maps_and_runs"]["lambda_even"],
            "lambda_odd": table["point_estimate_from_all_maps_and_runs"]["lambda_odd"],
            "legacy_n3_published_rounds": len(old_rounds),
            "corrected_n3_published_rounds": len(corrected),
            "hard_terminal_classification": hard["classification"],
            "hard_stage6_decision": hard["stage6_decision"],
        },
        "sources": [
            {"path": str(path.relative_to(root)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in (ltrg_path, table_path, hard_path)
        ],
    }
    text = json.dumps(payload, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")

if __name__ == "__main__":
    main()
