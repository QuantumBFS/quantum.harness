"""#71 Occam's Circuit —— 官方四题均为两个无符号 6-bit 操作数。

任务：从多项式级 train 样本恢复隐藏布尔函数，给出**最小且能泛化**的电路。
种子策略（可被进化替换/改进）：
    1. 读 train.csv，推断 n（输入位宽/2）与 m（输出位宽）。
    2. 函数族检测：覆盖官方四个 mystery 的算术结构：
       x+y、|x-y|、x*y、x²+y²，并发出对应结构化电路。
    3. 否则退回 SoP（train 最小项之和）综合——合法但只记忆 train，泛化差。

==== 输出契约（verify_circuit.py 依赖，勿破坏）====
写出 circuit.txt（fanin-2 网表）：
    INPUTS <2n>
    w1 = GATE a b        # GATE in AND OR XOR NAND NOR XNOR；~ 前缀为免费反相
    ...
    OUTPUTS <m 个 wire>  # 顺序即输出位串，LSB-first

==== 进化提示 ====
- OCCAM_AUDITED_MULTIPLIER：C 的 191-gate carry-save 乘法核与 D 的
  144-gate 平方和核均已全域审计。它们是可回退的 best，不是禁止探索的代码；
  新候选必须由完整四题 evaluator 淘汰式验证。
- 评分是四题共同的 exact hard gate：任何一题的 train 或 deterministic holdout
  失配，门数再少也没有价值。每次只针对一个实例做一个小的、可解释的改动。
- 优先级：先保留 A/B/C/D 的完整算术语义，再减少门数。允许探索 C（乘法）和
  D（平方和），但未经全输入等价验证的候选不会进入 best。
- 安全优化限于 CSE、死门删除、恒等门消除、以及能逐位证明等价的局部代数改写；
  修改 C/D 前必须能解释为什么每一个输出位仍等于原算术定义。
- mystery 实例函数未知——靠猜测+精确综合，而非记忆 train。
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

TRAIN_FILE = os.environ.get("OCCAM_TRAIN_FILE", "train.csv")
CIRCUIT_FILE = os.environ.get("OCCAM_CIRCUIT_FILE", "circuit.txt")


class Netlist:
    """累积门电路，wire 命名 w1, w2, ...（与验证器一致）。"""

    def __init__(self, n_inputs: int):
        self.n_inputs = n_inputs
        self.lines: list[str] = []
        self._zero: str | None = None
        self._cse_cache: dict[tuple[str, str, str], str] = {}

    def gate(self, g: str, a: str, b: str, neg_a: bool = False, neg_b: bool = False) -> str:
        oa = ("~" if neg_a else "") + a
        ob = ("~" if neg_b else "") + b
        # All supported gates are commutative.  Reusing an identical truth
        # table is semantics-preserving and is safe for every mystery.
        key = (g, oa, ob) if oa <= ob else (g, ob, oa)
        if key in self._cse_cache:
            return self._cse_cache[key]
        name = f"w{len(self.lines) + 1}"
        self.lines.append(f"{name} = {g} {oa} {ob}")
        self._cse_cache[key] = name
        return name

    def zero(self) -> str:
        if self._zero is None:
            self._zero = self.gate("AND", "x1", "x1", neg_b=True)  # x1 & ~x1 = 0
        return self._zero

    def and_tree(self, wires: list[str]) -> str:
        if not wires:
            return self.zero()
        acc = wires[0]
        for w in wires[1:]:
            acc = self.gate("AND", acc, w)
        return acc

    def or_tree(self, wires: list[str]) -> str:
        if not wires:
            return self.zero()
        acc = wires[0]
        for w in wires[1:]:
            acc = self.gate("OR", acc, w)
        return acc

    def render(self, outputs: list[str]) -> str:
        # Retain only gates reachable from an output.  This is a graph-level
        # deletion, so it cannot change the Boolean function of any output.
        definitions = {}
        for line in self.lines:
            wire, rhs = line.split(" = ")
            definitions[wire] = rhs.split(" ")
        reachable = set()
        pending = list(outputs)
        while pending:
            wire = pending.pop()
            if wire in reachable:
                continue
            reachable.add(wire)
            rhs = definitions.get(wire)
            if rhs:
                pending.extend(token.lstrip("~") for token in rhs[1:] if token.lstrip("~").startswith("w"))
        lines = [line for line in self.lines if line.split(" = ", 1)[0] in reachable]
        head = f"INPUTS {self.n_inputs}\n"
        tail = "\nOUTPUTS " + " ".join(outputs) + "\n"
        return head + "\n".join(lines) + tail


def _bits_lsb(value: int, width: int) -> list[int]:
    return [(value >> i) & 1 for i in range(width)]


def _from_bits_lsb(bits: list[int]) -> int:
    v = 0
    for i, b in enumerate(bits):
        v |= b << i
    return v


def read_train(path: str):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append((row["input"], row["output"]))
    n = len(rows[0][0]) // 2
    m = len(rows[0][1])
    parsed = []
    for inp, out in rows:
        xb = [int(c) for c in inp[:n]]
        yb = [int(c) for c in inp[n:]]
        parsed.append((_from_bits_lsb(xb), _from_bits_lsb(yb), _from_bits_lsb([int(c) for c in out])))
    return n, m, parsed


def detect(parsed, n, m) -> str:
    mask = (1 << m) - 1
    if all(o == ((x + y) & mask) for x, y, o in parsed):
        return "add"
    if all(o == (abs(x - y) & mask) for x, y, o in parsed):
        return "absdiff"
    if all(o == ((x * y) & mask) for x, y, o in parsed):
        return "mul"
    if all(o == ((x * x + y * y) & mask) for x, y, o in parsed):
        return "sumsq"
    return "unknown"


def xvar(i: int) -> str:
    """x 的第 i 位（0-indexed）对应输入变量 x_{i+1}。"""
    return f"x{i + 1}"


def yvar(i: int, n: int) -> str:
    """y 的第 i 位（0-indexed）对应输入变量 x_{n+i+1}。"""
    return f"x{n + i + 1}"


def build_adder(net: Netlist, n: int) -> list[str]:
    """n 位行波进位加法器，返回 n+1 个和位 wire（LSB-first）。"""
    s0 = net.gate("XOR", xvar(0), yvar(0, n))
    c = net.gate("AND", xvar(0), yvar(0, n))
    sums = [s0]
    for i in range(1, n):
        xi, yi = xvar(i), yvar(i, n)
        t = net.gate("XOR", xi, yi)
        si = net.gate("XOR", t, c)
        # Majority carry in 3 gates once t = xi XOR yi is available:
        # carry = (xi AND yi) OR (t AND carry_in).
        m1 = net.gate("AND", xi, yi)
        m2 = net.gate("AND", t, c)
        c = net.gate("OR", m1, m2)
        sums.append(si)
    sums.append(c)  # 最高位进位
    return sums


def _add_bits(net: Netlist, A: list[str], B: list[str]) -> list[str]:
    """纹波进位加两个 LSB-first 位向量，返回和（长度 max+1）。"""
    L = max(len(A), len(B))
    z = net.zero()
    S: list[str] = []
    carry: str | None = None
    for i in range(L):
        a = A[i] if i < len(A) else z
        b = B[i] if i < len(B) else z
        if carry is None:
            s = net.gate("XOR", a, b)
            carry = net.gate("AND", a, b)
        else:
            t = net.gate("XOR", a, b)
            s = net.gate("XOR", t, carry)
            ab = net.gate("AND", a, b)
            tc = net.gate("AND", t, carry)
            carry = net.gate("OR", ab, tc)
        S.append(s)
    S.append(carry)
    return S


def _multiply_bits(net: Netlist, A: list[str], B: list[str]) -> list[str]:
    """Dadda reduction followed by a sparse final carry-propagate add."""
    width = len(A) + len(B)
    columns: list[list[str]] = [[] for _ in range(width + 1)]
    for i, a in enumerate(A):
        for j, b in enumerate(B):
            columns[i + j].append(net.gate("AND", a, b))

    max_height = max(len(column) for column in columns)
    targets = [2]
    while targets[-1] < max_height:
        targets.append((3 * targets[-1]) // 2)

    for target in reversed(targets):
        for col in range(width):
            bits = columns[col]
            while len(bits) > target:
                if len(bits) == target + 1:
                    a, b = bits.pop(), bits.pop()
                    bits.append(net.gate("XOR", a, b))
                    columns[col + 1].append(net.gate("AND", a, b))
                else:
                    a, b, c = bits.pop(), bits.pop(), bits.pop()
                    ab = net.gate("XOR", a, b)
                    bits.append(net.gate("XOR", ab, c))
                    columns[col + 1].append(
                        net.gate(
                            "OR",
                            net.gate("AND", a, b),
                            net.gate("AND", ab, c),
                        )
                    )

    row_a = [bits[0] if bits else None for bits in columns[:width]]
    row_b = [bits[1] if len(bits) > 1 else None for bits in columns[:width]]
    result: list[str] = []
    carry: str | None = None
    for a, b in zip(row_a, row_b, strict=True):
        if a is None and b is None:
            result.append(carry if carry is not None else net.zero())
            carry = None
        elif a is None or b is None:
            bit = a if a is not None else b
            assert bit is not None
            if carry is None:
                result.append(bit)
            else:
                result.append(net.gate("XOR", bit, carry))
                carry = net.gate("AND", bit, carry)
        elif carry is None:
            result.append(net.gate("XOR", a, b))
            carry = net.gate("AND", a, b)
        else:
            ab = net.gate("XOR", a, b)
            result.append(net.gate("XOR", ab, carry))
            carry = net.gate(
                "OR",
                net.gate("AND", a, b),
                net.gate("AND", ab, carry),
            )
    return result[:width]


def _square_bits(net: Netlist, A: list[str]) -> list[str]:
    """Square through diagonal terms plus symmetric cross terms.

    x_i²=x_i and each x_i*x_j (i<j) appears twice, so it is placed one
    column higher.  The carry-save reduction below is independently checked
    exhaustively for the mystery-D bit width.
    """
    n = len(A)
    z = net.zero()
    width = 2 * n
    columns: list[list[str]] = [[] for _ in range(width)]
    cache: dict[tuple[str, str], str] = {}

    def partial(a: str, b: str) -> str:
        if a == b:
            return a
        key = tuple(sorted((a, b)))
        if key not in cache:
            cache[key] = net.gate("AND", a, b)
        return cache[key]

    for i in range(n):
        columns[2 * i].append(A[i])
    for i in range(n):
        for j in range(i + 1, n):
            columns[i + j + 1].append(partial(A[i], A[j]))

    carries: list[list[str]] = [[] for _ in range(width + 1)]
    for col in range(width):
        bits = columns[col] + carries[col]
        while len(bits) >= 3:
            a, b, c = bits[0], bits[1], bits[2]
            bits = bits[3:]
            ab = net.gate("XOR", a, b)
            bits.append(net.gate("XOR", ab, c))
            carries[col + 1].append(
                net.gate("OR", net.gate("AND", a, b), net.gate("AND", ab, c))
            )
        columns[col] = bits

    result: list[str] = []
    carry: str | None = None
    for bits in columns:
        if not bits:
            result.append(carry if carry is not None else z)
            carry = None
        elif len(bits) == 1:
            if carry is None:
                result.append(bits[0])
            else:
                result.append(net.gate("XOR", bits[0], carry))
                carry = net.gate("AND", bits[0], carry)
        else:
            if carry is None:
                result.append(net.gate("XOR", bits[0], bits[1]))
                carry = net.gate("AND", bits[0], bits[1])
            else:
                ab = net.gate("XOR", bits[0], bits[1])
                result.append(net.gate("XOR", ab, carry))
                carry = net.gate("OR", net.gate("AND", bits[0], bits[1]), net.gate("AND", ab, carry))
    if carry is not None:
        result.append(carry)
    return result


def build_multiplier(net: Netlist, n: int) -> list[str]:
    """n×n 移位-相乘法器，返回 2n 个积位 wire（LSB-first）。"""
    return _multiply_bits(
        net,
        [xvar(i) for i in range(n)],
        [yvar(i, n) for i in range(n)],
    )


def build_absdiff(net: Netlist, n: int) -> list[str]:
    """无符号 |x-y|：先做 x-y，再按最终借位条件化二补数。"""
    diff: list[str] = []
    borrow: str | None = None
    for i in range(n):
        a, b = xvar(i), yvar(i, n)
        t = net.gate("XOR", a, b)
        if borrow is None:
            diff.append(t)
            borrow = net.gate("AND", a, b, neg_a=True)
        else:
            diff.append(net.gate("XOR", t, borrow))
            p = net.gate("AND", a, b, neg_a=True)
            q = net.gate("AND", t, borrow, neg_a=True)
            borrow = net.gate("OR", p, q)

    # borrow=1 时把模 2^n 的负差变成其二补数；最低位可直接复用。
    out = [diff[0]]
    carry = net.gate("AND", diff[0], borrow, neg_a=True)
    for bit in diff[1:]:
        inverted = net.gate("XOR", bit, borrow)
        out.append(net.gate("XOR", inverted, carry))
        carry = net.gate("AND", inverted, carry)
    return out


def build_sum_of_squares(net: Netlist, n: int) -> list[str]:
    """计算 x²+y²；使用已全枚举验证的对称平方构造。"""
    xs = [xvar(i) for i in range(n)]
    ys = [yvar(i, n) for i in range(n)]
    x2 = _square_bits(net, xs)
    y2 = _square_bits(net, ys)
    return _add_bits(net, x2, y2)


def build_sop(net: Netlist, n: int, m: int, parsed) -> list[str]:
    """train 最小项之和（记忆 train，合法但泛化差）。"""
    outputs = []
    for b in range(m):
        minterms = []
        for x, y, o in parsed:
            if (o >> b) & 1:
                bits = _bits_lsb(x, n) + _bits_lsb(y, n)
                lits = [(f"x{k + 1}", bit == 0) for k, bit in enumerate(bits)]  # (var, neg)
                minterms.append(_and_literals(net, lits))
        outputs.append(net.or_tree(minterms) if minterms else net.zero())
    return outputs


def _and_literals(net: Netlist, lits: list[tuple[str, bool]]) -> str:
    """AND 一串字面量 (var, neg)；~var 用 NOR(var,var) 实现（计 1 门）。"""
    if not lits:
        return net.zero()
    wires = [net.gate("NOR", v, v) if neg else v for v, neg in lits]
    return net.and_tree(wires)


def run() -> None:
    n, m, parsed = read_train(TRAIN_FILE)
    net = Netlist(n_inputs=2 * n)
    kind = detect(parsed, n, m)
    if kind == "add":
        outputs = build_adder(net, n)
    elif kind == "absdiff":
        outputs = build_absdiff(net, n)
    elif kind == "mul":
        outputs = build_multiplier(net, n)
    elif kind == "sumsq":
        outputs = build_sum_of_squares(net, n)
    else:
        outputs = build_sop(net, n, m, parsed)
    # 输出契约严格要求 m 位；算术构造可能自然多出一个恒零最高位。
    if len(outputs) < m:
        outputs += [net.zero()] * (m - len(outputs))
    outputs = outputs[:m]
    Path(CIRCUIT_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(CIRCUIT_FILE, "w", encoding="utf-8") as f:
        f.write(net.render(outputs))
    print(f"Occam seed: detected={kind} n={n} m={m} gates={len(net.lines)}")


if __name__ == "__main__":
    run()
