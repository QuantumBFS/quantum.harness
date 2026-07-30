#!/usr/bin/env python3
"""Hash-bound outer protocol for the confirmed issue-121 lattice benchmark.

Chain-local COMPLETE files only prove a runner exited normally.  Only this outer
protocol writes the materialized root COMPLETE, after G0--G4 all have PASS
records.  JSON is canonical and forbids NaN/Infinity.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import statistics
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import numpy as np

PROTOCOL_ID = "issue121-triangular-large-lattice-v1"
SOLUTION_DIR = Path(__file__).resolve().parent
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
        value=float(actual)
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
    lines=["task_id\tstage\tcell_id\tchain_id\tmanifest\toutput"]
    for i,x in enumerate(entries):
        lines.append("\t".join(map(str,(i,x["stage"],x["cell_id"],x["chain_id"],
                                       x["manifest"],x["output"]))))
    write_bytes(path,("\n".join(lines)+"\n").encode())

def _array_script(table: str, count: int) -> str:
    return f"""#!/bin/bash
#SBATCH --job-name=i121-{table.replace("_tasks.tsv","")}
#SBATCH --array=0-{count-1}%8
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd -P)
SOLUTION_DIR=${{SOLUTION_DIR:-{SOLUTION_DIR}}}
PYTHON_BIN=${{PYTHON_BIN:-python3}}
line=$(sed -n "$((SLURM_ARRAY_TASK_ID+2))p" "$ROOT/{table}")
IFS=$'\\t' read -r task stage cell chain manifest_rel output_rel <<< "$line"
output="$ROOT/$output_rel"; mkdir -p "$output"
/usr/bin/time -f 'elapsed_seconds\\t%e\\nmax_rss_kb\\t%M' -o "$output/resource.tsv" \\
 "$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_ctqmc.py" \\
 --manifest "$ROOT/$manifest_rel" --output "$output" \\
 >"$output/runner.stdout" 2>"$output/runner.stderr"
""".replace("$","$")

def _audit_script(stage: str) -> str:
    ed=""
    if stage=="g1":
        ed="""while IFS=$'\\t' read -r cell manifest_rel exact_rel; do
 [[ "$cell" == cell_id ]] && continue
 exact="$ROOT/$exact_rel"; mkdir -p "$(dirname "$exact")"
 [[ -f "$exact" ]] || "$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_ed.py" --manifest "$ROOT/$manifest_rel" --output "$exact"
done < "$ROOT/ed_tasks.tsv"
""".replace("$","$")
    flag=" --write-complete" if stage=="full" else ""
    return f"""#!/bin/bash
