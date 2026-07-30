"""#34 N-queens 评估器（OmniEvolve TaskEvaluator）。

v2: 多 N 阶梯评估。

评估流程：
    1. main.py 在多个 N 值上运行（N=12,14,16），验证器逐个比对 OEIS
    2. verify_nq.py 执行多 N 交叉验证 + 反作弊 + 效率评分

评分（阶梯式）：
    - N=12 正确：0.3 分（基础门槛）
    - N=14 正确：+0.3 分
    - N=16 正确：+0.2 分
    - 效率奖励：+0.2 分（相对于种子的加速比）
    - 硬编码作弊：效率分归零，且多 N 验证暴露

不可作弊：多个 N 值交叉验证 + 源码扫描。
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

# 阶梯评估的 N 值（权重递增）
EVAL_NS = [12, 14, 16]


class NQueensEvaluator:
    """N-queens 多 N 阶梯评估器。"""

    version_id = "nqueens@2.0.0"

    def build_plan(
        self, candidate: CandidateArtifact, context: EvaluationContext
    ) -> EvaluationPlan:
        # 构建环境变量：第一个 N 由 main.py 直接读取
        return EvaluationPlan(
            commands=[
                CommandSpec(
                    argv=[sys.executable, "main.py"],
                    timeout_sec=100.0,
                    env={
                        "OPENBLAS_NUM_THREADS": "1",
                        "OMP_NUM_THREADS": "1",
                        "MKL_NUM_THREADS": "1",
                        "NQUEENS_N": str(EVAL_NS[0]),
                        "EVAL_NS": ",".join(str(n) for n in EVAL_NS),
                    },
                ),
                CommandSpec(
                    argv=[sys.executable, "verify_nq.py"],
                    timeout_sec=30.0,
                ),
            ],
            mounts=[
                MountSpec(source=os.path.join(_WORKSPACE, "verify_nq.py"), target="/workspace/verify_nq.py"),
                MountSpec(source=os.path.join(_WORKSPACE, "oeis_ref.py"), target="/workspace/oeis_ref.py"),
                MountSpec(source=os.path.join(_WORKSPACE, "tn_construct.py"), target="/workspace/tn_construct.py"),
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

        # 解析验证器输出（最后一个含 "score" 的 JSON 行）
        verify = None
        for line in reversed(result.stdout.strip().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "score" in obj:
                verify = obj
                break

        if verify is None:
            return EvalOutput(score=0.0, metrics={}, passed=False, failure_reason="no verifier output")

        if not verify.get("valid", False):
            return EvalOutput(
                score=0.0,
                metrics={},
                passed=False,
                failure_reason=verify.get("error", "invalid result"),
            )

        score = float(verify.get("score", 0.0))

        # 提取所有 N 的结果作为 metrics
        metrics = {"score": score}
        for n in EVAL_NS:
            key = f"Q({n})"
            if key in verify.get("results", {}):
                metrics[key] = verify["results"][key]

        metrics["wall_time_sec"] = float(verify.get("wall_time_sec", 0))

        passed = score >= 0.6  # 至少通过 N=12 和 N=14

        return EvalOutput(
            score=score,
            metrics=metrics,
            passed=passed,
            confidence=0.99,
        )

    def get_baseline(self) -> float:
        """基线：种子在 N=12 正确但 N=14/16 可能超时。"""
        return 0.3
