#!/usr/bin/env python3
"""Determinant-only CTQMC prototype for the triangular-lattice A/B model.

No 2**N Fock matrix is constructed. A resolved event stores a triangle id and
one of 12 local 3x3 templates (B,B^{-1}). The chronological word
(a_1,...,a_m) means T=B_m...B_1. Endpoint insertion is T'=BT.

With D=B-I, C=T(I+T)^{-1}=I-Q, and Q=(I+T)^{-1},

    K=I_3+D E^T C E,
    det(I+BT)/det(I+T)=det K,
    Q'=Q-Q E K^{-1}D E^T C.

K^{-1} is applied with solve, never formed. Deletion uses B^{-1}. Fixed
p_insert=p_delete leaves an attempted deletion at m=0 as a self-loop. Equal
left/right cyclic-rotation probabilities give unit acceptance.

For a nonempty word, let U be its touched sites and q=exp(-kappa*s). Choosing
the last factor touching each row gives T=I_(U^c) direct-sum T_U with
||T_U||_inf<=q<1. Hence det(I+T)>0. With fugacity z, the same proof is strict
for z*q<1, i.e. mu<kappa*s/beta; this window vanishes as beta tends to infinity
and is not a finite-density ground-state result.

This is an unrun, unaudited direct structured-product+dense-LU prototype.
Periodic rebuilding forms T in O(mN), then uses O(N^3) solve/slogdet and reports
an inverse residual. Primary traces are retained in memory and checkpoint JSON for
pilot audits, with O(number of measurements) memory; production needs chunked
storage. QR/UDT stabilization and production autocorrelation analysis are not
implemented and must not be claimed.
"""
from __future__ import annotations
import argparse, hashlib, importlib.metadata, itertools, json, math, os
import platform, sys, tempfile, time
from collections import deque
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Deque, Dict, List, Mapping, Optional, Sequence, Tuple
import numpy as np
from scipy.linalg import expm
try:
    import resource
except ImportError:  # pragma: no cover - non-POSIX portability
    resource=None

ALGORITHM_ID="triangular-ab-ctqmc-direct-lu-v1"
SCHEMA_VERSION=1
class ManifestError(ValueError): pass
class NumericalStabilityError(RuntimeError): pass
class DeterminantFailure(NumericalStabilityError):
    def __init__(self,kind:str,message:str)->None:
        super().__init__(message);self.kind=kind

@dataclass(frozen=True)
class Triangle:
    triangle_id:int
    sites:Tuple[int,int,int]
    orientation:str
    anchor:Tuple[int,int]

@dataclass(frozen=True)
class TriangularGeometry:
    Lx:int
    Ly:int
    coordinates:np.ndarray
    triangles:Tuple[Triangle,...]
    @property
    def n_sites(self)->int: return self.Lx*self.Ly
    @property
    def n_triangles(self)->int: return len(self.triangles)

@dataclass(frozen=True)
class LocalVertex:
    vertex_id:int
    family:str
    permutation:Tuple[int,int,int]
    block:np.ndarray
    block_inv:np.ndarray
    activity:float

@dataclass(frozen=True)
class Event:
    triangle_id:int
    vertex_id:int
    def to_json(self)->List[int]: return [self.triangle_id,self.vertex_id]
    @staticmethod
    def from_json(value:Sequence[int])->"Event":
        if len(value)!=2: raise ManifestError("event must be [triangle_id,vertex_id]")
        return Event(int(value[0]),int(value[1]))

@dataclass
class DenseFactors:
    T:np.ndarray
    Q:np.ndarray
    logdet:float
    inverse_residual_inf:float  # NaN after unchecked fast updates; rebuilt exactly

@dataclass
class LowRankProposal:
    T_new:Optional[np.ndarray]
    Q_new:Optional[np.ndarray]
    logdet_new:float
    log_det_ratio:float
    condition:float
    local_solve_residual_inf:float
    needs_rebuild:bool=False
    zero_weight:bool=False
    used_dense_fallback:bool=False

def _real(value:Any,name:str)->float:
    try: result=float(Fraction(value)) if isinstance(value,str) else float(value)
    except (TypeError,ValueError,ZeroDivisionError) as exc: raise ManifestError(f"invalid {name}") from exc
    if not math.isfinite(result): raise ManifestError(f"{name} must be finite")
    return result

def _integer(obj:Mapping[str,Any],key:str,lower:int)->int:
    value=obj.get(key)
    if isinstance(value,bool) or not isinstance(value,int) or value<lower:
        raise ManifestError(f"{key} must be integer >= {lower}")
    return value

def build_triangular_geometry(Lx:int,Ly:int)->TriangularGeometry:
    """Periodic up/down elementary triangles on an Lx by Ly torus."""
    if Lx<2 or Ly<2: raise ManifestError("Lx,Ly must be >=2")
    site=lambda x,y:(x%Lx)*Ly+(y%Ly)
    coords=np.empty((Lx*Ly,2),dtype=float); triangles:List[Triangle]=[]
    for x in range(Lx):
        for y in range(Ly):
            coords[site(x,y)]=(x,y)
            r,ex,ey,exy=site(x,y),site(x+1,y),site(x,y+1),site(x+1,y+1)
            triangles.append(Triangle(len(triangles),(r,ex,ey),"up",(x,y)))
            triangles.append(Triangle(len(triangles),(exy,ex,ey),"down",(x,y)))
    return TriangularGeometry(Lx,Ly,coords,tuple(triangles))

