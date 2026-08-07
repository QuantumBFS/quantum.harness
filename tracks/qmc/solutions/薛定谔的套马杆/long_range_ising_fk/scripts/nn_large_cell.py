#!/usr/bin/env python
"""Run one strict nearest-neighbor FK cell from the parameter-scan run spec.

The SCNet login image provides Python 2.7, so this small orchestration wrapper
is deliberately compatible with both Python 2.7 and Python 3.  All numerical
work is performed by Julia.
"""

from __future__ import print_function

import csv
import io
import json
import os
import subprocess
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


def main():
    repo = os.getcwd()
    spec_path = os.environ["HARNESS_RUN_SPEC"]
    if not os.path.isabs(spec_path):
        spec_path = os.path.join(repo, spec_path)
    with io.open(spec_path, encoding="utf-8") as stream:
        spec = json.load(stream)

    task_id = int(os.environ.get("SLURM_ARRAY_TASK_ID", os.environ.get("HARNESS_CELL_INDEX", "1")))
    if not 1 <= task_id <= len(spec["cells"]):
        raise SystemExit("array task {0} outside 1..{1}".format(task_id, len(spec["cells"])))
    planned = spec["cells"][task_id - 1]
    params = planned["params"]
    shared = spec["settings"]
    L = int(params["L"])
    seed = int(params["seed"])
    therm = int(shared["thermalization_sweeps_by_size"][str(L)])
    meas = int(shared["measurement_sweeps_by_size"][str(L)])
    blocks = int(shared["blocks"])

    run_dir = spec["run_dir"]
    if not os.path.isabs(run_dir):
        run_dir = os.path.join(repo, run_dir)
    cell_dir = os.path.join(run_dir, "cells", planned["cell_id"])
    if not os.path.isdir(cell_dir):
        os.makedirs(cell_dir)

    env = os.environ.copy()
    env.update(
        {
            "NN_CELL_ID": str(planned["cell_id"]),
            "NN_L": str(L),
            "NN_SEED": str(seed),
            "NN_BETA": str(shared["beta"]),
            "NN_THERM": str(therm),
            "NN_MEAS": str(meas),
            "NN_BLOCKS": str(blocks),
            "RUN_ROOT": str(run_dir),
        }
    )
    julia = os.environ.get("JULIA_BIN", os.path.expanduser("~/.local/bin/julia"))
    entrypoint = os.path.join(repo, shared["entrypoint"])
    returncode = subprocess.call(
        [julia, "--startup-file=no", entrypoint],
        cwd=repo,
        env=env,
    )
    if returncode != 0:
        return returncode

    summary_path = os.path.join(cell_dir, "summary.csv")
    with io.open(summary_path, encoding="utf-8", newline="") if sys.version_info[0] >= 3 else open(summary_path, "rb") as stream:
        summary = dict((key, numeric(value)) for key, value in next(csv.DictReader(stream)).items())

    effective_settings = dict(shared)
    effective_settings.update(
        {
            "thermalization_sweeps": therm,
            "measurement_sweeps": meas,
        }
    )
    observable_keys = ("Qm", "se_Qm", "Rp", "se_Rp", "chi", "se_chi", "tau_m2", "runtime_s")
    manifest = {
        "status": "success",
        "cell_id": planned["cell_id"],
        "params": params,
        "settings": effective_settings,
        "provenance": spec.get("provenance", {}),
        "observables": dict((key, summary[key]) for key in observable_keys),
        "evidence": ["summary.csv", "blocks.csv", "metadata.txt"],
    }
    fd, temporary = tempfile.mkstemp(prefix="manifest-", suffix=".json", dir=cell_dir)
    try:
        # os.fdopen's text stream accepts json.dump output on both the Python
        # 2.7 login image and Python 3.  io.open(..., encoding="utf-8") does
        # not accept the byte chunks emitted by Python 2's json encoder.
        with os.fdopen(fd, "w") as stream:
            json.dump(manifest, stream, indent=2, ensure_ascii=True, separators=(",", ": "))
            stream.write("\n")
        final_path = os.path.join(cell_dir, "manifest.json")
        if os.path.exists(final_path):
            os.unlink(final_path)
        os.rename(temporary, final_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
