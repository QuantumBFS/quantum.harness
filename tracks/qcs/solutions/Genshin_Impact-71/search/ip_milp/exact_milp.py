"""Auditable 0-1 MILP for exact synthesis over a fixed Boolean sample set.

The formulation is intentionally independent of the SAT search used elsewhere
for issue #71.  Each synthesized gate has:

* one-hot selectors for two (commutative) input literals;
* a one-hot selector for AND/OR/XOR/NAND/NOR/XNOR;
* a Boolean value on every supplied truth-table row.

Free input/output phase is represented by offering both polarities of every
available signal.  Products between topology selectors and earlier unknown
gate values are linearized with standard binary McCormick constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix


OPS = ("AND", "OR", "XOR", "NAND", "NOR", "XNOR")


def apply_op(op: str, left: np.ndarray, right: np.ndarray) -> np.ndarray:
    if op == "AND":
        return left & right
    if op == "OR":
        return left | right
    if op == "XOR":
        return left ^ right
    if op == "NAND":
        return ~(left & right)
    if op == "NOR":
        return ~(left | right)
    if op == "XNOR":
        return ~(left ^ right)
    raise ValueError(op)


@dataclass(frozen=True)
class Literal:
    name: str
    negated: bool
    dynamic_gate: int | None

    @property
    def token(self) -> str:
        return f"~{self.name}" if self.negated else self.name


@dataclass(frozen=True)
class SynthGate:
    op: str
    left: str
    right: str


@dataclass
class MilpResult:
    status: str
    solver_status: int
    message: str
    wall_seconds: float
    variable_count: int
    constraint_count: int
    nonzero_count: int
    mip_node_count: int | None
    mip_gap: float | None
    gates: list[SynthGate] | None

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "solver_status": self.solver_status,
            "message": self.message,
            "wall_seconds": self.wall_seconds,
            "variable_count": self.variable_count,
            "constraint_count": self.constraint_count,
            "nonzero_count": self.nonzero_count,
            "mip_node_count": self.mip_node_count,
            "mip_gap": self.mip_gap,
            "gates": None
            if self.gates is None
            else [
                {"op": gate.op, "left": gate.left, "right": gate.right}
                for gate in self.gates
            ],
        }


class Model:
    def __init__(self) -> None:
        self.var_names: list[str] = []
        self.var_index: dict[str, int] = {}
        self.rows: list[int] = []
        self.cols: list[int] = []
        self.data: list[float] = []
        self.lower: list[float] = []
        self.upper: list[float] = []

    def var(self, name: str) -> int:
        if name in self.var_index:
            raise ValueError(f"duplicate variable {name}")
        index = len(self.var_names)
        self.var_names.append(name)
        self.var_index[name] = index
        return index

    def add(
        self,
        coefficients: Mapping[int, float],
        lower: float = -np.inf,
        upper: float = np.inf,
    ) -> None:
        row = len(self.lower)
        for column, coefficient in coefficients.items():
            if coefficient:
                self.rows.append(row)
                self.cols.append(column)
                self.data.append(float(coefficient))
        self.lower.append(float(lower))
        self.upper.append(float(upper))

    def constraint(self) -> LinearConstraint:
        matrix = coo_matrix(
            (self.data, (self.rows, self.cols)),
            shape=(len(self.lower), len(self.var_names)),
            dtype=float,
        ).tocsr()
        return LinearConstraint(
            matrix, np.asarray(self.lower), np.asarray(self.upper)
        )


def _truth(op: str, left: int, right: int) -> int:
    if op == "AND":
        return left & right
    if op == "OR":
        return left | right
    if op == "XOR":
        return left ^ right
    if op == "NAND":
        return 1 - (left & right)
    if op == "NOR":
        return 1 - (left | right)
    if op == "XNOR":
        return 1 - (left ^ right)
    raise ValueError(op)


def zero_gate_literal(
    static_signals: Mapping[str, Sequence[bool]], target: Sequence[bool]
) -> str | None:
    target_array = np.asarray(target, dtype=bool)
    for name, raw in static_signals.items():
        values = np.asarray(raw, dtype=bool)
        if np.array_equal(values, target_array):
            return name
        if np.array_equal(~values, target_array):
            return f"~{name}"
    return None


def solve_exact(
    static_signals: Mapping[str, Sequence[bool]],
    target: Sequence[bool],
    gate_count: int,
    *,
    time_limit: float = 600.0,
    symmetry_breaking: bool = True,
    solver_display: bool = False,
) -> MilpResult:
    """Find a gate_count circuit, or prove the supplied rows infeasible."""
    if gate_count <= 0:
        raise ValueError("gate_count must be positive")
    names = list(static_signals)
    if not names:
        raise ValueError("at least one static signal is required")
    arrays = {name: np.asarray(static_signals[name], dtype=bool) for name in names}
    target_array = np.asarray(target, dtype=bool)
    row_count = len(target_array)
    if row_count == 0:
        raise ValueError("empty sample set")
    if any(len(values) != row_count for values in arrays.values()):
        raise ValueError("signal and target row counts differ")

    model = Model()
    selectors: dict[tuple[int, int, int], int] = {}
    literals: dict[int, list[Literal]] = {}
    op_vars: dict[tuple[int, int], int] = {}
    value_vars: dict[tuple[int, int], int] = {}
    port_vars: dict[tuple[int, int, int], int] = {}
    product_vars: dict[tuple[int, int, int, int], int] = {}

    for gate in range(gate_count):
        available = [
            Literal(name, negated, None)
            for name in names
            for negated in (False, True)
        ]
        available.extend(
            Literal(f"g{earlier}", negated, earlier)
            for earlier in range(gate)
            for negated in (False, True)
        )
        literals[gate] = available
        for port in range(2):
            for literal_index in range(len(available)):
                selectors[(gate, port, literal_index)] = model.var(
                    f"sel_g{gate}_p{port}_l{literal_index}"
                )
            model.add(
                {
                    selectors[(gate, port, literal_index)]: 1
                    for literal_index in range(len(available))
                },
                1,
                1,
            )
        if symmetry_breaking:
            # Every allowed operation is commutative, so order literal indices.
            coefficients: dict[int, float] = {}
            for literal_index in range(len(available)):
                coefficients[selectors[(gate, 0, literal_index)]] = literal_index
                coefficients[selectors[(gate, 1, literal_index)]] = -literal_index
            model.add(coefficients, upper=0)
        for op_index in range(len(OPS)):
            op_vars[(gate, op_index)] = model.var(f"op_g{gate}_{OPS[op_index]}")
        model.add(
            {op_vars[(gate, op_index)]: 1 for op_index in range(len(OPS))},
            1,
            1,
        )
        for row in range(row_count):
            value_vars[(gate, row)] = model.var(f"value_g{gate}_r{row}")
            for port in range(2):
                port_vars[(gate, port, row)] = model.var(
                    f"port_g{gate}_p{port}_r{row}"
                )

    # Port-value multiplexers.
    for gate in range(gate_count):
        for port in range(2):
            for row in range(row_count):
                coefficients: dict[int, float] = {
                    port_vars[(gate, port, row)]: 1
                }
                for literal_index, literal in enumerate(literals[gate]):
                    selector = selectors[(gate, port, literal_index)]
                    if literal.dynamic_gate is None:
                        value = bool(arrays[literal.name][row]) ^ literal.negated
                        if value:
                            coefficients[selector] = (
                                coefficients.get(selector, 0) - 1
                            )
                        continue
                    product = model.var(
                        f"prod_g{gate}_p{port}_l{literal_index}_r{row}"
                    )
                    product_vars[(gate, port, literal_index, row)] = product
                    coefficients[product] = coefficients.get(product, 0) - 1
                    source = value_vars[(literal.dynamic_gate, row)]
                    # product = selector AND (source XOR literal.negated)
                    model.add({product: 1, selector: -1}, upper=0)
                    if not literal.negated:
                        model.add({product: 1, source: -1}, upper=0)
                        model.add(
                            {product: 1, selector: -1, source: -1}, lower=-1
                        )
                    else:
                        model.add({product: 1, source: 1}, upper=1)
                        model.add(
                            {product: 1, selector: -1, source: 1}, lower=0
                        )
                model.add(coefficients, 0, 0)

    # Conditional truth-table constraints for the selected operation.
    for gate in range(gate_count):
        for row in range(row_count):
            left_var = port_vars[(gate, 0, row)]
            right_var = port_vars[(gate, 1, row)]
            output_var = value_vars[(gate, row)]
            for op_index, op in enumerate(OPS):
                op_var = op_vars[(gate, op_index)]
                for left in (0, 1):
                    for right in (0, 1):
                        # match(bit, variable) = constant + coefficient*variable.
                        left_constant, left_coefficient = (
                            (0, 1) if left else (1, -1)
                        )
                        right_constant, right_coefficient = (
                            (0, 1) if right else (1, -1)
                        )
                        constant = left_constant + right_constant
                        if _truth(op, left, right):
                            # output - op - match(left) - match(right) >= -2
                            model.add(
                                {
                                    output_var: 1,
                                    op_var: -1,
                                    left_var: -left_coefficient,
                                    right_var: -right_coefficient,
                                },
                                lower=-2 + constant,
                            )
                        else:
                            # output + op + match(left) + match(right) <= 3
                            model.add(
                                {
                                    output_var: 1,
                                    op_var: 1,
                                    left_var: left_coefficient,
                                    right_var: right_coefficient,
                                },
                                upper=3 - constant,
                            )

    # The last gate is the requested output; complementary output phases are
    # already expressible by the complementary gate operations.
    for row, target_value in enumerate(target_array):
        model.add(
            {value_vars[(gate_count - 1, row)]: 1},
            int(target_value),
            int(target_value),
        )

    constraint = model.constraint()
    variable_count = len(model.var_names)
    started = time.monotonic()
    result = milp(
        c=np.zeros(variable_count),
        integrality=np.ones(variable_count),
        bounds=Bounds(np.zeros(variable_count), np.ones(variable_count)),
        constraints=constraint,
        options={
            "disp": solver_display,
            "presolve": True,
            "time_limit": float(time_limit),
            "mip_rel_gap": 0.0,
            "random_seed": 42,
        },
    )
    elapsed = time.monotonic() - started
    status_names = {
        0: "OPTIMAL_FEASIBLE",
        1: "LIMIT",
        2: "PROVEN_INFEASIBLE",
        3: "UNBOUNDED",
        4: "SOLVER_ERROR",
    }
    gates: list[SynthGate] | None = None
    if result.x is not None and result.status == 0:
        gates = []
        for gate in range(gate_count):
            chosen_literals = []
            for port in range(2):
                chosen = max(
                    range(len(literals[gate])),
                    key=lambda index: result.x[selectors[(gate, port, index)]],
                )
                chosen_literals.append(literals[gate][chosen].token)
            chosen_op = max(
                range(len(OPS)), key=lambda index: result.x[op_vars[(gate, index)]]
            )
            gates.append(
                SynthGate(OPS[chosen_op], chosen_literals[0], chosen_literals[1])
            )
    return MilpResult(
        status=status_names.get(result.status, f"UNKNOWN_{result.status}"),
        solver_status=int(result.status),
        message=str(result.message),
        wall_seconds=elapsed,
        variable_count=variable_count,
        constraint_count=len(model.lower),
        nonzero_count=len(model.data),
        mip_node_count=(
            None
            if getattr(result, "mip_node_count", None) is None
            else int(result.mip_node_count)
        ),
        mip_gap=(
            None
            if getattr(result, "mip_gap", None) is None
            else float(result.mip_gap)
        ),
        gates=gates,
    )


def evaluate_synth(
    gates: Sequence[SynthGate], static_signals: Mapping[str, Sequence[bool]]
) -> np.ndarray:
    values = {
        name: np.asarray(raw, dtype=bool).copy()
        for name, raw in static_signals.items()
    }

    def literal(token: str) -> np.ndarray:
        negated = token.startswith("~")
        name = token[1:] if negated else token
        value = values[name]
        return ~value if negated else value

    for index, gate in enumerate(gates):
        values[f"g{index}"] = apply_op(
            gate.op, literal(gate.left), literal(gate.right)
        )
    return values[f"g{len(gates) - 1}"]
