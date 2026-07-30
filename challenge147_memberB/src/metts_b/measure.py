"""Per-sample METTS steps: evolution, energy measurement, Z-basis collapse.

A single METTS sample (one Markov chain step) is::

    |sigma>  --e^{-beta H/2}-->  |phi_sigma>  (normalised)
    measure E_sigma = <phi|H|phi> ,  E2_sigma = <phi|H^2|phi>
    compute Z-basis local conditional probs p_i(s_i | s_<i)
    sample s_i ~ p_i, collapse -> next product state |sigma'>

This module is **backend-agnostic** in the sense that all heavy linear algebra
is delegated to a small protocol: a backend exposes ``evolve(psi, tau)``,
``norm(psi)``, ``energy_moments(psi)`` and ``conditional_prob_and_collapse``.
The dense backend (``DenseBackend``) is implemented here; the snake-MPS backend
lives in ``mps_backend.py`` and implements the same protocol.

Energy via the "H|psi>" trick (convention-independent): given |phi> = the
evolved (unnormalised) state, form |chi> = H|phi>. Then
    E_sigma   = <phi|chi> / <phi|phi>     = Re(<phi|chi>/<phi|phi>)
    E2_sigma  = <chi|chi> / <phi|phi>
so we never touch H^2 explicitly and the same code works for any backend that
can apply H once. (For the dense backend H|psi> is a sparse matvec; for the MPS
backend it is a bond+field sum of local contractions.)
"""
from __future__ import annotations

import time
import numpy as np
import scipy.sparse as sp

from .bridge import tfim_bonds, assert_mem_available, MemoryBudgetExceeded
from .hamiltonian import (
    site_bit, product_state_vector, product_state_to_labels,
    build_hamiltonian, trotter_evolve_dense, spectral_evolve_state,
    _bond_parity_split,
)
from . import status


# ===========================================================================
# Dense backend: state vector of length 2**N. Exact within Trotter error; no
# truncation, so the only approximation is the Trotter step (and the spectral
# path removes even that). Capped at N<=14 by build_hamiltonian.
# ===========================================================================