#SBATCH --job-name=i121-audit-{stage}
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd -P)
SOLUTION_DIR=${{SOLUTION_DIR:-{SOLUTION_DIR}}}
PYTHON_BIN=${{PYTHON_BIN:-python3}}
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
ap=$(sbatch --parsable --dependency=afterok:$p "$H/audit_pilot.sbatch")
f=$(sbatch --parsable --dependency=afterok:$ap "$H/run_full_array.sbatch")
af=$(sbatch --parsable --dependency=afterok:$f "$H/audit_full.sbatch")
printf 'G0=%s G1=%s G1audit=%s pilot=%s pilotaudit=%s full=%s final=%s\\n' "$g0" "$g1" "$a1" "$p" "$ap" "$f" "$af"
""".replace("$","$")

def materialize(meta_path: Path, root: Path,
                execution: Optional[Mapping[str,Any]]=None) -> Mapping[str,Any]:
    meta=load_json(meta_path); validate_meta(meta)
    selected=json.loads(json.dumps(execution or DEFAULT_EXECUTION))
    validate_execution(selected)
    root=Path(root)
    _need(not root.exists() or not any(root.iterdir()),"output must be empty")
    root.mkdir(parents=True,exist_ok=True)
    meta_raw=canonical_bytes(meta); meta_hash=sha_bytes(meta_raw)
    write_bytes(root/"confirmed_meta_manifest.json",meta_raw,True)
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
    pilot=[x for x in prod if x["pilot"]]; remaining=[x for x in prod if not x["pilot"]]
    _need(tuple(map(len,(g1,prod,pilot,remaining)))==(32,80,12,68),
          "task cardinality")
    _task_table(root/"g1_tasks.tsv",g1); _task_table(root/"pilot_tasks.tsv",pilot)
    _task_table(root/"full_tasks.tsv",remaining)
    ed=["cell_id\tmanifest\texact_output"]
    for x in g1:
        if x["chain_id"]==0:
            ed.append(f'{x["cell_id"]}\t{x["manifest"]}\texact/g1/{x["cell_id"]}.json')
    write_bytes(root/"ed_tasks.tsv",("\n".join(ed)+"\n").encode())
    index={"schema_version":1,"protocol_id":PROTOCOL_ID,
      "status":"materialized_not_run","meta_manifest_sha256":meta_hash,
      "execution":selected,"diagnostic_method":DIAGNOSTIC_METHOD,
      "counts":{"g1_chains":32,"production_chains":80,
                "pilot_chains":12,"full_remaining_chains":68},
      "entries":entries,
      "claim_boundary":"materialization is not compute evidence; no root COMPLETE"}
    raw=canonical_bytes(index); write_bytes(root/"index.json",raw,True)
    write_bytes(root/"index.sha256",(sha_bytes(raw)+"  index.json\n").encode(),True)
    scripts={"run_g1_array.sbatch":_array_script("g1_tasks.tsv",32),
      "run_pilot_array.sbatch":_array_script("pilot_tasks.tsv",12),
      "run_full_array.sbatch":_array_script("full_tasks.tsv",68),
      "audit_g1.sbatch":_audit_script("g1"),
      "audit_pilot.sbatch":_audit_script("pilot"),
      "audit_full.sbatch":_audit_script("full"),
      "submit_after_live_cluster_check.sh":_submit_script(),
      "run_g0.sbatch":f"""#!/bin/bash