def build_vertex_catalog(epsilon:float,kappa:float,s:float,g_A:float,g_B:float)->List[LocalVertex]:
    """Exactly 12 templates: A/B times all six S3 permutations."""
    if min(epsilon,kappa,s)<=0 or min(g_A,g_B)<0 or g_A+g_B<=0:
        raise ManifestError("invalid positive model parameters")
    A=np.array([[-1-epsilon-kappa,1,-epsilon],[0,-1-kappa,1],[2,0,-2-kappa]],dtype=float)
    S=np.diag([1.0,1.0,-1.0]); result:List[LocalVertex]=[]
    for family,generator,coupling in (("A",A,g_A),("B",S@A@S,g_B)):
        for perm in itertools.permutations(range(3)):
            P=np.eye(3)[list(perm)]; X=P@generator@P.T
            result.append(LocalVertex(len(result),family,tuple(perm),expm(s*X),expm(-s*X),coupling/6))
    assert len(result)==12
    return result

def _left(M:np.ndarray,sites:Sequence[int],B:np.ndarray)->np.ndarray:
    out=M.copy(); idx=list(sites); out[idx,:]=B@M[idx,:]; return out
def _right(M:np.ndarray,sites:Sequence[int],B:np.ndarray)->np.ndarray:
    out=M.copy(); idx=list(sites); out[:,idx]=M[:,idx]@B; return out

def structured_product(n_sites:int,triangles:Sequence[Triangle],
                       catalog:Sequence[LocalVertex],word:Sequence[Event])->np.ndarray:
    """O(mN) rebuild of T=B_m...B_1 by local row updates."""
    T=np.eye(n_sites)
    for event in word:
        tri,v=triangles[event.triangle_id],catalog[event.vertex_id]
        idx=list(tri.sites)
        T[idx,:]=v.block@T[idx,:]
    return T

def inverse_residual_inf(T:np.ndarray,Q:np.ndarray)->float:
    I=np.eye(T.shape[0]);A=I+T
    return float(np.linalg.norm(A@Q-I,np.inf)/max(1.0,np.linalg.norm(A,np.inf)))

def factor_dense(T:np.ndarray)->DenseFactors:
    I=np.eye(T.shape[0]);A=I+T;sign,logdet=np.linalg.slogdet(A)
    if sign==0:
        raise DeterminantFailure("zero","current det(I+T) is zero")
    if sign<0:
        raise DeterminantFailure("negative","current det(I+T) is negative")
    Q=np.linalg.solve(A,I)
    return DenseFactors(T,Q,float(logdet),inverse_residual_inf(T,Q))

def low_rank_left_proposal(factors:DenseFactors,sites:Sequence[int],block:np.ndarray,
                           condition_max:float=1e12)->LowRankProposal:
    """Rank-3 proposal for T'=BT using C=I-Q and a 3x3 solve."""
    idx=list(sites); D=block-np.eye(3)
    Crows=-factors.Q[idx,:].copy(); Crows[np.arange(3),idx]+=1.0
    QE=factors.Q[:,idx]; K=np.eye(3)+D@Crows[:,idx]
    sign,logratio=np.linalg.slogdet(K); condition=float(np.linalg.cond(K))
    if sign<=0 or not math.isfinite(condition) or condition>condition_max:
        return LowRankProposal(None,None,math.nan,math.nan,condition,math.inf,needs_rebuild=True)
    rhs=D@Crows; solved=np.linalg.solve(K,rhs)
    residual=float(np.linalg.norm(K@solved-rhs,np.inf)/max(1.0,np.linalg.norm(rhs,np.inf)))
    return LowRankProposal(_left(factors.T,idx,block),factors.Q-QE@solved,
                           factors.logdet+float(logratio),float(logratio),condition,residual)

def _dense_left_proposal(factors:DenseFactors,sites:Sequence[int],block:np.ndarray)->LowRankProposal:
    T=_left(factors.T,sites,block); A=np.eye(T.shape[0])+T
    sign,logdet=np.linalg.slogdet(A)
    if sign==0:
        raise DeterminantFailure(
            "zero","computed zero candidate contradicts the strict support bound")
    if sign<0:
        raise DeterminantFailure("negative","dense candidate determinant is negative")
    Q=np.linalg.solve(A,np.eye(T.shape[0]))
    residual=inverse_residual_inf(T,Q)
    return LowRankProposal(T,Q,float(logdet),float(logdet-factors.logdet),
                           float(np.linalg.cond(A)),residual,used_dense_fallback=True)

def apply_low_rank_proposal(factors:DenseFactors,proposal:LowRankProposal)->DenseFactors:
    if proposal.needs_rebuild or proposal.zero_weight: raise ValueError("unresolved proposal")
    assert proposal.T_new is not None and proposal.Q_new is not None
    residual=proposal.local_solve_residual_inf if proposal.used_dense_fallback else math.nan
    return DenseFactors(proposal.T_new,proposal.Q_new,proposal.logdet_new,residual)

