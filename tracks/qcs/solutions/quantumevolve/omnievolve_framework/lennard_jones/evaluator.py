"""#117 Lennard-Jones 团簇评估器（OmniEvolve TaskEvaluator）。

评估流程（两步沙箱命令）：
    1. main.py        —— 候选代码（被进化的搜索策略），写出 candidate_result.json
    2. verify_lj.py   —— 验证器，用参考核 lj_ref 从坐标独立重算能量/力范数，
                         输出评分 JSON（最后一行）

评分（正确性门 + 性能分，对齐 examples/template 范式）：
    valid = 力范数收敛 且 自报能量与重算一致（由验证器判定）
    perf  = clip((E_BASE - E) / (E_BASE - E_GM), 0, 1)
    score = 0.5 (valid 即得) + 0.5 * perf
    passed = valid 且 E <= E_GM + 1e-3（触及已知全局极小）

不可作弊：能量由验证器从候选输出坐标重算，候选无法通过谎报能量获利。
"""

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

# 评分锚点（LJ38）
E_BASE = -150.0          # 无优化基线能量（score 0 锚点）
E_GM = -173.928426       # fcc 截角八面体全局极小（score 1 锚点）
GM_TOL = 1e-3            # 触及 GM 的容差


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class LennardJonesEvaluator:
    """LJ 团簇全局优化评估器。"""

    version_id = "lj-cluster@1.0.0"

    def build_plan(
        self, candidate: CandidateArtifact, context: EvaluationContext
    ) -> EvaluationPlan:
        return EvaluationPlan(
            commands=[
                # 步骤 1：候选搜索策略（被进化），写出 candidate_result.json
                CommandSpec(
                    argv=[sys.executable, "main.py"],
                    timeout_sec=160.0,
                    env={
                        "OPENBLAS_NUM_THREADS": "1",
                        "OMP_NUM_THREADS": "1",
                        "MKL_NUM_THREADS": "1",
                    },
                ),
                # 步骤 2：验证器独立重算，输出评分 JSON
                CommandSpec(argv=[sys.executable, "verify_lj.py"], timeout_sec=15.0),
            ],
            mounts=[
                MountSpec(source=os.path.join(_WORKSPACE, "lj_ref.py"), target="/workspace/lj_ref.py"),
                MountSpec(source=os.path.join(_WORKSPACE, "verify_lj.py"), target="/workspace/verify_lj.py"),
            ],
            expected_outputs=["candidate_result.json", "verify_result.json"],
            network_access=False,
        )

    def parse_result(
        self, result: SandboxExecutionResult, context: EvaluationContext
    ) -> EvalOutput:
        if result.timed_out:
            return EvalOutput(score=0.0, metrics={}, passed=False, failure_reason="timeout")

        if not result.return_codes or result.return_codes[0] != 0:
            tail = (result.stderr or "")[-500:]
            return EvalOutput(score=0.0, metrics={}, passed=False, failure_reason=f"candidate failed: {tail}")

        # 从 stdout 末尾向前扫描验证器的评分 JSON（含 energy_recomputed 键）
        verify = None
        for line in reversed(result.stdout.strip().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "energy_recomputed" in obj:
                verify = obj
                break

        if verify is None:
            return EvalOutput(score=0.0, metrics={}, passed=False, failure_reason="no verifier output")

        if not verify.get("valid", False):
            return EvalOutput(
                score=0.0,
                metrics={"force_norm": verify.get("force_norm", float("inf"))},
                passed=False,
                failure_reason=verify.get("error", "invalid structure"),
            )

        energy = float(verify["energy_recomputed"])
        perf = _clip((E_BASE - energy) / (E_BASE - E_GM), 0.0, 1.0)
        score = 0.5 + 0.5 * perf
        passed = energy <= E_GM + GM_TOL

        return EvalOutput(
            score=score,
            metrics={
                "energy_recomputed": energy,
                "force_norm": verify.get("force_norm", 0.0),
                "gap_to_gm": verify.get("gap_to_gm", E_GM - energy),
                "n_force_evals": verify.get("n_force_evals", 0),
                "perf": perf,
                "catch": float(verify.get("catch", False)),
                "execution_time_ms": result.execution_time_ms,
            },
            passed=passed,
            confidence=0.95,
        )

    def get_baseline(self) -> float:
        """基线分数：valid 结构但无能量进展（score 0.5 门）。"""
        return 0.5


class LennardJonesSearchEvaluator(LennardJonesEvaluator):
    """短预算搜索评估器；GM 命中后用函数评估次数打破同分。"""

    version_id = "lj-cluster-search-35s@1.0.0"

    def build_plan(
        self, candidate: CandidateArtifact, context: EvaluationContext
    ) -> EvaluationPlan:
        return EvaluationPlan(
            commands=[
                CommandSpec(
                    argv=[sys.executable, "main.py"],
                    timeout_sec=50.0,
                    env={
                        "OPENBLAS_NUM_THREADS": "1",
                        "OMP_NUM_THREADS": "1",
                        "MKL_NUM_THREADS": "1",
                        "LJ_TIME_BUDGET_SEC": "35.0",
                    },
                ),
                CommandSpec(argv=[sys.executable, "verify_lj.py"], timeout_sec=15.0),
            ],
            mounts=[
                MountSpec(source=os.path.join(_WORKSPACE, "lj_ref.py"), target="/workspace/lj_ref.py"),
                MountSpec(
                    source=os.path.join(_WORKSPACE, "verify_lj.py"),
                    target="/workspace/verify_lj.py",
                ),
            ],
            expected_outputs=["candidate_result.json", "verify_result.json"],
            network_access=False,
        )

    def parse_result(
        self, result: SandboxExecutionResult, context: EvaluationContext
    ) -> EvalOutput:
        base = super().parse_result(result, context)
        if not base.passed:
            # 未命中 GM 时仍以能量质量为主，且分数严格低于任何 GM 命中。
            return EvalOutput(
                score=min(0.989, base.score * 0.989),
                metrics=base.metrics,
                passed=False,
                failure_reason=base.failure_reason,
                confidence=base.confidence,
            )
        metrics = dict(base.metrics)
        n_evals = max(0, int(metrics.get("n_force_evals", 0)))
        efficiency = 1.0 / (1.0 + n_evals / 100.0)
        metrics["eval_efficiency"] = efficiency
        return EvalOutput(
            score=0.99 + 0.01 * efficiency,
            metrics=metrics,
            passed=True,
            confidence=base.confidence,
        )