#SBATCH --job-name=i121-g0
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd -P)
SOLUTION_DIR=${{SOLUTION_DIR:-{SOLUTION_DIR}}}
PYTHON_BIN=${{PYTHON_BIN:-python3}}
"$PYTHON_BIN" -m pytest -q "$SOLUTION_DIR/test_large_lattice_protocol.py" "$SOLUTION_DIR/test_large_lattice_ctqmc.py" -m 'not slow'
"$PYTHON_BIN" "$SOLUTION_DIR/large_lattice_protocol.py" record-g0 --root "$ROOT" --tests-exit-code 0
""".replace("$","$")}
    for name,text in scripts.items():
        write_bytes(root/"slurm"/name,text.encode(),True); os.chmod(root/"slurm"/name,0o755)
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

def verify_materialization(root: Path) -> Mapping[str,Any]:
    root=Path(root); index=load_json(root/"index.json")
    _need(index.get("protocol_id")==PROTOCOL_ID,"index protocol")
    expected=(root/"index.sha256").read_text(encoding="ascii").split()[0]
    _need(expected==sha_file(root/"index.json"),"index hash")
    meta=load_json(root/"confirmed_meta_manifest.json"); validate_meta(meta)
    _need(sha_bytes(canonical_bytes(meta))==index["meta_manifest_sha256"],
          "meta hash")
    for entry in index.get("entries",()):
        path=root/entry["manifest"]
        _need(path.is_file() and sha_file(path)==entry["manifest_sha256"],
              f"manifest hash: {path}")
    return index

def _load_chain(root: Path, entry: Mapping[str,Any]) -> Mapping[str,Any]:
    manifest_path=root/entry["manifest"]; output=root/entry["output"]
    result_path=output/"result.json"; done_path=output/"COMPLETE"
    _need(result_path.is_file() and done_path.is_file(),
          f"missing chain {entry['cell_id']}/c{entry['chain_id']}")
    manifest=load_json(manifest_path); result=load_json(result_path)
    done=load_json(done_path); digest=entry["manifest_sha256"]
    _need(sha_file(manifest_path)==digest,"manifest drift")
    _need(result.get("manifest_sha256")==digest and
          done.get("manifest_sha256")==digest,"result binding")
    _need(done.get("result_json_sha256")==sha_file(result_path),"result hash")
    _need(result.get("status")=="complete","chain status")
    _need(result.get("completed_steps")==manifest["monte_carlo"]["steps"],
          "step count")
    _need(result.get("geometry",{}).get("n_sites")==entry["N"],"geometry")
    _need(result.get("initialization")==entry["initialization"],"initialization")
    _need(result.get("observables",{}).get("count",0)>0,"no measurements")
    canonical_bytes(result)
    return result

def _momentum(results: Sequence[Mapping[str,Any]]) -> Mapping[str,Any]:
    total=sum(int(x["observables"]["count"]) for x in results); out={}
    for momentum in results[0]["observables"].get("momentum",{}):
        out[momentum]={}
        for name in ("one_body","density_raw","density_mode"):
            pairs=[x["observables"]["momentum"][momentum][name]["mean"]
                   for x in results]
            weights=[int(x["observables"]["count"]) for x in results]
            mean=[sum(w*float(p[i]) for w,p in zip(weights,pairs))/total
                  for i in (0,1)]
            out[momentum][name]={"mean":mean,"chain_means":pairs}
        raw=out[momentum]["density_raw"]["mean"]
        mode=out[momentum]["density_mode"]["mean"]
        out[momentum]["density_connected_from_means"]=[
            raw[0]-mode[0]**2-mode[1]**2,raw[1]]
    return out

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
    attempted=accepted=zeros=0
    keys=("delta_logdet","relative_T_drift_inf","relative_Q_drift_inf",
          "fast_inverse_residual_inf","rebuilt_inverse_residual_inf")
    values={key:[] for key in keys}
    for result in results:
        moves=result["counters"]["moves"]
        for name in ("insert","delete"):
            attempted+=int(moves[name]["attempted"])
            accepted+=int(moves[name]["accepted"])
        zeros+=int(result["counters"].get("zero_weight_rejections",0))
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
      "acceptance":{"attempted":attempted,"accepted":accepted,"rate":acceptance,
                    "required_range":list(acceptance_range),"pass":accept},
      "rebuild":{"maxima":maxima,"pass":rebuild},
      "positivity":{"zero_weight_count":zeros,"negative_sign_count":0,
        "negative_count_provenance":
        "successful strict-support runner; negatives abort before chain COMPLETE",
        "pass":zeros==0},
      "pass":convergence and rebuild and accept and zeros==0}

def _mean_se(pairs: Sequence[Sequence[float]], component: int) -> float:
    values=np.array([float(x[component]) for x in pairs])
    return float(np.std(values,ddof=1)/math.sqrt(len(values)))

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
    momentum={}
    for key,reference in exact["observables"].get("momentum",{}).items():
        if key not in cell["momentum"]:
            momentum[key]={"pass":False,"reason":"missing momentum"}; continue
        item={}
        for name in ("one_body","density_raw","density_mode"):
            sampled=cell["momentum"][key][name]
            se=max(_mean_se(sampled["chain_means"],i) for i in (0,1))
            allowance=max(zmax*se,1e-10)
            error=max(abs(float(sampled["mean"][i])-float(reference[name][i]))
                      for i in (0,1))
            item[name]={"max_abs_error":error,
                        "mcse_from_four_chain_means":se,
                        "allowance":allowance,"pass":error<=allowance}
        item["pass"]=all(v["pass"] for k,v in item.items() if k!="pass")
        momentum[key]=item
    return {"scalar":scalar,"momentum":momentum,
      "momentum_mcse_note":"SE across four chain means; core stores no momentum traces",
      "pass":all(x["pass"] for x in scalar.values()) and
             all(x["pass"] for x in momentum.values())}

def _gate(root: Path, name: str, payload: Mapping[str,Any]) -> Mapping[str,Any]:
    record={"schema_version":1,"protocol_id":PROTOCOL_ID,"gate":name,**payload}
    write_json(Path(root)/"gates"/f"{name}.json",record); return record

def record_g0(root: Path, code: int) -> Mapping[str,Any]:
    verify_materialization(root)
    return _gate(root,"G0",{"status":"PASS" if code==0 else "FAIL",
      "tests_exit_code":code,"index_sha256":sha_file(Path(root)/"index.json")})

def _require_gate(root: Path, name: str) -> Mapping[str,Any]:
    value=load_json(Path(root)/"gates"/f"{name}.json")
    _need(value.get("protocol_id")==PROTOCOL_ID and value.get("gate")==name and
          value.get("status")=="PASS",f"required {name} not PASS")
    return value

def audit(root: Path, stage: str, write_complete: bool=False) -> Mapping[str,Any]:
    root=Path(root); index=verify_materialization(root)
    thresholds=load_json(root/"confirmed_meta_manifest.json")["thresholds"]
    _require_gate(root,"G0")
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
    grouped={}; metadata={}
    for entry in entries:
        grouped.setdefault(entry["cell_id"],[]).append(_load_chain(root,entry))
        metadata.setdefault(entry["cell_id"],entry)
    cells={}
    for cell_id,results in grouped.items():
        first=metadata[cell_id]
        cell=summarize_cell(results,float(first["beta"]),int(first["N"]),
                            thresholds,arange)
        if stage=="g1":
            exact=root/"exact"/"g1"/f"{cell_id}.json"
            _need(exact.is_file(),f"missing ED {exact}")
            cell["ed"]=compare_ed(cell,load_json(exact),
                                  float(thresholds["ed_z_score_max"]))
            cell["pass"]=cell["pass"] and cell["ed"]["pass"]
        cells[cell_id]=cell
    passed=bool(cells) and all(x["pass"] for x in cells.values())
    limits=[]
    if stage=="pilot":
        limits=["rank3-versus-rebuild kernel speedup unavailable from core v1"]
        passed=False
    report=_gate(root,name,{"status":"PASS" if passed else "INCONCLUSIVE",
      "stage":stage,"cells":cells,"all_cells_pass":passed,
      "evidence_limits":limits,"diagnostic_method":DIAGNOSTIC_METHOD,
      "index_sha256":sha_file(root/"index.json")})
    if stage=="full":
        _gate(root,"G4",{"status":"PASS" if passed else "INCONCLUSIVE",
          "provenance_reconstruction":
          "canonical manifests and all chain result hashes reverified",
          "index_sha256":sha_file(root/"index.json")})
        if write_complete and passed:
            write_protocol_complete(root)
    return report

def write_protocol_complete(root: Path) -> Mapping[str,Any]:
    root=Path(root); index=verify_materialization(root); hashes={}
    for name in ("G0","G1","G2","G3","G4"):
        _require_gate(root,name); hashes[name]=sha_file(root/"gates"/f"{name}.json")
    payload={"schema_version":1,"protocol_id":PROTOCOL_ID,"status":"complete",
      "index_sha256":sha_file(root/"index.json"),
      "meta_manifest_sha256":index["meta_manifest_sha256"],
      "gate_report_sha256":hashes,
      "claim_boundary":"mu=0 finite-temperature scaling only; no finite-density ground-state or rapid-mixing claim"}
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
    inspect.add_argument("--stage",choices=("g1","pilot","full"),required=True)
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

if __name__=="__main__":
    raise SystemExit(main())
