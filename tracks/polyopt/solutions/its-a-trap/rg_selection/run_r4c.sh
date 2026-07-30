#!/bin/bash
# run_r4c.sh — R4c exact-runner gate (4B.4, BLOCKING). Runs the EXACT
# production path `run_n200.jl --mode a200 --manifest <m>` at N=10 with the
# frozen manifest schema, then verifies durable artifacts + semantic-hash
# match vs R4b + a missing-field RED mutation. Exit 0 = R4c PASS.
set -u
cd "$(dirname "$0")"
export PATH="$HOME/.juliaup/bin:$PATH"
export JULIA_PROJECT="$HOME/code/qh-method/julia-env"
R=results
fail() { echo "R4c FAIL: $1"; echo "R4c,FAIL,\"$1\"" >> $R/a200_release_gates.csv; exit 1; }
rm -f $R/a200_stage.txt $R/a200_heartbeat.txt $R/a200_final.json $R/a200_result.csv $R/a200_mosek.log

# 1) exact production invocation shape (N=10 test manifest, same schema)
systemd-run --user --scope -q -p MemoryMax=18G -p MemorySwapMax=0 \
  julia -t 2 run_n200.jl --mode a200 --manifest A200_CONFIG_N10test.json \
  > $R/r4c_runner.log 2>&1
RC=$?
[ $RC -eq 0 ] || fail "runner exit=$RC (see r4c_runner.log)"
grep -q "^RESOLVED: " $R/r4c_runner.log || fail "resolved builder call not logged"

# 2) durable artifacts exist; final JSON/CSV parseable
[ -s $R/a200_stage.txt ]     || fail "stage file missing"
[ -s $R/a200_heartbeat.txt ] || fail "heartbeat file missing"
python3 - <<'EOF' || fail "final JSON unparseable or fields missing"
import json
j = json.load(open("results/a200_final.json"))
need = ["E_per_site_lower_bound","semantic_hash","manifest_sha256","commit",
        "selection_status","solution_status","sig_scalarized","newwords",
        "gamma2_dim","rg_rows","total_wall_s","peak_rss_gb","mosek_log_sha256"]
missing = [k for k in need if k not in j]
assert not missing, missing
EOF
awk -F, 'NR==2 && NF>=13 {ok=1} END {exit ok?0:1}' $R/a200_result.csv || fail "final CSV unparseable"

# 3) semantic hash matches the R4b auto arm
H_RUN=$(python3 -c 'import json; print(json.load(open("results/a200_final.json"))["semantic_hash"])')
H_R4B=$(cat $R/r4b_auto_fullhash.txt)
[ "$H_RUN" = "$H_R4B" ] || fail "semantic hash mismatch runner=$H_RUN r4b=$H_R4B"

# 4) missing-field mutation must stop RED (exit 2)
grep -v '"quotient_id"' A200_CONFIG_N10test.json > $R/r4c_mutant.json
julia run_n200.jl --mode a200 --manifest $R/r4c_mutant.json > $R/r4c_mutant.log 2>&1
MRC=$?
grep -q "A200 RED" $R/r4c_mutant.log || fail "mutant did not print A200 RED"
[ $MRC -eq 2 ] || fail "mutant exit=$MRC != 2"

# 5) preserve N=10 gate artifacts under distinct names
for f in a200_final.json a200_result.csv a200_stage.txt a200_heartbeat.txt a200_mosek.log; do
  [ -f $R/$f ] && mv $R/$f $R/${f%.*}_n10gate.${f##*.}
done
echo "R4c,PASS,\"exact runner @ N=10: artifacts+hash+RED-mutation ok (runner hash $H_RUN)\"" >> $R/a200_release_gates.csv
echo "R4c PASS"