def rotate_left_factor_to_right(factors:DenseFactors,event:Event,
                                triangles:Sequence[Triangle],
                                catalog:Sequence[LocalVertex])->DenseFactors:
    """Move product-left B_m to right: T'=B_m^-1 T B_m."""
    tri,v=triangles[event.triangle_id],catalog[event.vertex_id]
    T=_right(_left(factors.T,tri.sites,v.block_inv),tri.sites,v.block)
    Q=_right(_left(factors.Q,tri.sites,v.block_inv),tri.sites,v.block)
    return DenseFactors(T,Q,factors.logdet,factors.inverse_residual_inf)

def rotate_right_factor_to_left(factors:DenseFactors,event:Event,
                                triangles:Sequence[Triangle],
                                catalog:Sequence[LocalVertex])->DenseFactors:
    """Move product-right B_1 to left: T'=B_1 T B_1^-1."""
    tri,v=triangles[event.triangle_id],catalog[event.vertex_id]
    T=_right(_left(factors.T,tri.sites,v.block),tri.sites,v.block_inv)
    Q=_right(_left(factors.Q,tri.sites,v.block),tri.sites,v.block_inv)
    return DenseFactors(T,Q,factors.logdet,factors.inverse_residual_inf)

def log_accept_insert(beta:float,activity:float,order_before:int,log_det_ratio:float,
                      p_insert:float,p_delete:float,p_label:float)->float:
    """min(0,log[(beta*lambda/(m+1))*r*pdel/(pins*plabel)])."""
    return min(0.0,math.log(beta)+math.log(activity)-math.log(order_before+1)
               +log_det_ratio+math.log(p_delete)-math.log(p_insert)-math.log(p_label))

def log_accept_delete(beta:float,activity:float,order_before:int,log_det_ratio:float,
                      p_insert:float,p_delete:float,p_label:float)->float:
    """min(0,log[(m/(beta*lambda))*r*pins*plabel/pdel])."""
    if order_before<1: raise ValueError("delete requires m>=1")
    return min(0.0,math.log(order_before)-math.log(beta)-math.log(activity)
               +log_det_ratio+math.log(p_insert)+math.log(p_label)-math.log(p_delete))

def measure_configuration(factors:DenseFactors,geometry:TriangularGeometry,beta:float,
                          G0:float,order:int,momenta:Sequence[Tuple[int,int]],
                          displacements:Sequence[Tuple[int,int]]=())->Mapping[str,Any]:
    """Order, energy, N/N^2, and momentum/real-space equal-time correlators."""
    N=geometry.n_sites; R=np.eye(N)-factors.Q; green=R.T
    density=np.diag(green).copy()
    density_pair=np.outer(density,density)-green*green.T
    np.fill_diagonal(density_pair,density)
    number,number2=float(density.sum()),float(density_pair.sum())
    out:Dict[str,Any]={"order":float(order),"energy_density":float((G0-order/beta)/N),
      "particle_number":number,"particle_number_squared":number2,
      "particle_density":number/N,"particle_density_squared":number2/(N*N),
      "momenta":{},"real_space_green":{}}
    x,y=geometry.coordinates[:,0],geometry.coordinates[:,1]
    for kx,ky in momenta:
        phase=np.exp(2j*math.pi*(kx*x/geometry.Lx+ky*y/geometry.Ly))
        one=complex(np.vdot(phase,green@phase)/N)
        den=complex(np.vdot(phase,density_pair@phase)/N)
        rho=complex(np.vdot(phase,density)/math.sqrt(N))
        out["momenta"][f"{kx},{ky}"]={"one_body":[one.real,one.imag],
          "density_raw":[den.real,den.imag],"density_mode":[rho.real,rho.imag]}
    for dx,dy in displacements:
        total=0.0
        for sx in range(geometry.Lx):
            for sy in range(geometry.Ly):
                i=sx*geometry.Ly+sy
                j=((sx+dx)%geometry.Lx)*geometry.Ly+(sy+dy)%geometry.Ly
                total+=float(green[i,j])
        out["real_space_green"][f"{dx},{dy}"]=[total/N,0.0]
    return out

