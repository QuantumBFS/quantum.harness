"""METTS Markov-chain driver, statistics, and per-sample trace output.

Ties the single-sample routine (``measure.run_one_sample``) into a chain:

    |sigma_0>  ->  |phi_0>  ->  measure E_0  ->  collapse -> |sigma_1>  -> ...

Per the task spec the METTS estimator is the **unweighted** sample mean of the
per-sample energies E_sigma (the collapse sampling makes pi(sigma) ~ w_sigma,
so <O>_beta = (1/M) sum_m <phi_m|O|phi_m> / <phi_m|phi_m>). We record both
E_sigma and E2_sigma = <phi|H^2|phi>/<phi|phi> per sample, so:

    u  = mean(E_sigma) / N
    C  = beta^2 * ( mean(E2_sigma) - mean(E_sigma)^2 ... ) / N   -- see below
    f  = reconstructed from the u(beta) curve by thermodynamic integration
         (core.observables.free_energy_from_u), per the shared convention.

Specific heat estimator. The naive C = beta^2 ( <E2> - <E>^2 ) / N mixes two
quantities with independent statistical errors and suffers large cancellation
near the specific-heat peak. We report TWO estimators and cross-check them:

  (A) sample-variance form (unbiased):
        C = beta^2 / (N (M-1)) * sum_m (E_sigma_m - mean_E)^2
      This equals beta^2 (mean(E2) - mean(E)^2)/N up to the (M-1)/M Bessel
      correction; we use the Bessel form and also report the connected form.
  (B) numerical derivative  C = -beta^2 du/dbeta  (computed in the driver,
      from the u(beta) curve), used as a cross-check on (A) per the report
      spec §3.3. The chain itself returns (A) + its SEM.

Statistics: SEM from binning analysis (blocking) so the reported error
accounts for sample autocorrelation. We also return the naive 1/sqrt(M) SEM
(assuming i.i.d.) for the 1/sqrt(M) scaling check (report §6.3).
"""
from __future__ import annotations

import os
import json
import time
import hashlib
import numpy as np

from .bridge import (
    free_energy_from_u, write_csv, write_manifest, assert_mem_available,
)
from .measure import run_one_sample, DenseBackend
from . import status


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def binning_sem(x, n_bins=20):
    """Standard error of the mean from binning/blocking analysis.

    Splits the 1D array ``x`` into ``n_bins`` contiguous blocks, takes the
    mean of each, and returns std(block_means, ddof=1)/sqrt(n_bins). This
    absorbs sample autocorrelation into a single conservative SEM (the block
    size grows with M, so for correlated samples the SEM plateaus at the true
    autocorrelation-corrected value). Falls back to the i.i.d. SEM when there
    are too few samples.
    """
    x = np.asarray(x, dtype=float)
    if x.size < 2:
        return 0.0
    nb = min(n_bins, x.size)
    if nb < 2:
        return float(np.std(x, ddof=1) / np.sqrt(x.size))
    blocks = np.array_split(x, nb)
    means = np.array([b.mean() for b in blocks if b.size > 0])
    if means.size < 2:
        return float(np.std(x, ddof=1) / np.sqrt(x.size))
    return float(np.std(means, ddof=1) / np.sqrt(means.size))


def iid_sem(x):
    """Naive SEM assuming independent samples (1/sqrt(M))."""
    x = np.asarray(x, dtype=float)
    if x.size < 2:
        return 0.0
    return float(np.std(x, ddof=1) / np.sqrt(x.size))


# ---------------------------------------------------------------------------
# Config / version bookkeeping
# ---------------------------------------------------------------------------

