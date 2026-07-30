"""Configuration for a METTS run.

A ``METTSConfig`` is a plain dataclass; runs are driven from a YAML file (or a
plain Python dict). YAML is loaded via PyYAML if available, else a tiny
hand-rolled parser is *not* attempted (we refuse to silently misread a config)
-- instead the caller can pass a dict directly. Defaults are chosen for the
2x2 h=3.0 ED-validation run and for crash safety: small Trotter step, modest
sample counts, memory-guarded.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict


@dataclass
class METTSConfig:
    # lattice / model
    Lx: int = 2
    Ly: int = 2
    h: float = 3.0
    J: float = 1.0
    boundary: str = "OBC"

    # thermodynamics grid
    betas: list = field(default_factory=lambda: [0.3, 0.6, 1.0])

    # METTS sampling
    n_warmup: int = 20
    n_production: int = 200
    n_chains: int = 1
    seed: int = 20260729
    basis: str = "Z"                 # collapse basis (Z2 antithetic is a flag)
    antithetic_z2: bool = False      # future: pair each sample with its Z2 flip

    # evolution
    evolve_mode: str = "trotter"     # "trotter" or "spectral"
    dtau: float = 0.05
    trotter_order: int = 2
    max_bond_dim: int = 64           # only used by the MPS backend
    trunc_tol: float = 1e-10         # only used by the MPS backend

    # backend
    backend: str = "dense"           # "dense" or "mps"

    # output
    out_dir: str = "metts_runs/run_default"
    write_traces: bool = True
    write_checkpoints: bool = False
    label: str = "default"

    # diagnostics / safety
    prob_tol: float = 1e-9
    mem_guard: bool = True

    def to_dict(self):
        return asdict(self)

    def run_id(self):
        return f"{self.label}_L{self.Lx}x{self.Ly}_h{self.h}_b{self.betas[0]:g}-{self.betas[-1]:g}"


def load_config(path: str) -> METTSConfig:
    """Load a YAML config file into a METTSConfig. Requires PyYAML; if it is
    not installed we raise a clear error rather than guessing."""
    import yaml  # noqa
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    cfg = METTSConfig()
    for k, v in raw.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg


def config_from_dict(d: dict) -> METTSConfig:
    cfg = METTSConfig()
    for k, v in (d or {}).items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg
