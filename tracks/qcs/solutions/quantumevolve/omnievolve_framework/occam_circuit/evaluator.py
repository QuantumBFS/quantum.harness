"""#71 Occam's Circuit 评估器（OmniEvolve TaskEvaluator）。

评估流程（两步沙箱命令）：
    1. main.py          —— 候选（被进化的电路综合策略），读 train/test_inputs，写出 circuit.txt
    2. verify_circuit.py —— 验证器，在 train/test 上模拟电路、与真值比对，输出评分 JSON

评分（对齐题面排行榜：精度优先、门数次之）：
    score  = 0.7 * test_acc + 0.3 * max(0, 1 - gates / GATE_CAP)
    passed = train_acc == 1.0（拟合训练集）且 test_acc >= 0.99（能泛化）

不可作弊：test 输出由验证器持有并比对，候选只见 train + test_inputs；
记忆 train 的电路 test_acc 会很低，无法靠记忆得高分。

隔离说明：test_outputs.csv 挂载到 /verifier_data/（非 /workspace/），
在 docker 沙箱中候选无法访问。trusted_subprocess 模式无文件隔离（已知限制，
仅用于开发调试；正式评估须切 docker/monty 后端）。
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from pathlib import Path

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


class OccamCircuitEvaluator:
    """Occam's Circuit 评估器。"""

    version_id = "occam-circuit@1.0.0"

    # mystery 官方隐藏 test 尚未公开；本地进化时从官方 train 做固定 80/20 隔离。
    # 通过 OCCAM_INSTANCE=mystery-A..D 选择实例。
    INSTANCE = os.environ.get("OCCAM_INSTANCE", "practice-add-n4")
    GATE_CAP = 150.0  # 门数满分参考（越少越好）

    def _ds(self, name: str) -> str:
        official = Path(_WORKSPACE) / "datasets" / self.INSTANCE
        if (official / "test_outputs.csv").exists():
            return str(official / name)
        return str(self._ensure_dev_split() / name)

    def _ensure_dev_split(self) -> Path:
        """把 mystery train 固定拆为候选可见 80% 与验证器私有 20%。"""
        source = Path(_WORKSPACE) / "datasets" / self.INSTANCE / "train.csv"
        target = Path(_WORKSPACE).parents[1] / ".omnievolve" / "occam_dev" / self.INSTANCE
        train_path = target / "train.csv"
        test_in_path = target / "test_inputs.csv"
        test_out_path = target / "test_outputs.csv"
        if train_path.exists() and test_in_path.exists() and test_out_path.exists():
            return target
        with source.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        visible = [row for i, row in enumerate(rows) if i % 5 != 0]
        hidden = [row for i, row in enumerate(rows) if i % 5 == 0]
        target.mkdir(parents=True, exist_ok=True)
        with train_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["input", "output"])
            writer.writeheader()
            writer.writerows(visible)
        with test_in_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["input"])
            writer.writeheader()
            writer.writerows({"input": row["input"]} for row in hidden)
        with test_out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["output"])
            writer.writeheader()
            writer.writerows({"output": row["output"]} for row in hidden)
        return target

    def build_plan(
        self, candidate: CandidateArtifact, context: EvaluationContext
    ) -> EvaluationPlan:
        return EvaluationPlan(
            commands=[
                CommandSpec(argv=[sys.executable, "main.py"], timeout_sec=40.0),
                CommandSpec(argv=[sys.executable, "verify_circuit.py"], timeout_sec=30.0),
            ],
            mounts=[
                MountSpec(source=os.path.join(_WORKSPACE, "verify_circuit.py"), target="/workspace/verify_circuit.py"),
                MountSpec(source=self._ds("train.csv"), target="/workspace/train.csv"),
                MountSpec(source=self._ds("test_inputs.csv"), target="/workspace/test_inputs.csv"),
                # test_outputs 挂载到 /verifier_data/（非 /workspace/），docker 模式下候选不可见
                MountSpec(source=self._ds("test_outputs.csv"), target="/verifier_data/test_outputs.csv"),
            ],
            expected_outputs=["circuit.txt", "verify_result.json"],
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

        verify = None
        for line in reversed(result.stdout.strip().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "test_acc" in obj:
                verify = obj
                break

        if verify is None or not verify.get("valid", False):
            reason = verify.get("error", "no verifier output") if verify else "no verifier output"
            return EvalOutput(score=0.0, metrics={}, passed=False, failure_reason=reason)

        test_acc = float(verify["test_acc"])
        train_acc = float(verify["train_acc"])
        gates = int(verify["gates"])
        gate_term = max(0.0, 1.0 - gates / self.GATE_CAP)
        score = 0.7 * test_acc + 0.3 * gate_term
        passed = train_acc == 1.0 and test_acc >= 0.99

        return EvalOutput(
            score=score,
            metrics={
                "test_acc": test_acc,
                "train_acc": train_acc,
                "bit_acc": verify.get("bit_acc", 0.0),
                "gates": gates,
                "gate_term": gate_term,
                "execution_time_ms": result.execution_time_ms,
                "instance": self.INSTANCE,
            },
            passed=passed,
            confidence=0.95,
        )

    def get_baseline(self) -> float:
        """基线分数：种子在 practice-add 上约 0.95（test_acc=1.0, ~23 门）。"""
        return 0.7


class OccamCircuitSuiteEvaluator(OccamCircuitEvaluator):
    """四个 mystery 联合评估：准确率是硬门，总门数只在全对时破同分。"""

    version_id = "occam-circuit-suite@1.1.0"
    INSTANCES = ("mystery-A", "mystery-B", "mystery-C", "mystery-D")
    TOTAL_GATE_CAP = 1000.0

    def _split_for(self, instance: str) -> Path:
        previous = self.INSTANCE
        try:
            self.INSTANCE = instance
            return self._ensure_dev_split()
        finally:
            self.INSTANCE = previous

    def build_plan(
        self, candidate: CandidateArtifact, context: EvaluationContext
    ) -> EvaluationPlan:
        commands: list[CommandSpec] = []
        mounts: list[MountSpec] = [
            MountSpec(
                source=os.path.join(_WORKSPACE, "verify_circuit.py"),
                target="/workspace/verify_circuit.py",
            )
        ]
        expected: list[str] = []
        for instance in self.INSTANCES:
            split = self._split_for(instance)
            train_file = f"{instance}_train.csv"
            test_input_file = f"{instance}_test_inputs.csv"
            test_output_file = f"{instance}_test_outputs.csv"
            circuit = f"{instance}.txt"
            verify_out = f"{instance}_verify.json"
            candidate_env = {
                "OCCAM_INSTANCE": instance,
                "OCCAM_TRAIN_FILE": train_file,
                "OCCAM_CIRCUIT_FILE": circuit,
            }
            verifier_env = {
                **candidate_env,
                "OCCAM_TEST_INPUT_FILE": test_input_file,
                "OCCAM_TEST_OUTPUT_FILE": f"/verifier_data/{test_output_file}",
                "OCCAM_TEST_OUTPUT_FALLBACK": test_output_file,
                "OCCAM_VERIFY_OUTPUT": verify_out,
            }
            commands.append(
                CommandSpec(
                    argv=[sys.executable, "main.py"],
                    timeout_sec=40.0,
                    env=candidate_env,
                )
            )
            commands.append(
                CommandSpec(
                    argv=[sys.executable, "verify_circuit.py"],
                    timeout_sec=30.0,
                    env=verifier_env,
                )
            )
            mounts.extend(
                [
                    MountSpec(
                        source=str(split / "train.csv"),
                        target=f"/workspace/{train_file}",
                    ),
                    MountSpec(
                        source=str(split / "test_inputs.csv"),
                        target=f"/workspace/{test_input_file}",
                    ),
                    MountSpec(
                        source=str(split / "test_outputs.csv"),
                        target=f"/verifier_data/{test_output_file}",
                    ),
                ]
            )
            expected.extend([circuit, verify_out])
        return EvaluationPlan(
            commands=commands,
            mounts=mounts,
            expected_outputs=expected,
            network_access=False,
        )

    def parse_result(
        self, result: SandboxExecutionResult, context: EvaluationContext
    ) -> EvalOutput:
        if result.timed_out or any(code != 0 for code in result.return_codes):
            return EvalOutput(
                score=0.0,
                metrics={},
                passed=False,
                failure_reason=(result.stderr or "suite command failed")[-500:],
            )
        by_instance: dict[str, dict] = {}
        for line in result.stdout.splitlines():
            try:
                obj = json.loads(line.strip())
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("instance") in self.INSTANCES:
                by_instance[obj["instance"]] = obj
        if set(by_instance) != set(self.INSTANCES):
            return EvalOutput(
                score=0.0,
                metrics={"seen_instances": sorted(by_instance)},
                passed=False,
                failure_reason="missing suite verifier result",
            )
        min_test = min(float(v["test_acc"]) for v in by_instance.values())
        min_train = min(float(v["train_acc"]) for v in by_instance.values())
        average_test = sum(float(v["test_acc"]) for v in by_instance.values()) / len(
            by_instance
        )
        average_bit = sum(float(v["bit_acc"]) for v in by_instance.values()) / len(
            by_instance
        )
        total_gates = sum(int(v["gates"]) for v in by_instance.values())
        gate_term = max(0.0, 1.0 - total_gates / self.TOTAL_GATE_CAP)
        passed = min_train == 1.0 and min_test == 1.0
        if passed:
            # Keep the official ordering unchanged for exact candidates.
            score = 0.99 + 0.01 * gate_term
        else:
            # Dense diagnostic fitness for failed mutations.  Exactness remains a
            # hard pass gate, but the next generation can now distinguish a
            # one-bit near miss from a completely broken circuit.
            score = (
                0.70 * min_test
                + 0.20 * average_test
                + 0.09 * average_bit
                + 0.01 * gate_term
            )
        suite_behavior_signature = hashlib.sha256(
            "|".join(
                str(by_instance[instance].get("behavior_signature", "missing"))
                for instance in self.INSTANCES
            ).encode("ascii")
        ).hexdigest()[:16]
        metrics: dict[str, object] = {
            "min_test_acc": min_test,
            "min_train_acc": min_train,
            "average_test_acc": average_test,
            "average_bit_acc": average_bit,
            "total_gates": total_gates,
            "gate_delta_vs_399": total_gates - 399,
            "gate_term": gate_term,
            "behavior_signature": suite_behavior_signature,
            "execution_time_ms": result.execution_time_ms,
        }
        for instance, values in by_instance.items():
            metrics[f"{instance}_test_acc"] = float(values["test_acc"])
            metrics[f"{instance}_train_acc"] = float(values["train_acc"])
            metrics[f"{instance}_bit_acc"] = float(values["bit_acc"])
            metrics[f"{instance}_gates"] = int(values["gates"])
            metrics[f"{instance}_behavior_signature"] = values.get(
                "behavior_signature", ""
            )
            metrics[f"{instance}_circuit_signature"] = values.get(
                "circuit_signature", ""
            )
            if values.get("first_test_failure") is not None:
                metrics[f"{instance}_first_test_failure"] = values[
                    "first_test_failure"
                ]
        return EvalOutput(
            score=score,
            metrics=metrics,
            passed=passed,
            confidence=0.95,
            failure_reason=None if passed else "at least one mystery instance is not exact",
        )

    def get_baseline(self) -> float:
        return 0.99
