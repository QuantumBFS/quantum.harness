#!/usr/bin/env python3
from pathlib import Path

import exact_tn


REPO = Path(
    "/home/user_milksang/private/homefile/quantum_harness/issue71_occam"
)
OUTPUT = REPO / "results/occam71/routes/exact-tn-seed42"
CODE = (
    REPO
    / "tracks/qcs/solutions/Genshin_Impact-71/routes/exact_tn"
)

exact_tn.write_hash_manifest(
    OUTPUT,
    [CODE / "exact_tn.py", CODE / "slurm_exact_tn.sh"],
)