class DenseBackend:
    """Dense state-vector METTS backend (gold reference, N <= ~10-12)."""

    def __init__(self, Lx, Ly, h, J=1.0, dtau=0.05, evolve="trotter",
                 mem_guard=True):
        self.Lx, self.Ly = int(Lx), int(Ly)
        self.h, self.J = float(h), float(J)
        self.N = self.Lx * self.Ly
        self.dtau = float(dtau)
        self.evolve_mode = evolve           # "trotter" or "spectral"
        self.mem_guard = mem_guard
        self.bonds = tfim_bonds(self.Lx, self.Ly)
        self.bonds_layers = _bond_parity_split(self.bonds)
        # Spectral path needs the full Hamiltonian + its spectrum (cached).
        # Trotter path only needs H for the energy measurement (H|psi>).
        self._H = None
        self._spec = None
        if self.evolve_mode == "spectral" or self.N <= 12:
            # build H lazily on first use to keep __init__ cheap
            pass

    # -- lazy heavy objects -------------------------------------------------
    def _hamiltonian(self):
        if self._H is None:
            self._H = build_hamiltonian(self.Lx, self.Ly, self.h, self.J)
        return self._H

    def _spectrum(self):
        if self._spec is None:
            H = self._hamiltonian()
            self._spec = {}
            spectral_evolve_state(H, np.zeros(2 ** self.N, dtype=np.complex128),
                                  0.0, cache=self._spec)
        return self._spec

    # -- protocol -----------------------------------------------------------
    def make_product_state(self, spins):
        return product_state_vector(spins, self.N)

    def evolve(self, psi, beta):
        """Apply e^{-beta H/2} to ``psi``. Returns the (unnormalised) evolved
        state. ``beta`` here is the full inverse temperature; the METTS
        imaginary-time length is beta/2 (task spec §5.2)."""
        tau = beta / 2.0
        if self.evolve_mode == "spectral":
            H = self._hamiltonian()
            psi, _ = spectral_evolve_state(H, psi, tau, cache=self._spectrum())
            return psi
        # Trotter: n_steps = ceil(tau / dtau), clamp step count for safety.
        n_steps = max(1, int(np.ceil(tau / self.dtau)))
        trotter_evolve_dense(psi, self.Lx, self.Ly, self.h, self.dtau,
                             n_steps, J=self.J, bonds_layers=self.bonds_layers)
        return psi

    def norm(self, psi):
        return float(np.sqrt(np.vdot(psi, psi).real))

    def energy_moments(self, psi):
        """Return (E_sigma, E2_sigma) = (<phi|H|phi>, <phi|H^2|phi>) / <phi|phi>.

        Uses |chi> = H|phi> so H^2 is never formed: E2 = <chi|chi>/<phi|phi>.
        """
        H = self._hamiltonian()
        phi2 = float(np.vdot(psi, psi).real)
        if phi2 <= 0 or not np.isfinite(phi2):
            return float("nan"), float("nan"), float("nan")
        chi = H @ psi
        E = float((np.vdot(psi, chi) / phi2).real)
        E2 = float((np.vdot(chi, chi) / phi2).real)
        return E, E2, phi2

    def conditional_prob_and_collapse(self, psi, rng, basis="Z",
                                      prob_tol=1e-9):
        """Exact sequential Z-basis collapse (single trajectory).

        Sweep sites i = 0..N-1, which is bit significance MSB->LSB
        (bit b = N-1-i). At site i, conditioned on the already-fixed spins
        s_0..s_{i-1}, compute p_i(up), p_i(down) as the mass of the current
        (already-projected) |psi|^2 lying under bit_b=1 vs bit_b=0. Sample
        s_i ~ (p_down, p_up), record the conditional probabilities used, then
        project onto the sampled outcome (zero the discarded half and
        renormalise) so the next site's conditional is exact.

        This is provably equivalent to sampling the joint Z-basis distribution
        p(s)=|<s|psi>|^2: the product of the recorded conditionals telescopes
        to the joint marginal. No MPS / truncation is involved, so it is
        crash-proof. Returns (probs[N,2], spins[N] in +/-1, residual_mass).
        """
        N = self.N
        if basis != "Z":
            raise NotImplementedError("only Z-basis collapse is supported in v0")
        a = (psi * psi.conj()).real.copy()         # |psi|^2 per basis index
        probs = np.empty((N, 2), dtype=np.float64)  # probs[site]=(p_down,p_up)
        spins = np.empty(N, dtype=np.int8)
        idx = np.arange(a.shape[0])
        for i in range(N):
            b = site_bit(i, N)
            bit = (idx >> b) & 1
            mask_up = bit.astype(bool)
            p_up = float(a[mask_up].sum())
            p_down = float(a[~mask_up].sum())
            tot = p_up + p_down
            if not np.isfinite(tot) or tot <= 0:
                raise _ProbabilityError(
                    f"site {i} (bit {b}): non-positive/non-finite weight "
                    f"tot={tot} (p_up={p_up}, p_down={p_down})", site=i)
            pu = p_up / tot
            pd = p_down / tot
            if pu < -prob_tol or pu > 1.0 + prob_tol:
                raise _ProbabilityError(
                    f"site {i}: p_up={pu} out of [0,1]", site=i)
            probs[i] = (pd, pu)
            # sample this site's outcome (single draw)
            spins[i] = 1 if rng.random() < pu else -1
            # project onto the sampled outcome, renormalise to a distribution
            if spins[i] == 1:
                a[~mask_up] = 0.0
            else:
                a[mask_up] = 0.0
            s = a.sum()
            if s > 0:
                a /= s
        return probs, spins, float(a.sum())


class _ProbabilityError(Exception):
    def __init__(self, msg, site=None):
        super().__init__(msg)
        self.site = site


# ===========================================================================
# High-level single-sample routine. Builds the trace dict (task spec §7) and
# never raises past a recoverable error: it returns a trace with a failure
# status code instead, carrying diagnostics.
# ===========================================================================

def _mem_mb():
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e6
    except Exception:
        return float("nan")