class ObservableAccumulator:
    KEYS=("order","energy_density","particle_number","particle_number_squared",
          "particle_density","particle_density_squared")
    def __init__(self)->None:
        self.count=0
        self.scalar={k:{"sum":0.0,"sum_sq":0.0} for k in self.KEYS}
        self.primary_traces={k:[] for k in self.KEYS}
        self.momentum:Dict[str,Any]={}
        self.real_space:Dict[str,Any]={}
    @staticmethod
    def _add_complex(target:Dict[str,Any],key:str,name:str,pair:Sequence[float])->None:
        slot=target.setdefault(key,{}).setdefault(
            name,{"sum_real":0.0,"sum_imag":0.0,"sum_abs_sq":0.0})
        real,imag=map(float,pair)
        slot["sum_real"]+=real;slot["sum_imag"]+=imag
        slot["sum_abs_sq"]+=real*real+imag*imag
    def add(self,obs:Mapping[str,Any])->None:
        self.count+=1
        for k in self.KEYS:
            value=float(obs[k]);self.scalar[k]["sum"]+=value
            self.scalar[k]["sum_sq"]+=value*value
            self.primary_traces[k].append(value)
        for momentum,values in obs["momenta"].items():
            for name,pair in values.items():
                self._add_complex(self.momentum,momentum,name,pair)
        for displacement,pair in obs.get("real_space_green",{}).items():
            self._add_complex(self.real_space,displacement,"one_body",pair)
    def state(self)->Mapping[str,Any]:
        return {"count":self.count,"scalar":self.scalar,
                "primary_traces":self.primary_traces,
                "momentum":self.momentum,"real_space_green":self.real_space}
    @classmethod
    def from_state(cls,state:Mapping[str,Any])->"ObservableAccumulator":
        obj=cls();obj.count=int(state.get("count",0))
        obj.scalar=state.get("scalar",obj.scalar)
        obj.primary_traces=state.get("primary_traces",obj.primary_traces)
        obj.momentum=state.get("momentum",{})
        obj.real_space=state.get("real_space_green",{})
        return obj
    @staticmethod
    def _complex_summary(values:Mapping[str,Any],count:int)->Mapping[str,Any]:
        result:Dict[str,Any]={}
        for key,components in values.items():
            result[key]={}
            for name,raw in components.items():
                mean=[raw["sum_real"]/count,raw["sum_imag"]/count]
                var=max(0.0,raw["sum_abs_sq"]/count-mean[0]**2-mean[1]**2)
                result[key][name]={"mean":mean,
                  "naive_stderr_abs":math.sqrt(var/count)}
        return result
    def summary(self,beta:float,n_sites:int)->Mapping[str,Any]:
        if not self.count:
            return {"count":0,"compressibility":None,
                    "primary_traces":self.primary_traces}
        scalar={}
        for k,raw in self.scalar.items():
            mean=raw["sum"]/self.count
            var=max(0.0,raw["sum_sq"]/self.count-mean*mean)
            scalar[k]={"mean":mean,"naive_stderr":math.sqrt(var/self.count)}
        momentum=self._complex_summary(self.momentum,self.count)
        real_space=self._complex_summary(self.real_space,self.count)
        for key in momentum:
            if "density_raw" in momentum[key] and "density_mode" in momentum[key]:
                raw=momentum[key]["density_raw"]["mean"]
                mode=momentum[key]["density_mode"]["mean"]
                momentum[key]["density_connected_from_means"]=[
                    raw[0]-mode[0]**2-mode[1]**2,raw[1]]
        mean_n=scalar["particle_number"]["mean"]
        mean_n2=scalar["particle_number_squared"]["mean"]
        compressibility=beta*(mean_n2-mean_n*mean_n)/n_sites
        return {"count":self.count,"scalar":scalar,
                "compressibility":compressibility,
                "primary_traces":self.primary_traces,
                "momentum":momentum,"real_space_green":real_space,
                "error_note":"naive iid errors; use primary_traces for tau_int/ESS/R-hat"}

def linux_max_rss_kb()->Optional[int]:
    if resource is None or not sys.platform.startswith("linux"):
        return None
    try:
        value=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except (AttributeError,OSError,ValueError):
        return None
    return value if value>=0 else None

def atomic_write_json(path:Path,payload:Mapping[str,Any])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix="."+path.name+".",suffix=".tmp",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            json.dump(payload,handle,indent=2,sort_keys=True,allow_nan=False)
            handle.write("\n")
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def execution_environment() -> Mapping[str,Any]:
    return {"python_executable":str(Path(sys.executable).resolve()),
      "python_version":platform.python_version(),
      "numpy_version":importlib.metadata.version("numpy"),
      "scipy_version":importlib.metadata.version("scipy"),
      "slurm":{"job_id":os.environ.get("SLURM_JOB_ID"),
               "array_job_id":os.environ.get("SLURM_ARRAY_JOB_ID"),
               "array_task_id":os.environ.get("SLURM_ARRAY_TASK_ID"),
               "cluster_name":os.environ.get("SLURM_CLUSTER_NAME")}}

def validate_existing_complete(output: Path, manifest_sha256: str,
                               expected_steps: int) -> Mapping[str,Any]:
    result_path=output/"result.json"; done_path=output/"CHAIN_COMPLETE"
    if not result_path.is_file() or not done_path.is_file():
        raise ManifestError("incomplete CHAIN_COMPLETE artifact set")
    result=json.loads(result_path.read_text()); done=json.loads(done_path.read_text())
    digest=hashlib.sha256(result_path.read_bytes()).hexdigest()
    for payload,label in ((result,"result"),(done,"CHAIN_COMPLETE")):
        if payload.get("algorithm_id")!=ALGORITHM_ID:
            raise ManifestError(f"{label} algorithm mismatch")
        if payload.get("status")!="run_complete_unvalidated":
            raise ManifestError(f"{label} status mismatch")
        if payload.get("scope")!="single_chain_execution_only":
            raise ManifestError(f"{label} scope mismatch")
        if payload.get("manifest_sha256")!=manifest_sha256:
            raise ManifestError(f"{label} manifest mismatch")
        if int(payload.get("completed_steps",-1))!=expected_steps:
            raise ManifestError(f"{label} step mismatch")
    if done.get("result_json_sha256")!=digest:
        raise ManifestError("CHAIN_COMPLETE result hash mismatch")
    return result

def archive_recoverable_failure(failed: Path) -> Path:
    payload=json.loads(failed.read_text())
    if payload.get("determinant_failure_kind") in ("zero","negative"):
        raise ManifestError("scientific determinant failure is immutable")
    raw=failed.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
    archive=failed.parent/"failures"/f"FAILED.{digest}.json"
    archive.parent.mkdir(parents=True,exist_ok=True)
    if archive.exists() and archive.read_bytes()!=raw:
        raise ManifestError("failure archive hash collision")
    if not archive.exists():
        os.replace(failed,archive)
    else:
        failed.unlink()
    return archive

