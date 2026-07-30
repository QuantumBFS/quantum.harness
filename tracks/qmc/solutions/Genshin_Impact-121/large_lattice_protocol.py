#!/usr/bin/env python3
"""Hash-bound outer protocol for the confirmed issue-121 lattice benchmark.

Chain-local CHAIN_COMPLETE files only prove a runner exited normally.  Only this outer
protocol writes the materialized root COMPLETE, after G0--G4 all have PASS
records.  JSON is canonical and forbids NaN/Infinity.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shlex
import statistics
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import numpy as np

PROTOCOL_ID = "issue121-triangular-large-lattice-v1"
CORE_ALGORITHM_ID = "triangular-ab-ctqmc-direct-lu-v1"
ED_ALGORITHM_ID = "triangular-ab-full-fock-ed-oracle-v1"
BENCHMARK_ALGORITHM_ID = "rank3-vs-full-word-rebuild-v1"
SOLUTION_DIR = Path(__file__).resolve().parent
SOURCE_FILES = (
    "large_lattice_protocol.py", "large_lattice_ctqmc.py",
    "large_lattice_ed.py", "local_vertex_physics.py",
    "local_vertex_physics_frozen.json", "test_large_lattice_protocol.py",
    "test_large_lattice_ctqmc.py", "test_local_vertex_physics.py",
    "large_lattice_kernel_benchmark.py",
    "test_large_lattice_kernel_benchmark.py",
)
SIZES = ((4,16),(6,36),(8,64),(12,144),(16,256))
BETAS = (0.5,1.0,2.0,4.0)
BETA_EXACT = ("1/2","1","2","4")
LOCAL = {
    "epsilon":0.01,"epsilon_exact":"1/100",
    "kappa":0.02,"kappa_exact":"1/50",
    "s":0.25,"s_exact":"1/4",
    "g_A":0.25,"g_A_exact":"1/4",
    "g_B":0.25,"g_B_exact":"1/4",
}
CHAINS = (
    (0,"cold",0),(1,"cold",0),
    (2,"hot","round(beta*N)"),(3,"hot","round(beta*N)"),
)
PILOT = {(4,0),(8,2),(12,3)}
DIAGNOSTIC_METHOD = (
    "rank-normalized split-Rhat; bulk/tail ESS=sum of per-split-chain "
    "Geyer initial-positive-sequence ESS; pooled tail cutoffs 5%/95%"
)
DEFAULT_EXECUTION = {
    "g1":{"steps":30000,"warmup":3000,"measure_every":1,
          "checkpoint_every":3000,"rebuild_every":128},
    "production":{"steps":100000,"warmup":10000,"measure_every":10,
                  "checkpoint_every":5000,"rebuild_every":256},
    "woodbury_condition_max":1.0e12,
    "move_probabilities":{"insert":0.35,"delete":0.35,
        "rotate_left_to_right":0.15,"rotate_right_to_left":0.15},
}

class ProtocolError(RuntimeError):
    pass

def _need(ok: bool, message: str) -> None:
    if not ok:
        raise ProtocolError(message)

def _bad_constant(value: str) -> None:
    raise ProtocolError(f"non-finite JSON token forbidden: {value}")

def load_json(path: Path) -> Mapping[str,Any]:
    try:
        value=json.loads(Path(path).read_text(encoding="utf-8"),
                         parse_constant=_bad_constant)
    except (OSError,ValueError,TypeError) as exc:
        raise ProtocolError(f"cannot load strict JSON: {path}") from exc
    _need(isinstance(value,dict),f"JSON root must be object: {path}")
    return value

def canonical_bytes(value: Any) -> bytes:
    try:
        text=json.dumps(value,sort_keys=True,separators=(",",":"),
                        ensure_ascii=False,allow_nan=False)
    except (TypeError,ValueError) as exc:
        raise ProtocolError("payload is not finite canonical JSON") from exc
    return (text+"\n").encode("utf-8")

def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def sha_file(path: Path) -> str:
    return sha_bytes(Path(path).read_bytes())

def write_bytes(path: Path, raw: bytes, exclusive: bool=False) -> None:
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if exclusive and path.exists():
        raise ProtocolError(f"refuse overwrite: {path}")
    fd,tmp=tempfile.mkstemp(prefix="."+path.name+".",suffix=".tmp",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        if exclusive and path.exists():
            raise ProtocolError(f"concurrent immutable artifact: {path}")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def write_json(path: Path, value: Mapping[str,Any], exclusive: bool=False) -> None:
    write_bytes(path,canonical_bytes(value),exclusive)

def _float_eq(actual: Any, expected: float, name: str) -> None:
    _need(not isinstance(actual,bool),f"{name} must be numeric")
    try:
        value=float(Fraction(actual)) if isinstance(actual,str) else float(actual)
    except (TypeError,ValueError) as exc:
        raise ProtocolError(f"{name} must be numeric") from exc
    _need(math.isfinite(value) and value==expected,f"{name} drift")

def validate_meta(meta: Mapping[str,Any]) -> None:
    _need(meta.get("schema_version")==1,"meta schema")
    _need(meta.get("document_type")=="preregistered_large_lattice_run",
          "document_type drift")
    _need(meta.get("issue")==121 and meta.get("team")=="Genshin_Impact",
          "issue/team drift")
    rat=meta.get("ratification")
    _need(isinstance(rat,Mapping) and rat.get("required_before_any_compute") is True,
          "ratification guard absent")
    _need(rat.get("status")=="confirmed","ratification.status must be confirmed")
    _need(meta.get("status") in {"confirmed","ratified","confirmed_for_execution","ratified_setup_frozen_pending_gates"},
          "top status must record confirmation")
    model=meta.get("model")
    _need(isinstance(model,Mapping),"model missing")
    _need(model.get("fermions")=="spinless, one orbital per site","fermion drift")
    _need(model.get("particle_number_conserving") is True,"number drift")
    _float_eq(model.get("chemical_potential_mu"),0.0,"mu")
    lattice=model.get("lattice")
    _need(isinstance(lattice,Mapping),"lattice missing")
    _need(lattice.get("type")=="periodic triangular L by L","lattice drift")
    _need(lattice.get("boundary_conditions")=="periodic in both primitive directions",
          "boundary drift")
    _need(lattice.get("vertices")=="all elementary up and down triangles",
          "triangle drift")
    local=model.get("local_parameters")
    _need(isinstance(local,Mapping),"local parameters missing")
    for key,expected in LOCAL.items():
        if isinstance(expected,float):
            _float_eq(local.get(key),expected,key)
        else:
            _need(local.get(key)==expected,f"{key} exact drift")
    _need(40*float(local["epsilon"])+59*float(local["kappa"])<2,
          "separation region violated")
    grid=meta.get("grid")
    _need(isinstance(grid,Mapping),"grid missing")
    _need(tuple((x.get("L"),x.get("N")) for x in grid.get("sizes",()))==SIZES,
          "size grid drift")
    _need(tuple(grid.get("beta",()))==BETAS,"beta grid drift")
    _need(tuple(grid.get("beta_exact",()))==BETA_EXACT,"beta exact drift")
    _need(grid.get("full_cells")==20,"cell count drift")
    random=meta.get("randomness")
    _need(isinstance(random,Mapping) and random.get("chains_per_cell")==4,
          "chain count drift")
    _need(random.get("seed_rule")==
          "121000000 + 10000*L + 10*beta_index + chain_id","seed rule drift")
    _need(random.get("beta_index")=={"1/2":0,"1":1,"2":2,"4":3},
          "beta index drift")
    seen=tuple((x.get("chain_id"),x.get("start"),x.get("initial_order"))
               for x in random.get("chains",()))
    _need(seen==CHAINS,"initialization drift")
    _need(tuple(x.get("id") for x in meta.get("gates",()))==
          ("G0","G1","G2","G3","G4"),"gate drift")
    measurement=meta.get("measurement_protocol")
    _need(isinstance(measurement,Mapping),"measurement protocol missing")
    real=measurement.get("real_space_green")
    _need(isinstance(real,Mapping) and
          real.get("rule")=="all lattice displacements" and
          real.get("indices")=="all (dx,dy) with 0<=dx<L and 0<=dy<L" and
          real.get("estimator")=="translation-averaged equal-time G(dx,dy)",
          "real-space measurement drift")
    momentum=measurement.get("momenta")
    _need(isinstance(momentum,Mapping),"momentum protocol missing")
    _need(momentum.get("Gamma")==[0,0],"Gamma drift")
    _need(momentum.get("qmin")==[[1,0],[0,1]],"qmin drift")
    _need(momentum.get("M_points")=={
          "condition":"L even",
          "indices":[["L/2",0],[0,"L/2"],["L/2","L/2"]]},
          "M protocol drift")
    _need(momentum.get("K_points")=={
          "condition":"L%3==0",
          "indices":[["L/3","2L/3"],["2L/3","L/3"]]},
          "K protocol drift")
    _need(momentum.get("deduplication")==
          "Deduplicate coincident momentum indices at small L while retaining all protocol labels in provenance.",
          "momentum deduplication drift")
    _need(momentum.get("G1_L3_note")==
          "L=3 has no integer M point; use Gamma, qmin, and the two K points.",
          "G1 L3 note drift")
    thresholds=meta.get("thresholds")
    _need(isinstance(thresholds,Mapping),"thresholds missing")
    for key in ("fast_vs_rebuild_relative_error_max","inverse_residual_max",
                "full_acceptance_hard_range","pilot_acceptance_target",
                "r_hat_max","bulk_ess_min","tail_ess_min","ed_z_score_max"):
        _need(key in thresholds,f"threshold missing: {key}")

def validate_execution(execution: Mapping[str,Any]) -> None:
    for stage in ("g1","production"):
        value=execution.get(stage)
        _need(isinstance(value,Mapping),f"execution.{stage} missing")
        for key,low in (("steps",1),("warmup",0),("measure_every",1),
                        ("checkpoint_every",1),("rebuild_every",1)):
            x=value.get(key)
            _need(isinstance(x,int) and not isinstance(x,bool) and x>=low,
                  f"{stage}.{key} invalid")
        _need(value["warmup"]<value["steps"],f"{stage} warmup>=steps")
    _float_eq(execution.get("woodbury_condition_max"),1e12,"condition")
    moves=execution.get("move_probabilities")
    names={"insert","delete","rotate_left_to_right","rotate_right_to_left"}
    _need(isinstance(moves,Mapping) and set(moves)==names,"moves invalid")
    _need(abs(sum(float(x) for x in moves.values())-1)<1e-15,"moves sum")
    _need(moves["insert"]==moves["delete"],"birth/death asymmetry")
    _need(moves["rotate_left_to_right"]==moves["rotate_right_to_left"],
          "rotation asymmetry")

def seed_for(L: int, beta_index: int, chain_id: int) -> int:
    return 121000000+10000*L+10*beta_index+chain_id

def _unique(points: Iterable[Tuple[int,int]], L: int) -> List[List[int]]:
    out=[]; seen=set()
    for x,y in points:
        point=(int(x)%L,int(y)%L)
        if point not in seen:
            seen.add(point); out.append([point[0],point[1]])
    return out

def measurements(L: int) -> Mapping[str,Any]:
    gamma=[[0,0]]
    qmin=[[1,0],[0,1]]
    m=_unique(((L//2,0),(0,L//2),(L//2,L//2)),L) if L%2==0 else []
    k=(_unique(((L//3,2*L//3),(2*L//3,L//3)),L)
       if L%3==0 else [])
    momenta=_unique((tuple(x) for group in (gamma,qmin,m,k) for x in group),L)
    return {"momenta":momenta,
            "displacements":[[x,y] for x in range(L) for y in range(L)],
            "momentum_labels":{
                "Gamma":[0,0],
                "qmin":qmin,
                "M_points":{"condition":"L even","indices":m},
                "K_points":{"condition":"L%3==0","indices":k},
                "deduplication":
                    "Deduplicate coincident momentum indices at small L while retaining all protocol labels in provenance.",
                "G1_L3_note":
                    "L=3 has no integer M point; use Gamma, qmin, and the two K points.",
                "K_note":("two exact K points included" if L%3==0 else
                          "K points omitted because L%3!=0")},
            "normalization":{"one_body":"phase^dagger G phase / N",
                             "density_raw":"phase^dagger <n_i n_j> phase / N"}}

def runner_manifest(meta_hash: str, stage: str, L: int, beta_index: int,
                    chain_id: int, execution: Mapping[str,Any]) -> Mapping[str,Any]:
    _need(stage in {"g1","production"},"bad stage")
    beta=BETAS[beta_index]; mode="cold" if chain_id<2 else "hot"
    order=0 if mode=="cold" else int(math.floor(beta*L*L+0.5))
    schedule=execution[stage]
    return {"schema_version":1,
      "protocol_binding":{"protocol_id":PROTOCOL_ID,
        "meta_manifest_sha256":meta_hash,"stage":stage,
        "cell_id":f"L{L}-b{beta_index}","chain_id":chain_id},
      "lattice":{"Lx":L,"Ly":L},
      "model":{"epsilon":"1/100","kappa":"1/50","vertex_strength":"1/4",
               "g_A":"1/4","g_B":"1/4","beta":BETA_EXACT[beta_index]},
      "monte_carlo":{"steps":schedule["steps"],"warmup":schedule["warmup"],
        "measure_every":schedule["measure_every"],
        "checkpoint_every":schedule["checkpoint_every"],
        "rebuild_every":schedule["rebuild_every"],
        "seed":seed_for(L,beta_index,chain_id),
        "woodbury_condition_max":execution["woodbury_condition_max"],
        "move_probabilities":dict(execution["move_probabilities"]),
        "initialization":{"mode":mode,"initial_order":order}},
      "measurements":measurements(L),
      "exact_diagonalization":{"hermitian_tolerance":1e-10}}

def _task_table(path: Path, entries: Sequence[Mapping[str,Any]]) -> None:
    write_bytes(path,_task_table_bytes(entries))

def _array_script(table: str, count: int, python_bin: str, result_root: str) -> str:
    return f"""#!/bin/bash
