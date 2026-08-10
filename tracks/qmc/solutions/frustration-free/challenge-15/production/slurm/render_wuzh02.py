"""Render WUZH02 wrappers only after an active audited profile exists."""

from __future__ import annotations

import argparse
from pathlib import Path

from challenge15.cluster_profile import load_profile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--role", required=True, choices=("oracle", "exact", "reducer"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    profile = load_profile(args.profile)
    if profile.controller != "wuzh02":
        parser.error("renderer requires an active WUZH02 profile")
    profile.require_role(args.role)
    scheduler = profile.scheduler
    text = f"""#!/usr/bin/env bash
#SBATCH --partition={scheduler['partition']}
#SBATCH --account={scheduler['account']}
#SBATCH --qos={scheduler['qos']}
#SBATCH --nodes={scheduler['nodes']}
#SBATCH --ntasks={scheduler['ntasks']}
#SBATCH --cpus-per-task={scheduler['cpus_per_task']}
#SBATCH --mem={scheduler['mem']}
#SBATCH --time={scheduler['time']}
set -euo pipefail
printf '%s\\n' 'WUZH02 wrapper requires deployment-bound interpreter arguments' >&2
exit 2
"""
    with Path(args.output).open("x", encoding="utf-8") as stream:
        stream.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
