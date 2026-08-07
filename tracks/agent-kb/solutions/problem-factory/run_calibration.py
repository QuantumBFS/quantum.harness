#!/usr/bin/env python3
"""Calibration gate (issue #133): the rubric must accept mentor-curated quality
classes and reject candidates outside them. Two sets: dev (#124-#128 + controls,
used to build the rubric) and held-out test (#112 + controls, first seen after
the rubric was frozen). If the rubric cannot reconstruct the curated classes,
it is not trusted on new problems."""

import glob

from pf import rubric

SETS = {
    "dev": (sorted(glob.glob("calibration/issue-*.yaml")),
            sorted(glob.glob("calibration/neg-*.yaml"))),
    "test": (sorted(glob.glob("calibration/test/issue-*.yaml")),
             sorted(glob.glob("calibration/test/neg-*.yaml"))),
}


def main():
    rows, all_ok = [], True
    for name, (positives, negatives) in SETS.items():
        pos_ok = neg_ok = 0
        for path in positives + negatives:
            c = rubric.load(path)
            g = rubric.grade(c)
            expect = path in positives
            correct = g["accepted"] == expect
            pos_ok += expect and correct
            neg_ok += (not expect) and correct
            all_ok &= correct
            best = g["class"] or max(g["classes"], key=lambda k: sum(g["classes"][k].values()))
            failed = [k for k, v in g["classes"][best].items() if not v]
            rows.append((name, c["id"], expect, g["accepted"], g["class"] or "-",
                         correct, ", ".join(failed) or "-"))
            mark = "ok " if correct else "MISS"
            print(f"[{mark}] {name:<4} {c['id']:<28} expect={'accept' if expect else 'reject'} "
                  f"got={'accept' if g['accepted'] else 'reject'} class={rows[-1][4]:<6} "
                  f"failed: {rows[-1][6]}", flush=True)
        print(f"  {name}: {pos_ok}/{len(positives)} positives, "
              f"{neg_ok}/{len(negatives)} negatives", flush=True)

    summary = "calibration: " + "; ".join(
        f"{name} {sum(1 for r in rows if r[0] == name and r[1].startswith('issue') and r[5])}"
        f"/{len(SETS[name][0])} pos" for name in SETS) + \
        f" -> {'CALIBRATED' if all_ok else 'NOT CALIBRATED'}"
    print("\n" + summary)

    with open("results/calibration.md", "w") as f:
        f.write("# Calibration Gate Report\n\n" + summary + "\n\n")
        f.write("| set | candidate | expected | got | class | failed checks |\n|---|---|---|---|---|---|\n")
        for name, cid, expect, accepted, cls, correct, failed in rows:
            f.write(f"| {name} | {cid} | {'accept' if expect else 'reject'} | "
                    f"{'accept' if accepted else 'reject'}{' (MISS)' if not correct else ''} "
                    f"| {cls} | {failed} |\n")


if __name__ == "__main__":
    main()