#SBATCH --job-name=i121-{table.replace("_tasks.tsv","")}
#SBATCH --array=0-{count-1}%8
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --chdir={result_root}
set -euo pipefail
ROOT={shlex.quote(result_root)}
SOLUTION_DIR={shlex.quote(str(SOLUTION_DIR))}
PYTHON_BIN={shlex.quote(python_bin)}
preflight=$("$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_protocol.py" validate --root "$ROOT")
line=$(sed -n "$((SLURM_ARRAY_TASK_ID+2))p" "$ROOT/{table}")
IFS=$'\\t' read -r task stage cell chain manifest_rel output_rel <<< "$line"
output="$ROOT/$output_rel"; mkdir -p "$output"
printf '%s\\n' "$preflight" >"$output/preflight.log"
resume=()
if [[ -f "$output/CHAIN_COMPLETE" ]]; then
 "$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_ctqmc.py" \\
  --manifest "$ROOT/$manifest_rel" --output "$output"
 exit 0
fi
if [[ -f "$output/checkpoint.json" ]]; then resume=(--resume); fi
 "$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_ctqmc.py" \\
 --manifest "$ROOT/$manifest_rel" --output "$output" "${{resume[@]}}" \\
 >>"$output/runner.stdout" 2>>"$output/runner.stderr"
""".replace("$","$")
def _audit_script(stage: str, python_bin: str, result_root: str) -> str:
    ed=""
    if stage=="g1":
        ed="""while IFS=$'\\t' read -r cell manifest_rel exact_rel; do
 [[ "$cell" == cell_id ]] && continue
 exact="$ROOT/$exact_rel"; mkdir -p "$(dirname "$exact")"
 [[ -f "$exact" ]] || "$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_ed.py" --manifest "$ROOT/$manifest_rel" --output "$exact"
done < "$ROOT/ed_tasks.tsv"
""".replace("$","$")
    flag=" --write-complete" if stage=="provenance" else ""
    return f"""#!/bin/bash
#SBATCH --job-name=i121-audit-{stage}
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --chdir={result_root}
set -euo pipefail
ROOT={shlex.quote(result_root)}
SOLUTION_DIR={shlex.quote(str(SOLUTION_DIR))}
PYTHON_BIN={shlex.quote(python_bin)}
preflight=$("$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_protocol.py" validate --root "$ROOT")
printf '%s\n' "$preflight"
{ed}"$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_protocol.py" audit --root "$ROOT" --stage {stage}{flag}
""".replace("$","$")

def _submit_script() -> str:
    return """#!/bin/bash
# Run only after live sinfo, squeue, and scontrol node inspection.
set -euo pipefail
H=$(cd "$(dirname "$0")" && pwd -P)
g0=$(sbatch --parsable "$H/run_g0.sbatch")
g1=$(sbatch --parsable --dependency=afterok:$g0 "$H/run_g1_array.sbatch")
a1=$(sbatch --parsable --dependency=afterok:$g1 "$H/audit_g1.sbatch")
p=$(sbatch --parsable --dependency=afterok:$a1 "$H/run_pilot_array.sbatch")
kb=$(sbatch --parsable --dependency=afterok:$a1 "$H/run_kernel_benchmark.sbatch")
ap=$(sbatch --parsable --dependency=afterok:$p:$kb "$H/audit_pilot.sbatch")
f=$(sbatch --parsable --dependency=afterok:$ap "$H/run_full_array.sbatch")
a3=$(sbatch --parsable --dependency=afterok:$f "$H/audit_full.sbatch")
a4=$(sbatch --parsable --dependency=afterok:$a3 "$H/audit_g4.sbatch")
printf 'G0=%s G1=%s G1audit=%s pilot=%s kernel=%s pilotaudit=%s full=%s G3=%s G4=%s\\n' "$g0" "$g1" "$a1" "$p" "$kb" "$ap" "$f" "$a3" "$a4"
""".replace("$","$")

def kernel_benchmark_manifest(sources: Mapping[str,Any]) -> Mapping[str,Any]:
    return {"schema_version":1,"algorithm_id":BENCHMARK_ALGORITHM_ID,
      "parameters":{"sizes":[4,8,12,16],"beta":4.0,
        "order_rule":"ceil(beta*N)","seed":121730001,"repeats":9,"warmup":2,
        "woodbury_condition_max":1.0e12,
        "model":{"epsilon":0.01,"kappa":0.02,"s":0.25,
                 "g_A":0.25,"g_B":0.25}},
      "source_snapshot":sources,
      "output":"benchmark/kernel_benchmark.json",
      "resource_output":"benchmark/resource.tsv",
      "stdout":"benchmark/runner.stdout","stderr":"benchmark/runner.stderr"}

def _benchmark_script(python_bin: str, result_root: str) -> str:
    return f"""#!/bin/bash
#SBATCH --job-name=i121-kernel
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --chdir={result_root}
set -euo pipefail
ROOT={shlex.quote(result_root)}
SOLUTION_DIR={shlex.quote(str(SOLUTION_DIR))}
PYTHON_BIN={shlex.quote(python_bin)}
preflight=$("$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_protocol.py" validate --root "$ROOT")
mkdir -p "$ROOT/benchmark"
printf '%s\\n' "$preflight" >"$ROOT/benchmark/preflight.log"
if [[ -f "$ROOT/benchmark/kernel_benchmark.json" ]]; then exit 0; fi
 "$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_kernel_benchmark.py" \\
 --sizes 4,8,12,16 --beta 4 --seed 121730001 --repeats 9 --warmup 2 \\
 --condition-max 1e12 --output "$ROOT/benchmark/kernel_benchmark.json" \\
 --resource-output "$ROOT/benchmark/resource.tsv" \\
 >>"$ROOT/benchmark/runner.stdout" 2>>"$ROOT/benchmark/runner.stderr"
