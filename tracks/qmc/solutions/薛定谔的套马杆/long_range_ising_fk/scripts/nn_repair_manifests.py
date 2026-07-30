#!/usr/bin/env python
"""Rebuild NN manifests from completed numerical evidence without recomputing."""

from __future__ import print_function

import csv
import io
import json
import os
import sys
import tempfile


def numeric(value):
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def write_json_atomic(path, value):
    directory = os.path.dirname(path)
    fd, temporary = tempfile.mkstemp(prefix="manifest-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=True, separators=(",", ": "))
            stream.write("\n")
        if os.path.exists(path):
            os.unlink(path)
        os.rename(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    spec_path = sys.argv[1]
    with io.open(spec_path, encoding="utf-8") as stream:
        spec = json.load(stream)
    run_dir = spec["run_dir"]
    if not os.path.isabs(run_dir):
        run_dir = os.path.abspath(run_dir)

    repaired = 0
    incomplete = []
    observable_keys = (
        "Qm",
        "se_Qm",
        "Rp",
        "se_Rp",
        "chi",
        "se_chi",
        "tau_m2",
        "runtime_s",
    )
    for planned in spec["cells"]:
        cell_dir = os.path.join(run_dir, "cells", planned["cell_id"])
        evidence = [os.path.join(cell_dir, name) for name in ("summary.csv", "blocks.csv", "metadata.txt")]
        if not all(os.path.isfile(path) and os.path.getsize(path) > 0 for path in evidence):
            incomplete.append(planned["cell_id"])
            continue
        summary_path = evidence[0]
        if sys.version_info[0] >= 3:
            stream = io.open(summary_path, encoding="utf-8", newline="")
        else:
            stream = open(summary_path, "rb")
        with stream:
            summary = dict((key, numeric(value)) for key, value in next(csv.DictReader(stream)).items())
        L = int(planned["params"]["L"])
        settings = dict(spec["settings"])
        settings.update(
            {
                "thermalization_sweeps": int(settings["thermalization_sweeps_by_size"][str(L)]),
                "measurement_sweeps": int(settings["measurement_sweeps_by_size"][str(L)]),
            }
        )
        manifest = {
            "status": "success",
            "cell_id": planned["cell_id"],
            "params": planned["params"],
            "settings": settings,
            "provenance": spec.get("provenance", {}),
            "observables": dict((key, summary[key]) for key in observable_keys),
            "evidence": ["summary.csv", "blocks.csv", "metadata.txt"],
        }
        write_json_atomic(os.path.join(cell_dir, "manifest.json"), manifest)
        repaired += 1

    print("repaired={0} incomplete={1}".format(repaired, len(incomplete)))
    if incomplete:
        print("incomplete_cells={0}".format(",".join(incomplete)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
