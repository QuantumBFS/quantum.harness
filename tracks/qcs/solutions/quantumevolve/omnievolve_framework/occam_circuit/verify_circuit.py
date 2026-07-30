"""#71 Occam's Circuit 验证器（沙箱内运行，verify.jl 的纯 Python 移植）。

读取候选代码 (main.py) 写出的网表 circuit.txt，在 train/test 输入上逐位模拟，
与真值比对，输出评分 JSON（最后一行）供评估器解析。保持沙箱纯 Python，无需 Julia。

网表格式（与题面一致）：
    INPUTS 16
    w1 = XOR x1 x9
    w2 = AND x1 x9
    w3 = XOR ~w1 x2          # ~ 为免费反相器
    ...
    OUTPUTS w1 w3 w7 ...

- 输入变量 x1..x{2n}（1-indexed），对应输入位串字符 0..2n-1。
- 门：AND OR XOR NAND NOR XNOR，fanin-2；反相器 ~ 免费（不计入门数）。
- OUTPUTS 列出 m 个输出 wire（顺序即输出位串，LSB-first）。

评分输出 JSON 键：
    train_acc / test_acc   —— 精确匹配准确率（整条输出位串全对）
    bit_acc                —— 逐位准确率
    gates                  —— 门数（反相器免费）
    valid                  —— 网表可解析、可运行、输出宽度正确
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys

CIRCUIT_FILE = os.environ.get("OCCAM_CIRCUIT_FILE", "circuit.txt")
TRAIN_FILE = os.environ.get("OCCAM_TRAIN_FILE", "train.csv")
TEST_IN_FILE = os.environ.get("OCCAM_TEST_INPUT_FILE", "test_inputs.csv")
# test_outputs 隔离在 /verifier_data/（docker 模式）；trusted 模式 fallback 到 cwd
TEST_OUT_FILE = os.environ.get("OCCAM_TEST_OUTPUT_FILE", "/verifier_data/test_outputs.csv")
TEST_OUT_FALLBACK = os.environ.get("OCCAM_TEST_OUTPUT_FALLBACK", "test_outputs.csv")
VERIFY_OUTPUT = os.environ.get("OCCAM_VERIFY_OUTPUT", "verify_result.json")

GATES = {"AND", "OR", "XOR", "NAND", "NOR", "XNOR"}


def _fail(reason: str) -> dict:
    return {
        "train_acc": 0.0, "test_acc": 0.0, "bit_acc": 0.0,
        "gates": 0, "n_inputs": 0, "m_outputs": 0,
        "valid": False, "error": reason,
    }


def parse_netlist(text: str) -> tuple[int, list[tuple[str, str, str, bool, bool]], list[str]]:
    """解析网表 -> (n_inputs, gates, outputs)。

    gates: [(gate, op_a, op_b, neg_a, neg_b)]，wire 名按定义顺序隐含（w1, w2, ...）。
    返回的 gates 用 wire 名 -> 索引由调用方维护。
    """
    n_inputs = None
    gates: list[tuple[str, str, str, bool, bool]] = []
    outputs: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        up = line.upper()
        if up.startswith("INPUTS"):
            n_inputs = int(line.split()[1])
            continue
        if up.startswith("OUTPUTS"):
            outputs = line.split()[1:]
            continue
        if "=" in line:
            lhs, rhs = line.split("=", 1)
            lhs = lhs.strip()
            toks = rhs.split()
            gate = toks[0].upper()
            if gate not in GATES:
                raise ValueError(f"unknown gate {gate!r}")
            if len(toks) != 3:
                raise ValueError(f"gate {lhs} needs exactly 2 operands")
            ops = []
            for t in toks[1:]:
                neg = t.startswith("~")
                name = t[1:] if neg else t
                ops.append((name, neg))
            gates.append((gate, ops[0][0], ops[1][0], ops[0][1], ops[1][1]))
    if n_inputs is None:
        raise ValueError("missing INPUTS line")
    if not outputs:
        raise ValueError("missing OUTPUTS line")
    return n_inputs, gates, outputs


def _apply_gate(gate: str, a: int, b: int) -> int:
    if gate == "AND":
        return a & b
    if gate == "OR":
        return a | b
    if gate == "XOR":
        return a ^ b
    if gate == "NAND":
        return 1 - (a & b)
    if gate == "NOR":
        return 1 - (a | b)
    if gate == "XNOR":
        return 1 - (a ^ b)
    raise ValueError(gate)


def simulate(n_inputs: int, gates, outputs: list[str], inp: str) -> str:
    """对单个输入位串模拟电路，返回输出位串。"""
    env: dict[str, int] = {}
    for k in range(n_inputs):
        env[f"x{k + 1}"] = int(inp[k])
    for i, (gate, op_a, op_b, neg_a, neg_b) in enumerate(gates, start=1):
        va = env[op_a]
        vb = env[op_b]
        if neg_a:
            va = 1 - va
        if neg_b:
            vb = 1 - vb
        env[f"w{i}"] = _apply_gate(gate, va, vb)
    return "".join(str(env[w]) for w in outputs)


def _read_csv_col(path: str, col: str) -> list[str]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row[col] for row in reader]


def main() -> dict:
    # test_outputs 优先从隔离路径读（docker），fallback 到 cwd（trusted mode）
    test_out_path = TEST_OUT_FILE if os.path.exists(TEST_OUT_FILE) else TEST_OUT_FALLBACK
    for required in (CIRCUIT_FILE, TRAIN_FILE, TEST_IN_FILE, test_out_path):
        if not os.path.exists(required):
            return _fail(f"missing {required}")

    try:
        with open(CIRCUIT_FILE, encoding="utf-8") as f:
            netlist_text = f.read()
        n_inputs, gates, outputs = parse_netlist(netlist_text)
    except (ValueError, IndexError, KeyError) as exc:
        return _fail(f"bad netlist: {exc}")

    try:
        train_in = _read_csv_col(TRAIN_FILE, "input")
        train_out = _read_csv_col(TRAIN_FILE, "output")
        test_in = _read_csv_col(TEST_IN_FILE, "input")
        test_out = _read_csv_col(test_out_path, "output")
    except (KeyError, OSError) as exc:
        return _fail(f"bad dataset: {exc}")

    m = len(outputs)
    # 输出宽度须与数据一致
    if train_out and len(train_out[0]) != m:
        return _fail(f"OUTPUTS width {m} != data output width {len(train_out[0])}")

    def accuracy(inputs, truths):
        if not inputs:
            return 0.0, 0.0, 0, None, []
        exact = 0
        bit_ok = 0
        bit_tot = 0
        first_failure = None
        predictions = []
        for inp, truth in zip(inputs, truths):
            if len(inp) != n_inputs:
                return 0.0, 0.0, 0, None, []
            try:
                pred = simulate(n_inputs, gates, outputs, inp)
            except KeyError:
                return 0.0, 0.0, 0, None, []
            predictions.append(pred)
            if pred == truth:
                exact += 1
            elif first_failure is None:
                first_failure = {
                    "input": inp,
                    "expected": truth,
                    "actual": pred,
                    "wrong_bits": [
                        index
                        for index, (actual, expected) in enumerate(zip(pred, truth))
                        if actual != expected
                    ],
                }
            for p, t in zip(pred, truth):
                bit_tot += 1
                if p == t:
                    bit_ok += 1
        return (
            exact / len(inputs),
            bit_ok / bit_tot if bit_tot else 0.0,
            exact,
            first_failure,
            predictions,
        )

    train_acc, train_bit, train_exact, train_failure, train_predictions = accuracy(
        train_in, train_out
    )
    test_acc, test_bit, test_exact, test_failure, test_predictions = accuracy(
        test_in, test_out
    )
    bit_acc = 0.5 * (train_bit + test_bit)
    behavior_signature = hashlib.sha256(
        "\n".join([*train_predictions, "--test--", *test_predictions]).encode("ascii")
    ).hexdigest()[:16]
    circuit_signature = hashlib.sha256(
        "\n".join(
            line.strip()
            for line in netlist_text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ).encode("utf-8")
    ).hexdigest()[:16]

    return {
        "instance": os.environ.get("OCCAM_INSTANCE", ""),
        "train_acc": float(train_acc),
        "test_acc": float(test_acc),
        "bit_acc": float(bit_acc),
        "gates": len(gates),
        "n_inputs": n_inputs,
        "m_outputs": m,
        "train_exact": train_exact,
        "test_exact": test_exact,
        "first_train_failure": train_failure,
        "first_test_failure": test_failure,
        "behavior_signature": behavior_signature,
        "circuit_signature": circuit_signature,
        "valid": True,
        "error": "",
    }


if __name__ == "__main__":
    result = main()
    with open(VERIFY_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f)
    print(json.dumps(result))
    sys.exit(0)