def run_one_sample(backend, spins_in, beta, rng, sample_id, step,
                   dtau, trotter_order=2, evolve_mode="trotter",
                   checkpoint_dir=None, t_start=None, mem_start=None,
                   prob_tol=1e-9, basis="Z", seed=None):
    """Run one METTS sample end-to-end and return (trace_dict, spins_out).

    The trace dict follows the B task-spec §7 schema exactly. On any
    recoverable failure the trace carries the matching status code and the
    partial state (norms, probabilities gathered so far); ``spins_out`` is the
    best-effort next product state (falls back to ``spins_in`` on collapse
    failure so the chain can continue from a known-valid state).
    """
    N = backend.N
    t0 = time.time()
    warnings = []
    trace = {
        "sample_id": int(sample_id),
        "step": int(step),
        "seed": int(seed) if seed is not None else None,
        "beta": float(beta),
        "imag_time_target": float(beta / 2.0),
        "trotter_order": int(trotter_order),
        "trotter_dt": float(dtau),
        "trotter_steps": int(max(1, np.ceil((beta / 2.0) / dtau))) if evolve_mode == "trotter" else 0,
        "evolve_mode": evolve_mode,
        "initial_product_state": product_state_to_labels(spins_in),
        "collapse_basis": basis,
        "collapse_probabilities": [],
        "collapsed_product_state": None,
        "energy": None,
        "norm_before": None,
        "norm_after": None,
        "truncation_error_step": [],
        "truncation_error_total": 0.0,
        "max_bond_dimension": 2 ** N if evolve_mode != "spectral" else None,
        "wall_time_sec": None,
        "memory_estimate_mb": None,
        "status_code": status.OK,
        "warnings": warnings,
        "error_message": None,
        "checkpoint_path": None,
        "timestamp": time.time(),
        "config_hash": None,
        "code_version": None,
    }
    try:
        psi = backend.make_product_state(spins_in)
        norm_before = backend.norm(psi)
        trace["norm_before"] = float(norm_before)
        if not np.isfinite(norm_before) or norm_before <= 0:
            trace["status_code"] = status.NORM_ERROR
            trace["error_message"] = f"norm_before={norm_before}"
            return trace, spins_in
        # evolve to beta/2
        psi = backend.evolve(psi, beta)
        norm_after = backend.norm(psi)
        trace["norm_after"] = float(norm_after)
        if not np.isfinite(norm_after) or norm_after <= 0:
            trace["status_code"] = status.EVOLUTION_NAN
            trace["error_message"] = f"norm_after={norm_after}"
            return trace, spins_in
        # energy
        E, E2, phi2 = backend.energy_moments(psi)
        # E must be finite. E2 is OPTIONAL: the dense backend returns
        # <phi|H^2|phi> (used for the 方案 A specific heat); the MPS backend
        # returns nan by design (C is obtained from the u(beta) curve via
        # 方案 B instead). A nan E2 is therefore NOT an error.
        if not np.isfinite(E):
            trace["status_code"] = status.ENERGY_ERROR
            trace["error_message"] = f"E={E} phi2={phi2}"
            return trace, spins_in
        trace["energy"] = float(E)
        trace["energy2"] = float(E2) if np.isfinite(E2) else None
        # collapse
        try:
            probs, spins_out, mass = backend.conditional_prob_and_collapse(
                psi, rng, basis=basis, prob_tol=prob_tol)
        except _ProbabilityError as e:
            trace["status_code"] = status.PROBABILITY_ERROR
            trace["error_message"] = str(e)
            return trace, spins_in
        # validate probabilities
        pmin = float(probs.min())
        pmax = float(probs.max())
        if pmin < -prob_tol or pmax > 1.0 + prob_tol:
            trace["status_code"] = status.PROBABILITY_ERROR
            trace["error_message"] = f"prob out of range [{pmin},{pmax}]"
            return trace, spins_in
        if abs(probs.sum(axis=1).max() - 1.0) > 1e-6:
            warnings.append(f"per-site prob sum deviates: "
                            f"{probs.sum(axis=1)}")
        trace["collapse_probabilities"] = [
            {"site": int(i), "p_up": float(probs[i, 1]),
             "p_down": float(probs[i, 0])}
            for i in range(N)
        ]
        trace["collapsed_product_state"] = product_state_to_labels(spins_out)
        # validate collapsed state is a legal product state
        if not np.all(np.isin(spins_out, [-1, 1])):
            trace["status_code"] = status.COLLAPSE_ERROR
            trace["error_message"] = "collapsed state not +/-1"
            return trace, spins_in
    except MemoryBudgetExceeded as e:
        trace["status_code"] = status.MEMORY_LIMIT
        trace["error_message"] = str(e)
        return trace, spins_in
    except Exception as e:
        trace["status_code"] = status.UNKNOWN_ERROR
        trace["error_message"] = repr(e)
        return trace, spins_in
    trace["wall_time_sec"] = float(time.time() - t0)
    trace["memory_estimate_mb"] = float(_mem_mb())
    trace["status_code"] = status.OK
    return trace, spins_out
