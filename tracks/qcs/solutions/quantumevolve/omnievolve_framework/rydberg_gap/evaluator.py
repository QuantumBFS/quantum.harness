"""#233 Evaluator: Certified spectral gap for PXP Rydberg chain.

Two-step verification (like Lennard-Jones evaluator):
  1. main.py — candidate code, writes candidate_result.json
  2. verify_gap.py — anti-cheat + LMI verification, outputs verification JSON

Anti-cheat: verify_gap.py reads main.py source and checks for eigvalsh/eigh
in certify_gap. This runs INSIDE the sandbox where main.py is accessible.

Scoring:
  - If anti-cheat fails → score = 0
  - If LMI verification fails → score = 0
  - Otherwise: score = certified_gap / ED_gap (1.0 = perfect certificate)

ED reference is hardcoded (precomputed) so the evaluator never runs ED.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

from omnievolve.eval.task_evaluator import (
    CandidateArtifact,
    CommandSpec,
    EvalOutput,
    EvaluationContext,
    EvaluationPlan,
    MountSpec,
    SandboxExecutionResult,
)

_WORKSPACE = os.path.dirname(os.path.abspath(__file__))

# ED reference values (precomputed offline, hardcoded — evaluator never runs ED)
_ED_REFERENCE = {
    (8, 0.0): {"E0": -5.112422251823336, "gap": 1.1065151028379407},
    (6, 0.0): {"E0": -3.705778838995111, "gap": 1.1661532576026752},
    (10, 0.0): {"E0": -6.558680244989908, "gap": 1.0685361731155575},
}

DEFAULT_N = 8
DEFAULT_DELTA = 0.0


class RydbergGapEvaluator:
    """SDP gap certificate evaluator for #233 with two-step verification."""

    version_id = "rydberg-gap@4.0.0"

    def __init__(self, n: int = DEFAULT_N, delta: float = DEFAULT_DELTA):
        self.n = n
        self.delta = delta
        ref = _ED_REFERENCE.get((n, delta))
        if ref is None:
            raise ValueError(f"No ED reference for n={n}, delta={delta}")
        self.gap_ed = ref["gap"]
        self.E0_ed = ref["E0"]

    def get_baseline(self) -> float:
        """Baseline: Gershgorin E0_lb gives certified_gap = 0 → score 0."""
        return 0.0

    def build_plan(
        self, candidate: CandidateArtifact, context: EvaluationContext
    ) -> EvaluationPlan:
        return EvaluationPlan(
            commands=[
                # Step 1: candidate code, writes candidate_result.json
                CommandSpec(
                    argv=[sys.executable, "main.py", str(self.n), str(self.delta)],
                    timeout_sec=90.0,
                ),
                # Step 2: verifier (anti-cheat + LMI check)
                CommandSpec(
                    argv=[sys.executable, "verify_gap.py"],
                    timeout_sec=15.0,
                ),
            ],
            mounts=[
                MountSpec(
                    source=os.path.join(_WORKSPACE, "verify_gap.py"),
                    target="/workspace/verify_gap.py",
                ),
            ],
            expected_outputs=["candidate_result.json"],
            network_access=False,
        )

    def parse_result(
        self, result: SandboxExecutionResult, context: EvaluationContext
    ) -> EvalOutput:
        if result.timed_out:
            return EvalOutput(score=0.0, metrics={}, passed=False,
                              failure_reason="Timeout")

        if not result.return_codes or result.return_codes[0] != 0:
            return EvalOutput(score=0.0, metrics={}, passed=False,
                              failure_reason=result.stderr[-500:] if result.stderr else "crash")

        # Parse verifier output (last JSON line with "verified" key)
        verify = None
        for line in reversed(result.stdout.strip().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "verified" in obj:
                verify = obj
                break

        if verify is None:
            return EvalOutput(score=0.0, metrics={}, passed=False,
                              failure_reason="No verifier output")

        if not verify.get("verified", False):
            return EvalOutput(
                score=0.0,
                metrics={"anti_cheat": verify.get("anti_cheat", "")},
                passed=False,
                failure_reason=verify.get("error", "verification failed"),
            )

        # Read candidate result for scoring
        try:
            # Parse candidate output from stdout (first JSON line)
            candidate_data = None
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict) and "certified_gap" in obj:
                        candidate_data = obj
                        break
                except json.JSONDecodeError:
                    continue

            if candidate_data is None:
                return EvalOutput(score=0.0, metrics={}, passed=False,
                                  failure_reason="No candidate output")

            cert_gap = candidate_data.get("certified_gap", 0.0)
            E0_lb = candidate_data.get("E0_lb", None)

            if cert_gap <= 0:
                return EvalOutput(score=0.0, metrics=candidate_data, passed=True,
                                  failure_reason="certified_gap ≤ 0")

            if E0_lb is None:
                return EvalOutput(score=0.0, metrics=candidate_data, passed=False,
                                  failure_reason="Missing E0_lb")

            # E0_lb validity check
            if E0_lb > self.E0_ed + 1e-8:
                return EvalOutput(
                    score=0.0, metrics=candidate_data, passed=False,
                    failure_reason=f"E0_lb={E0_lb:.10f} > E0_ed={self.E0_ed:.10f}",
                )

            # Scoring
            score = min(cert_gap / self.gap_ed, 1.0)

            # Over-certification check
            if cert_gap > self.gap_ed * 1.01:
                score = 0.0

            candidate_data["score"] = score
            candidate_data["gap_ed"] = self.gap_ed
            return EvalOutput(score=score, metrics=candidate_data, passed=True,
                              confidence=0.95)

        except Exception as e:
            return EvalOutput(score=0.0, metrics={}, passed=False,
                              failure_reason=f"Parse error: {e}")