class CTQMC:
    """Cyclic-word sampler; resume rebuilds dense factors from the word."""
    def __init__(self,geometry:TriangularGeometry,catalog:Sequence[LocalVertex],
                 model:Mapping[str,float],mc:Mapping[str,Any],
                 momenta:Sequence[Tuple[int,int]],
                 displacements:Sequence[Tuple[int,int]],output_dir:Path,
                 manifest_sha256:str)->None:
        self.geometry=geometry; self.catalog=list(catalog); self.model=dict(model)
        self.beta=model["beta"]; self.output_dir=Path(output_dir)
        self.manifest_sha256=manifest_sha256; self.steps=int(mc["steps"])
        self.warmup=int(mc["warmup"]); self.measure_every=int(mc["measure_every"])
        self.checkpoint_every=int(mc["checkpoint_every"]); self.rebuild_every=int(mc["rebuild_every"])
        self.condition_max=float(mc.get("woodbury_condition_max",1e12))
        self.moves=dict(mc["move_probabilities"]);self.momenta=tuple(momenta)
        self.displacements=tuple(displacements)
        self.initialization=dict(mc["initialization"])
        self.rng=np.random.Generator(np.random.PCG64DXSM(int(mc["seed"])))
        self.word:Deque[Event]=deque();self.completed_steps=0
        self.accumulator=ObservableAccumulator()
        self.G0=geometry.n_triangles*(model["g_A"]+model["g_B"])
        self.active=[v.vertex_id for v in catalog if v.activity>0]
        weights=np.array([catalog[i].activity for i in self.active])
        self.template_probabilities=weights/weights.sum()
        self.counters={"moves":{k:{"attempted":0,"accepted":0} for k in self.moves},
          "rank3_updates_accepted":0,"low_rank_rebuild_gates":0,
          "dense_candidate_fallbacks":0,"zero_weight_rejections":0,"rebuilds":0,
          "determinant_failures":{"zero":0,"negative":0}}
        self.rebuild_diagnostics:List[Mapping[str,Any]]=[];self.moves_since_rebuild=0
        if self.initialization["mode"]=="hot":
            for _ in range(self.initialization["initial_order"]):
                event,_=self._sample_event();self.word.append(event)
        initial_T=structured_product(self.geometry.n_sites,self.geometry.triangles,
                                     self.catalog,list(self.word))
        self.factors=factor_dense(initial_T)
        self._record("initial-"+self.initialization["mode"],
                     self.factors.inverse_residual_inf)
    @classmethod
    def from_manifest(cls,manifest:Mapping[str,Any],output_dir:Path,
                      manifest_sha256:str="unbound-in-memory")->"CTQMC":
        if int(manifest.get("schema_version",-1))!=SCHEMA_VERSION:
            raise ManifestError("schema_version must be 1")
        lat,mod,mc=manifest["lattice"],manifest["model"],manifest["monte_carlo"]
        geometry=build_triangular_geometry(_integer(lat,"Lx",2),_integer(lat,"Ly",2))
        model={k:_real(mod[k],"model."+k) for k in
               ("epsilon","kappa","vertex_strength","g_A","g_B","beta")}
        if model["beta"]<=0:raise ManifestError("beta must be positive")
        catalog=build_vertex_catalog(model["epsilon"],model["kappa"],model["vertex_strength"],
                                     model["g_A"],model["g_B"])
        lower={"steps":1,"warmup":0,"measure_every":1,"checkpoint_every":1,"rebuild_every":1,"seed":0}
        parsed={k:_integer(mc,k,v) for k,v in lower.items()}
        if parsed["warmup"]>=parsed["steps"]:raise ManifestError("warmup>=steps")
        parsed["woodbury_condition_max"]=_real(mc.get("woodbury_condition_max",1e12),"condition")
        default={"insert":.35,"delete":.35,"rotate_left_to_right":.15,"rotate_right_to_left":.15}
        supplied=mc.get("move_probabilities",default)
        moves={k:_real(supplied.get(k),"move."+k) for k in default}
        if min(moves.values())<=0 or abs(sum(moves.values())-1)>1e-12:
            raise ManifestError("move probabilities must be positive and sum to one")
        if abs(moves["insert"]-moves["delete"])>1e-15:
            raise ManifestError("prototype requires fixed p_insert=p_delete")
        if abs(moves["rotate_left_to_right"]-moves["rotate_right_to_left"])>1e-15:
            raise ManifestError("cyclic reverse probabilities must match")
        parsed["move_probabilities"]=moves
        initialization=mc.get("initialization",{"mode":"cold","initial_order":0})
        if not isinstance(initialization,Mapping):
            raise ManifestError("monte_carlo.initialization must be an object")
        mode=initialization.get("mode","cold")
        if mode not in ("cold","hot"):
            raise ManifestError("initialization.mode must be cold or hot")
        initial_order=_integer(initialization,"initial_order",0)
        if mode=="cold" and initial_order!=0:
            raise ManifestError("cold initialization requires initial_order=0")
        if mode=="hot" and initial_order<1:
            raise ManifestError("hot initialization requires initial_order>=1")
        parsed["initialization"]={"mode":mode,"initial_order":initial_order}
        measurements=manifest.get("measurements",{})
        raw=measurements.get("momenta",[[0,0]])
        momenta=[(int(k[0]),int(k[1])) for k in raw]
        raw_r=measurements.get("displacements",[[0,0],[1,0],[0,1]])
        displacements=[(int(r[0]),int(r[1])) for r in raw_r]
        return cls(geometry,catalog,model,parsed,momenta,displacements,
                   Path(output_dir),manifest_sha256)
    def _record(self,reason:str,fast_residual:Optional[float]=None,
                delta_logdet:Optional[float]=0.0,
                relative_T:Optional[float]=0.0,
                relative_Q:Optional[float]=0.0)->None:
        self.counters["rebuilds"]+=1
        rebuilt_residual=self.factors.inverse_residual_inf
        self.rebuild_diagnostics.append({"step":self.completed_steps,"reason":reason,
          "order":len(self.word),"fast_inverse_residual_inf":fast_residual,
          "rebuilt_inverse_residual_inf":rebuilt_residual,
          "delta_logdet":delta_logdet,
          "relative_T_drift_inf":relative_T,
          "relative_Q_drift_inf":relative_Q,
          "structured_row_work":3*len(self.word)*self.geometry.n_sites})
    def rebuild(self,reason:str,compare_fast:bool=True)->None:
        fast=self.factors
        fast_residual=inverse_residual_inf(fast.T,fast.Q) if compare_fast else None
        T=structured_product(self.geometry.n_sites,self.geometry.triangles,
                             self.catalog,list(self.word))
        rebuilt=factor_dense(T)
        if compare_fast:
            delta_logdet=float(rebuilt.logdet-fast.logdet)
            relative_T=float(np.linalg.norm(rebuilt.T-fast.T,np.inf)/
                             max(1.0,np.linalg.norm(rebuilt.T,np.inf)))
            relative_Q=float(np.linalg.norm(rebuilt.Q-fast.Q,np.inf)/
                             max(1.0,np.linalg.norm(rebuilt.Q,np.inf)))
        else:
            delta_logdet=relative_T=relative_Q=None
        self.factors=rebuilt;self.moves_since_rebuild=0
        self._record(reason,fast_residual,delta_logdet,relative_T,relative_Q)
    def _event_data(self,event:Event)->Tuple[Triangle,LocalVertex,float]:
        tri=self.geometry.triangles[event.triangle_id]; v=self.catalog[event.vertex_id]
        return tri,v,v.activity/self.G0
    def _sample_event(self)->Tuple[Event,float]:
        tri=int(self.rng.integers(self.geometry.n_triangles))
        pos=int(self.rng.choice(len(self.active),p=self.template_probabilities))
        event=Event(tri,self.active[pos]); return event,self._event_data(event)[2]
    def _proposal(self,sites:Sequence[int],block:np.ndarray)->LowRankProposal:
        p=low_rank_left_proposal(self.factors,sites,block,self.condition_max)
        if not p.needs_rebuild:return p
        self.counters["low_rank_rebuild_gates"]+=1; self.rebuild("low-rank-gate")
        p=low_rank_left_proposal(self.factors,sites,block,self.condition_max)
        if not p.needs_rebuild:return p
        self.counters["dense_candidate_fallbacks"]+=1
        return _dense_left_proposal(self.factors,sites,block)
    def _accept(self,loga:float)->bool:
        return loga>=0 or math.log(max(float(self.rng.random()),np.finfo(float).tiny))<loga
    def _insert(self)->bool:
        raw=self.counters["moves"]["insert"]; raw["attempted"]+=1
        event,plabel=self._sample_event(); tri,v,_=self._event_data(event)
        p=self._proposal(tri.sites,v.block)
        if p.zero_weight:self.counters["zero_weight_rejections"]+=1;return False
        loga=log_accept_insert(self.beta,v.activity,len(self.word),p.log_det_ratio,
                               self.moves["insert"],self.moves["delete"],plabel)
        if not self._accept(loga):return False
        self.factors=apply_low_rank_proposal(self.factors,p);self.word.append(event)
        raw["accepted"]+=1;self.counters["rank3_updates_accepted"]+=int(not p.used_dense_fallback)
        self.moves_since_rebuild+=1;return True
    def _delete(self)->bool:
        raw=self.counters["moves"]["delete"];raw["attempted"]+=1
        if not self.word:return False
        event=self.word[-1];tri,v,plabel=self._event_data(event)
        p=self._proposal(tri.sites,v.block_inv)
        if p.zero_weight:self.counters["zero_weight_rejections"]+=1;return False
        loga=log_accept_delete(self.beta,v.activity,len(self.word),p.log_det_ratio,
                               self.moves["insert"],self.moves["delete"],plabel)
        if not self._accept(loga):return False
        self.factors=apply_low_rank_proposal(self.factors,p);self.word.pop()
        raw["accepted"]+=1;self.counters["rank3_updates_accepted"]+=int(not p.used_dense_fallback)
        self.moves_since_rebuild+=1;return True
    def _rotate_ltr(self)->bool:
        raw=self.counters["moves"]["rotate_left_to_right"];raw["attempted"]+=1
        if len(self.word)<2:return False
        event=self.word[-1];self.factors=rotate_left_factor_to_right(
            self.factors,event,self.geometry.triangles,self.catalog)
        self.word.rotate(1);raw["accepted"]+=1;self.moves_since_rebuild+=1;return True
    def _rotate_rtl(self)->bool:
        raw=self.counters["moves"]["rotate_right_to_left"];raw["attempted"]+=1
        if len(self.word)<2:return False
        event=self.word[0];self.factors=rotate_right_factor_to_left(
            self.factors,event,self.geometry.triangles,self.catalog)
        self.word.rotate(-1);raw["accepted"]+=1;self.moves_since_rebuild+=1;return True
    def step(self)->None:
        u=float(self.rng.random());cumulative=0.0;move=list(self.moves)[-1]
        for name,p in self.moves.items():
            cumulative+=p
            if u<cumulative:move=name;break
        {"insert":self._insert,"delete":self._delete,
         "rotate_left_to_right":self._rotate_ltr,
         "rotate_right_to_left":self._rotate_rtl}[move]()
        if self.moves_since_rebuild>=self.rebuild_every:self.rebuild("periodic")
    def checkpoint_payload(self,status:str="running")->Mapping[str,Any]:
        return {"schema_version":1,"algorithm_id":ALGORITHM_ID,"status":status,
          "manifest_sha256":self.manifest_sha256,"completed_steps":self.completed_steps,
          "word":[e.to_json() for e in self.word],"rng_state":self.rng.bit_generator.state,
          "counters":self.counters,"accumulator":self.accumulator.state(),
          "moves_since_rebuild":self.moves_since_rebuild,
          "rebuild_diagnostics":self.rebuild_diagnostics,
          "last_state":{"order":len(self.word),"logdet":self.factors.logdet}}
    def save_checkpoint(self,status:str="running")->None:
        atomic_write_json(self.output_dir/"checkpoint.json",self.checkpoint_payload(status))
    def load_checkpoint(self)->None:
        data=json.loads((self.output_dir/"checkpoint.json").read_text())
        if data.get("schema_version")!=1 or data.get("status") not in {
                "running","run_failed","run_complete_unvalidated"}:
            raise ManifestError("checkpoint schema/status mismatch")
        if data.get("algorithm_id")!=ALGORITHM_ID or data.get("manifest_sha256")!=self.manifest_sha256:
            raise ManifestError("checkpoint protocol mismatch")
        completed=data.get("completed_steps")
        if isinstance(completed,bool) or not isinstance(completed,int) or not (
                0<=completed<=self.steps):
            raise ManifestError("checkpoint completed_steps invalid")
        accumulator=data.get("accumulator")
        expected_count=max(0,completed-self.warmup)//self.measure_every
        if not isinstance(accumulator,Mapping) or accumulator.get("count")!=expected_count:
            raise ManifestError("checkpoint accumulator count mismatch")
        traces=accumulator.get("primary_traces")
        if not isinstance(traces,Mapping) or set(traces)!=set(ObservableAccumulator.KEYS) or any(
                not isinstance(trace,list) or len(trace)!=expected_count
                for trace in traces.values()):
            raise ManifestError("checkpoint primary trace length mismatch")
        self.completed_steps=completed
        self.word=deque(Event.from_json(e) for e in data["word"])
        self.rng.bit_generator.state=data["rng_state"];self.counters=data["counters"]
        self.counters.setdefault("determinant_failures",{"zero":0,"negative":0})
        saved_moves_since_rebuild=int(data.get("moves_since_rebuild",0))
        self.accumulator=ObservableAccumulator.from_state(data["accumulator"])
        self.rebuild_diagnostics=list(data.get("rebuild_diagnostics",[]))
        self.rebuild("resume",False)
        self.moves_since_rebuild=saved_moves_since_rebuild
    def run(self)->Mapping[str,Any]:
        run_started=time.perf_counter()
        self.output_dir.mkdir(parents=True,exist_ok=True)
        for index in range(self.completed_steps,self.steps):
            self.step();self.completed_steps=index+1
            if self.completed_steps>self.warmup and (
                self.completed_steps-self.warmup)%self.measure_every==0:
                self.accumulator.add(measure_configuration(
                    self.factors,self.geometry,self.beta,self.G0,len(self.word),
                    self.momenta,self.displacements))
            if self.completed_steps%self.checkpoint_every==0:
                self.save_checkpoint();atomic_write_json(self.output_dir/"progress.json",{
                    "step":self.completed_steps,"order":len(self.word),
                    "measurements":self.accumulator.count,
                    "latest_rebuild":self.rebuild_diagnostics[-1]})
                print(json.dumps({"step":self.completed_steps,"order":len(self.word)}),flush=True)
        self.rebuild("final")
        wall_seconds=float(time.perf_counter()-run_started)
        max_rss_kb=linux_max_rss_kb()
        move_acceptance={}
        for name,raw in self.counters["moves"].items():
            attempted=int(raw["attempted"]);accepted=int(raw["accepted"])
            move_acceptance[name]={"attempted":attempted,"accepted":accepted,
              "rate":accepted/attempted if attempted else None}
        result={"schema_version":1,"status":"run_complete_unvalidated",
          "scope":"single_chain_execution_only","algorithm_id":ALGORITHM_ID,
          "manifest_sha256":self.manifest_sha256,
          "geometry":{"Lx":self.geometry.Lx,"Ly":self.geometry.Ly,
                      "n_sites":self.geometry.n_sites,"n_triangles":self.geometry.n_triangles},
          "model":self.model,"initialization":self.initialization,
          "measurements":{"momenta":[list(k) for k in self.momenta],
                          "displacements":[list(r) for r in self.displacements]},
          "completed_steps":self.completed_steps,
          "final_order":len(self.word),"final_logdet":self.factors.logdet,
          "counters":self.counters,"move_acceptance":move_acceptance,
          "rebuild_diagnostics":self.rebuild_diagnostics,
          "timing":{"wall_seconds":wall_seconds},
          "resource_usage":{"max_rss_kb":max_rss_kb},
          "execution_environment":execution_environment(),
          "recovered_failure_archives":[
            {"path":str(path.relative_to(self.output_dir)),
             "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sorted((self.output_dir/"failures").glob("FAILED.*.json"))
          ] if (self.output_dir/"failures").is_dir() else [],
          "observables":self.accumulator.summary(self.beta,self.geometry.n_sites),
          "implementation":{"fock_space_constructed":False,
            "local_storage":"12 local 3x3 B/B_inv templates","state":"dense T,Q,logdet",
            "stabilization":"direct O(mN) rebuild + dense O(N^3) LU",
            "trace_storage":"pilot-only in-memory/checkpoint JSON; O(n_measurements)",
            "not_implemented":["QR/UDT","chunked production trace storage",
                               "autocorrelation-aware errors"]},
          "validation_status":"single chain ran; correctness and science gates remain unvalidated",
          "claim_boundary":"mu is not implemented; no finite-density ground-state or mixing claim"}
        result_path=self.output_dir/"result.json"
        atomic_write_json(result_path,result)
        self.save_checkpoint("run_complete_unvalidated")
        result_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest()
        atomic_write_json(self.output_dir/"CHAIN_COMPLETE",{
          "schema_version":1,"status":"run_complete_unvalidated",
          "scope":"single_chain_execution_only","algorithm_id":ALGORITHM_ID,
          "manifest_sha256":self.manifest_sha256,
          "result_json_sha256":result_sha256,
          "completed_steps":self.completed_steps})
        return result

def load_manifest(path:Path)->Tuple[Mapping[str,Any],str]:
    raw=path.read_bytes();data=json.loads(raw.decode())
    if not isinstance(data,dict):raise ManifestError("manifest root must be object")
    return data,hashlib.sha256(raw).hexdigest()

def main(argv:Optional[Sequence[str]]=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--resume",action="store_true")
    parser.add_argument("--validate-only",action="store_true")
    args=parser.parse_args(argv)
    if args.resume and args.validate_only:
        raise ManifestError("--resume and --validate-only are mutually exclusive")
    manifest,digest=load_manifest(args.manifest)
    if args.validate_only:
        sampler=CTQMC.from_manifest(manifest,args.output,digest)
        print(json.dumps({"algorithm_id":ALGORITHM_ID,"manifest_sha256":digest,
          "n_sites":sampler.geometry.n_sites,
          "n_triangles":sampler.geometry.n_triangles,
          "local_templates":len(sampler.catalog),"status":"parsed, not run"},
          indent=2,allow_nan=False))
        return 0
    checkpoint=args.output/"checkpoint.json"
    result=args.output/"result.json"
    chain_complete=args.output/"CHAIN_COMPLETE"
    failed=args.output/"FAILED"
    if chain_complete.exists():
        completed=validate_existing_complete(
            args.output,digest,int(manifest["monte_carlo"]["steps"]))
        print(json.dumps({"status":completed["status"],
          "idempotent_existing_complete":True},allow_nan=False),flush=True)
        return 0
    if args.resume and not checkpoint.is_file():
        raise ManifestError("--resume needs checkpoint; active FAILED retained")
    if failed.exists():
        if args.resume:
            archive_recoverable_failure(failed)
        else:
            raise ManifestError("FAILED exists; use --resume for recoverable failures")
    if not args.resume and (checkpoint.exists() or result.exists()):
        raise ManifestError("output exists; use --resume or a new directory")
    sampler:Optional[CTQMC]=None
    try:
        sampler=CTQMC.from_manifest(manifest,args.output,digest)
        if args.resume:
            sampler.load_checkpoint()
        final=sampler.run()
    except Exception as exc:
        kind=exc.kind if isinstance(exc,DeterminantFailure) else None
        if sampler is not None:
            counts=sampler.counters.setdefault(
                "determinant_failures",{"zero":0,"negative":0})
            if kind in counts:
                counts[kind]=int(counts[kind])+1
            completed_steps=sampler.completed_steps
            try:
                sampler.save_checkpoint("run_failed")
            except Exception:
                pass
            failure_counts=dict(counts)
        else:
            failure_counts={"zero":int(kind=="zero"),
                            "negative":int(kind=="negative")}
            completed_steps=0
        failure_payload={"schema_version":1,"status":"run_failed",
          "scope":"single_chain_execution_only","algorithm_id":ALGORITHM_ID,
          "manifest_sha256":digest,"completed_steps":completed_steps,
          "failed_unix_time":float(time.time()),
          "error_type":type(exc).__name__,"error_message":str(exc),
          "determinant_failure_kind":kind,
          "determinant_failures":failure_counts}
        try:
            atomic_write_json(failed,failure_payload)
        except Exception:
            pass
        raise
    print(json.dumps({"status":final["status"],
      "wall_seconds":final["timing"]["wall_seconds"]},
      allow_nan=False),flush=True)
    return 0
if __name__=="__main__":raise SystemExit(main())