""".replace("$","$")

def _generated_scripts(python_bin: str, result_root: str) -> Mapping[str,str]:
    return {"run_g1_array.sbatch":_array_script("g1_tasks.tsv",32,python_bin,result_root),
      "run_pilot_array.sbatch":_array_script("pilot_tasks.tsv",12,python_bin,result_root),
      "run_full_array.sbatch":_array_script("full_tasks.tsv",68,python_bin,result_root),
      "audit_g1.sbatch":_audit_script("g1",python_bin,result_root),
      "audit_pilot.sbatch":_audit_script("pilot",python_bin,result_root),
      "audit_full.sbatch":_audit_script("full",python_bin,result_root),
      "audit_g4.sbatch":_audit_script("provenance",python_bin,result_root),
      "run_kernel_benchmark.sbatch":_benchmark_script(python_bin,result_root),
      "submit_after_live_cluster_check.sh":_submit_script(),
      "run_g0.sbatch":f"""#!/bin/bash
#SBATCH --job-name=i121-g0
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --chdir={result_root}
set -euo pipefail
ROOT={shlex.quote(result_root)}
SOLUTION_DIR={shlex.quote(str(SOLUTION_DIR))}
PYTHON_BIN={shlex.quote(python_bin)}
"$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_protocol.py" validate --root "$ROOT"
"$PYTHON_BIN" -m pytest -q "$SOLUTION_DIR/test_large_lattice_protocol.py" "$SOLUTION_DIR/test_large_lattice_ctqmc.py" "$SOLUTION_DIR/test_local_vertex_physics.py" "$SOLUTION_DIR/test_large_lattice_kernel_benchmark.py" -m 'not slow'
"$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_protocol.py" record-g0 --root "$ROOT" --tests-exit-code 0
""".replace("$","$")}

def materialize(meta_path: Path, root: Path,
                execution: Optional[Mapping[str,Any]]=None) -> Mapping[str,Any]:
    meta=load_json(meta_path); validate_meta(meta)
    selected=json.loads(json.dumps(execution or DEFAULT_EXECUTION))
    validate_execution(selected)
    environment=environment_snapshot(); sources=source_snapshot()
    python_bin=environment["python_executable"]
    root=Path(root)
    _need(not root.exists() or not any(root.iterdir()),"output must be empty")
    root.mkdir(parents=True,exist_ok=True)
    meta_raw=canonical_bytes(meta); meta_hash=sha_bytes(meta_raw)
    write_bytes(root/"confirmed_meta_manifest.json",meta_raw,True)
    benchmark_manifest=kernel_benchmark_manifest(sources)
    benchmark_raw=canonical_bytes(benchmark_manifest)
    write_bytes(root/"kernel_benchmark_manifest.json",benchmark_raw,True)
    entries=[]
    for stage,sizes in (("g1",(2,3)),("production",tuple(x[0] for x in SIZES))):
        for L in sizes:
            for bi,beta in enumerate(BETAS):
                for chain in range(4):
                    manifest=runner_manifest(meta_hash,stage,L,bi,chain,selected)
                    slug=("%.8g"%beta).replace(".","p")
                    rel=Path("manifests")/stage/f"L{L}"/f"beta-{slug}"/f"chain-{chain}.json"
                    raw=canonical_bytes(manifest); write_bytes(root/rel,raw,True)
                    output=Path("chains")/stage/f"L{L}"/f"beta-{slug}"/f"chain-{chain}"
                    entries.append({"stage":stage,"cell_id":f"L{L}-b{bi}",
                        "L":L,"N":L*L,"beta":beta,"beta_index":bi,
                        "chain_id":chain,"seed":seed_for(L,bi,chain),
                        "initialization":manifest["monte_carlo"]["initialization"],
                        "manifest":rel.as_posix(),"manifest_sha256":sha_bytes(raw),
                        "output":output.as_posix(),
                        "pilot":stage=="production" and (L,bi) in PILOT})
    g1=[x for x in entries if x["stage"]=="g1"]
    prod=[x for x in entries if x["stage"]=="production"]
    pilot=[x for x in prod if x["pilot"]]
    remaining=[x for x in prod if not x["pilot"]]
    _need(tuple(map(len,(g1,prod,pilot,remaining)))==(32,80,12,68),
          "task cardinality")
    _task_table(root/"g1_tasks.tsv",g1)
    _task_table(root/"pilot_tasks.tsv",pilot)
    _task_table(root/"full_tasks.tsv",remaining)
    ed=["cell_id\tmanifest\texact_output"]
    for x in g1:
        if x["chain_id"]==0:
            ed.append(f'{x["cell_id"]}\t{x["manifest"]}\texact/g1/{x["cell_id"]}.json')
    write_bytes(root/"ed_tasks.tsv",("\n".join(ed)+"\n").encode())
    scripts=_generated_scripts(python_bin,str(root.resolve()))
    for name,text in scripts.items():
        write_bytes(root/"slurm"/name,text.encode(),True)
        os.chmod(root/"slurm"/name,0o755)
    artifact_paths=("g1_tasks.tsv","pilot_tasks.tsv","full_tasks.tsv","ed_tasks.tsv",
                    "kernel_benchmark_manifest.json",
                    *(f"slurm/{name}" for name in scripts))
    artifact_hashes={name:sha_file(root/name) for name in artifact_paths}
    index={"schema_version":1,"protocol_id":PROTOCOL_ID,
      "status":"materialized_not_run","meta_manifest_sha256":meta_hash,
      "execution":selected,"environment":environment,"source_snapshot":sources,
      "kernel_benchmark":{"manifest":"kernel_benchmark_manifest.json",
        "manifest_sha256":sha_bytes(benchmark_raw),
        "output":benchmark_manifest["output"],
        "resource_output":benchmark_manifest["resource_output"],
        "stdout":benchmark_manifest["stdout"],
        "stderr":benchmark_manifest["stderr"]},
      "generated_artifact_sha256":artifact_hashes,
      "diagnostic_method":DIAGNOSTIC_METHOD,
      "counts":{"g1_chains":32,"production_chains":80,
                "pilot_chains":12,"full_remaining_chains":68},
      "entries":entries,
      "claim_boundary":("materialization is not compute evidence; no root COMPLETE; "
        "integrity is tamper-evident accidental-drift detection, not "
        "cryptographic authentication; trust root is the git commit plus "
        "externally recorded result hashes")}
    raw=canonical_bytes(index); write_bytes(root/"index.json",raw,True)
    write_bytes(root/"index.sha256",(sha_bytes(raw)+"  index.json\n").encode(),True)
    return index

def _rankdata(values: np.ndarray) -> np.ndarray:
    order=np.argsort(values,kind="mergesort"); ranks=np.empty(len(values),float)
    start=0
    while start<len(values):
        stop=start+1
        while stop<len(values) and values[order[stop]]==values[order[start]]:
            stop+=1
        ranks[order[start:stop]]=0.5*(start+1+stop); start=stop
    return ranks

def _rank_normalize(chains: Sequence[np.ndarray]) -> List[np.ndarray]:
    lengths=[len(x) for x in chains]; pooled=np.concatenate(chains)
    _need(len(pooled)>0,"empty trace")
    ranks=_rankdata(pooled); probabilities=(ranks-0.375)/(len(pooled)+0.25)
    normal=statistics.NormalDist()
    z=np.array([normal.inv_cdf(float(p)) for p in probabilities])
    out=[]; offset=0
    for length in lengths:
        out.append(z[offset:offset+length]); offset+=length
    return out

def ips_tau_int(values: Sequence[float]) -> float:
    x=np.asarray(values,float)
    _need(x.ndim==1 and len(x)>=4 and np.all(np.isfinite(x)),
          "IPS needs >=4 finite values")
    centered=x-np.mean(x); gamma0=float(np.dot(centered,centered)/len(x))
    if gamma0<=np.finfo(float).eps:
        return 0.5
    tau=0.5; lag=1
    while lag+1<len(x):
        rho1=float(np.dot(centered[:-lag],centered[lag:])/(len(x)*gamma0))
        lag2=lag+1
        rho2=float(np.dot(centered[:-lag2],centered[lag2:])/(len(x)*gamma0))
        pair=rho1+rho2
        if not math.isfinite(pair) or pair<=0:
            break
        tau+=pair; lag+=2
    return max(0.5,tau)

def _split(chains: Sequence[Sequence[float]]) -> List[np.ndarray]:
    arrays=[np.asarray(x,float) for x in chains]
    _need(len(arrays)>=2 and all(x.ndim==1 and len(x)>=8 and
          np.all(np.isfinite(x)) for x in arrays),"short/nonfinite chains")
    half=min(len(x)//2 for x in arrays)
    return [part for x in arrays for part in (x[:half],x[-half:])]

def _rhat(split: Sequence[np.ndarray]) -> float:
    n=min(len(x) for x in split); values=[x[:n] for x in split]
    means=np.array([np.mean(x) for x in values])
    W=float(np.mean([np.var(x,ddof=1) for x in values]))
    B=float(n*np.var(means,ddof=1))
    if W<=np.finfo(float).eps:
        return 1.0 if B<=np.finfo(float).eps else math.inf
    return float(math.sqrt(max(0,((n-1)*W/n+B/n)/W)))

def _ess(split: Sequence[np.ndarray]) -> float:
    return float(sum(len(x)/(2*ips_tau_int(x)) for x in split))

def multi_chain_diagnostics(chains: Sequence[Sequence[float]]) -> Mapping[str,Any]:
    split=_split(chains); ranked=_rank_normalize(split)
    pooled=np.concatenate(split); low,high=np.quantile(pooled,[0.05,0.95])
    lower=[(x<=low).astype(float) for x in split]
    upper=[(x>=high).astype(float) for x in split]
    return {"method":DIAGNOSTIC_METHOD,"split_chains":len(split),
      "samples_per_split":min(len(x) for x in split),
      "split_r_hat":_rhat(ranked),"bulk_ess":_ess(ranked),
      "tail_ess":min(_ess(lower),_ess(upper)),
      "tau_int_by_original_chain":[ips_tau_int(x) for x in chains]}

def verify_materialization(root: Path,
                           validate_complete: bool=True) -> Mapping[str,Any]:
    root=Path(root); index=load_json(root/"index.json")
    _need(index.get("protocol_id")==PROTOCOL_ID,"index protocol")
    expected_hash=(root/"index.sha256").read_text(encoding="ascii").split()[0]
    _need(expected_hash==sha_file(root/"index.json"),"index hash")
    meta=load_json(root/"confirmed_meta_manifest.json"); validate_meta(meta)
    meta_hash=sha_bytes(canonical_bytes(meta))
    _need(meta_hash==index.get("meta_manifest_sha256"),"meta hash")
    execution=index.get("execution"); _need(isinstance(execution,Mapping),"execution missing")
    validate_execution(execution)
    counts={"g1_chains":32,"production_chains":80,
            "pilot_chains":12,"full_remaining_chains":68}
    _need(index.get("counts")==counts,"index counts")
    environment=index.get("environment")
    _need(isinstance(environment,Mapping),"environment missing")
    python_path=Path(str(environment.get("python_executable","")))
    _need(python_path.is_absolute() and python_path.is_file(),"environment Python")
    sources=index.get("source_snapshot")
    _need(isinstance(sources,Mapping) and sources.get("git_commit") and
          set(sources.get("tracked_files_sha256",{}))==set(SOURCE_FILES),
          "source snapshot")
    _need(source_snapshot()==sources,"current source snapshot drift")
    expected_entries=[]
    for stage,sizes in (("g1",(2,3)),("production",tuple(x[0] for x in SIZES))):
        for L in sizes:
            for bi,beta in enumerate(BETAS):
                for chain in range(4):
                    manifest=runner_manifest(meta_hash,stage,L,bi,chain,execution)
                    slug=("%.8g"%beta).replace(".","p")
                    rel=Path("manifests")/stage/f"L{L}"/f"beta-{slug}"/f"chain-{chain}.json"
                    raw=canonical_bytes(manifest)
                    output=Path("chains")/stage/f"L{L}"/f"beta-{slug}"/f"chain-{chain}"
                    expected_entries.append({"stage":stage,"cell_id":f"L{L}-b{bi}",
                      "L":L,"N":L*L,"beta":beta,"beta_index":bi,
                      "chain_id":chain,"seed":seed_for(L,bi,chain),
                      "initialization":manifest["monte_carlo"]["initialization"],
                      "manifest":rel.as_posix(),"manifest_sha256":sha_bytes(raw),
                      "output":output.as_posix(),
                      "pilot":stage=="production" and (L,bi) in PILOT})
    entries=index.get("entries")
    _need(isinstance(entries,list) and entries==expected_entries,
          "index entries/cardinality drift")
    identities={(x["stage"],x["cell_id"],x["chain_id"]) for x in entries}
    _need(len(identities)==112,"index entries are not unique")
    for entry in entries:
        manifest_path=_safe_relative(root,entry["manifest"],"manifest")
        _safe_relative(root,entry["output"],"output")
        _need(manifest_path.is_file() and
              sha_file(manifest_path)==entry["manifest_sha256"],
              f"manifest hash: {manifest_path}")
        _need(canonical_bytes(load_json(manifest_path))==manifest_path.read_bytes(),
              f"manifest not canonical: {manifest_path}")
    g1=[x for x in entries if x["stage"]=="g1"]
    prod=[x for x in entries if x["stage"]=="production"]
    pilot=[x for x in prod if x["pilot"]]
    remaining=[x for x in prod if not x["pilot"]]
    expected_tables={"g1_tasks.tsv":_task_table_bytes(g1),
                     "pilot_tasks.tsv":_task_table_bytes(pilot),
                     "full_tasks.tsv":_task_table_bytes(remaining)}
    ed=["cell_id\tmanifest\texact_output"]
    for x in g1:
        if x["chain_id"]==0:
            ed.append(f'{x["cell_id"]}\t{x["manifest"]}\texact/g1/{x["cell_id"]}.json')
    expected_tables["ed_tasks.tsv"]=("\n".join(ed)+"\n").encode()
    for name,raw in expected_tables.items():
        _need((root/name).read_bytes()==raw,f"{name} drift")
    artifacts=index.get("generated_artifact_sha256")
    _need(isinstance(artifacts,Mapping),"generated artifact hashes missing")
    expected_benchmark=kernel_benchmark_manifest(sources)
    expected_artifacts=dict(expected_tables)
    expected_artifacts["kernel_benchmark_manifest.json"]=canonical_bytes(
        expected_benchmark)
    for name,text in _generated_scripts(
            index["environment"]["python_executable"],str(root.resolve())).items():
        expected_artifacts[f"slurm/{name}"]=text.encode()
    _need(set(artifacts)==set(expected_artifacts),
          "generated artifact key set drift")
    for name,raw in expected_artifacts.items():
        path=_safe_relative(root,name,"generated artifact")
        _need(path.is_file() and path.read_bytes()==raw,
              f"generated artifact content: {name}")
        _need(artifacts[name]==sha_bytes(raw),
              f"generated artifact hash: {name}")
    benchmark_info=index.get("kernel_benchmark")
    _need(isinstance(benchmark_info,Mapping),"kernel benchmark index missing")
    benchmark_path=_safe_relative(
        root,benchmark_info.get("manifest"),"kernel benchmark manifest")
    _need(load_json(benchmark_path)==expected_benchmark,
          "kernel benchmark manifest drift")
    _need(benchmark_info.get("manifest_sha256")==sha_file(benchmark_path),
          "kernel benchmark manifest hash")
    for key in ("output","resource_output","stdout","stderr"):
        _need(benchmark_info.get(key)==expected_benchmark[key],
              f"kernel benchmark {key} drift")
        _safe_relative(root,benchmark_info[key],f"kernel benchmark {key}")
    if validate_complete and (root/"COMPLETE").exists():
        _validate_protocol_complete(root,index)
    return index

def _load_chain(root: Path, entry: Mapping[str,Any]) -> Mapping[str,Any]:
    manifest_path=_safe_relative(root,entry["manifest"],"manifest")
    output=_safe_relative(root,entry["output"],"output")
    result_path=output/"result.json"; done_path=output/"CHAIN_COMPLETE"
    _need(result_path.is_file() and done_path.is_file(),
          f"missing chain {entry['cell_id']}/c{entry['chain_id']}")
    manifest=load_json(manifest_path); result=load_json(result_path)
    done=load_json(done_path); digest=entry["manifest_sha256"]
    _need(sha_file(manifest_path)==digest,"manifest drift")
    for payload,label in ((result,"result"),(done,"CHAIN_COMPLETE")):
        _need(payload.get("schema_version")==1,f"{label} schema")
        _need(payload.get("algorithm_id")==CORE_ALGORITHM_ID,
              f"{label} algorithm")
        _need(payload.get("scope")=="single_chain_execution_only",
              f"{label} scope")
        _need(payload.get("status")=="run_complete_unvalidated",
              f"{label} status")
        _need(payload.get("manifest_sha256")==digest,f"{label} binding")
    _need(done.get("result_json_sha256")==sha_file(result_path),"result hash")
    steps=manifest["monte_carlo"]["steps"]
    _need(result.get("completed_steps")==steps and
          done.get("completed_steps")==steps,"step count")
    geometry=result.get("geometry",{})
    _need(geometry.get("Lx",entry["L"])==entry["L"] and
          geometry.get("Ly",entry["L"])==entry["L"] and
          geometry.get("n_sites")==entry["N"],"geometry")
    _need(result.get("initialization")==entry["initialization"],"initialization")
    for key,value in manifest["model"].items():
        _float_eq(result.get("model",{}).get(key),float(Fraction(value)),
                  f"result model {key}")
    measured=result.get("measurements",{})
    _need(measured.get("momenta")==manifest["measurements"]["momenta"] and
          measured.get("displacements")==manifest["measurements"]["displacements"],
          "measurement binding")
    _need(result.get("observables",{}).get("count",0)>0,"no measurements")
    canonical_bytes(result); canonical_bytes(done)
    return result

def _aggregate_complex(results: Sequence[Mapping[str,Any]], section: str,
                       names: Sequence[str]) -> Mapping[str,Any]:
    total=sum(int(x["observables"]["count"]) for x in results); out={}
    first=results[0]["observables"].get(section,{})
    for key in first:
        out[key]={}
        for name in names:
            pairs=[]; naive=[]; weights=[]
            for result in results:
                raw=result["observables"][section][key][name]
                pairs.append(raw["mean"])
                naive.append(float(raw.get("naive_stderr_abs",math.inf)))
                weights.append(int(result["observables"]["count"]))
            mean=[sum(w*float(p[i]) for w,p in zip(weights,pairs))/total
                  for i in (0,1)]
            out[key][name]={"mean":mean,"chain_means":pairs,
                            "chain_naive_stderr_abs":naive}
    return out

def _momentum(results: Sequence[Mapping[str,Any]]) -> Mapping[str,Any]:
    out=_aggregate_complex(results,"momentum",
                           ("one_body","density_raw","density_mode"))
    for momentum in out:
        raw=out[momentum]["density_raw"]["mean"]
        mode=out[momentum]["density_mode"]["mean"]
        out[momentum]["density_connected_from_means"]=[
            raw[0]-mode[0]**2-mode[1]**2,raw[1]]
    return out

def _real_space(results: Sequence[Mapping[str,Any]]) -> Mapping[str,Any]:
    return _aggregate_complex(results,"real_space_green",("one_body",))

def summarize_cell(results: Sequence[Mapping[str,Any]], beta: float, n_sites: int,
                   thresholds: Mapping[str,Any],
                   acceptance_range: Sequence[float]) -> Mapping[str,Any]:
    _need(len(results)==4,"cell needs four chains")
    names=("order","energy_density","particle_number",
           "particle_number_squared","particle_density")
    traces={name:[[float(v) for v in x["observables"]["primary_traces"][name]]
                  for x in results] for name in names}
    diagnostics={name:multi_chain_diagnostics(value) for name,value in traces.items()
                 if name!="particle_number_squared"}
    pooled={name:np.concatenate(value) for name,value in traces.items()}
    scalar={name:{"mean":float(np.mean(value)),
                  "sample_std":float(np.std(value,ddof=1))}
            for name,value in pooled.items()}
    mean_n=scalar["particle_number"]["mean"]
    compressibility=beta*(scalar["particle_number_squared"]["mean"]-mean_n**2)/n_sites
    influence=[beta*(np.asarray(n2)-2*mean_n*np.asarray(n))/n_sites
               for n,n2 in zip(traces["particle_number"],
                               traces["particle_number_squared"])]
    comp_diag=multi_chain_diagnostics(influence)
    comp_mcse=float(np.std(np.concatenate(influence),ddof=1)/
                     math.sqrt(max(1,comp_diag["bulk_ess"])))
    attempted=accepted=zeros=det_zeros=negatives=0
    keys=("delta_logdet","relative_T_drift_inf","relative_Q_drift_inf",
          "fast_inverse_residual_inf","rebuilt_inverse_residual_inf")
    values={key:[] for key in keys}
    for result in results:
        moves=result["counters"]["moves"]
        for name in ("insert","delete"):
            attempted+=int(moves[name]["attempted"])
            accepted+=int(moves[name]["accepted"])
        zeros+=int(result["counters"].get("zero_weight_rejections",0))
        failures=result["counters"].get("determinant_failures",{})
        det_zeros+=int(failures.get("zero",0))
        negatives+=int(failures.get("negative",0))
        for record in result.get("rebuild_diagnostics",()):
            for key in keys:
                if record.get(key) is not None:
                    number=abs(float(record[key]))
                    _need(math.isfinite(number),f"nonfinite {key}")
                    values[key].append(number)
    _need(attempted>0,"no insert/delete attempts")
    acceptance=accepted/attempted
    maxima={key:max(value,default=0.0) for key,value in values.items()}
    convergence=all(x["split_r_hat"]<=float(thresholds["r_hat_max"]) and
        x["bulk_ess"]>=float(thresholds["bulk_ess_min"]) and
        x["tail_ess"]>=float(thresholds["tail_ess_min"])
        for x in diagnostics.values())
    rebuild=max(maxima["delta_logdet"],maxima["relative_T_drift_inf"],
                maxima["relative_Q_drift_inf"])<=float(
                    thresholds["fast_vs_rebuild_relative_error_max"]) and max(
                maxima["fast_inverse_residual_inf"],
                maxima["rebuilt_inverse_residual_inf"])<=float(
                    thresholds["inverse_residual_max"])
    accept=float(acceptance_range[0])<=acceptance<=float(acceptance_range[1])
    return {"chains":4,"samples":sum(map(len,traces["order"])),"scalar":scalar,
      "compressibility":compressibility,"compressibility_mcse":comp_mcse,
      "diagnostics":diagnostics,"compressibility_diagnostics":comp_diag,
      "momentum":_momentum(results),
      "real_space_green":_real_space(results),
      "acceptance":{"attempted":attempted,"accepted":accepted,"rate":acceptance,
                    "required_range":list(acceptance_range),"pass":accept},
      "rebuild":{"maxima":maxima,"pass":rebuild},
      "positivity":{"zero_weight_count":zeros,
        "zero_determinant_failure_count":det_zeros,
        "negative_sign_count":negatives,
        "negative_count_provenance":"sum of chain determinant_failures counters",
        "pass":zeros==0 and det_zeros==0 and negatives==0},
      "pass":convergence and rebuild and accept and zeros==0 and
             det_zeros==0 and negatives==0}

def _mean_se(pairs: Sequence[Sequence[float]], component: int) -> float:
    values=np.array([float(x[component]) for x in pairs])
    return float(np.std(values,ddof=1)/math.sqrt(len(values)))

def _complex_mcse(sampled: Mapping[str,Any]) -> float:
    between=max(_mean_se(sampled["chain_means"],i) for i in (0,1))
    naive=[float(x) for x in sampled.get("chain_naive_stderr_abs",())
           if math.isfinite(float(x))]
    within=math.sqrt(sum(x*x for x in naive))/len(naive) if naive else 0.0
    return max(between,within)

def _compare_complex_section(sampled_section: Mapping[str,Any],
                             exact_section: Mapping[str,Any],
                             names: Sequence[str],zmax: float) -> Mapping[str,Any]:
    comparison={}
    for key,reference in exact_section.items():
        if key not in sampled_section:
            comparison[key]={"pass":False,"reason":"missing observable"}; continue
        item={}
        for name in names:
            sampled=sampled_section[key][name]
            target=reference[name] if isinstance(reference,Mapping) else reference
            se=_complex_mcse(sampled); allowance=max(zmax*se,1e-10)
            error=max(abs(float(sampled["mean"][i])-float(target[i]))
                      for i in (0,1))
            item[name]={"max_abs_error":error,"mcse":se,
                        "allowance":allowance,"pass":error<=allowance}
        item["pass"]=all(v["pass"] for k,v in item.items() if k!="pass")
        comparison[key]=item
    for key in sampled_section:
        if key not in exact_section:
            comparison[key]={"pass":False,"reason":"unexpected observable"}
    return comparison

def validate_ed_binding(root: Path, entries: Sequence[Mapping[str,Any]],
                        exact: Mapping[str,Any]) -> None:
    _need(len(entries)==4 and {x["chain_id"] for x in entries}==set(range(4)),
          "ED cell chain set")
    manifests=[load_json(_safe_relative(root,x["manifest"],"ED manifest"))
               for x in entries]
    physical=("lattice","model","measurements","exact_diagonalization")
    reference={key:manifests[0][key] for key in physical}
    for manifest in manifests[1:]:
        _need(all(manifest[key]==reference[key] for key in physical),
              "ED cell physical manifest mismatch")
    chain0=next(x for x in entries if x["chain_id"]==0)
    manifest0=load_json(root/chain0["manifest"])
    _need(exact.get("schema_version")==1 and exact.get("status")=="complete",
          "ED status")
    _need(exact.get("algorithm_id")==ED_ALGORITHM_ID,"ED algorithm")
    _need(exact.get("runner_manifest_sha256")==chain0["manifest_sha256"],
          "ED manifest digest")
    geometry=exact.get("geometry",{})
    _need(geometry.get("Lx")==chain0["L"] and
          geometry.get("Ly")==chain0["L"] and
          geometry.get("n_sites")==chain0["N"],"ED geometry")
    for key,value in manifest0["model"].items():
        _float_eq(exact.get("model",{}).get(key),float(Fraction(value)),
                  f"ED model {key}")
    observables=exact.get("observables",{})
    expected_momenta={f"{x},{y}" for x,y in manifest0["measurements"]["momenta"]}
    expected_real={f"{x},{y}" for x,y in manifest0["measurements"]["displacements"]}
    _need(set(observables.get("momentum",{}))==expected_momenta,
          "ED momentum set")
    _need(set(observables.get("real_space_green",{}))==expected_real,
          "ED displacement set")
    diagnostics=exact.get("diagnostics",{})
    for key in ("density_matrix_trace_residual",
                "green_hermitian_residual_inf",
                "green_trace_minus_particle_number_abs",
                "density_pair_diagonal_residual_inf"):
        value=float(diagnostics.get(key,math.inf))
        _need(math.isfinite(value) and value<=1e-8,f"ED diagnostic {key}")
    canonical_bytes(exact)


def compare_ed(cell: Mapping[str,Any], exact: Mapping[str,Any],
               zmax: float) -> Mapping[str,Any]:
    scalar={}
    for name in ("energy_density","particle_density"):
        diag=cell["diagnostics"][name]
        se=cell["scalar"][name]["sample_std"]/math.sqrt(max(1,diag["bulk_ess"]))
        estimate=cell["scalar"][name]["mean"]
        target=float(exact["observables"]["scalar"][name])
        allowance=max(zmax*se,1e-10)
        scalar[name]={"estimate":estimate,"exact":target,"mcse":se,
                      "allowance":allowance,
                      "pass":abs(estimate-target)<=allowance}
    estimate=cell["compressibility"]
    target=float(exact["observables"]["scalar"]["compressibility"])
    allowance=max(zmax*cell["compressibility_mcse"],1e-10)
    scalar["compressibility"]={"estimate":estimate,"exact":target,
      "mcse":cell["compressibility_mcse"],"allowance":allowance,
      "pass":abs(estimate-target)<=allowance}
    momentum=_compare_complex_section(
        cell["momentum"],exact["observables"].get("momentum",{}),
        ("one_body","density_raw","density_mode"),zmax)
    real_space=_compare_complex_section(
        cell["real_space_green"],
        exact["observables"].get("real_space_green",{}),("one_body",),zmax)
    return {"scalar":scalar,"momentum":momentum,
      "real_space_green":real_space,
      "complex_mcse_note":
      "maximum of SE across four chain means and combined per-chain naive SE",
      "pass":all(x["pass"] for x in scalar.values()) and
             all(x["pass"] for x in momentum.values()) and
             all(x["pass"] for x in real_space.values())}

def _gate(root: Path, name: str, payload: Mapping[str,Any]) -> Mapping[str,Any]:
    root=Path(root)
    _need(not (root/"COMPLETE").exists(),
          "root COMPLETE is immutable; refuse gate overwrite")
    index=verify_materialization(root)
    bindings={"index_sha256":sha_file(root/"index.json"),
              "meta_manifest_sha256":index["meta_manifest_sha256"]}
    record={"schema_version":1,"protocol_id":PROTOCOL_ID,"gate":name,
            **payload,**bindings}
    path=root/"gates"/f"{name}.json"
    if path.exists():
        raw=path.read_bytes(); digest=sha_bytes(raw)
        history=root/"gates"/"history"/f"{name}.{digest}.json"
        if not history.exists():
            write_bytes(history,raw,True)
    write_json(path,record); return record

def record_g0(root: Path, code: int) -> Mapping[str,Any]:
    verify_materialization(root)
    return _gate(root,"G0",{"status":"PASS" if code==0 else "FAIL",
      "tests_exit_code":code})

def _validate_gate_record(root: Path, name: str, value: Mapping[str,Any],
                          index: Mapping[str,Any]) -> None:
    _need(isinstance(value,Mapping),f"required {name} record")
    _need(value.get("schema_version")==1,f"required {name} schema")
    _need(value.get("protocol_id")==PROTOCOL_ID and value.get("gate")==name,
          f"required {name} identity")
    _need(value.get("status")=="PASS",f"required {name} not PASS")
    _need(value.get("index_sha256")==sha_file(root/"index.json"),
          f"required {name} index binding")
    _need(value.get("meta_manifest_sha256")==index["meta_manifest_sha256"],
          f"required {name} meta binding")
    if name=="G0":
        _need(value.get("tests_exit_code")==0,"required G0 test evidence")
    elif name in {"G1","G2","G3"}:
        expected={"G1":("g1",8),"G2":("pilot",3),
                  "G3":("full",20)}[name]
        cells=value.get("cells")
        _need(value.get("stage")==expected[0],f"required {name} stage")
        _need(isinstance(cells,Mapping) and len(cells)==expected[1],
              f"required {name} cell cardinality")
        _need(value.get("chain_cells_pass") is True and
              value.get("all_cells_pass") is True and
              all(isinstance(cell,Mapping) and cell.get("pass") is True
                  for cell in cells.values()),f"required {name} cell evidence")
        if name=="G2":
            _need(isinstance(value.get("kernel_benchmark"),Mapping) and
                  value["kernel_benchmark"].get("pass") is True,
                  "required G2 kernel benchmark evidence")
            _need(isinstance(value.get("resource_gate"),Mapping) and
                  value["resource_gate"].get("pass") is True,
                  "required G2 resource evidence")
    elif name=="G4":
        chains=value.get("chains"); checks=value.get("checks")
        _need(isinstance(chains,list) and len(chains)==112,
              "required G4 chain cardinality")
        _need(value.get("distinct_slurm_array_tasks")==112,
              "required G4 distinct task evidence")
        _need(isinstance(checks,Mapping) and bool(checks) and
              all(item is True for item in checks.values()),
              "required G4 provenance checks")
    else:
        raise ProtocolError(f"unknown gate {name}")
    canonical_bytes(value)

def _require_gate(root: Path, name: str,
                  index: Optional[Mapping[str,Any]]=None) -> Mapping[str,Any]:
    root=Path(root)
    if index is None:
        index=verify_materialization(root,validate_complete=False)
    value=load_json(root/"gates"/f"{name}.json")
    _validate_gate_record(root,name,value,index)
    return value

def _validate_complete_evidence(root: Path, index: Mapping[str,Any],
                                gates: Mapping[str,Mapping[str,Any]]) -> None:
    expected={(entry["stage"],entry["cell_id"],entry["chain_id"]):entry
              for entry in index["entries"]}
    records=gates["G4"].get("chains")
    _need(isinstance(records,list),"COMPLETE G4 chain evidence")
    by_identity={}
    for record in records:
        _need(isinstance(record,Mapping),"COMPLETE G4 chain record")
        identity=(record.get("stage"),record.get("cell_id"),
                  record.get("chain_id"))
        _need(identity in expected and identity not in by_identity,
              "COMPLETE G4 chain identity")
        by_identity[identity]=record
    _need(set(by_identity)==set(expected),"COMPLETE G4 chain coverage")
    hash_fields={"result_sha256":"result.json",
      "chain_complete_sha256":"CHAIN_COMPLETE",
      "runner_stdout_sha256":"runner.stdout",
      "runner_stderr_sha256":"runner.stderr",
      "preflight_sha256":"preflight.log"}
    for identity,entry in expected.items():
        record=by_identity[identity]
        output=_safe_relative(root,entry["output"],"COMPLETE chain output")
        for field,filename in hash_fields.items():
            path=output/filename
            _need(path.is_file() and record.get(field)==sha_file(path),
                  f"COMPLETE chain evidence drift: {identity} {filename}")
        resource=record.get("resource")
        resource_path=output/"resource.tsv"
        _need(isinstance(resource,Mapping) and resource_path.is_file() and
              resource.get("sha256")==sha_file(resource_path),
              f"COMPLETE chain evidence drift: {identity} resource.tsv")
    g1_cells=gates["G1"].get("cells")
    expected_cells={entry["cell_id"] for entry in index["entries"]
                    if entry["stage"]=="g1"}
    _need(isinstance(g1_cells,Mapping) and set(g1_cells)==expected_cells,
          "COMPLETE G1 ED coverage")
    for cell_id in expected_cells:
        exact=root/"exact"/"g1"/f"{cell_id}.json"
        cell=g1_cells[cell_id]
        _need(exact.is_file() and isinstance(cell,Mapping) and
              cell.get("exact_ed_sha256")==sha_file(exact),
              f"COMPLETE G1 ED evidence drift: {cell_id}")
    current_benchmark=validate_kernel_benchmark(root,index)
    _need(gates["G2"].get("kernel_benchmark")==current_benchmark,
          "COMPLETE G2 benchmark evidence drift")

def _validate_protocol_complete(root: Path,
                                index: Mapping[str,Any]) -> Mapping[str,Any]:
    root=Path(root); path=root/"COMPLETE"; value=load_json(path)
    _need(value.get("schema_version")==1,"COMPLETE schema")
    _need(value.get("protocol_id")==PROTOCOL_ID,"COMPLETE protocol")
    _need(value.get("status")=="complete","COMPLETE status")
    _need(value.get("index_sha256")==sha_file(root/"index.json"),
          "COMPLETE index binding")
    _need(value.get("meta_manifest_sha256")==index["meta_manifest_sha256"],
          "COMPLETE meta binding")
    hashes=value.get("gate_report_sha256")
    _need(isinstance(hashes,Mapping) and
          set(hashes)=={"G0","G1","G2","G3","G4"},
          "COMPLETE gate hash set")
    gates={}
    for name in ("G0","G1","G2","G3","G4"):
        gates[name]=_require_gate(root,name,index=index)
        _need(hashes[name]==sha_file(root/"gates"/f"{name}.json"),
              f"COMPLETE stale {name} gate hash")
    _validate_complete_evidence(root,index,gates)
    _need(canonical_bytes(value)==path.read_bytes(),"COMPLETE not canonical")
    return value

def _resource_evidence(path: Path) -> Mapping[str,Any]:
    _need(path.is_file(),"resource.tsv missing")
    elapsed=[]; rss=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        fields=line.split("\t")
        if len(fields)!=2:
            continue
        if fields[0]=="elapsed_seconds":
            elapsed.append(float(fields[1]))
        elif fields[0]=="max_rss_kb":
            rss.append(int(fields[1]))
    _need(elapsed and rss and all(math.isfinite(x) and x>=0 for x in elapsed)
          and all(x>0 for x in rss),"resource.tsv invalid")
    return {"attempts":len(elapsed),"elapsed_seconds":elapsed,
            "max_rss_kb":rss,"sha256":sha_file(path)}

def validate_kernel_benchmark(root: Path,
                              index: Mapping[str,Any]) -> Mapping[str,Any]:
    info=index["kernel_benchmark"]
    manifest_path=_safe_relative(root,info["manifest"],"benchmark manifest")
    manifest=load_json(manifest_path); expected=kernel_benchmark_manifest(
        index["source_snapshot"])
    _need(manifest==expected,"benchmark manifest content")
    _need(sha_file(manifest_path)==info["manifest_sha256"],
          "benchmark manifest digest")
    output=_safe_relative(root,info["output"],"benchmark output")
    _need(output.is_file(),"benchmark output missing")
    report=load_json(output)
    _need(report.get("schema_version")==1,"benchmark schema")
    _need(report.get("algorithm_id")==BENCHMARK_ALGORITHM_ID,
          "benchmark algorithm")
    _need(report.get("status")=="benchmark_complete_unvalidated",
          "benchmark status")
    parameters=report.get("parameters",{})
    _need(parameters==manifest["parameters"],"benchmark parameters/model")
    provenance=report.get("provenance",{})
    sources=index["source_snapshot"]["tracked_files_sha256"]
    _need(provenance.get("benchmark_source_sha256")==
          sources["large_lattice_kernel_benchmark.py"],
          "benchmark source hash")
    _need(provenance.get("ctqmc_source_sha256")==
          sources["large_lattice_ctqmc.py"],"benchmark CTQMC source hash")
    _need(provenance.get("source_commit")==
          index["source_snapshot"]["git_commit"],"benchmark source commit")
    environment=report.get("environment",{})
    _need(Path(str(environment.get("python_executable",""))).resolve()==
          Path(index["environment"]["python_executable"]).resolve(),
          "benchmark Python environment")
    _need(environment.get("numpy_version")==index["environment"]["numpy_version"]
          and environment.get("scipy_version")==index["environment"]["scipy_version"],
          "benchmark package environment")
    blas=report.get("single_thread_blas",{})
    _need(blas.get("set_before_numpy_import") is True and
          set(blas.get("environment",{}).values())=={"1"},
          "benchmark BLAS threading")
    cases=report.get("cases")
    _need(isinstance(cases,list) and
          [(x.get("L"),x.get("N")) for x in cases]==
          [(4,16),(8,64),(12,144),(16,256)],"benchmark sizes")
    correctness=report.get("overall_correctness_pass") is True
    fallback=report.get("total_fallback_count")=={"insert":0,"delete":0}
    case_checks=True; case_by_n={}
    for case in cases:
        case_by_n[int(case["N"])]=case
        case_checks=case_checks and case.get("correctness",{}).get("pass") is True
        case_checks=case_checks and case.get("fallback_count")=={
            "insert":0,"delete":0}
        for move in ("insert","delete"):
            timing=case.get("latency",{}).get(move,{})
            rank=timing.get("rank3",{}); dense=timing.get("full_word_rebuild",{})
            rank_samples=[int(x) for x in rank.get("samples_ns",())]
            dense_samples=[int(x) for x in dense.get("samples_ns",())]
            _need(len(rank_samples)==manifest["parameters"]["repeats"] and
                  len(dense_samples)==manifest["parameters"]["repeats"] and
                  min(rank_samples+dense_samples)>0,"benchmark timing samples")
            _float_eq(rank.get("median_ns"),statistics.median(rank_samples),
                      "benchmark rank3 median")
            _float_eq(dense.get("median_ns"),statistics.median(dense_samples),
                      "benchmark dense median")
            expected_speed=float(dense["median_ns"])/float(rank["median_ns"])
            _float_eq(timing.get("speedup_dense_over_rank3"),expected_speed,
                      "benchmark speedup")
    speedup_n144={move:float(case_by_n[144]["latency"][move][
        "speedup_dense_over_rank3"]) for move in ("insert","delete")}
    slopes={}
    x=np.log(np.array([64.0,144.0,256.0]))
    for move in ("insert","delete"):
        y=np.log(np.array([float(case_by_n[n]["latency"][move]["rank3"][
            "median_ns"]) for n in (64,144,256)]))
        slopes[move]=float(np.polyfit(x,y,1)[0])
    speedup_pass=all(value>2.0 for value in speedup_n144.values())
    slope_pass=all(math.isfinite(value) and value<=2.7
                   for value in slopes.values())
    resource=_resource_evidence(_safe_relative(
        root,info["resource_output"],"benchmark resource"))
    log_hashes={}
    for key in ("stdout","stderr"):
        path=_safe_relative(root,info[key],f"benchmark {key}")
        _need(path.is_file(),f"benchmark {key} missing")
        log_hashes[key]=sha_file(path)
    preflight=root/"benchmark"/"preflight.log"
    _need(preflight.is_file(),"benchmark preflight log missing")
    passed=correctness and fallback and case_checks and speedup_pass and slope_pass
    return {"pass":passed,"correctness_pass":correctness and case_checks,
      "fallback_pass":fallback,"speedup_N144":speedup_n144,
      "speedup_pass":speedup_pass,"rank3_loglog_slopes_N64_144_256":slopes,
      "slope_max":2.7,"slope_pass":slope_pass,
      "manifest_sha256":sha_file(manifest_path),
      "output_sha256":sha_file(output),"resource":resource,
      "log_sha256":log_hashes,"preflight_sha256":sha_file(preflight)}

def _normalize_slurm_id(value: Any) -> Optional[str]:
    if isinstance(value,bool):
        return None
    if isinstance(value,int):
        return str(value) if value>=0 else None
    if isinstance(value,str) and value and value.isascii() and value.isdecimal():
        return value
    return None

def audit_provenance(root: Path, index: Mapping[str,Any],
                     write_complete: bool=False) -> Mapping[str,Any]:
    _require_gate(root,"G3")
    checks={"source_snapshot":source_snapshot()==index["source_snapshot"],
            "environment":environment_snapshot()==index["environment"]}
    chains=[]; jobs=set()
    for entry in index["entries"]:
        result=_load_chain(root,entry); output=root/entry["output"]
        execution=result.get("execution_environment",{})
        expected=index["environment"]
        env_ok=all(execution.get(key)==expected.get(key) for key in (
            "python_executable","python_version","numpy_version","scipy_version"))
        slurm=execution.get("slurm",{})
        job_id=_normalize_slurm_id(slurm.get("job_id"))
        task_id=_normalize_slurm_id(slurm.get("array_task_id"))
        job_ok=job_id is not None and task_id is not None
        _need((output/"runner.stdout").is_file() and
              (output/"runner.stderr").is_file() and
              (output/"preflight.log").is_file(),"runner/preflight logs missing")
        resource=_resource_evidence(output/"resource.tsv")
        checks[f"{entry['stage']}:{entry['cell_id']}:c{entry['chain_id']}"] = (
            env_ok and job_ok)
        if job_ok:
            jobs.add((job_id,task_id))
        chains.append({"stage":entry["stage"],"cell_id":entry["cell_id"],
          "chain_id":entry["chain_id"],"result_sha256":sha_file(output/"result.json"),
          "chain_complete_sha256":sha_file(output/"CHAIN_COMPLETE"),
          "runner_stdout_sha256":sha_file(output/"runner.stdout"),
          "runner_stderr_sha256":sha_file(output/"runner.stderr"),
          "preflight_sha256":sha_file(output/"preflight.log"),
          "resource":resource,"slurm_job_id":job_id,"array_task_id":task_id})
    passed=all(checks.values()) and len(chains)==112 and len(jobs)==112
    report=_gate(root,"G4",{"status":"PASS" if passed else "INCONCLUSIVE",
      "stage":"provenance","checks":checks,"chains":chains,
      "distinct_slurm_array_tasks":len(jobs),
      "provenance_reconstruction":
      "separate same-implementation provenance audit; does not query sacct or independently recompute scientific observables; checks source, environment, reported Slurm IDs, logs, resources, manifests, and result hashes"})
    if write_complete and passed:
        write_protocol_complete(root)
    return report

def pilot_resource_gate(root: Path, entries: Sequence[Mapping[str,Any]],
                        cells: Mapping[str,Any]) -> Mapping[str,Any]:
    grouped={}; records=[]; passed=True
    for entry in entries:
        output=root/entry["output"]
        try:
            evidence=_resource_evidence(output/"resource.tsv")
            for name in ("runner.stdout","runner.stderr","preflight.log"):
                _need((output/name).is_file(),f"pilot {name} missing")
            result=load_json(output/"result.json")
            result_wall=float(result.get("timing",{}).get("wall_seconds",math.nan))
            result_rss=int(result.get("resource_usage",{}).get("max_rss_kb",0))
            wall=sum(map(float,evidence["elapsed_seconds"]))
            rss=max([result_rss,*map(int,evidence["max_rss_kb"])])
            _need(math.isfinite(result_wall) and result_wall>0 and
                  math.isfinite(wall) and wall>0 and rss>0,
                  "pilot nonfinite resource")
            grouped.setdefault(int(entry["N"]),{"wall":[],"rss":[]})
            grouped[int(entry["N"])]["wall"].append(wall)
            grouped[int(entry["N"])]["rss"].append(rss)
            records.append({"cell_id":entry["cell_id"],"chain_id":entry["chain_id"],
              "wall_seconds_all_attempts":wall,"result_wall_seconds":result_wall,
              "max_rss_kb":rss,"resource":evidence})
        except (ProtocolError,OSError,ValueError,TypeError) as exc:
            passed=False; records.append({"cell_id":entry["cell_id"],
              "chain_id":entry["chain_id"],"error":str(exc)})
    medians={}
    for n_sites in (16,64,144):
        values=grouped.get(n_sites,{"wall":[],"rss":[]})
        if len(values["wall"])!=4 or len(values["rss"])!=4:
            passed=False; continue
        medians[str(n_sites)]={"wall_seconds":float(statistics.median(values["wall"])),
          "max_rss_kb":float(statistics.median(values["rss"]))}
    memory_exponent=wall_exponent=math.inf; projection={}
    if all(str(n) in medians for n in (64,144)):
        ratio=144.0/64.0
        memory_exponent=math.log(medians["144"]["max_rss_kb"]/
                                 medians["64"]["max_rss_kb"])/math.log(ratio)
        wall_exponent=math.log(medians["144"]["wall_seconds"]/
                               medians["64"]["wall_seconds"])/math.log(ratio)
        nratio=256.0/144.0
        projected_wall=1.5*medians["144"]["wall_seconds"]*nratio**max(0.0,wall_exponent)
        projected_rss=1.5*medians["144"]["max_rss_kb"]*nratio**max(0.0,memory_exponent)
        projection={"N":256,"safety_factor":1.5,"wall_seconds":projected_wall,
          "max_rss_kb":projected_rss,
          "current_4h_sufficient":projected_wall<=14400,
          "current_8G_sufficient":projected_rss<=8*1024*1024,
          "advisory_only_no_preregistered_wall_or_memory_limit":True}
    memory_pass=math.isfinite(memory_exponent) and memory_exponent<=2.5
    warmup={}; warmup_pass=True
    by_cell={x["cell_id"]:x for x in entries}
    for cell_id,cell in cells.items():
        taus=[float(tau) for diagnostic in cell["diagnostics"].values()
              for tau in diagnostic["tau_int_by_original_chain"]]
        maximum=max(taus); manifest=load_json(root/by_cell[cell_id]["manifest"])
        warmup_steps=int(manifest["monte_carlo"]["warmup"])
        measure_every=int(manifest["monte_carlo"]["measure_every"])
        required=50.0*maximum*measure_every
        cell_pass=math.isfinite(maximum) and warmup_steps>=required
        warmup_pass=warmup_pass and cell_pass
        warmup[cell_id]={"max_tau_int_measurements":maximum,
          "measure_every":measure_every,"warmup_steps":warmup_steps,
          "required_warmup_steps":required,"pass":cell_pass}
    passed=passed and memory_pass and warmup_pass
    return {"pass":passed,"chain_records":records,"median_by_N":medians,
      "memory_loglog_exponent_N64_144":memory_exponent,
      "memory_exponent_max":2.5,"memory_scaling_pass":memory_pass,
      "wall_loglog_exponent_N64_144":wall_exponent,
      "warmup_rule":"warmup_steps >= 50*max_tau_int_measurements*measure_every",
      "warmup":warmup,"warmup_pass":warmup_pass,
      "conservative_L16_projection":projection}

def audit(root: Path, stage: str, write_complete: bool=False) -> Mapping[str,Any]:
    root=Path(root); index=verify_materialization(root)
    thresholds=load_json(root/"confirmed_meta_manifest.json")["thresholds"]
    _require_gate(root,"G0")
    if stage=="provenance":
        return audit_provenance(root,index,write_complete)
    if stage in {"pilot","full"}: _require_gate(root,"G1")
    if stage=="full": _require_gate(root,"G2")
    if stage=="g1":
        entries=[x for x in index["entries"] if x["stage"]=="g1"]
        name="G1"; arange=thresholds["full_acceptance_hard_range"]
    elif stage=="pilot":
        entries=[x for x in index["entries"] if x["stage"]=="production" and x["pilot"]]
        name="G2"; arange=thresholds["pilot_acceptance_target"]
    elif stage=="full":
        entries=[x for x in index["entries"] if x["stage"]=="production"]
        name="G3"; arange=thresholds["full_acceptance_hard_range"]
    else:
        raise ProtocolError("bad audit stage")
    grouped={}; metadata={}; cell_entries={}
    for entry in entries:
        grouped.setdefault(entry["cell_id"],[]).append(_load_chain(root,entry))
        metadata.setdefault(entry["cell_id"],entry)
        cell_entries.setdefault(entry["cell_id"],[]).append(entry)
    cells={}
    for cell_id,results in grouped.items():
        first=metadata[cell_id]
        cell=summarize_cell(results,float(first["beta"]),int(first["N"]),
                            thresholds,arange)
        if stage=="g1":
            exact_path=root/"exact"/"g1"/f"{cell_id}.json"
            _need(exact_path.is_file(),f"missing ED {exact_path}")
            exact=load_json(exact_path)
            validate_ed_binding(root,cell_entries[cell_id],exact)
            cell["exact_ed_sha256"]=sha_file(exact_path)
            cell["ed"]=compare_ed(cell,exact,float(thresholds["ed_z_score_max"]))
            cell["pass"]=cell["pass"] and cell["ed"]["pass"]
        cells[cell_id]=cell
    chain_cells_pass=bool(cells) and all(x["pass"] for x in cells.values())
    passed=chain_cells_pass; limits=[]; benchmark=None; resources=None
    if stage=="pilot":
        try:
            benchmark=validate_kernel_benchmark(root,index)
        except (ProtocolError,KeyError,TypeError,ValueError) as exc:
            benchmark={"pass":False,"validation_error":str(exc)}
        resources=pilot_resource_gate(root,entries,cells)
        passed=(chain_cells_pass and bool(benchmark.get("pass")) and
                bool(resources.get("pass")))
        if not benchmark.get("pass"):
            limits.append("kernel benchmark gate did not pass")
        if not resources.get("pass"):
            limits.append("pilot resource/warmup/scaling gate did not pass")
    return _gate(root,name,{"status":"PASS" if passed else "INCONCLUSIVE",
      "stage":stage,"cells":cells,"chain_cells_pass":chain_cells_pass,
      "all_cells_pass":passed,"kernel_benchmark":benchmark,
      "resource_gate":resources,"evidence_limits":limits,
      "diagnostic_method":DIAGNOSTIC_METHOD})

def write_protocol_complete(root: Path) -> Mapping[str,Any]:
    root=Path(root)
    _need(not (root/"COMPLETE").exists(),"refuse COMPLETE overwrite")
    index=verify_materialization(root); hashes={}
    for name in ("G0","G1","G2","G3","G4"):
        _require_gate(root,name); hashes[name]=sha_file(root/"gates"/f"{name}.json")
    payload={"schema_version":1,"protocol_id":PROTOCOL_ID,"status":"complete",
      "index_sha256":sha_file(root/"index.json"),
      "meta_manifest_sha256":index["meta_manifest_sha256"],
      "gate_report_sha256":hashes,
      "claim_boundary":("mu=0 finite-temperature scaling only; no finite-density ground-state or rapid-mixing claim; "
        "G4 is a separate same-implementation provenance audit without sacct verification or independent scientific recomputation")}
    write_json(root/"COMPLETE",payload,True); return payload

def _execution(args: argparse.Namespace) -> Mapping[str,Any]:
    value=json.loads(json.dumps(DEFAULT_EXECUTION))
    for stage in ("g1","production"):
        for key in ("steps","warmup","measure_every","checkpoint_every","rebuild_every"):
            override=getattr(args,f"{stage}_{key}",None)
            if override is not None: value[stage][key]=override
    return value

def main(argv: Optional[Sequence[str]]=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    make=sub.add_parser("materialize")
    make.add_argument("--meta",type=Path,required=True)
    make.add_argument("--output",type=Path,required=True)
    for stage in ("g1","production"):
        for key in ("steps","warmup","measure_every","checkpoint_every","rebuild_every"):
            make.add_argument(f"--{stage}-{key.replace('_','-')}",
                              dest=f"{stage}_{key}",type=int)
    check=sub.add_parser("validate"); check.add_argument("--root",type=Path,required=True)
    g0=sub.add_parser("record-g0"); g0.add_argument("--root",type=Path,required=True)
    g0.add_argument("--tests-exit-code",type=int,required=True)
    inspect=sub.add_parser("audit"); inspect.add_argument("--root",type=Path,required=True)
    inspect.add_argument("--stage",choices=("g1","pilot","full","provenance"),required=True)
    inspect.add_argument("--write-complete",action="store_true")
    args=parser.parse_args(argv)
    if args.command=="materialize":
        result=materialize(args.meta,args.output,_execution(args))
    elif args.command=="validate":
        result=verify_materialization(args.root)
    elif args.command=="record-g0":
        result=record_g0(args.root,args.tests_exit_code)
    else:
        result=audit(args.root,args.stage,args.write_complete)
    print(json.dumps({"protocol_id":PROTOCOL_ID,"command":args.command,
                      "status":result.get("status","ok")},
                     sort_keys=True,allow_nan=False),flush=True)
    return 2 if args.command=="audit" and result.get("status")!="PASS" else 0

def environment_snapshot() -> Mapping[str,Any]:
    # Preserve the invoked venv entry point; resolving it drops venv site-packages.
    executable=Path(os.path.abspath(sys.executable))
    _need(executable.is_absolute() and executable.is_file(),
          "validated Python executable is unavailable")
    versions={}
    for package in ("numpy","scipy","pytest"):
        try:
            versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ProtocolError(f"validated environment lacks {package}") from exc
    return {
      "python_executable":str(executable),
      "python_version":platform.python_version(),
      "python_implementation":platform.python_implementation(),
      "numpy_version":versions["numpy"],"scipy_version":versions["scipy"],
      "pytest_version":versions["pytest"]}

def _git_output(*args: str) -> str:
    try:
        result=subprocess.run(
            ("git",*args),cwd=SOLUTION_DIR,check=True,text=True,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    except (OSError,subprocess.CalledProcessError) as exc:
        raise ProtocolError("cannot capture git provenance") from exc
    return result.stdout.strip()

def source_snapshot() -> Mapping[str,Any]:
    files={}
    for name in SOURCE_FILES:
        path=SOLUTION_DIR/name
        _need(path.is_file(),f"source artifact missing: {name}")
        files[name]=sha_file(path)
    status=_git_output("status","--porcelain","--",*[str(SOLUTION_DIR/name)
                         for name in SOURCE_FILES])
    return {"git_commit":_git_output("rev-parse","HEAD"),
            "tracked_files_sha256":files,
            "source_files_dirty":bool(status)}

def _safe_relative(root: Path, raw: Any, label: str) -> Path:
    _need(isinstance(raw,str) and raw and not Path(raw).is_absolute(),
          f"{label} path invalid")
    root_resolved=Path(root).resolve()
    candidate=(root_resolved/raw).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ProtocolError(f"{label} path escapes root") from exc
    return candidate

def _task_table_bytes(entries: Sequence[Mapping[str,Any]]) -> bytes:
    lines=["task_id\tstage\tcell_id\tchain_id\tmanifest\toutput"]
    for i,x in enumerate(entries):
        lines.append("\t".join(map(str,(i,x["stage"],x["cell_id"],x["chain_id"],
                                       x["manifest"],x["output"]))))
    return ("\n".join(lines)+"\n").encode()

if __name__=="__main__":
    raise SystemExit(main())
