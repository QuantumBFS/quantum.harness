"""OmniEvolve evaluator for the sparse graph-33 state-polynomial basis search."""

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
_PREFIX = "OMNIEVOLVE_GRAPH33_RESULT="


class Graph33BasisEvaluator:
    version_id = "graph33-sparse-state-basis@1.0.0"

    def build_plan(self, candidate: CandidateArtifact, context: EvaluationContext) -> EvaluationPlan:
        return EvaluationPlan(
            commands=[
                CommandSpec(
                    argv=[sys.executable, "verify_candidate.py", "main.py"],
                    timeout_sec=30.0,
                )
            ],
            mounts=[
                MountSpec(source=os.path.join(_WORKSPACE, name), target=f"/workspace/{name}")
                for name in ("verify_candidate.py", "problem.py", "theta_relaxation.py")
            ],
            expected_outputs=[],
            network_access=False,
        )

    def parse_result(
        self, result: SandboxExecutionResult, context: EvaluationContext
    ) -> EvalOutput:
        if result.timed_out:
            return EvalOutput(score=0.0, metrics={}, passed=False, failure_reason="SDP timeout")
        payload = None
        for line in reversed(result.stdout.splitlines()):
            if line.startswith(_PREFIX):
                try:
                    payload = json.loads(line[len(_PREFIX) :])
                except json.JSONDecodeError:
                    payload = None
                break
        if payload is None or not payload.get("valid", False):
            error = "missing verifier result" if payload is None else payload.get("error", "rejected")
            return EvalOutput(
                score=0.0,
                metrics={"verifier_error": error},
                passed=False,
                failure_reason=str(error),
            )
        metrics = dict(payload)
        metrics.pop("score", None)
        metrics.pop("valid", None)
        metrics.pop("passed", None)
        metrics["execution_time_ms"] = result.execution_time_ms
        return EvalOutput(
            score=float(payload["score"]),
            metrics=metrics,
            passed=True,
            confidence=0.99,
        )

    def get_baseline(self) -> float:
        return 0.50
