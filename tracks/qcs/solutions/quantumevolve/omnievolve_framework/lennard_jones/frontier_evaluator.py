"""OmniEvolve evaluator for the #117 monoatomic large-N frontier track."""

from __future__ import annotations

import json
import math
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

_HERE = os.path.dirname(os.path.abspath(__file__))
E_STRICT_BASELINE = -6558.225147857512


class LennardJonesFrontierEvaluator:
    version_id = "lj924-frontier@1.3.0"

    def build_plan(
        self, candidate: CandidateArtifact, context: EvaluationContext
    ) -> EvaluationPlan:
        mounts = [
            MountSpec(
                source=os.path.join(_HERE, "lj_ref.py"),
                target="/workspace/lj_ref.py",
            ),
            MountSpec(
                source=os.path.join(_HERE, "verify_frontier.py"),
                target="/workspace/verify_frontier.py",
            ),
        ]
        for n in (923, 924, 925):
            mounts.append(
                MountSpec(
                    source=os.path.join(_HERE, "frontier", "incumbents", f"{n}.TXT"),
                    target=f"/workspace/{n}.TXT",
                )
            )
        return EvaluationPlan(
            commands=[
                CommandSpec(
                    argv=[sys.executable, "main.py"],
                    timeout_sec=190.0,
                    env={
                        "OPENBLAS_NUM_THREADS": "1",
                        "OMP_NUM_THREADS": "1",
                        "MKL_NUM_THREADS": "1",
                        "LJ_FRONTIER_TIME_BUDGET_SEC": "170",
                        "LJ924_INCUMBENT_FILE": "924.TXT",
                        "LJ_FRONTIER_RUN_KEY": candidate.candidate_id,
                    },
                ),
                CommandSpec(
                    argv=[sys.executable, "verify_frontier.py"],
                    timeout_sec=30.0,
                ),
            ],
            mounts=mounts,
            expected_outputs=["candidate_result.json", "verify_result.json"],
            network_access=False,
        )

    def parse_result(
        self, result: SandboxExecutionResult, context: EvaluationContext
    ) -> EvalOutput:
        if result.timed_out or not result.return_codes or result.return_codes[0] != 0:
            return EvalOutput(
                score=0.0,
                metrics={},
                passed=False,
                failure_reason=(result.stderr or "candidate timeout/failure")[-500:],
            )
        verified = None
        for line in reversed(result.stdout.splitlines()):
            try:
                obj = json.loads(line.strip())
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "energy_recomputed" in obj:
                verified = obj
                break
        if (
            not verified
            or not verified.get("valid", False)
            or not verified.get("monotonicity_ok", False)
        ):
            return EvalOutput(
                score=0.0,
                metrics=verified or {},
                passed=False,
                failure_reason=(verified or {}).get("error", "missing verifier result"),
            )
        energy = float(verified["energy_recomputed"])
        delta = E_STRICT_BASELINE - energy
        n_evals = max(0, int(verified.get("n_force_evals", 0)))
        efficiency = 1.0 / (1.0 + n_evals / 1000.0)
        strict_improvement = bool(verified.get("strict_improvement", False))
        proposal_valid = bool(verified.get("proposal_valid", False))
        if strict_improvement:
            # A verifier-valid record improvement always outranks search-only
            # progress, preserving the official competition objective.
            score = 2.0 + min(delta, 100.0)
        elif proposal_valid:
            proposal_energy = float(verified["proposal_energy_recomputed"])
            proposal_force = max(
                0.0, float(verified.get("proposal_max_atom_force", 0.0))
            )
            energy_signal = max(
                -100.0,
                min(100.0, E_STRICT_BASELINE - proposal_energy),
            )
            force_penalty = 0.01 * math.log1p(proposal_force / 1e-8)
            behavior_penalty = (
                0.0 if verified.get("proposal_differs_from_submission", False) else 0.25
            )
            proposal_merit = energy_signal - force_penalty - behavior_penalty
            # Keep all search-only scores below the strict-improvement tier while
            # exposing a dense ordering among failed basins.
            score = min(1.999999, 1.0 + 1e-4 * proposal_merit)
        else:
            # A candidate that hides its attempted structure behind the incumbent
            # is verifier-valid but useless for evolution.
            proposal_merit = -1000.0
            score = 0.5
        metrics = dict(verified)
        metrics["eval_efficiency"] = efficiency
        metrics["proposal_search_fitness"] = proposal_merit if not strict_improvement else delta
        return EvalOutput(
            score=score,
            metrics=metrics,
            passed=True,
            confidence=0.95,
        )

    def get_baseline(self) -> float:
        return 1.0
