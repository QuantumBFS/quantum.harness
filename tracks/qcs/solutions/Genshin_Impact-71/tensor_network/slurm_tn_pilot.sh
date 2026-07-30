#!/usr/bin/env bash
#SBATCH --job-name=occam71-tn-pilot
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:30:00
#SBATCH --output=results/occam71/tensor-network/logs/pilot-%j.out

set -euo pipefail

REPO=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
CODE="$REPO/tracks/qcs/solutions/Genshin_Impact-71/tensor_network"
DATA="$REPO/results/occam71/occam-circuit/datasets"
RUN="$REPO/results/occam71/tensor-network/pilot-seed42/job-${SLURM_JOB_ID}"
PYTHON=/home/user_milksang/.conda/envs/crystalgpt/bin/python

mkdir -p "$RUN/models" "$RUN/reports" "$RUN/logs"
cd "$CODE"

"$PYTHON" -u -m unittest -v test_tn_arm.py

sha256sum \
  tn_common.py tn_truth.py train_mps.py rank_diag.py audit_mps.py \
  test_tn_arm.py TN_DESIGN.md slurm_tn_pilot.sh \
  > "$RUN/code.sha256"

for instance in practice-add-n4 practice-mul-n4; do
  for order in blocked_lsb interleaved_lsb; do
    "$PYTHON" -u rank_diag.py \
      --instance "$instance" \
      --train-csv "$DATA/$instance/train.csv" \
      --order "$order" \
      --ranks 1,2,4,8 \
      --iterations 8 \
      --root-seed 42 \
      --report-out "$RUN/reports/rank-${instance}-${order}.json"
    for bond in 2 4; do
      stem="${instance}-${order}-bond${bond}"
      "$PYTHON" -u train_mps.py \
        --instance "$instance" \
        --train-csv "$DATA/$instance/train.csv" \
        --order "$order" \
        --bond "$bond" \
        --ridge 1e-5 \
        --sweeps 6 \
        --patience 2 \
        --validation-fraction 0.2 \
        --root-seed 42 \
        --model-out "$RUN/models/$stem.npz" \
        --report-out "$RUN/reports/train-$stem.json"
      "$PYTHON" -u audit_mps.py \
        --model "$RUN/models/$stem.npz" \
        --oracle-ranks \
        --report-out "$RUN/reports/audit-$stem.json"
    done
  done
done

"$PYTHON" - "$RUN" "$SLURM_JOB_ID" <<'PY'
import hashlib
import json
import pathlib
import sys

run = pathlib.Path(sys.argv[1])
job_id = sys.argv[2]
files = sorted(
    path for path in run.rglob("*")
    if path.is_file() and path.name not in {"manifest.json", "SUCCESS"}
)
manifest = {
    "schema": "occam71-tn-pilot-manifest-v1",
    "status": "success",
    "job_id": job_id,
    "root_seed": 42,
    "files": [
        {
            "path": str(path.relative_to(run)),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in files
    ],
}
temporary = run / "manifest.json.tmp"
temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
temporary.replace(run / "manifest.json")
(run / "SUCCESS").write_text("success\n")
print(json.dumps(manifest, sort_keys=True), flush=True)
PY
