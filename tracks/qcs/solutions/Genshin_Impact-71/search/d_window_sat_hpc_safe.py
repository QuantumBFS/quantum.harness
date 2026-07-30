#!/usr/bin/env python3
"""Conflict-budget launcher for the cycle-safe two-root SAT implementation."""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

from pysat.solvers import Solver


BASE = Path(__file__).with_name("d_window_sat_safe_remote.py")
spec = importlib.util.spec_from_file_location("d_window_sat_safe_impl", BASE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {BASE}")
impl = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = impl
spec.loader.exec_module(impl)


def solve_hpc(encoding, timeout_seconds, solver_preference):
    """Interpret the CLI timeout number as millions of conflicts."""
    solver = None
    chosen = None
    for name in solver_preference:
        try:
            solver = Solver(name=name, bootstrap_with=encoding.clauses)
            chosen = name
            break
        except Exception:
            pass
    if solver is None:
        raise RuntimeError("no supported PySAT backend")
    try:
        try:
            solver.configure({"seed": impl.SEED})
        except Exception:
            pass
        conflict_budget = max(1, int(timeout_seconds * 1_000_000))
        solver.conf_budget(conflict_budget)
        started = time.monotonic()
        result = solver.solve_limited(expect_interrupt=False)
        elapsed = time.monotonic() - started
        model = solver.get_model() if result is True else None
        stats = dict(solver.accum_stats())
        stats["configured_conflict_budget"] = conflict_budget
        return result, model, chosen, elapsed, stats
    finally:
        solver.delete()


impl.solve_with_timeout = solve_hpc
impl.main()
