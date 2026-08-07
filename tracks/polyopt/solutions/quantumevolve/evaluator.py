"""OmniEvolve evaluator for the fast certified-sandwich pilot of issue #232."""

from __future__ import annotations

import json
import os
import sys

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
_PREFIX = "OMNIEVOLVE_BELL_RESULT="


class BellCertificateEvaluator:
    """Require exact SOHS validity before optimizing the Bell sandwich gap."""

    version_id = "bell-certificate-fast@1.0.0"

    def build_plan(
        self, candidate: CandidateArtifact, context: EvaluationContext
    ) -> EvaluationPlan:
        return EvaluationPlan(
            commands=[
                CommandSpec(
                    argv=[sys.executable, "verify_candidate.py", "main.py"],
                    timeout_sec=8.0,
                )
            ],
            mounts=[
                MountSpec(
                    source=os.path.join(_WORKSPACE, "verify_candidate.py"),
                    target="/workspace/verify_candidate.py",
                )
            ],
            expected_outputs=[],
            network_access=False,
        )

    def parse_result(
        self, result: SandboxExecutionResult, context: EvaluationContext
    ) -> EvalOutput:
        if result.timed_out:
            return EvalOutput(
                score=0.0, metrics={}, passed=False, failure_reason="verification timeout"
            )

        payload = None
        for line in reversed(result.stdout.splitlines()):
            if line.startswith(_PREFIX):
                try:
                    payload = json.loads(line[len(_PREFIX) :])
                except json.JSONDecodeError:
                    payload = None
                break
        if payload is None:
            return EvalOutput(
                score=0.0,
                metrics={},
                passed=False,
                failure_reason="missing independent verifier result",
            )
        if not payload.get("valid", False):
            return EvalOutput(
                score=0.0,
                metrics={"verifier_error": payload.get("error", "unknown")},
                passed=False,
                failure_reason=str(payload.get("error", "candidate rejected")),
            )

        metrics = {
            key: payload[key]
            for key in (
                "problem_id",
                "certificate_valid",
                "sandwich_valid",
                "closed",
                "upper_bound",
                "lower_bound",
                "sandwich_gap",
                "residual_l1",
                "residual_terms",
                "first_residual",
                "behavior_signature",
            )
        }
        metrics["execution_time_ms"] = result.execution_time_ms
        passed = bool(payload["passed"])
        return EvalOutput(
            score=float(payload["score"]),
            metrics=metrics,
            passed=passed,
            confidence=1.0,
            failure_reason=None
            if passed
            else "invalid certificate or inconsistent Bell sandwich",
        )

    def get_baseline(self) -> float:
        # Deliberately suboptimal angles in initial_code.py score around 0.92.
        return 0.92