def config_hash(config: dict) -> str:
    """Stable SHA-256 of a JSON-serialisable config dict (sorted keys)."""
    blob = json.dumps(config, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def git_version():
    """Short git commit of the repo, or 'unknown'. Never raises."""
    try:
        import subprocess
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# Chain driver
# ---------------------------------------------------------------------------

class METTSChainResult:
    """Container for one chain's thermodynamics + diagnostics."""

    def __init__(self):
        self.beta = None
        self.N = None
        self.u = float("nan")
        self.C = float("nan")
        self.f = float("nan")
        self.u_err = 0.0
        self.C_err = 0.0
        self.n_production = 0
        self.n_warmup = 0
        self.n_failed = 0
        self.E_samples = []          # production per-sample E_sigma
        self.E2_samples = []         # production per-sample E2_sigma
        self.status_codes = []
        self.first_sample_seed = None
        self.last_spin = None


def run_chain(backend, beta, n_warmup, n_production, seed,
              dtau, evolve_mode="trotter", initial_spins=None,
              trace_dir=None, sample_id_start=0, chain_id=0,
              write_traces=True, prob_tol=1e-9, basis="Z",
              checkpoint_dir=None):
    """Run one METTS Markov chain at a single beta.

    Returns a ``METTSChainResult`` and, if ``trace_dir`` is set, writes one
    JSON per sample plus a ``chain_summary.csv``. Warm-up samples are evolved
    and collapsed (so the chain thermalises) but excluded from the
    thermodynamic average; their traces are still written (with
    ``step`` < 0 convention-free marker via the ``warmup`` field) for
    diagnostics.
    """
    N = backend.N
    rng = np.random.default_rng(seed)
    if initial_spins is None:
        spins = (rng.integers(0, 2, size=N) * 2 - 1).astype(np.int8)
    else:
        spins = np.asarray(initial_spins, dtype=np.int8).copy()
    res = METTSChainResult()
    res.beta = float(beta)
    res.N = int(N)
    res.first_sample_seed = int(seed)
    os.makedirs(trace_dir, exist_ok=True) if trace_dir else None
    summary_rows = []
    total = n_warmup + n_production
    for k in range(total):
        is_warmup = k < n_warmup
        step = k - n_warmup + 1 if not is_warmup else -(k + 1)
        sample_id = sample_id_start + k
        # per-sample seed for reproducibility of the collapse draw
        s_seed = (int(seed) * 1000003 + k) & 0xFFFFFFFF
        trace, spins_new = run_one_sample(
            backend, spins, beta, rng, sample_id=sample_id, step=step,
            dtau=dtau, evolve_mode=evolve_mode, seed=s_seed,
            prob_tol=prob_tol, basis=basis, checkpoint_dir=checkpoint_dir,
        )
        # stamp config/version once (cheap)
        trace["config_hash"] = None  # filled by caller via run_config
        trace["code_version"] = git_version()
        if write_traces and trace_dir:
            fn = os.path.join(
                trace_dir,
                f"{'warmup' if is_warmup else 'sample'}_{sample_id:06d}.json")
            with open(fn, "w") as f:
                json.dump(trace, f, indent=2)
        summary_rows.append({
            "sample_id": sample_id, "step": step, "warmup": is_warmup,
            "beta": beta, "energy": trace.get("energy"),
            "norm_after": trace.get("norm_after"),
            "status": trace["status_code"], "seed": s_seed,
        })
        if trace["status_code"] == status.OK and not is_warmup:
            res.E_samples.append(float(trace["energy"]))
            res.E2_samples.append(float(trace["energy2"]))
            res.n_production += 1
        elif is_warmup and trace["status_code"] == status.OK:
            res.n_warmup += 1
        else:
            res.n_failed += 1
        res.status_codes.append(trace["status_code"])
        # advance the chain: use the collapsed state if it is valid, else
        # fall back to the input state (keeps the chain on a legal product
        # state after a recoverable failure).
        if trace["status_code"] == status.OK:
            spins = spins_new
        else:
            # leave spins unchanged; record a fresh random state only if the
            # failure was a collapse/evolution error (avoids a stuck chain)
            if trace["status_code"] in (status.COLLAPSE_ERROR,
                                        status.EVOLUTION_NAN,
                                        status.PROBABILITY_ERROR):
                spins = (rng.integers(0, 2, size=N) * 2 - 1).astype(np.int8)
    res.last_spin = spins
    # thermodynamics from production samples
    if res.n_production > 0:
        Es = np.array(res.E_samples)
        E2s = np.array(res.E2_samples)
        meanE = float(Es.mean())
        res.u = meanE / N
        # Specific heat = beta^2 ( <H^2> - <H>^2 ) / N  (report "方案 A",
        # fluctuation formula). In METTS <H^2>_beta = mean(E2_sigma) and
        # <H>_beta = mean(E_sigma), so the thermal variance of H is
        #   Var_beta(H) = mean(E2_sigma) - mean(E_sigma)^2
        # NOT Var_sigma(E_sigma) (the between-sample variance alone). The two
        # differ by the within-sample variance E[E2_sigma - E_sigma^2] >= 0,
        # which METTS typical states carry and which is essential at low T.
        # (Law of total variance: Var_beta(H) = E[Var_phi(H)] + Var_sigma(E).)
        varH = float(E2s.mean()) - meanE * meanE
        if varH < 0:                      # numerical guard; should not happen
            varH = 0.0
        res.C = float(beta * beta) * varH / N
        res.u_err = binning_sem(Es) / N
        # SEM on C via the delta-method linearisation of V = mean(E2) - meanE^2
        # around the sample mean: g_sigma = E2_sigma - 2*meanE*E_sigma is the
        # linear part, V = mean(g) + meanE^2, so SEM(V) = SEM(mean(g)) (the
        # constant meanE^2 does not contribute). Binning absorbs autocorrelation.
        if res.n_production > 1:
            g = E2s - 2.0 * meanE * Es
            res.C_err = float(beta * beta) / N * binning_sem(g)
        else:
            res.C_err = 0.0
    if write_traces and trace_dir and summary_rows:
        write_csv(os.path.join(trace_dir, "chain_summary.csv"), summary_rows,
                  ["sample_id", "step", "warmup", "beta", "energy",
                   "norm_after", "status", "seed"])
    return res


# ---------------------------------------------------------------------------
# Multi-beta scan: produces u(beta), C(beta), then f(beta) by thermodynamic
# integration over u, exactly as the shared convention (free_energy_from_u)
# prescribes. This is the routine the ED comparison and the convergence
# analysis call.
# ---------------------------------------------------------------------------

def metts_scan(backend, beta_list, n_warmup, n_production, seed,
               dtau, evolve_mode="trotter", trace_root=None, chain_id=0,
               write_traces=True, prob_tol=1e-9, basis="Z",
               n_chains=1, checkpoint_dir=None):
    """Run METTS for a list of betas. If ``n_chains>1`` runs that many
    independent chains per beta (different seeds + initial states) and
    combines them into a single ThermoResult per beta with chain-pooled SEM
    and a Gelman-Rubin Rhat diagnostic on u.

    Returns a list of dicts (one per beta) with keys: beta, u, u_err, C,
    C_err, f, n_samples, n_chains, rhat_u, status, plus the per-chain results.
    f is filled from the u(beta) curve via free_energy_from_u.
    """
    from .bridge import ThermoResult, rel_err  # noqa (local for clarity)
    per_beta = []
    chain_results = {b: [] for b in beta_list}
    for b in beta_list:
        for c in range(n_chains):
            cseed = (int(seed) + c * 7919 + int(round(b * 1000))) & 0x7FFFFFFF
            tdir = None
            if trace_root:
                tdir = os.path.join(trace_root, f"beta_{b:g}", f"chain_{c}")
            cr = run_chain(
                backend, b, n_warmup, n_production, cseed, dtau,
                evolve_mode=evolve_mode, trace_dir=tdir,
                sample_id_start=0, chain_id=c, write_traces=write_traces,
                prob_tol=prob_tol, basis=basis, checkpoint_dir=checkpoint_dir,
            )
            chain_results[b].append(cr)
    # combine
    us = []
    for b in beta_list:
        chains = chain_results[b]
        good = [c for c in chains if c.n_production > 0]
        if not good:
            per_beta.append({
                "beta": b, "u": float("nan"), "u_err": float("nan"),
                "C": float("nan"), "C_err": float("nan"), "f": float("nan"),
                "n_samples": 0, "n_chains": n_chains, "rhat_u": float("nan"),
                "status": "no_production_samples",
            })
            us.append(float("nan"))
            continue
        # pool all production E samples across chains
        allE = np.concatenate([np.array(c.E_samples) for c in good])
        allE2 = np.concatenate([np.array(c.E2_samples) for c in good])
        N = good[0].N
        meanE = float(allE.mean())
        u = meanE / N
        # specific heat via the fluctuation formula (see run_chain): thermal
        # variance of H = mean(E2_sigma) - mean(E_sigma)^2, including the
        # within-sample variance carried by each METTS typical state.
        varH = float(allE2.mean()) - meanE * meanE
        if varH < 0:
            varH = 0.0
        C = float(b * b) * varH / N
        # SEM: chain means' spread / sqrt(n_chains) (between-chain) pooled with
        # within-chain binning SEM (conservative max). For a single chain this
        # reduces to the binning SEM.
        if len(good) > 1:
            chain_means = np.array([np.mean(c.E_samples) for c in good])
            between = float(np.std(chain_means, ddof=1) / np.sqrt(len(good)))
            within = float(np.mean([binning_sem(c.E_samples) for c in good]))
            u_err = max(between, within) / N
            # Gelman-Rubin Rhat on E (not u; scale cancels)
            rhat = _gelman_rubin([np.array(c.E_samples) for c in good])
        else:
            u_err = binning_sem(allE) / N
            rhat = float("nan")
        if allE.size > 1:
            g = allE2 - 2.0 * meanE * allE        # delta-method for Var(H)
            C_err = float(b * b) / N * binning_sem(g)
        else:
            C_err = 0.0
        per_beta.append({
            "beta": float(b), "u": float(u), "u_err": float(u_err),
            "C": float(C), "C_err": float(C_err), "f": float("nan"),
            "n_samples": int(allE.size), "n_chains": len(good),
            "rhat_u": float(rhat), "status": "OK",
            "n_failed": int(sum(c.n_failed for c in chains)),
        })
        us.append(u)
    # free energy from the u(beta) curve (thermodynamic integration)
    fs = free_energy_from_u(beta_list, us)
    for row, fv in zip(per_beta, fs):
        row["f"] = float(fv) if np.isfinite(fv) else float("nan")
    return per_beta


def _gelman_rubin(chains):
    """Gelman-Rubin potential scale reduction factor (Rhat) for >=2 chains of
    possibly unequal length (truncated to the shortest). Returns nan if not
    computable. Values < 1.05 indicate good mixing."""
    m = len(chains)
    if m < 2:
        return float("nan")
    n = min(c.size for c in chains)
    if n < 2:
        return float("nan")
    X = np.array([c[:n] for c in chains])            # (m, n)
    chain_means = X.mean(axis=1)
    chain_vars = X.var(axis=1, ddof=1)
    W = float(chain_vars.mean())
    B = float(n * chain_means.var(ddof=1))
    if W <= 0:
        return float("nan")
    var_hat = (n - 1) / n * W + B / n
    return float(np.sqrt(var_hat / W))
